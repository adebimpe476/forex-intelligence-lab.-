"""Offline-only deterministic tests: no MT5 terminal or account required."""
from types import SimpleNamespace
import time

from forexlab.auto_break_retest import BreakRetestDetector, Candle, Proposal
from forexlab.mt5_demo_runner import eligible_volume, quote_plan


def candles(start=0):
    return [Candle(start + 300 * n, 100.8, 102.0, 100.0, 100.8)
            for n in range(25)]


def test_no_signal_from_initial_unbroken_range():
    detector = BreakRetestDetector()
    assert detector.advance("XAUUSD", candles()) is None
    assert detector.pending == {}


def test_short_requires_break_then_later_closed_rejection():
    d = BreakRetestDetector()
    bars = candles()
    bars.append(Candle(25 * 300, 100.8, 101.0, 98.8, 99.0))
    assert d.advance("XAUUSD", bars) is None
    assert d.pending["XAUUSD"].side == "SELL"
    assert d.advance("XAUUSD", bars) is None  # no duplicate on same bar
    bars.append(Candle(26 * 300, 100.0, 100.3, 98.7, 99.3))
    candidate = d.advance("XAUUSD", bars)
    assert candidate and candidate.side == "SELL"
    assert candidate.level == 100.0
    assert candidate.stop > candidate.entry_reference
    assert d.advance("XAUUSD", bars) is None


def test_long_requires_break_then_later_closed_rejection():
    d = BreakRetestDetector()
    bars = candles()
    bars.append(Candle(25 * 300, 101.0, 103.2, 100.8, 103.0))
    assert d.advance("XAUUSD", bars) is None
    bars.append(Candle(26 * 300, 102.1, 103.0, 101.7, 102.7))
    candidate = d.advance("XAUUSD", bars)
    assert candidate and candidate.side == "BUY"
    assert candidate.stop < candidate.entry_reference


def test_cancellation_on_reclaim():
    d = BreakRetestDetector()
    bars = candles()
    bars.append(Candle(25 * 300, 100.8, 101.0, 98.8, 99.0))
    d.advance("XAUUSD", bars)
    bars.append(Candle(26 * 300, 99.0, 102.2, 98.9, 101.5))
    assert d.advance("XAUUSD", bars) is None
    assert "XAUUSD" not in d.pending


def test_rounding_never_increases_trade_volume():
    assert eligible_volume(0.078, 0.01, 1.00, 0.01) == 0.07
    assert eligible_volume(0.009, 0.01, 1.00, 0.01) == 0.0
    assert eligible_volume(4.8, 0.1, 1.00, 0.1) == 1.0


class FakeMT5:
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1

    def __init__(self, spread=0.1):
        self.spread = spread

    def symbol_info(self, symbol):
        return SimpleNamespace(point=0.01, digits=2, trade_stops_level=10,
                               volume_min=0.01, volume_max=2, volume_step=0.01)

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(bid=99.2, ask=99.2 + self.spread, time=int(time.time()))

    def order_calc_profit(self, order_type, symbol, volume, entry, stop):
        return -100.0 * abs(entry - stop)

    def order_calc_margin(self, order_type, symbol, volume, entry):
        return 100 * volume

    def account_info(self):
        return SimpleNamespace(margin_free=10000)


def test_broker_sized_demo_candidate_with_fresh_quote():
    prop = Proposal("SELL", 100.0, 99.3, 100.5, 2.0, 300, 0)
    plan = quote_plan(FakeMT5(), "XAUUSD", prop, 10000.0, 0.0025, 1.0, 0.15)
    assert plan
    assert plan["side"] == "SELL"
    assert plan["volume"] == 0.16
    assert plan["sl"] == 100.5
    assert plan["tp"] == 96.60
    assert plan["estimated_risk"] <= plan["risk_budget"]


def test_reject_wide_spread():
    prop = Proposal("SELL", 100.0, 99.3, 100.5, 2.0, 300, 0)
    assert quote_plan(FakeMT5(spread=1.1), "XAUUSD", prop, 10000, 0.0025, 1, 0.15) is None
