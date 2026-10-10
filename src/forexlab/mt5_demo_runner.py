"""Zero-subscription, Windows MT5 demo-only M5 automation prototype.

Python package MetaTrader5 and a running MT5 desktop terminal are required.
No live-money execution path exists. Not a profitable/validated strategy.
Uses broker's own tradable symbol prices; not NQ/GC futures offsets.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time

from forexlab.auto_break_retest import BreakRetestDetector, Candle, Proposal

STATE_PATH = Path("artifacts/mt5_demo_state.json")
MAGIC = 9152609


def read_state(path: Path = STATE_PATH) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def save_state(value: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path.with_suffix(".tmp")
    target.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(target, path)


def eligible_volume(raw: float, minimum: float, maximum: float, step: float) -> float:
    """Round down to actual broker volume increments; do not round up risk."""
    if step <= 0 or minimum <= 0 or maximum < minimum or raw < minimum:
        return 0.0
    steps = math.floor((min(raw, maximum) - minimum) / step + 1e-8)
    return round(minimum + steps * step, 8)


def quote_plan(mt5, symbol: str, proposal: Proposal, equity: float,
               risk_fraction: float, cap_lots: float, max_spread_atr: float) -> dict | None:
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if info is None or tick is None or info.point <= 0 or tick.ask <= tick.bid:
        return None
    if time.time() - tick.time > 10 or tick.time > time.time() + 10:
        return None
    if tick.ask - tick.bid > max_spread_atr * proposal.atr:
        return None
    side = proposal.side
    entry = tick.ask if side == "BUY" else tick.bid
    if abs(entry - proposal.entry_reference) > 0.20 * proposal.atr:
        # Do not chase a confirmation whose execution price moved.
        return None

    stop = round(proposal.stop, info.digits)
    distance = entry - stop if side == "BUY" else stop - entry
    if distance < 0.55 * proposal.atr or distance > 3.0 * proposal.atr:
        return None
    min_distance = (info.trade_stops_level + 2) * info.point
    if distance <= min_distance or 2.0 * distance <= min_distance:
        return None
    target = round(entry + (2.0 * distance if side == "BUY" else -2.0 * distance), info.digits)
    if target <= 0:
        return None
    order_type = mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL
    loss_per_lot = mt5.order_calc_profit(order_type, symbol, 1.0, entry, stop)
    if loss_per_lot is None or loss_per_lot >= 0:
        return None
    # 15% cushion estimates commissions and adverse stop slippage.
    # Real gaps can exceed this estimate. No guaranteed maximum loss.
    risk_budget = equity * risk_fraction
    lots = eligible_volume(
        risk_budget / (-loss_per_lot * 1.15),
        info.volume_min,
        min(info.volume_max, cap_lots),
        info.volume_step,
    )
    if lots <= 0:
        return None
    margin = mt5.order_calc_margin(order_type, symbol, lots, entry)
    account = mt5.account_info()
    if margin is None or account is None or margin > account.margin_free * 0.50:
        return None
    if -loss_per_lot * lots * 1.15 > risk_budget + 0.01:
        return None
    return {"side": side, "entry": round(entry, info.digits), "sl": stop,
            "tp": target, "volume": lots, "risk_budget": round(risk_budget, 2),
            "estimated_risk": round(-loss_per_lot * lots * 1.15, 2),
            "level": proposal.level, "bar_time": proposal.candle_time,
            "distance": distance}


def broker_filling(mt5, info) -> int:
    # SYMBOL_FILLING_* are flags; ORDER_FILLING_* are enum values.
    if info.filling_mode & mt5.SYMBOL_FILLING_IOC:
        return mt5.ORDER_FILLING_IOC
    if info.filling_mode & mt5.SYMBOL_FILLING_FOK:
        return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_RETURN  # Broker order_check may reject; never blindly retry.


def assert_demo(mt5) -> None:
    account = mt5.account_info()
    if account is None or account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        raise RuntimeError("HARD SAFETY LOCK: This program only runs on MT5 DEMO accounts.")
    terminal = mt5.terminal_info()
    if terminal is None or not terminal.connected:
        raise RuntimeError("MT5 terminal disconnected.")


def handle_breakeven(mt5, state: dict, symbols: list[str]) -> None:
    positions = mt5.positions_get()
    if positions is None:
        return
    for position in positions:
        if position.magic != MAGIC or position.symbol not in symbols:
            continue
        if position.sl <= 0 or position.tp <= 0:
            print("SAFETY WARNING: unexpected missing protective order", position.ticket)
            continue
        key = f"{position.symbol}:{position.ticket}"
        anchor = state.setdefault("position_risk", {}).setdefault(
            key, {"initial_risk": abs(position.price_open - position.sl), "moved": False}
        )
        if anchor["moved"] or anchor["initial_risk"] <= 0:
            continue
        is_buy = position.type == mt5.POSITION_TYPE_BUY
        tick = mt5.symbol_info_tick(position.symbol)
        info = mt5.symbol_info(position.symbol)
        if tick is None or info is None or tick.bid <= 0 or tick.ask <= 0:
            continue
        current_exit = tick.bid if is_buy else tick.ask
        progress = current_exit - position.price_open if is_buy else position.price_open - current_exit
        if progress < 1.25 * anchor["initial_risk"]:
            continue
        be_price = round(position.price_open, info.digits)
        if (is_buy and current_exit - be_price <= (info.trade_stops_level + 2) * info.point
                or not is_buy and be_price - current_exit <= (info.trade_stops_level + 2) * info.point):
            continue
        response = mt5.order_send({
            "action": mt5.TRADE_ACTION_SLTP, "symbol": position.symbol,
            "position": position.ticket, "sl": be_price, "tp": position.tp,
            "magic": MAGIC, "comment": "ForexLab demo BE",
        })
        if response and response.retcode == mt5.TRADE_RETCODE_DONE:
            anchor["moved"] = True
            save_state(state)
            print("DEMO BE moved:", position.symbol, be_price)
        else:
            print("DEMO BE modification rejected; keeping existing SL")


def run(symbols: list[str], dry_run: bool, poll_seconds: float,
        risk_fraction: float, daily_loss_fraction: float, cap_lots: float) -> None:
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise SystemExit("Install free MT5 Python bindings on Windows: pip install MetaTrader5") from exc

    if not mt5.initialize():
        raise SystemExit(f"MT5 terminal initialize failed: {mt5.last_error()}")
    try:
        assert_demo(mt5)  # Demo-only even in dry-run mode.
        account = mt5.account_info()
        today = datetime.now(timezone.utc).date().isoformat()
        state = read_state()
        identity = f"{account.login}:{today}"
        if state.get("identity") != identity:
            state = {"identity": identity, "baseline_equity": account.equity,
                     "attempts": 0, "position_risk": {}}
            save_state(state)

        detector = BreakRetestDetector()
        for symbol in symbols:
            if not mt5.symbol_select(symbol, True):
                raise ValueError(f"Broker symbol not found: {symbol}")
            bars = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 1, 50)
            if bars is None or len(bars) < 22:
                raise ValueError(f"Missing >=22 completed M5 bars for {symbol}")
            detector.last_seen[symbol] = int(bars[-1]["time"])
        print("MT5 DEMO", "SIGNAL-ONLY" if dry_run else "AUTOMATED DEMO ORDERS",
              "symbols=", symbols, "risk_fraction=", risk_fraction)

        while True:
            assert_demo(mt5)
            utc_day = datetime.now(timezone.utc).date().isoformat()
            if utc_day != today:
                today = utc_day
                state = {"identity": f"{account.login}:{today}",
                         "baseline_equity": mt5.account_info().equity,
                         "attempts": 0, "position_risk": {}}
                save_state(state)
            handle_breakeven(mt5, state, symbols)
            save_state(state)
            account = mt5.account_info()
            if account is None:
                raise RuntimeError("Account data unavailable")
            for symbol in symbols:
                rows = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 1, 50)
                if rows is None or len(rows) < 22:
                    continue
                bars = [Candle(int(r["time"]), float(r["open"]), float(r["high"]),
                               float(r["low"]), float(r["close"])) for r in rows]
                if time.time() - (bars[-1].time + 300) > 90:
                    continue  # Stale M5 bar: no entry.
                signal = detector.advance(symbol, bars)
                if signal is None:
                    continue
                print("M5 REJECTION CANDIDATE", symbol, signal)
                if state["attempts"] >= 1 or account.equity <= state["baseline_equity"] * (1 - daily_loss_fraction):
                    print("BLOCK: daily trade count or loss circuit breaker")
                    continue
                if mt5.positions_total() != 0 or mt5.orders_total() != 0:
                    print("BLOCK: other account positions or orders already exist")
                    continue
                plan = quote_plan(mt5, symbol, signal, account.equity, risk_fraction, cap_lots, 0.15)
                if plan is None:
                    print("BLOCK: stale quote, spread, stop distance, price drift, volume or margin")
                    continue
                print("CANDIDATE PLAN", symbol, plan, "(NOT VALIDATED PROFITABLE)")
                if dry_run:
                    continue
                info = mt5.symbol_info(symbol)
                request = {
                    "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol,
                    "volume": plan["volume"],
                    "type": mt5.ORDER_TYPE_BUY if plan["side"] == "BUY" else mt5.ORDER_TYPE_SELL,
                    "price": plan["entry"], "sl": plan["sl"], "tp": plan["tp"],
                    "deviation": 20, "magic": MAGIC,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": broker_filling(mt5, info),
                    "comment": "ForexLab DEMO B/R",
                }
                check = mt5.order_check(request)
                if check is None or check.retcode != 0:
                    print("BLOCK: broker order_check rejected", check)
                    continue
                # Persist before submission to prevent duplicated retry on interruption.
                state["attempts"] += 1
                save_state(state)
                result = mt5.order_send(request)
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    print("DEMO ORDER FILLED", symbol, plan, "ticket", result.order)
                else:
                    print("DEMO ORDER UNCERTAIN/REJECTED: daily attempt consumed; review manually", result)
            time.sleep(poll_seconds)
    finally:
        mt5.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description="MT5 demo-only autonomous candidate and order runner")
    parser.add_argument("--symbol", action="append", required=True,
                        help="Exact symbol exposed by your DEMO broker, repeat for Gold and NASDAQ")
    parser.add_argument("--demo-execute", action="store_true",
                        help="Submit REAL ORDERS ON DEMO ONLY. Default is signal-only.")
    parser.add_argument("--risk-fraction", type=float, default=0.0025,
                        help="Per-trade fractional equity budget (default 0.25%%)")
    parser.add_argument("--daily-loss", type=float, default=0.01,
                        help="Halt new trades after this fractional equity loss (default 1%%)")
    parser.add_argument("--max-lots", type=float, default=1.0)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    if not (0 < args.risk_fraction <= 0.005 and 0 < args.daily_loss <= 0.02
            and 0 < args.max_lots <= 5 and args.poll_seconds >= 1.0):
        parser.error("Safety limits: risk<=0.5%, daily loss<=2%, max lots<=5, poll>=1s")
    run(args.symbol, not args.demo_execute, args.poll_seconds,
        args.risk_fraction, args.daily_loss, args.max_lots)


if __name__ == "__main__":
    main()
