"""Original research-only USD-account FX exposure and position-size gate.

Never connects to broker; NEVER approves executable orders. Inputs must be actual
side-aware executable quote prices when moving to demo. Per-symbol contract
assumptions are illustrative and MUST be reconciled to MT5 symbol_info and
order_calc_profit, order_calc_margin before any demo order.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from typing import Iterable

SUPPORTED = {"EURUSD": Decimal("0.0001"), "GBPUSD": Decimal("0.0001"), "USDJPY": Decimal("0.01")}
CONTRACT_UNITS_PER_LOT = Decimal("100000")


def _dec(value, name: str) -> Decimal:
    try:
        if isinstance(value, bool):
            raise ValueError()
        x = Decimal(str(value))
        if not x.is_finite():
            raise ValueError()
        return x
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{name} must be a finite decimal") from exc


@dataclass(frozen=True)
class RiskPolicy:
    risk_per_trade_fraction: str = "0.005"  # 0.5% of baseline equity
    max_open_risk_fraction: str = "0.02"     # 2% including the new trade
    max_daily_loss_fraction: str = "0.02"    # hard stop relative to start-of-day equity
    slippage_pips_per_side: str = "0.5"      # two adverse fills; not a spread substitute
    roundtrip_commission_usd_per_lot: str = "7"
    lot_step: str = "0.01"
    min_lots: str = "0.01"
    max_lots: str = "5.00"
    max_same_usd_direction_positions: int = 2


def usd_direction(pair: str, side: str) -> int:
    """Sign of USD directional exposure; +1 long USD, -1 short USD."""
    if pair not in SUPPORTED or side not in ("BUY", "SELL"):
        raise ValueError("Unsupported pair or direction")
    return (1 if side == "BUY" else -1) * (1 if pair == "USDJPY" else -1)


def _wait(signal_id: str, pair: str, reason: str) -> dict:
    return {"signal_id": signal_id, "pair": pair, "status": "BLOCKED",
            "reason": reason, "lots": "0", "risk_usd": "0",
            "execution_allowed": False, "research_only": True}


def assess_risk(*, signal_id: str, pair: str, side: str, entry: object,
                stop: object, equity_usd: object, day_start_equity_usd: object,
                day_realized_pnl_usd: object = "0", day_unrealized_pnl_usd: object = "0",
                open_risk_usd: object = "0",
                open_positions: Iterable[tuple[str, str]] = (),
                seen_signal_ids: Iterable[str] = (), policy: RiskPolicy = RiskPolicy(),
                account_currency: str = "USD") -> dict:
    """Return an example maximum *research* volume with stop/commission/slippage included.

    The entry should be *ask* on BUY and *bid* on SELL. Stop should represent
    the side at which a stop loss would close, bid for BUY/ask for SELL.
    No account login, symbol spec, broker margin, position netting, rollovers,
    spread forecast or live freshness check is implemented.
    """
    signal_id = str(signal_id)
    if not signal_id.strip():
        return _wait(signal_id, pair, "EMPTY_SIGNAL_ID")
    if account_currency != "USD" or pair not in SUPPORTED or side not in ("BUY", "SELL"):
        return _wait(signal_id, pair, "UNSUPPORTED_SYMBOL_SIDE_OR_ACCOUNT_CURRENCY")
    if signal_id in set(seen_signal_ids):
        return _wait(signal_id, pair, "DUPLICATE_SIGNAL")
    try:
        entry, stop = _dec(entry, "entry"), _dec(stop, "stop")
        eq, start = _dec(equity_usd, "equity"), _dec(day_start_equity_usd, "day_start_equity")
        daily, floating = _dec(day_realized_pnl_usd, "daily realized PnL"), _dec(day_unrealized_pnl_usd, "daily unrealized PnL")
        open_risk = _dec(open_risk_usd, "open risk")
        frac, total_frac = _dec(policy.risk_per_trade_fraction, "risk fraction"), _dec(policy.max_open_risk_fraction, "open risk limit")
        daily_frac = _dec(policy.max_daily_loss_fraction, "daily loss limit")
        slip = _dec(policy.slippage_pips_per_side, "slippage pips")
        commission = _dec(policy.roundtrip_commission_usd_per_lot, "commission")
        step, minimum, maximum = [_dec(z, name) for z, name in ((policy.lot_step, "lot step"), (policy.min_lots, "min lots"), (policy.max_lots, "max lots"))]
        if not (eq > 0 and start > 0 and entry > 0 and stop > 0 and open_risk >= 0
                and Decimal("0") < frac <= Decimal("0.01") and Decimal("0") < total_frac <= Decimal("0.05")
                and total_frac >= frac and Decimal("0") < daily_frac <= Decimal("0.05")
                and slip >= 0 and commission >= 0 and step > 0 and minimum > 0
                and maximum >= minimum and (minimum / step) == (minimum / step).to_integral_value()
                and isinstance(policy.max_same_usd_direction_positions, int)
                and policy.max_same_usd_direction_positions >= 1):
            return _wait(signal_id, pair, "INVALID_POLICY_OR_ACCOUNT_STATE")
        if (side == "BUY" and stop >= entry) or (side == "SELL" and stop <= entry):
            return _wait(signal_id, pair, "STOP_WRONG_SIDE")
        desired_usd_direction = usd_direction(pair, side)
        same = 0
        for current_pair, current_side in open_positions:
            if usd_direction(current_pair, current_side) == desired_usd_direction:
                same += 1
        if same >= policy.max_same_usd_direction_positions:
            return _wait(signal_id, pair, "CORRELATED_USD_DIRECTION_LIMIT")
        # Daily limit uses day-opening equity; winning earlier does not raise the stop.
        daily_room = start * daily_frac + min(daily + floating, Decimal("0"))
        open_room = eq * total_frac - open_risk
        budget = min(eq * frac, daily_room, open_room)
        if daily_room <= 0:
            return _wait(signal_id, pair, "DAILY_LOSS_LIMIT")
        if open_room <= 0:
            return _wait(signal_id, pair, "PORTFOLIO_RISK_LIMIT")
        if budget <= 0:
            return _wait(signal_id, pair, "NO_RISK_BUDGET")
        pip = SUPPORTED[pair]
        adverse = slip * pip
        # Double adverse fill allowance: worse entry and worse stop.
        worst_entry = entry + adverse if side == "BUY" else entry - adverse
        worst_stop = stop - adverse if side == "BUY" else stop + adverse
        if worst_entry <= 0 or worst_stop <= 0:
            return _wait(signal_id, pair, "NONPOSITIVE_WORST_FILL")
        adverse_distance = (worst_entry - worst_stop) if side == "BUY" else (worst_stop - worst_entry)
        if adverse_distance <= 0:
            return _wait(signal_id, pair, "INVALID_EFFECTIVE_STOP")
        # Quote USD pairs: quote-currency loss already USD.
        # USDJPY: JPY loss converted at adverse closing price, a research approximation.
        per_lot = CONTRACT_UNITS_PER_LOT * adverse_distance
        if pair == "USDJPY":
            per_lot = per_lot / worst_stop
        per_lot += commission
        allowed_steps = (budget / per_lot / step).to_integral_value(rounding=ROUND_FLOOR)
        max_steps = (maximum / step).to_integral_value(rounding=ROUND_FLOOR)
        lots = min(allowed_steps, max_steps) * step
        if lots < minimum:
            return _wait(signal_id, pair, "BELOW_MINIMUM_LOT_RISK_BUDGET")
        planned_risk = lots * per_lot
        return {"signal_id": signal_id, "pair": pair, "side": side,
                "status": "RESEARCH_SIZE_ONLY", "lots": str(lots),
                "risk_usd": str(planned_risk.quantize(Decimal("0.01"))),
                "budget_usd": str(budget.quantize(Decimal("0.01"))),
                "stop_distance_pips": format((abs(entry - stop) / pip).normalize(), "f"),
                "modeled_risk_usd_per_lot": str(per_lot.quantize(Decimal("0.01"))),
                "usd_direction": desired_usd_direction,
                "execution_allowed": False, "research_only": True,
                "warning": "Illustrative USD-account lot sizing; require MT5 order_calc_profit/margin and verified live quotes before demo."}
    except (ValueError, InvalidOperation, ArithmeticError, OverflowError, TypeError) as exc:
        return _wait(signal_id, pair, "INVALID_INPUT: " + str(exc))
