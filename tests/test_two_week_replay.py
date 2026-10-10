"""No-lookahead tests use made-up M5 candles solely to test engine logic."""
from dataclasses import replace
from forexlab.two_week_replay import Bar, ReplayConfig, simulate
import pytest


def m5(n, o=100.8, h=102.0, l=100.0, c=100.8, spread=1):
    return Bar(n * 300, o, h, l, c, spread)


def sample():
    b = [m5(n) for n in range(25)]
    b.append(m5(25, 100.8, 103.2, 100.8, 103.0))  # broke previous high after close
    b.append(m5(26, 102.1, 103.0, 101.7, 102.7))  # next completed 5m rejects level
    return b


def config(**kwargs):
    return ReplayConfig(start_utc=27*300, end_utc=80*300,
                        symbol="XAUUSD", point=0.1,
                        usd_per_price_unit_per_lot=100.0, **kwargs)


def test_signal_on_last_bar_cannot_fill_same_bar():
    r = simulate(sample(), config())
    assert r["trades_closed"] == 0
    assert r["net_realized_pnl_usd"] == 0
    assert r["candidate_count"] == 1


def test_market_entry_occurs_next_open_and_both_hit_bar_stops_first():
    bars = sample() + [m5(27, 102.7, 107.0, 100.0, 105)]
    r = simulate(bars, config())
    assert r["trades_closed"] == 1
    trade = r["trades"][0]
    # The previous candle CLOSE and next candle OPEN share the same UTC boundary.
    # The signal-bar start proves the decision used the EARLIER candle only.
    assert trade["signal_time_utc"] == trade["entry_time_utc"]
    assert trade["signal_bar_open_utc"] != trade["entry_time_utc"]
    assert trade["entry_time_utc"].startswith("1970-01-01T02:15:")
    assert trade["reason"] == "STOP_OR_AMBIGUOUS_STOP_FIRST"
    assert trade["net_usd"] < 0


def test_future_candles_cannot_change_past_realized_trade():
    prefix = sample() + [m5(27, 102.7, 107.0, 100.0, 105)]
    r1 = simulate(prefix, config())
    far_future = [m5(28 + n, 500.0, 600.0, 400.0, 500.0)
                  for n in range(10)]
    r2 = simulate(prefix + far_future, config())
    assert r1["trades"][0] == r2["trades"][0]
    assert r1["net_realized_pnl_usd"] == r2["net_realized_pnl_usd"]


def test_positive_spread_and_bad_execution_prevent_order():
    bars = sample() + [m5(27, 102.7, 103.3, 101.9, 102.5, spread=100)]
    r = simulate(bars, config())
    assert r["trades_closed"] == 0
    assert r["unrealized_mark_to_market_usd_estimate"] is None
    assert any(x["reason"] == "EXECUTION_QUALITY_OR_STOP_GATE" for x in r["rejections"])


def test_no_footprint_data_may_silently_pass_orderflow_gate():
    with pytest.raises(ValueError, match="NO_GENUINE_ORDERFLOW"):
        simulate(sample(), config(require_orderflow=True))


def test_broken_weekend_gap_resets_breakout_before_entry():
    bars = sample() + [m5(50, 102.7, 107.0, 100.0, 105)]
    r = simulate(bars, config())
    assert not r["trades"]
    assert any(x["reason"] == "GAP_BEFORE_NEXT_OPEN" for x in r["rejections"])
    assert r["gaps_across_all_loaded_bars"] == 1


def test_replay_rejects_invalid_m5_or_risk_inputs():
    with pytest.raises(ValueError, match="UTC-aligned"):
        simulate([Bar(11, 100, 101, 99, 100, 1)] + sample(), config())
    with pytest.raises(ValueError, match="risk limits"):
        config(risk_fraction=0.5).validate()


def test_one_entry_per_utc_date_in_closed_bar_replay():
    bars = sample() + [m5(27, 102.7, 107.0, 100.0, 105)]
    # Two separate valid breakouts within same UTC day should be capped.
    # In fixture, additional candidates may or may not arise; invariant is size.
    bars.extend(m5(28 + n, 100.8, 102.0, 100.0, 100.8) for n in range(24))
    r = simulate(bars, config())
    assert len(r["trades"]) <= 1


def test_pnl_shrinks_with_higher_adverse_slippage():
    b = sample() + [m5(27, 102.7, 107.0, 100.0, 105)]
    lower = simulate(b, config(slippage_price_per_side=0.05, commission_usd_per_lot_roundtrip=1.0))
    higher = simulate(b, config(slippage_price_per_side=0.2, commission_usd_per_lot_roundtrip=10.0))
    assert lower["trades_closed"] == 1
    assert higher["trades_closed"] == 1
    assert higher["net_realized_pnl_usd"] <= lower["net_realized_pnl_usd"]


def test_replay_never_counts_trades_after_test_end():
    prefix = sample()
    end = replace(config(), end_utc=27 * 300)
    later = [m5(27, 102.7, 107.0, 100.0, 105)]
    assert simulate(prefix + later, end)["trades_closed"] == 0
    assert simulate(prefix + later, end)["net_realized_pnl_usd"] == 0
