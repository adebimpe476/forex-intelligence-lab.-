import numpy as np
import pandas as pd
import pytest
from forexlab.strategies import trend_following, breakout, mean_reversion, STRATEGIES
from forexlab.backtest import diagnostic_backtest
from forexlab.data import audit_indicative_csv, _parse_fred_csv


def synthetic_prices(n=240):
    """Deterministic TEST FIXTURE ONLY; NOT real prices."""
    return pd.Series(1.2 * np.exp(np.linspace(0, 0.1, n) + 0.01*np.sin(np.arange(n)/6)),
                     index=pd.date_range("2020-01-01", periods=n, freq="B"))


def test_signals_never_look_forward():
    p = synthetic_prices()
    for fn in STRATEGIES.values():
        s = fn(p)
        # Changing future rows never changes signals at or before cutoff.
        altered = p.copy()
        altered.iloc[180:] = altered.iloc[180:] * 4
        assert (fn(altered).iloc[:180] == s.iloc[:180]).all(), fn.__name__


def test_backtest_research_only_and_lag():
    p = synthetic_prices()
    for strategy in STRATEGIES:
        r = diagnostic_backtest(p, strategy)
        assert r['VALIDATED'] is False
        assert r['observations'] == 240
        assert r['last_20pct_untouched_diagnostic']['days'] == 48
        assert 'signal_lag' in r


def test_short_sample_rejected():
    with pytest.raises(ValueError, match='need >='):
        diagnostic_backtest(synthetic_prices(23), 'trend_following')


def test_missing_not_forward_filled():
    raw = b'DATE,DEXUSEU\n1999-01-04,1.1812\n1999-01-05,.\n1999-01-06,1.1636\n'
    s = _parse_fred_csv(raw, 'DEXUSEU')
    assert len(s) == 3 and s.isna().sum() == 1
    assert s.iloc[0] == pytest.approx(1.1812)


def test_data_snapshot_audit():
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'data/raw/fred_h10_daily_snapshot_2026-10-08.csv'
    r = audit_indicative_csv(path)
    assert r['rows'] == 24
    assert all(r['pairs'][pair]['valid'] == 23 for pair in ('EURUSD','USDJPY','GBPUSD'))


def test_ml_features_are_strictly_historical_and_future_labels_are_removed():
    from forexlab.ml import make_daily_supervised_sample
    p = synthetic_prices(360)
    X, y = make_daily_supervised_sample(p, horizon=1)
    altered = p.copy()
    altered.iloc[220:] *= 2.5
    X2, y2 = make_daily_supervised_sample(altered, horizon=1)
    # Changing the future must not change earlier features / labels.
    pd.testing.assert_frame_equal(X.loc[X.index < p.index[219]],
                                  X2.loc[X2.index < p.index[219]])
    pd.testing.assert_series_equal(y.loc[y.index < p.index[219]],
                                   y2.loc[y2.index < p.index[219]])
    assert p.index[-1] not in X.index  # unknown t+1 label excluded


def test_chronological_partitions_do_not_overlap():
    from forexlab.ml import make_daily_supervised_sample, chronological_partitions
    X,y=make_daily_supervised_sample(synthetic_prices(440))
    a,b,c=chronological_partitions(X,y,gap=2)
    assert a[0].index.max() < b[0].index.min() < b[0].index.max() < c[0].index.min()
    assert len(set(a[0].index)&set(b[0].index))==0


def test_tick_validator_requires_tz_and_preserves_spreads():
    from forexlab.tickdata import validate_ticks
    x = pd.DataFrame({'timestamp_utc':['2026-01-01T00:01:00Z','2026-01-01T00:02:00Z'],
                      'bid':[1.1000,1.1010], 'ask':[1.1002,1.1014]})
    v,a=validate_ticks(x)
    assert a['row_count']==2
    assert v['spread'].iloc[1]==pytest.approx(.0004)
    x.loc[0,'timestamp_utc']='2026-01-01T00:01:00'
    with pytest.raises(ValueError,match='timezone'):
        validate_ticks(x)


def test_tick_validator_rejects_crossed_and_bad_quotes():
    from forexlab.tickdata import validate_ticks
    x=pd.DataFrame({'timestamp_utc':['2026-01-01T00:01:00Z'], 'bid':[1.2],'ask':[1.1]})
    with pytest.raises(ValueError,match='Crossed'):
        validate_ticks(x)
    x.loc[0,'ask']=float('inf')
    with pytest.raises(ValueError,match='finite'):
        validate_ticks(x)


def test_tick_validator_rejects_unsorted_but_keeps_same_timestamp_updates():
    from forexlab.tickdata import validate_ticks
    x=pd.DataFrame({'timestamp_utc':['2026-01-01T00:01:00Z','2026-01-01T00:01:00Z'],
                    'bid':[1.1,1.2], 'ask':[1.1001,1.2001]})
    v,a=validate_ticks(x)
    assert a['same_timestamp_updates']==1 and len(v)==2
    x.loc[0,'timestamp_utc']='2026-01-01T00:02:00Z'
    with pytest.raises(ValueError,match='ordered'):
        validate_ticks(x)


def test_resampling_never_creates_empty_bars_or_lookahead():
    from forexlab.tickdata import validate_ticks,to_bars,ALLOWED_TIMEFRAMES
    raw=pd.DataFrame({'timestamp_utc':['2026-01-01T00:01:00Z','2026-01-01T00:14:00Z',
                                      '2026-01-01T00:15:00Z','2026-01-03T00:00:00Z'],
                      'bid':[1.00,1.20,1.10,1.05],
                      'ask':[1.01,1.21,1.11,1.06]})
    clean,_=validate_ticks(raw)
    m15=to_bars(clean,'M15')
    assert len(m15)==3  # skipped thousands of missing M15 windows
    assert m15.iloc[0]['bid_open']==1.00
    assert m15.iloc[0]['bid_high']==1.20
    assert m15.iloc[0]['bid_close']==1.20
    assert m15.iloc[0]['tick_count']==2
    assert m15.iloc[1]['bid_open']==1.10
    assert m15.iloc[0]['bar_end_utc'] == m15.iloc[1]['bar_start_utc']
    changed=raw.copy();changed.loc[2,'bid']=2.50;changed.loc[2,'ask']=2.51
    clean2,_=validate_ticks(changed)
    m15_2=to_bars(clean2,'M15')
    pd.testing.assert_series_equal(m15.iloc[0],m15_2.iloc[0])
    for tf in ALLOWED_TIMEFRAMES:
        out=to_bars(clean,tf)
        assert out['tick_count'].sum()==len(clean)
        assert (out['bar_end_utc']>out['bar_start_utc']).all()


def test_tick_resampler_writes_audit_not_trading_orders(tmp_path):
    from forexlab.tickdata import resample_tick_csv
    src=tmp_path/'synthetic_fixture.csv'
    pd.DataFrame({'timestamp_utc':['2026-01-01T00:01:00Z','2026-01-01T00:02:00Z'],
                  'bid':[1.01,1.02], 'ask':[1.011,1.021]}).to_csv(src,index=False)
    report=resample_tick_csv(src,tmp_path/'out',['M15','H4'])
    assert report['execution_ready'] is False
    assert (tmp_path/'out'/'synthetic_fixture_M15_bidask.csv').exists()
