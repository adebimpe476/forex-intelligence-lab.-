"""Footprint tests use invented trades for plumbing QA, not trading evidence."""
from decimal import Decimal as D
import pytest

from forexlab.orderflow import Trade, aggregate_footprints, load_exchange_trade_csv, orderflow_observations


def t(ms, seq, price, qty, side):
    return Trade(ms, seq, D(price), D(qty), side)


def test_m5_delta_cvd_prices_and_poc_from_true_sided_trades():
    events = [
        t(1000, 1, "100.00", "7", "BUY"),
        t(2000, 2, "100.25", "2", "SELL"),
        t(300000, 3, "100.25", "3", "SELL"),
        t(300001, 4, "100.50", "6", "BUY"),
    ]
    result = aggregate_footprints(events, tick_size="0.25", minutes=5, as_of_ms=600000)
    assert len(result) == 2
    assert (result[0].buy, result[0].sell, result[0].delta, result[0].cvd) == (
        D("7"), D("2"), D("5"), D("5")
    )
    assert result[0].poc == D("100")
    assert result[1].delta == D("3")
    assert result[1].cvd == D("8")
    assert result[1].close == D("100.50")
    assert result[1].levels[0].sell == D("3")


def test_last_incomplete_bar_is_excluded_by_default():
    events = [t(1000, 1, "100", "2", "BUY"),
              t(300000, 2, "100.25", "3", "SELL")]
    r = aggregate_footprints(events, tick_size="0.25", as_of_ms=360000)
    assert len(r) == 1
    assert r[0].start_ms == 0
    assert len(aggregate_footprints(events, tick_size="0.25", as_of_ms=600000)) == 2
    with pytest.raises(ValueError, match="explicit exchange clock"):
        aggregate_footprints(events, tick_size="0.25")


def test_bid_ask_diagonal_stacks():
    # Buys at 100.25, 100.50, 100.75 vs low preceding price sells.
    events = [t(1000, 1, "100.00", "1", "SELL")]
    for i, price in enumerate(("100.25", "100.50", "100.75"), start=2):
        events.append(t(i * 1000, i, price, "12", "BUY"))
    r = aggregate_footprints(events, tick_size="0.25", as_of_ms=300000)
    assert r[0].buy_stacks == ((D("100.25"), D("100.50"), D("100.75")),)
    assert r[0].sell_stacks == ()


def test_bad_tick_grid_duplicates_and_time_reversal_rejected():
    with pytest.raises(ValueError, match="tick grid"):
        aggregate_footprints([t(0, 1, "100.10", "2", "BUY")],
                             tick_size="0.25", as_of_ms=300000)
    with pytest.raises(ValueError, match="duplicate"):
        aggregate_footprints([t(0, 1, "100", "2", "BUY"),
                              t(1, 1, "100", "1", "SELL")],
                             tick_size="0.25", as_of_ms=300000)
    with pytest.raises(ValueError, match="Nonmonotonic"):
        aggregate_footprints([t(1000, 1, "100", "2", "BUY"),
                              t(500, 2, "100", "1", "SELL")],
                             tick_size="0.25", as_of_ms=300000)


def test_csv_strict_utc_provenance_and_sequence(tmp_path):
    file = tmp_path / "test.csv"
    file.write_text(
        "timestamp_utc,sequence,price,quantity,aggressor\n"
        "2026-10-09T14:30:00Z,1,4190.25,3,BUY\n"
        "2026-10-09T14:30:00.003Z,2,4190.00,1,SELL\n",
        encoding="utf-8"
    )
    with pytest.raises(PermissionError):
        load_exchange_trade_csv(file, source_verified=False, rights_approved=True)
    events = load_exchange_trade_csv(file, source_verified=True, rights_approved=True)
    assert events[0].aggressor == "BUY"
    assert events[1].timestamp_ms - events[0].timestamp_ms == 3
    file.write_text(
        "timestamp_utc,sequence,price,quantity,aggressor\n"
        "2026-10-09T14:30:00,1,4190.25,3,BUY\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="UTC"):
        load_exchange_trade_csv(file, source_verified=True, rights_approved=True)


def test_signal_metadata_never_allows_execution():
    events = [
        t(1000, 1, "100", "1", "SELL"),
        t(300000, 2, "100", "9", "SELL"),
        t(300002, 3, "100.25", "1", "BUY"),
    ]
    bars = aggregate_footprints(events, tick_size="0.25", as_of_ms=600000)
    meta = orderflow_observations(bars)
    assert meta["ready"]
    assert meta["sell_aggression_without_new_low"]
    assert meta["execution_allowed"] is False
    assert meta["validated_alpha"] is False


def test_multitimeframe_aggregation_counts():
    events = [t(n * 60_000, n, "100.00", "1", "BUY") for n in range(30)]
    for minutes, n_expected in ((1, 30), (5, 6), (15, 2)):
        bars = aggregate_footprints(events, tick_size="0.25", minutes=minutes,
                                    as_of_ms=30 * 60_000)
        assert len(bars) == n_expected
        assert bars[-1].cvd == D("30")
