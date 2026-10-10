"""Research-only, source-checked trade footprint and order-flow aggregation.

Never synthesize exchange prints from MT5 OHLC/tick volume, chart images, or
broker CFD quotes. A source must contain *actual executed trades*, a trusted
aggressor side, sequence IDs and a contract-specific tick size. The functions
do NOT assert an execution edge or feed broker orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import csv
from pathlib import Path
from typing import Literal

Aggressor = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class Trade:
    timestamp_ms: int
    sequence: int
    price: Decimal
    quantity: Decimal
    aggressor: Aggressor


@dataclass(frozen=True)
class Level:
    price: Decimal
    buy: Decimal
    sell: Decimal

    @property
    def delta(self) -> Decimal:
        return self.buy - self.sell

    @property
    def volume(self) -> Decimal:
        return self.buy + self.sell


@dataclass(frozen=True)
class Footprint:
    start_ms: int
    duration_minutes: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    buy: Decimal
    sell: Decimal
    delta: Decimal
    cvd: Decimal
    poc: Decimal
    levels: tuple[Level, ...]
    buy_imbalances: tuple[Decimal, ...]
    sell_imbalances: tuple[Decimal, ...]
    buy_stacks: tuple[tuple[Decimal, ...], ...]
    sell_stacks: tuple[tuple[Decimal, ...], ...]


def _decimal(value: str, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise ValueError(label)
        return result
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid {label}") from exc


def load_exchange_trade_csv(
    path: str | Path, *, source_verified: bool, rights_approved: bool
) -> list[Trade]:
    """Strict input contract: timestamp_utc,sequence,price,quantity,aggressor.

    Caller must verify source AND authorization outside this parser. These
    boolean declarations are NOT legal or cryptographic license verification.
    For untrusted/unspecified datasets, fail closed.
    """
    if not (source_verified and rights_approved):
        raise PermissionError("Trade feed provenance and usage rights not approved")
    out: list[Trade] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required = {"timestamp_utc", "sequence", "price", "quantity", "aggressor"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Missing required timestamp, sequence or aggressor columns")
        for row in reader:
            raw = row["timestamp_utc"]
            try:
                when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except (ValueError, AttributeError) as exc:
                raise ValueError("Invalid exchange timestamp") from exc
            if when.tzinfo is None or when.utcoffset().total_seconds() != 0:
                raise ValueError("Require explicitly UTC timestamp (not local broker time)")
            ms = int(when.timestamp() * 1000)
            seq = int(row["sequence"])
            qty = _decimal(row["quantity"], "quantity")
            price = _decimal(row["price"], "price")
            side = row["aggressor"].strip().upper()
            if price <= 0 or qty <= 0 or seq < 0 or side not in ("BUY", "SELL"):
                raise ValueError("Invalid trade price, size, sequence or aggressor")
            if out and (ms < out[-1].timestamp_ms or seq <= out[-1].sequence):
                raise ValueError("Out-of-order or duplicate market prints")
            out.append(Trade(ms, seq, price, qty, side))  # type: ignore[arg-type]
    if not out:
        raise ValueError("Empty exchange trade dataset")
    return out


def _stacks(prices: list[Decimal], steps: Decimal, minimum: int) -> tuple[tuple[Decimal, ...], ...]:
    stacks: list[tuple[Decimal, ...]] = []
    run: list[Decimal] = []
    for value in prices:
        if not run or value == run[-1] + steps:
            run.append(value)
        else:
            if len(run) >= minimum:
                stacks.append(tuple(run))
            run = [value]
    if len(run) >= minimum:
        stacks.append(tuple(run))
    return tuple(stacks)


def aggregate_footprints(
    trades: list[Trade], *, tick_size: str,
    minutes: int = 5, imbalance_ratio: str = "3",
    minimum_imbalance_quantity: str = "1",
    min_stack: int = 3,
    include_incomplete_last_bar: bool = False,
    as_of_ms: int | None = None,
) -> list[Footprint]:
    """Compute executed trade volume at price, candle delta, CVD and stacked imbalance.

    'as_of_ms' is the exchange-clock processing instant, not local wall time.
    CVD restarts at the beginning of supplied data, not a global session.
    Buy imbalance: buyer aggression at p vs seller aggression at p - tick.
    Sell imbalance: seller aggression at p vs buyer aggression at p + tick.
    Missing opposite quantities may qualify only after minimum own-side size.
    """
    tick = _decimal(tick_size, "tick size")
    ratio = _decimal(imbalance_ratio, "imbalance ratio")
    minimum = _decimal(minimum_imbalance_quantity, "minimum quantity")
    if tick <= 0 or ratio <= 1 or minimum <= 0 or min_stack < 2 or minutes not in (1, 5, 15):
        raise ValueError("Invalid footprint aggregation configuration")
    if not trades:
        return []
    interval_ms = minutes * 60_000
    buckets: dict[int, list[Trade]] = {}
    previous_time = -1
    previous_id = -1
    for trade in trades:
        if trade.timestamp_ms < previous_time or trade.sequence <= previous_id:
            raise ValueError("Nonmonotonic timestamp or duplicate sequence")
        if trade.price <= 0 or trade.quantity <= 0 or trade.aggressor not in ("BUY", "SELL"):
            raise ValueError("Invalid market print")
        if trade.price % tick != 0:
            raise ValueError("Price not on declared exchange tick grid")
        key = trade.timestamp_ms // interval_ms * interval_ms
        buckets.setdefault(key, []).append(trade)
        previous_time = trade.timestamp_ms
        previous_id = trade.sequence

    if not include_incomplete_last_bar and as_of_ms is None:
        raise ValueError("Need an explicit exchange clock to exclude incomplete candles")

    output = []
    cumulative = Decimal("0")
    for start, batch in sorted(buckets.items()):
        if not include_incomplete_last_bar and start + interval_ms > as_of_ms:
            continue
        per_level: dict[Decimal, list[Decimal]] = {}
        for t in batch:
            level = per_level.setdefault(t.price, [Decimal("0"), Decimal("0")])
            level[0 if t.aggressor == "BUY" else 1] += t.quantity
        levels = tuple(Level(price, quantities[0], quantities[1])
                       for price, quantities in sorted(per_level.items()))
        by_price = {l.price: l for l in levels}
        buys = sum((l.buy for l in levels), Decimal("0"))
        sells = sum((l.sell for l in levels), Decimal("0"))
        delta = buys - sells
        cumulative += delta
        # On tied POC levels, prefer level closest to final transaction price.
        poc = max(levels, key=lambda l: (l.volume, -abs(l.price - batch[-1].price))).price
        buy_imbalances = []
        sell_imbalances = []
        for lv in levels:
            below = by_price.get(lv.price - tick)
            above = by_price.get(lv.price + tick)
            below_sells = below.sell if below else Decimal("0")
            above_buys = above.buy if above else Decimal("0")
            if lv.buy >= minimum and lv.buy >= ratio * below_sells:
                buy_imbalances.append(lv.price)
            if lv.sell >= minimum and lv.sell >= ratio * above_buys:
                sell_imbalances.append(lv.price)
        output.append(Footprint(
            start_ms=start, duration_minutes=minutes,
            open=batch[0].price, high=max(x.price for x in batch),
            low=min(x.price for x in batch), close=batch[-1].price,
            buy=buys, sell=sells, delta=delta, cvd=cumulative, poc=poc,
            levels=levels,
            buy_imbalances=tuple(buy_imbalances),
            sell_imbalances=tuple(sell_imbalances),
            buy_stacks=_stacks(buy_imbalances, tick, min_stack),
            sell_stacks=_stacks(sell_imbalances, tick, min_stack),
        ))
    return output


def orderflow_observations(bars: list[Footprint]) -> dict[str, object]:
    """Descriptive conditions, not validated trade signals or causal proof."""
    if len(bars) < 2:
        return {"ready": False, "reason": "NEED_TWO_COMPLETED_BARS"}
    previous, last = bars[-2], bars[-1]
    return {
        "ready": True,
        "last_bar_ms": last.start_ms,
        "last_delta": str(last.delta),
        "last_cvd": str(last.cvd),
        "last_bar_buy_stacked_imbalances": len(last.buy_stacks),
        "last_bar_sell_stacked_imbalances": len(last.sell_stacks),
        "positive_price_negative_delta_divergence": bool(
            last.close > previous.close and last.delta < 0
        ),
        "negative_price_positive_delta_divergence": bool(
            last.close < previous.close and last.delta > 0
        ),
        "sell_aggression_without_new_low": bool(
            last.delta < 0 and last.low >= previous.low
        ),
        "buy_aggression_without_new_high": bool(
            last.delta > 0 and last.high <= previous.high
        ),
        "validated_alpha": False,
        "execution_allowed": False,
    }
