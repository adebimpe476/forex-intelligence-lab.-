"""Research-only order-book snapshot normalization and liquidity comparisons.

Depth is resting limit-order interest, not executed trading volume. This does
NOT create a Bookmap heatmap UI or provide an exchange feed. Inputs must come
from authorized L2 snapshots (not broker OHLC and not screenshot pixels).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class DepthSnapshot:
    timestamp_ms: int
    sequence: int
    bids: tuple[tuple[Decimal, Decimal], ...]  # price, size
    asks: tuple[tuple[Decimal, Decimal], ...]


def depth_metrics(
    snapshots: list[DepthSnapshot], *, tick_size: str, levels: int = 10
) -> list[dict]:
    tick = Decimal(tick_size)
    if not tick.is_finite() or tick <= 0 or not 1 <= levels <= 50:
        raise ValueError("Invalid depth metrics parameters")
    results = []
    old_bid: dict[Decimal, Decimal] = {}
    old_ask: dict[Decimal, Decimal] = {}
    previous_time, previous_seq = -1, -1

    for snapshot in snapshots:
        if snapshot.timestamp_ms < previous_time or snapshot.sequence <= previous_seq:
            raise ValueError("Nonmonotonic book update or duplicate sequence ID")
        bids = dict(snapshot.bids)
        asks = dict(snapshot.asks)
        if not bids or not asks or len(bids) != len(snapshot.bids) or len(asks) != len(snapshot.asks):
            raise ValueError("Missing or duplicated book levels")
        for price, quantity in [*snapshot.bids, *snapshot.asks]:
            if (not price.is_finite() or not quantity.is_finite() or price <= 0
                    or quantity < 0 or price % tick != 0):
                raise ValueError("Invalid book price or quantity")
        top_bids = sorted(bids, reverse=True)[:levels]
        top_asks = sorted(asks)[:levels]
        if top_bids[0] >= top_asks[0]:
            raise ValueError("Crossed order book")
        # Changes are only diagnostic; cannot tell cancellations from filled limit orders
        # without independently synchronized executed-trade events.
        bid_add = sum((max(Decimal("0"), size - old_bid.get(p, Decimal("0")))
                       for p, size in bids.items()), Decimal("0"))
        ask_add = sum((max(Decimal("0"), size - old_ask.get(p, Decimal("0")))
                       for p, size in asks.items()), Decimal("0"))
        bid_decrease = sum((max(Decimal("0"), old - bids.get(p, Decimal("0")))
                            for p, old in old_bid.items()), Decimal("0"))
        ask_decrease = sum((max(Decimal("0"), old - asks.get(p, Decimal("0")))
                            for p, old in old_ask.items()), Decimal("0"))
        visible_bid = sum((bids[p] for p in top_bids), Decimal("0"))
        visible_ask = sum((asks[p] for p in top_asks), Decimal("0"))
        denom = visible_bid + visible_ask
        results.append({
            "timestamp_ms": snapshot.timestamp_ms,
            "best_bid": str(top_bids[0]), "best_ask": str(top_asks[0]),
            "bid_visible": str(visible_bid), "ask_visible": str(visible_ask),
            "visible_imbalance": str((visible_bid - visible_ask) / denom if denom else Decimal("0")),
            "bid_increase_since_previous": str(bid_add if results else Decimal("0")),
            "ask_increase_since_previous": str(ask_add if results else Decimal("0")),
            "bid_decrease_since_previous": str(bid_decrease if results else Decimal("0")),
            "ask_decrease_since_previous": str(ask_decrease if results else Decimal("0")),
            "bid_levels": [(str(p), str(bids[p])) for p in top_bids],
            "ask_levels": [(str(p), str(asks[p])) for p in top_asks],
            "is_real_heatmap_rendered": False,
            "is_book_snapshot_only": True,
            "execution_allowed": False,
        })
        old_bid, old_ask = bids, asks
        previous_time, previous_seq = snapshot.timestamp_ms, snapshot.sequence
    return results
