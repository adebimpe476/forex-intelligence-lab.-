"""Research-only causal quote simulator for testing LEAN integration assumptions.

No broker connection, AI model, order submission, overnight swap or price forecast.
Simulated tick-sized fills are only *hypothetical*, never validated executions.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math

import numpy as np
import pandas as pd

from .tickdata import validate_ticks, to_bars


@dataclass(frozen=True)
class SimulatorConfig:
    pair: str = "EURUSD"
    fast: int = 5
    slow: int = 12
    stop_pips: float = 12.0
    take_pips: float = 18.0
    slippage_pips_per_side: float = 0.2
    commission_usd_roundtrip_per_lot: float = 7.0
    max_entry_spread_pips: float = 2.0
    max_entry_delay_seconds: int = 30
    max_gap_seconds: int = 900
    max_holding_minutes: int = 120


def _config_check(c: SimulatorConfig) -> None:
    if c.pair not in ("EURUSD", "GBPUSD"):
        raise ValueError("Only USD-quoted FX pairs are supported; JPY conversion is unverified")
    if not (2 <= c.fast < c.slow <= 500):
        raise ValueError("Require 2 <= fast < slow <= 500")
    for key in ("stop_pips", "take_pips", "max_entry_spread_pips"):
        v = getattr(c, key)
        if not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError(f"{key} must be positive and finite")
    for key in ("slippage_pips_per_side", "commission_usd_roundtrip_per_lot"):
        v = getattr(c, key)
        if not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise ValueError(f"{key} must be nonnegative and finite")
    if not (0 < c.max_entry_delay_seconds <= 600 and 0 < c.max_gap_seconds <= 86400 and
            0 < c.max_holding_minutes <= 1440):
        raise ValueError("Invalid event timing limits")


def _utc_epoch_ns(values: object) -> np.ndarray:
    """Portable UTC epoch nanoseconds on pandas 2.x and 3.x."""
    return pd.DatetimeIndex(values).as_unit("ns").asi8


def simulate_quotes(raw_ticks: pd.DataFrame, config: SimulatorConfig = SimulatorConfig()) -> dict:
    """One-lot example USD PnL on CLOSED M15 EMA cross candidates, quote-side fills.

    Signal from bar ending at T; fill at first tick at/after T, if fresh.
    Stop and target use the closing quote side, never mid. Entry/exit charge
    adverse modeled slippage and roundtrip commission. Gaps during a trade
    invalidate that candidate, not quietly count it as a winner. This is NOT
    a proof of profitability, swap/margin/latency/broker fills are absent.
    """
    _config_check(config)
    ticks, audit = validate_ticks(raw_ticks)
    bars = to_bars(ticks, "M15")
    if len(bars) < config.slow + 3:
        raise ValueError("Insufficient M15 closed-bar history")
    mid = bars["mid_close"].astype(float)
    fast = mid.ewm(span=config.fast, adjust=False, min_periods=config.fast).mean()
    slow = mid.ewm(span=config.slow, adjust=False, min_periods=config.slow).mean()
    prev_diff = (fast - slow).shift(1)
    diff = fast - slow
    pip = 0.0001
    slip = config.slippage_pips_per_side * pip
    quotes = ticks.reset_index(drop=True)
    # Pandas 3 defaults some parsed datetimes to microseconds; explicit ns is vital:
    # Timestamp.value below is nanoseconds, so mixed units would skip ALL fills.
    timestamps = _utc_epoch_ns(quotes["timestamp_utc"])
    last_exit_ns = -1
    executions = []
    rejects = []
    max_seconds = config.max_holding_minutes * 60
    for bi in range(config.slow + 1, len(bars)):
        # Never compare EMA values from disconnected intervals as continuous data.
        sample = bars.iloc[bi - config.slow - 1:bi + 1]
        if not bool((sample["bar_start_utc"].diff().iloc[1:] == pd.Timedelta(minutes=15)).all()):
            continue
        if not (math.isfinite(diff.iloc[bi]) and math.isfinite(prev_diff.iloc[bi])):
            continue
        direction = 1 if prev_diff.iloc[bi] <= 0 < diff.iloc[bi] else (-1 if prev_diff.iloc[bi] >= 0 > diff.iloc[bi] else 0)
        if not direction:
            continue
        at = pd.Timestamp(bars.iloc[bi]["bar_end_utc"])
        start_ns = int(at.value)
        if start_ns <= last_exit_ns:
            rejects.append({"signal_time":at.isoformat(), "reason":"OVERLAPPING_POSITION"})
            continue
        j = int(np.searchsorted(timestamps, start_ns, side="left"))
        if j >= len(quotes):
            rejects.append({"signal_time":at.isoformat(), "reason":"NO_FUTURE_QUOTE"})
            continue
        delay = (timestamps[j] - start_ns) / 1e9
        if delay > config.max_entry_delay_seconds:
            rejects.append({"signal_time":at.isoformat(), "reason":"STALE_ENTRY_QUOTE"})
            continue
        first = quotes.iloc[j]
        spread_pips = (float(first.ask) - float(first.bid)) / pip
        if spread_pips > config.max_entry_spread_pips:
            rejects.append({"signal_time":at.isoformat(), "reason":"SPREAD_TOO_WIDE"})
            continue
        entry = (float(first.ask) + slip) if direction == 1 else (float(first.bid) - slip)
        stop = entry - direction * config.stop_pips * pip
        take = entry + direction * config.take_pips * pip
        cutoff_ns = timestamps[j] + max_seconds * 1_000_000_000
        reason = None
        exit_idx = None
        for k in range(j + 1, len(quotes)):
            elapsed = (timestamps[k] - timestamps[k - 1]) / 1e9
            if elapsed > config.max_gap_seconds:
                reason = "UNOBSERVED_DATA_GAP"
                break
            if timestamps[k] > cutoff_ns:
                exit_idx = k - 1
                reason = "TIME_LIMIT"
                break
            q = quotes.iloc[k]
            closing = float(q.bid) if direction == 1 else float(q.ask)
            if (closing <= stop if direction == 1 else closing >= stop):
                exit_idx = k
                reason = "STOP"
                break
            if (closing >= take if direction == 1 else closing <= take):
                exit_idx = k
                reason = "TAKE"
                break
        if reason == "UNOBSERVED_DATA_GAP":
            rejects.append({"signal_time":at.isoformat(), "reason":reason})
            # Data uncertainty contaminates the candidate; no favorable mark-to-market is fabricated.
            last_exit_ns = int(timestamps[k])
            continue
        if exit_idx is None:
            rejects.append({"signal_time":at.isoformat(), "reason":"UNFINISHED_POSITION"})
            last_exit_ns = int(timestamps[-1])
            continue
        q = quotes.iloc[exit_idx]
        exit_price = (float(q.bid) - slip) if direction == 1 else (float(q.ask) + slip)
        pnl_usd = (exit_price - entry) * direction * 100_000 - config.commission_usd_roundtrip_per_lot
        last_exit_ns = int(timestamps[exit_idx])
        executions.append({"signal_time":at.isoformat(), "entry_time":pd.Timestamp(timestamps[j],tz="UTC").isoformat(),
                           "exit_time":pd.Timestamp(timestamps[exit_idx],tz="UTC").isoformat(),
                           "side":"BUY" if direction == 1 else "SELL", "entry":round(entry,7),
                           "exit":round(exit_price,7), "stop":round(stop,7), "target":round(take,7),
                           "reason":reason, "pnl_usd_one_lot":round(pnl_usd,4)})
    net = np.asarray([x["pnl_usd_one_lot"] for x in executions],dtype=float)
    wins = int(np.sum(net>0))
    equity = np.concatenate(([0.],np.cumsum(net)))
    dd = float(np.max(np.maximum.accumulate(equity) - equity))
    # Hash the actual normalized input quotes for traceable, exact-repeat comparisons.
    base = quotes[["timestamp_utc", "bid", "ask"]].to_csv(index=False, date_format="%Y-%m-%dT%H:%M:%S.%f%z")
    return {"mode":"RESEARCH_REFERENCE_SIMULATOR", "pair":config.pair,
            "data_sha256": hashlib.sha256(base.encode()).hexdigest(),
            "parameters":dict(config.__dict__), "ticks":audit["row_count"],
            "observed_m15_bars":len(bars), "trades_closed":len(executions),
            "candidate_rejections":len(rejects), "net_usd_one_standard_lot":round(float(net.sum()),4),
            "win_rate":float(wins/len(net)) if len(net) else None,
            "max_drawdown_usd_one_lot":round(dd,4), "trades":executions,
            "rejections":rejects, "invalid_outcomes_present":any(q["reason"] in ("UNOBSERVED_DATA_GAP", "UNFINISHED_POSITION") for q in rejects),
            "source_verified":False, "strategy_validated":False, "execution_allowed":False,
            "lean_engine_verified":False, "broker_equivalent":False,
            "warning":"No swaps, dynamic sizing, margin, broker fills, overnight charges or true observed slippage; synthetic fixtures are never market evidence."}
