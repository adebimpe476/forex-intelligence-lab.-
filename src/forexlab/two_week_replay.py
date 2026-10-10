"""No-lookahead M5 broker-CFD replay for Gold/NASDAQ research.

RESEARCH ONLY. No network, LEAN, or broker orders. Signal computed ONLY from
completed bars, market entry at NEXT bar open. Intrabar stop wins any unknown
stop/take ordering. OHLC spread is a historical proxy, not observed tick fills.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
import csv
import json
import math
from pathlib import Path

from forexlab.auto_break_retest import BreakRetestDetector, Candle, Proposal
from forexlab.orderflow import Footprint

@dataclass(frozen=True)
class Bar:
    time: int  # Unix UTC seconds, OPEN of completed 5m broker BID bar
    open: float
    high: float
    low: float
    close: float
    spread_points: float

    def validate(self) -> None:
        Candle(self.time, self.open, self.high, self.low, self.close)
        if self.time % 300 != 0 or not math.isfinite(self.spread_points) or self.spread_points <= 0:
            raise ValueError("Require UTC-aligned M5 opens and positive observed broker bar spread proxy")


@dataclass(frozen=True)
class ReplayConfig:
    start_utc: int
    end_utc: int
    symbol: str
    point: float
    usd_per_price_unit_per_lot: float
    equity_usd: float = 10000.0
    risk_fraction: float = 0.0025
    daily_max_drawdown: float = 0.01
    slippage_price_per_side: float = 0.10
    commission_usd_per_lot_roundtrip: float = 7.0
    min_lot: float = 0.01
    lot_step: float = 0.01
    max_lot: float = 1.0
    max_holding_bars: int = 24
    be_trigger_r: float = 1.25
    require_orderflow: bool = False

    def validate(self) -> None:
        positive = (self.point, self.usd_per_price_unit_per_lot, self.equity_usd,
                    self.min_lot, self.lot_step, self.max_lot, self.be_trigger_r)
        if any(not math.isfinite(x) or x <= 0 for x in positive):
            raise ValueError("Invalid positive contract, capital or BE configuration")
        if not self.symbol or not self.start_utc < self.end_utc or self.max_lot < self.min_lot:
            raise ValueError("Invalid trading interval or symbol")
        if not (0 < self.risk_fraction <= 0.005 and 0 < self.daily_max_drawdown <= 0.02):
            raise ValueError("Research risk limits exceeded")
        if self.max_holding_bars < 1 or self.max_holding_bars > 500:
            raise ValueError("Invalid max holding period")
        if any(not math.isfinite(x) or x < 0 for x in
               (self.slippage_price_per_side, self.commission_usd_per_lot_roundtrip)):
            raise ValueError("Trading friction must be finite and nonnegative")


def load_bars(path: str | Path) -> tuple[list[Bar], str]:
    file = Path(path)
    payload = file.read_bytes()
    reader = csv.DictReader(payload.decode("utf-8-sig").splitlines())
    required = {"datetime_utc", "open", "high", "low", "close", "spread_points"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValueError("Required: datetime_utc,open,high,low,close,spread_points")
    out = []
    for row in reader:
        timestamp = datetime.fromisoformat(row["datetime_utc"].replace("Z", "+00:00"))
        if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
            raise ValueError("Timestamps require explicit UTC offset; no local broker time")
        b = Bar(int(timestamp.timestamp()), *(float(row[key]) for key in
               ("open", "high", "low", "close", "spread_points")))
        b.validate()
        if out and b.time <= out[-1].time:
            raise ValueError("Bars must be in strict timestamp order, unique")
        out.append(b)
    if len(out) < 22:
        raise ValueError("Insufficient completed M5 broker bars")
    return out, sha256(payload).hexdigest()


def verify_manifest(path: str | Path, digest: str, config: ReplayConfig) -> dict:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Invalid provenance manifest")
    required = {"sha256", "provider", "broker_symbol", "broker_server", "timeframe",
                "price_side", "account_currency", "point", "usd_per_price_unit_per_lot",
                "research_permission_declared", "historical_spread_is_proxy"}
    if not required.issubset(manifest):
        raise ValueError("Missing broker metadata or permission fields")
    if (manifest["sha256"] != digest or manifest["broker_symbol"] != config.symbol
            or manifest["timeframe"] != "M5" or manifest["price_side"] != "BID"
            or manifest["account_currency"] != "USD"
            or manifest["point"] != config.point
            or manifest["usd_per_price_unit_per_lot"] != config.usd_per_price_unit_per_lot
            or manifest["research_permission_declared"] is not True
            or manifest["historical_spread_is_proxy"] is not True
            or not manifest["provider"] or not manifest["broker_server"]):
        raise ValueError("Provenance/rights/currency/contract mismatch")
    return manifest


def _safe_lot(budget_usd: float, risk_distance: float, config: ReplayConfig) -> float:
    # 15% risk cushion: estimate only, NOT a real maximum loss in gaps.
    raw = budget_usd / (risk_distance * config.usd_per_price_unit_per_lot * 1.15)
    if raw < config.min_lot:
        return 0.0
    steps = math.floor((min(raw, config.max_lot) - config.min_lot) / config.lot_step + 1e-9)
    size = round(config.min_lot + steps * config.lot_step, 8)
    if (size * risk_distance * config.usd_per_price_unit_per_lot * 1.15
            > budget_usd + 1e-6):
        return 0.0
    return size


def _orderflow_gate(proposal: Proposal, current_end_ms: int,
                    by_start_ms: dict[int, Footprint] | None) -> bool:
    """Only completed contemporaneous genuine trade prints; no future flow."""
    if by_start_ms is None:
        return False
    current = by_start_ms.get(current_end_ms - 300_000)
    previous = by_start_ms.get(current_end_ms - 600_000)
    if not current or not previous:
        return False
    if (current.start_ms + 300_000 != current_end_ms
            or previous.start_ms + 300_000 != current.start_ms):
        return False
    # Conservative preliminary hypothesis, NOT tuned, NOT profitable by definition.
    if proposal.side == "BUY":
        return (current.delta > 0 and current.cvd > previous.cvd
                and bool(current.buy_imbalances))
    return (current.delta < 0 and current.cvd < previous.cvd
            and bool(current.sell_imbalances))


def _d(utc_sec: int) -> str:
    return datetime.fromtimestamp(utc_sec, timezone.utc).isoformat()


def simulate(
    bars: list[Bar], config: ReplayConfig, *,
    orderflow_by_start_ms: dict[int, Footprint] | None = None,
) -> dict:
    """Serial and causal M5 event replay; no simultaneous trades on a symbol.

    One open attempt per UTC date. Breakeven is decided on a COMPLETED bar and
    effective no earlier than next open, to avoid assuming favorable intrabar
    path. If a bar includes both TP and SL, assume SL first.
    """
    config.validate()
    if len(bars) < 22:
        raise ValueError("Insufficient historical bar data")
    if config.require_orderflow and orderflow_by_start_ms is None:
        raise ValueError("NO_GENUINE_ORDERFLOW: fail closed; do not fake delta")

    detector = BreakRetestDetector()
    recent: list[Candle] = []
    position = None
    proposal: Proposal | None = None
    closed = []
    rejects: list[dict] = []
    equity = config.equity_usd
    peak_equity = equity
    max_closed_dd = 0.0
    opened_utc_days: set[str] = set()
    day_base: dict[str, float] = {}
    previous: Bar | None = None
    observed_days: set[str] = set()
    gap_count = 0
    candidate_count = 0

    def exit_trade(execution_price: float, reason: str, current: Bar) -> None:
        nonlocal position, equity, peak_equity, max_closed_dd
        p = position
        side = 1 if p["side"] == "BUY" else -1
        net = ((execution_price - p["entry"]) * side *
               config.usd_per_price_unit_per_lot * p["lot"]
               - config.commission_usd_per_lot_roundtrip * p["lot"])
        equity += net
        peak_equity = max(peak_equity, equity)
        max_closed_dd = max(max_closed_dd, peak_equity - equity)
        closed.append({**p["record"], "exit_time_utc": _d(current.time),
                       "exit_time_precision": "M5_BAR_OPEN_ONLY_EXCEPT_OPEN_EXITS",
                       "exit": round(execution_price, 7), "reason": reason,
                       "net_usd": round(net, 2),
                       "equity_after_usd": round(equity, 2),
                       "breakeven_attempted": p["be_moved"]})
        position = None

    for i, bar in enumerate(bars):
        bar.validate()
        if bar.time >= config.end_utc:
            break  # Do not process ANY candle outside the pre-registered test end.
        if previous and bar.time <= previous.time:
            raise ValueError("History must be time-ordered and unique")
        gap = previous is not None and bar.time != previous.time + 300
        if gap:
            gap_count += 1
            recent.clear()
            detector = BreakRetestDetector()
            if proposal:
                rejects.append({"time_utc": _d(bar.time), "reason": "GAP_BEFORE_NEXT_OPEN"})
                proposal = None
        in_window = config.start_utc <= bar.time < config.end_utc
        day = _d(bar.time)[:10]
        if in_window:
            observed_days.add(day)
            day_base.setdefault(day, equity)

        # 1. Orders based on the PREVIOUS COMPLETED M5 candle execute now,
        # at the next M5 OPEN, using no H/L/C of this bar to decide entry.
        if proposal is not None and position is None:
            prior_proposal = proposal
            proposal = None
            if not in_window:
                pass
            elif day in opened_utc_days:
                rejects.append({"time_utc": _d(bar.time), "reason": "ONE_ENTRY_PER_UTC_DAY"})
            elif equity <= day_base[day] * (1 - config.daily_max_drawdown):
                rejects.append({"time_utc": _d(bar.time), "reason": "DAILY_LOSS_GATE"})
            else:
                spread = bar.spread_points * config.point
                entry = (bar.open + spread + config.slippage_price_per_side
                         if prior_proposal.side == "BUY"
                         else bar.open - config.slippage_price_per_side)
                dist = (entry - prior_proposal.stop if prior_proposal.side == "BUY"
                        else prior_proposal.stop - entry)
                if (spread > prior_proposal.atr * 0.15
                        or abs(entry - prior_proposal.entry_reference) > prior_proposal.atr * 0.20
                        or not 0.55 * prior_proposal.atr <= dist <= 3.0 * prior_proposal.atr
                        or entry <= 0):
                    rejects.append({"time_utc": _d(bar.time), "reason": "EXECUTION_QUALITY_OR_STOP_GATE"})
                else:
                    lot = _safe_lot(equity * config.risk_fraction, dist, config)
                    if not lot:
                        rejects.append({"time_utc": _d(bar.time), "reason": "MIN_LOT_TOO_RISKY"})
                    else:
                        target = entry + (2 * dist if prior_proposal.side == "BUY" else -2 * dist)
                        if target <= 0:
                            rejects.append({"time_utc": _d(bar.time), "reason": "NONPOSITIVE_TARGET"})
                        else:
                            position = {
                                "side": prior_proposal.side, "entry": entry,
                                "sl": prior_proposal.stop, "tp": target, "risk": dist,
                                "lot": lot, "opened_time": bar.time,
                                "bars_held": 0, "be_ready": False, "be_moved": False,
                                "record": {
                                    "signal_bar_open_utc": _d(prior_proposal.candle_time),
                                    "signal_time_utc": _d(prior_proposal.candle_time + 300),
                                    "entry_time_utc": _d(bar.time), "symbol": config.symbol,
                                    "side": prior_proposal.side,
                                    "broken_level": round(prior_proposal.level, 7),
                                    "entry": round(entry, 7),
                                    "original_sl": round(prior_proposal.stop, 7),
                                    "tp": round(target, 7),
                                    "lot": lot,
                                    "planned_risk_usd_with_15pct_cushion": round(
                                        lot * dist * config.usd_per_price_unit_per_lot * 1.15, 2),
                                },
                            }
                            opened_utc_days.add(day)

        # 2. Manage any already-open position. The OPEN is known first.
        # Stop/TP high-low checks are made on this candle only after entry.
        if position:
            p = position
            spread = bar.spread_points * config.point
            exit_open = bar.open if p["side"] == "BUY" else bar.open + spread
            if p["bars_held"] >= config.max_holding_bars:
                exit_trade(exit_open + (-config.slippage_price_per_side if p["side"] == "BUY"
                                        else config.slippage_price_per_side),
                           "TIME_EXIT_NEXT_OPEN", bar)
            else:
                # Gap-through uses market open, never the more favorable stop level.
                hit_stop_at_open = (exit_open <= p["sl"] if p["side"] == "BUY"
                                    else exit_open >= p["sl"])
                hit_target_at_open = (exit_open >= p["tp"] if p["side"] == "BUY"
                                      else exit_open <= p["tp"])
                if hit_stop_at_open:
                    exit_trade(exit_open + (-config.slippage_price_per_side if p["side"] == "BUY"
                                            else config.slippage_price_per_side),
                               "STOP_GAP_OPEN", bar)
                elif hit_target_at_open:
                    exit_trade(p["tp"] + (-config.slippage_price_per_side if p["side"] == "BUY"
                                          else config.slippage_price_per_side),
                               "TARGET_GAP_OPEN", bar)
                else:
                    # Previous bar's closed quote may arm BE for the NEXT bar,
                    # not retrospectively within the bar that triggered it.
                    if p["be_ready"] and not p["be_moved"] and (
                            (p["side"] == "BUY" and exit_open > p["entry"])
                            or (p["side"] == "SELL" and exit_open < p["entry"])):
                        p["sl"] = p["entry"]
                        p["be_moved"] = True
                    stop_touch = (bar.low <= p["sl"] if p["side"] == "BUY"
                                  else bar.high + spread >= p["sl"])
                    take_touch = (bar.high >= p["tp"] if p["side"] == "BUY"
                                  else bar.low + spread <= p["tp"])
                    if stop_touch:  # STOP FIRST if high-low ambiguity.
                        exit_trade(p["sl"] + (-config.slippage_price_per_side if p["side"] == "BUY"
                                              else config.slippage_price_per_side),
                                   "STOP_OR_AMBIGUOUS_STOP_FIRST", bar)
                    elif take_touch:
                        exit_trade(p["tp"] + (-config.slippage_price_per_side if p["side"] == "BUY"
                                              else config.slippage_price_per_side),
                                   "TAKE_PROFIT", bar)
                    else:
                        p["bars_held"] += 1
                        close_quote = bar.close if p["side"] == "BUY" else bar.close + spread
                        favorable = (close_quote - p["entry"] if p["side"] == "BUY"
                                     else p["entry"] - close_quote)
                        if favorable >= config.be_trigger_r * p["risk"]:
                            p["be_ready"] = True

        # 3. Only AFTER this bar is completely closed do we let the detector
        # inspect it and generate a signal for the following bar. Never pass future.
        recent.append(Candle(bar.time, bar.open, bar.high, bar.low, bar.close))
        if len(recent) >= 22:
            signal = detector.advance(config.symbol, recent[-50:])
            if signal and config.start_utc <= bar.time + 300 < config.end_utc:
                candidate_count += 1
                if config.require_orderflow and not _orderflow_gate(
                        signal, (bar.time + 300) * 1000, orderflow_by_start_ms):
                    rejects.append({"time_utc": _d(bar.time + 300), "reason": "ORDERFLOW_NOT_CONFIRMED"})
                elif position is not None:
                    rejects.append({"time_utc": _d(bar.time + 300), "reason": "POSITION_OPEN"})
                else:
                    proposal = signal

        previous = bar

    # NEVER pretend open/unresolved trades earned realized profit.
    unrealized = None
    if position:
        last = bars[-1]
        if last.time >= config.start_utc:
            last_spread = last.spread_points * config.point
            mark = last.close if position["side"] == "BUY" else last.close + last_spread
            direction = 1 if position["side"] == "BUY" else -1
            unrealized = round(
                (mark - position["entry"]) * direction *
                position["lot"] * config.usd_per_price_unit_per_lot
                - position["lot"] * config.commission_usd_per_lot_roundtrip, 2)
    winners = sum(t["net_usd"] > 0 for t in closed)
    losses = sum(t["net_usd"] < 0 for t in closed)
    total_gain = sum(t["net_usd"] for t in closed if t["net_usd"] > 0)
    total_loss = -sum(t["net_usd"] for t in closed if t["net_usd"] < 0)
    return {
        "status": "RESEARCH_MODEL_WITH_HISTORICAL_OHLC_SPREAD_PROXY",
        "data_source_authenticated": False,
        "broker_fills_verified": False,
        "uses_genuine_orderflow_if_provided": bool(config.require_orderflow),
        "orderbook_depth_replayed": False,
        "assumes_no_lookahead": True,
        "signal_bar_close_then_next_bar_open": True,
        "ambiguous_same_bar_result": "STOP_FIRST",
        "time_window_utc": [_d(config.start_utc), _d(config.end_utc)],
        "symbol": config.symbol,
        "starting_equity_usd": config.equity_usd,
        "ending_realized_equity_usd": round(equity, 2),
        "net_realized_pnl_usd": round(equity - config.equity_usd, 2),
        "unrealized_mark_to_market_usd_estimate": unrealized,
        "trades_closed": len(closed), "win_rate_closed": winners / len(closed) if closed else None,
        "wins": winners, "losses": losses,
        "profit_factor": total_gain / total_loss if total_loss else None,
        "max_closed_equity_drawdown_usd": round(max_closed_dd, 2),
        "candidate_count": candidate_count,
        "rejections": rejects,
        "observed_utc_dates_in_window": sorted(observed_days),
        "window_has_at_least_eight_utc_dates": len(observed_days) >= 8,
        "gaps_across_all_loaded_bars": gap_count,
        "config": asdict(config),
        "trades": closed,
        "performance_validated": False,
        "execution_allowed": False,
        "warning": "M5 bar-high/low chronology unknown; modeled spread/slippage/commission, broker funding and intrabar risk not proven. Historical curve is NOT independently validated edge.",
    }
