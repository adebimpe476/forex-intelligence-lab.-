"""Snapshot math tests do not imply order book data availability."""
from decimal import Decimal as D

import pytest

from forexlab.orderbook import DepthSnapshot, depth_metrics


def snap(time_ms, seq, bids, asks):
    return DepthSnapshot(time_ms, seq,
                         tuple((D(str(p)), D(str(q))) for p, q in bids),
                         tuple((D(str(p)), D(str(q))) for p, q in asks))


def test_depth_imbalance_and_changes_are_not_marked_executable():
    s = [
        snap(1000, 1, [("100.00", 10), ("99.75", 5)],
                         [("100.25", 5), ("100.50", 5)]),
        snap(2000, 2, [("100.00", 16), ("99.75", 2)],
                         [("100.25", 2), ("100.50", 5)]),
    ]
    out = depth_metrics(s, tick_size="0.25")
    assert out[0]["visible_imbalance"] == str(D("5") / D("25"))
    assert out[1]["bid_increase_since_previous"] == "6"
    assert out[1]["bid_decrease_since_previous"] == "3"
    assert out[1]["ask_decrease_since_previous"] == "3"
    assert out[1]["execution_allowed"] is False


def test_depth_rejects_crossed_books_duplicate_or_invalid_updates():
    with pytest.raises(ValueError, match="Crossed"):
        depth_metrics([snap(1000, 1, [("100.25", 1)], [("100.25", 1)])], tick_size="0.25")
    with pytest.raises(ValueError, match="duplicate sequence"):
        depth_metrics([
            snap(1000, 1, [("100.00", 1)], [("100.25", 1)]),
            snap(2000, 1, [("100.00", 1)], [("100.25", 1)]),
        ], tick_size="0.25")
    with pytest.raises(ValueError, match="Invalid book"):
        depth_metrics([snap(1000, 1, [("100.10", 1)], [("100.25", 1)])], tick_size="0.25")
