"""Reference simulator safety and causality on synthetic quotes, NOT real market evidence."""
import pandas as pd
import pytest
from forexlab.quote_simulator import simulate_quotes, SimulatorConfig


def ticks(prices=None,spread=0.0001, span_seconds=1):
    # Each M15 has quote at 14m59s and the next period has a new quote at its start.
    prices=prices or [1.1,1.1,1.1001,1.1002,1.1003,1.1004,1.1005,1.1006,1.1007,
                      1.1008,1.1009,1.1010,1.1011,1.1010,1.1009,1.1008,1.1007,
                      1.1006,1.1005,1.1004,1.1003,1.1002,1.1001,1.1000,1.0999]
    times=pd.date_range('2026-01-06T00:00:00Z',periods=len(prices),freq='15min')
    rows=[]
    for t,p in zip(times,prices):
        rows.append((t.isoformat(),p-spread/2,p+spread/2))
        rows.append(((t+pd.Timedelta(minutes=14,seconds=59)).isoformat(),p-spread/2,p+spread/2))
    return pd.DataFrame(rows,columns=['timestamp_utc','bid','ask'])


def conf(**kw):
    return SimulatorConfig(fast=2,slow=4,stop_pips=5,take_pips=5,
                           max_entry_delay_seconds=30,max_gap_seconds=901,**kw)


def test_requires_realistic_completeness_and_never_executes():
    out=simulate_quotes(ticks(),conf())
    assert out['execution_allowed'] is False
    assert out['lean_engine_verified'] is False
    assert out['broker_equivalent'] is False
    assert len(out['data_sha256'])==64
    assert out['mode']=='RESEARCH_REFERENCE_SIMULATOR'


def test_lagged_signals_no_pre_close_entry():
    out=simulate_quotes(ticks(),conf())
    for trade in out['trades']:
        assert pd.Timestamp(trade['entry_time'])>=pd.Timestamp(trade['signal_time'])
        assert pd.Timestamp(trade['exit_time'])>pd.Timestamp(trade['entry_time'])


def test_future_quotes_cannot_change_earlier_decisions():
    sample=ticks()
    a=simulate_quotes(sample,conf())
    ext=ticks([1.104]*12)
    anchor=pd.Timestamp(sample.timestamp_utc.iloc[-1])+pd.Timedelta(minutes=15)
    new=ext.copy()
    start=pd.Timestamp(ext.timestamp_utc.iloc[0]); delta=anchor-start
    new['timestamp_utc']=[(pd.Timestamp(x)+delta).isoformat() for x in ext.timestamp_utc]
    b=simulate_quotes(pd.concat([sample,new],ignore_index=True),conf())
    # Closed trades from the original sample must remain unchanged; any unclosed are excluded.
    for trade in a['trades']:
        assert trade in b['trades']


def test_wide_spreads_rejected():
    o=simulate_quotes(ticks(spread=0.001),conf())
    assert o['trades_closed']==0
    assert all(x['reason']=='SPREAD_TOO_WIDE' for x in o['rejections'])


def test_corrupt_crossed_and_naive_inputs_rejected():
    raw=ticks()
    raw.loc[0,'ask']=1.0
    with pytest.raises(ValueError,match='Crossed'):
        simulate_quotes(raw,conf())
    raw=ticks();raw.loc[0,'timestamp_utc']='2026-01-06T00:00:00'
    with pytest.raises(ValueError,match='timezone'):
        simulate_quotes(raw,conf())


def test_insufficient_observations_and_bad_config_rejected():
    with pytest.raises(ValueError,match='Insufficient'):
        simulate_quotes(ticks([1.1]*3),conf())
    with pytest.raises(ValueError,match='USD-quoted'):
        simulate_quotes(ticks(),SimulatorConfig(pair='USDJPY'))
    with pytest.raises(ValueError,match='Require 2'):
        simulate_quotes(ticks(),SimulatorConfig(fast=9,slow=5))


def test_results_are_reproducible_without_retraining():
    raw=ticks()
    a=simulate_quotes(raw,conf())
    b=simulate_quotes(raw,conf())
    assert a == b


def test_profit_report_never_marks_strategy_validated():
    out=simulate_quotes(ticks(),conf())
    assert 'profitability_verified' not in out
    assert not out['execution_allowed']


def test_quote_fill_and_all_costs_apply_on_synthetic_take_profit():
    result = simulate_quotes(ticks(), conf())
    assert result['trades_closed'] == 1
    trade = result['trades'][0]
    assert trade['side'] == 'SELL' and trade['reason'] == 'TAKE'
    # One full lot, 0.2 pip adverse slippage per side and $7 roundtrip cost.
    assert trade['pnl_usd_one_lot'] == pytest.approx(49.0)
    assert result['win_rate'] == 1.0  # SYNTHETIC fixture, NOT a measured win rate
    assert result['strategy_validated'] is False


def test_unobserved_gap_never_reclassified_as_profit():
    sample = ticks()
    # Preserve enough closed bars for a candidate; introduce a gap during the trade.
    sample = sample[~sample['timestamp_utc'].str.startswith('2026-01-06T04:')].reset_index(drop=True)
    out = simulate_quotes(sample, conf())
    # Neither missing price points nor skipped data intervals may be invented.
    assert out['trades_closed'] == 0
    assert out['rejections'] == [{'signal_time':'2026-01-06T03:45:00+00:00', 'reason':'UNOBSERVED_DATA_GAP'}]
    assert out['invalid_outcomes_present'] is True
    assert out['execution_allowed'] is False
