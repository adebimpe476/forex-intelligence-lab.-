"""Synthetic fixtures test causal logic and reject false high-win-rate claims."""
import numpy as np
import pandas as pd
import pytest
from forexlab.intelligence import analyze_pair, PERIODS
from forexlab.edge_audit import audit_net_r

ASOF = pd.Timestamp('2026-06-01T12:00:00Z')


def frames(*, flip_d1=False, wide_spread=False):
    out = {}
    for tf, delta in PERIODS.items():
        n = 45
        close_times = pd.date_range(end=ASOF.floor(delta), periods=n, freq=delta, tz='UTC')
        prices = np.linspace(1.05, 1.15, n)
        if tf == 'D1' and flip_d1:
            prices = prices[::-1]
        spreads = .0002 if not wide_spread else .0012
        out[tf] = pd.DataFrame({
            'bar_start_utc': close_times - delta,
            'bar_end_utc': close_times,
            'bid_close': prices - spreads/2,
            'ask_close': prices + spreads/2,
            'mid_close': prices,
            'spread_last': spreads,
            'tick_count': np.full(n, 10),
        })
    return out


def test_own_trend_breakout_hypothesis_uses_all_five_closed_timeframes():
    x = analyze_pair('EURUSD', frames(), ASOF)
    assert x['action'] == 'BUY'
    assert x['hypothesis'] == 'trend_breakout_confluence'
    assert x['regime'] == 'TREND'
    assert x['research_only'] is True and x['execution_allowed'] is False


def test_conflicting_higher_timeframe_causes_wait():
    x = analyze_pair('GBPUSD', frames(flip_d1=True), ASOF)
    assert x['action'] == 'WAIT'
    assert 'NOT_ALIGNED' in x['blockers'][0]


def test_high_spread_blocks_signal_even_with_perfect_trend():
    x = analyze_pair('EURUSD', frames(wide_spread=True), ASOF)
    assert x['action'] == 'WAIT'
    assert x['blockers'] == ['HISTORICAL_SPREAD_PROXY_TOO_WIDE']


def test_stale_insufficient_and_corrupt_data_fail_closed():
    sample = frames()
    assert analyze_pair('USDJPY', sample, ASOF + pd.Timedelta(hours=2))['action'] == 'WAIT'
    sample['H1'] = sample['H1'].tail(8)
    x = analyze_pair('USDJPY', sample, ASOF)
    assert x['action'] == 'WAIT' and x['blockers'][0].startswith('DATA_NOT_READY')
    sample = frames()
    sample['M30'].loc[0, 'ask_close'] = 0
    assert analyze_pair('USDJPY', sample, ASOF)['action'] == 'WAIT'


def test_future_bars_never_modify_past_decision():
    frames_now = frames()
    first = analyze_pair('EURUSD', frames_now, ASOF)
    extra = frames()
    for tf, delta in PERIODS.items():
        last = extra[tf].iloc[-1:].copy()
        last['bar_start_utc'] = last['bar_start_utc'] + delta * 2
        last['bar_end_utc'] = last['bar_end_utc'] + delta * 2
        last['bid_close'] = 99
        last['ask_close'] = 99.0002
        last['mid_close'] = 99.0001
        extra[tf] = pd.concat([extra[tf], last], ignore_index=True)
    second = analyze_pair('EURUSD', extra, ASOF)
    assert first == second


def test_no_naive_timezone_accepted():
    sample = frames()
    sample['M15']['bar_end_utc'] = sample['M15']['bar_end_utc'].dt.tz_localize(None)
    assert analyze_pair('EURUSD', sample, ASOF)['action'] == 'WAIT'


def test_95_percent_winners_can_still_lose_money():
    # 95 tiny +0.01R gains and five -1R losses: high win rate, NEGATIVE expectancy.
    x = audit_net_r([.01]*95 + [-1.0]*5)
    assert x['win_rate_excluding_breakevens'] == pytest.approx(.95)
    assert x['expectancy_net_r_per_trade'] < 0
    assert x['passes_minimum_sample_and_positive_expectancy'] is False
    assert x['validated'] is False and x['execution_allowed'] is False


def test_positive_diagnostic_does_not_authorize_execution():
    x = audit_net_r([2.0]*60 + [-1.0]*40)
    assert x['passes_minimum_sample_and_positive_expectancy'] is True
    assert x['validated'] is False and x['execution_allowed'] is False


def test_insufficient_and_nonfinite_r_samples_rejected():
    assert audit_net_r([1., -1.])['passes_minimum_sample_and_positive_expectancy'] is False
    with pytest.raises(ValueError):
        audit_net_r([np.nan, 2.0])
    with pytest.raises(ValueError):
        audit_net_r([])
