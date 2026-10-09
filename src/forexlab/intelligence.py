"""Original, conservative research-only multi-timeframe decision hypotheses.

Consumes CLOSED bid/ask OHLC bars from tickdata.to_bars(). No hidden AI,
execution, optimization, probability forecasts, broker connectivity or orders.
Signals here are *candidates for independent testing*, never live advice.

Research principles:
 - Fail closed on missing, stale, inconsistent or incomplete evidence.
 - Use ONLY bars closed by `asof_utc`; no look-ahead.
 - Detect regime before selecting a trend or countertrend hypothesis.
 - Treat historical bar spread as a proxy, NOT a real-time execution quote.
 - Use all five requested timeframes, but never force a signal.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
import pandas as pd
import numpy as np

PERIODS = {"M15": pd.Timedelta(minutes=15), "M30": pd.Timedelta(minutes=30),
           "H1": pd.Timedelta(hours=1), "H4": pd.Timedelta(hours=4),
           "D1": pd.Timedelta(days=1)}
MIN_BARS = {"M15": 22, "M30": 15, "H1": 22, "H4": 22, "D1": 22}
PAIRS = {"EURUSD", "GBPUSD", "USDJPY"}
FIELDS = {"bar_start_utc", "bar_end_utc", "bid_close", "ask_close",
          "mid_close", "spread_last", "tick_count"}


def _as_utc(ts: object) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        raise ValueError("asof and bar times require explicit timezone")
    return t.tz_convert("UTC")


def _history(frame: pd.DataFrame, tf: str, asof: pd.Timestamp) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or not FIELDS.issubset(frame.columns):
        raise ValueError(f"{tf}: missing validated bid/ask bar fields")
    if frame.empty:
        raise ValueError(f"{tf}: empty history")
    x = frame.copy()
    for key in ("bar_start_utc", "bar_end_utc"):
        if not all(pd.Timestamp(v).tzinfo is not None for v in x[key]):
            raise ValueError(f"{tf}: timestamps must carry timezone")
        x[key] = pd.to_datetime(x[key], utc=True, errors="raise")
    if not x["bar_end_utc"].is_monotonic_increasing or x["bar_end_utc"].duplicated().any():
        raise ValueError(f"{tf}: unordered or repeated bar ends")
    if ((x["bar_end_utc"] - x["bar_start_utc"]) != PERIODS[tf]).any():
        raise ValueError(f"{tf}: incorrect bar duration")
    for key in ("bid_close", "ask_close", "mid_close", "spread_last", "tick_count"):
        x[key] = pd.to_numeric(x[key], errors="raise")
        if not np.isfinite(x[key].to_numpy(dtype=float)).all():
            raise ValueError(f"{tf}: nonfinite {key}")
    if ((x["bid_close"] <= 0) | (x["ask_close"] < x["bid_close"]) |
        (x["mid_close"] <= 0) | (x["spread_last"] < 0) | (x["tick_count"] <= 0)).any():
        raise ValueError(f"{tf}: invalid bid/ask price, spread or tick count")
    if ((x["mid_close"] < x["bid_close"] - 1e-10) |
        (x["mid_close"] > x["ask_close"] + 1e-10)).any():
        raise ValueError(f"{tf}: mid price outside bid/ask")
    # A bar that closes in the future is never available at `asof`.
    x = x.loc[x["bar_end_utc"] <= asof]
    if len(x) < MIN_BARS[tf]:
        raise ValueError(f"{tf}: insufficient completed bars ({len(x)} < {MIN_BARS[tf]})")
    last_end = x["bar_end_utc"].iloc[-1]
    if asof - last_end > 2 * PERIODS[tf]:
        raise ValueError(f"{tf}: stale completed bars")
    return x


def _efficiency(closes: pd.Series, periods: int = 20) -> float:
    v = closes.tail(periods + 1).to_numpy(dtype=float)
    travel = float(np.abs(np.diff(v)).sum())
    return float(abs(v[-1] - v[0]) / travel) if travel > 0 else 0.0


def _blank(pair: str, asof: str, code: str, detail: str = "") -> dict:
    return {"pair": pair, "asof_utc": asof, "action": "WAIT",
            "hypothesis": None, "regime": "UNKNOWN", "evidence": {},
            "blockers": [code + (": " + detail if detail else "")],
            "research_only": True, "execution_allowed": False}


def analyze_pair(pair: str, bars: Mapping[str, pd.DataFrame], asof_utc: object,
                 *, max_completed_bar_spread_bps: float = 5.0) -> dict:
    """Produce BUY / SELL / WAIT **research candidates**, never executable orders.

    Parameters were selected as *unverified hypotheses*, not optimized values.
    
    The H4 price-path efficiency ratio selects a trend/range regime.
    Trend: D1/H1/M30 direction plus M15 breakout must agree with H4 direction.
    Range: H1 z-score extreme plus opposing M15 close change proposes reversion.
    All outputs are non-executable even if BUY/SELL; actual market spread and
    order fills must be checked separately on a live verified feed.
    """
    try:
        asof = _as_utc(asof_utc)
        asof_text = asof.isoformat()
    except (ValueError, TypeError) as exc:
        return _blank(pair, str(asof_utc), "INVALID_ASOF", str(exc))
    if pair not in PAIRS:
        return _blank(pair, asof_text, "UNSUPPORTED_PAIR")
    if not isinstance(max_completed_bar_spread_bps, (float, int)) or not math.isfinite(max_completed_bar_spread_bps) or max_completed_bar_spread_bps <= 0:
        return _blank(pair, asof_text, "INVALID_SPREAD_LIMIT")
    try:
        x = {tf: _history(bars[tf], tf, asof) for tf in PERIODS}
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return _blank(pair, asof_text, "DATA_NOT_READY", str(exc))
    c = {tf: x[tf]["mid_close"].astype(float) for tf in PERIODS}
    spread_bps = float(x["M15"]["spread_last"].iloc[-1] / c["M15"].iloc[-1] * 10000)
    eff = _efficiency(c["H4"])
    h4_change = float(c["H4"].iloc[-1] / c["H4"].iloc[-21] - 1)
    d1_change = float(c["D1"].iloc[-1] / c["D1"].iloc[-21] - 1)
    h1_change = float(c["H1"].iloc[-1] / c["H1"].iloc[-9] - 1)
    m30_change = float(c["M30"].iloc[-1] / c["M30"].iloc[-7] - 1)
    m15 = c["M15"]
    breakout_side = 1 if m15.iloc[-1] > m15.iloc[-21:-1].max() else (-1 if m15.iloc[-1] < m15.iloc[-21:-1].min() else 0)
    regime = "TREND" if eff >= .38 else ("RANGE" if eff <= .20 else "TRANSITION")
    evidence = {"h4_efficiency_ratio": round(eff, 5),
                "h4_return_20_bars": round(h4_change, 6),
                "d1_return_20_bars": round(d1_change, 6),
                "h1_return_8_bars": round(h1_change, 6),
                "m30_return_6_bars": round(m30_change, 6),
                "m15_breakout_side": breakout_side,
                "m15_completed_bar_spread_bps": round(spread_bps, 4),
                "spread_is_historical_proxy_only": True}
    output = {"pair": pair, "asof_utc": asof_text, "action": "WAIT",
              "hypothesis": None, "regime": regime, "evidence": evidence,
              "blockers": [], "research_only": True, "execution_allowed": False}
    if spread_bps > max_completed_bar_spread_bps:
        output["blockers"] = ["HISTORICAL_SPREAD_PROXY_TOO_WIDE"]
        return output
    if regime == "TREND":
        for side, direction in ((1, "BUY"), (-1, "SELL")):
            if (breakout_side == side and side * d1_change > .0005 and
                side * h4_change > .0005 and side * h1_change > 0 and
                side * m30_change > 0):
                output.update(action=direction, hypothesis="trend_breakout_confluence")
                return output
        output["blockers"] = ["TREND_TIMEFRAMES_OR_BREAKOUT_NOT_ALIGNED"]
    elif regime == "RANGE":
        p = c["H1"].tail(20)
        sigma = float(p.std())
        z = float((p.iloc[-1] - p.mean()) / sigma) if sigma > 0 else 0.0
        output["evidence"]["h1_zscore_20_bars"] = round(z, 4)
        short_momentum = float(m15.iloc[-1] - m15.iloc[-2])
        if abs(d1_change) <= .04 and z <= -1.5 and short_momentum > 0:
            output.update(action="BUY", hypothesis="range_mean_reversion")
        elif abs(d1_change) <= .04 and z >= 1.5 and short_momentum < 0:
            output.update(action="SELL", hypothesis="range_mean_reversion")
        else:
            output["blockers"] = ["RANGE_REVERSAL_NOT_CONFIRMED"]
    else:
        output["blockers"] = ["TRANSITION_REGIME_UNCERTAIN"]
    return output
