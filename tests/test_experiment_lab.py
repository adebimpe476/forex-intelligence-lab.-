import copy
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from forexlab.research_lab import append_ledger, read_ledger, run_diagnostic_experiment, public_experiments
from forexlab.server import app


def csv_fixture(tmp_path, n=240):
    dates = pd.date_range('2020-01-01', periods=n, freq='B')
    p = 1.1*np.exp(np.linspace(0, .1, n) + .008*np.sin(np.arange(n)/4))
    filename = tmp_path/'synthetic.csv'
    pd.DataFrame({'date': dates, 'EURUSD': p, 'GBPUSD': p+.15, 'USDJPY': 110+p}).to_csv(filename,index=False)
    return filename


def run(csv, ledger, strategy='trend_following'):
    return run_diagnostic_experiment(data_path=csv,ledger_path=ledger,
      pair='EURUSD',strategy=strategy,source_kind='SYNTHETIC_TEST',
      cost_bps=2,acknowledge_nontradable=True)


def test_append_and_hash_chain_integrity(tmp_path):
    p=csv_fixture(tmp_path); ledger=tmp_path/'journal.jsonl'
    first=run(p,ledger);second=run(p,ledger,'breakout')
    assert first['prev_entry_hash']=='0'*64
    assert second['prev_entry_hash']==first['entry_hash']
    assert len(read_ledger(ledger))==2
    public=public_experiments(ledger)
    assert public['validated_strategies']==0 and public['execution_allowed'] is False
    assert public['records'][0]['experiment_id']==second['experiment_id']


def test_no_duplicate_or_lock_debris(tmp_path):
    p=csv_fixture(tmp_path); ledger=tmp_path/'journal.jsonl';run(p,ledger)
    with pytest.raises(ValueError,match='already recorded'):run(p,ledger)
    assert len(read_ledger(ledger))==1
    assert not (tmp_path/'journal.jsonl.lock').exists()


def test_corrupt_ledger_refuses_to_report(tmp_path):
    p=csv_fixture(tmp_path); ledger=tmp_path/'journal.jsonl';run(p,ledger)
    contents=ledger.read_text()
    ledger.write_text(contents.replace('trend_following','mean_reversion',1))
    with pytest.raises(ValueError,match='integrity failure'):read_ledger(ledger)
    with pytest.raises(ValueError,match='integrity failure'):run(p,ledger,'breakout')


def test_nontradable_acknowledgment_and_source_required(tmp_path):
    p=csv_fixture(tmp_path);ledger=tmp_path/'journal.jsonl'
    with pytest.raises(ValueError,match='acknowledge'):
        run_diagnostic_experiment(data_path=p,ledger_path=ledger,
          pair='EURUSD',strategy='breakout',source_kind='SYNTHETIC_TEST')
    with pytest.raises(ValueError,match='Unsupported'):
        run_diagnostic_experiment(data_path=p,ledger_path=ledger,
          pair='EURUSD',strategy='breakout',source_kind='BROKER_EXECUTION',acknowledge_nontradable=True)
    assert not ledger.exists()


def test_short_and_duplicate_dates_rejected(tmp_path):
    p=csv_fixture(tmp_path,n=40);ledger=tmp_path/'journal.jsonl'
    with pytest.raises(ValueError,match='need >='):
        run(p,ledger)
    p=csv_fixture(tmp_path)
    df=pd.read_csv(p);df.loc[10,'date']=df.loc[9,'date'];df.to_csv(p,index=False)
    with pytest.raises(ValueError,match='Dates must'):
        run(p,ledger)
    assert not ledger.exists()


def test_no_nonfinite_cost_allowed(tmp_path):
    p=csv_fixture(tmp_path);ledger=tmp_path/'journal.jsonl'
    for bad in [float('nan'), float('inf'),-1]:
        with pytest.raises(ValueError,match='cost_bps'):
            run_diagnostic_experiment(data_path=p,ledger_path=ledger,
              pair='EURUSD',strategy='trend_following',source_kind='SYNTHETIC_TEST',
              cost_bps=bad,acknowledge_nontradable=True)


def test_no_live_order_endpoints_and_read_only_api():
    c=TestClient(app)
    h=c.get('/api/health');assert h.status_code==200
    assert h.json()['order_execution_enabled'] is False
    x=c.get('/api/experiments');assert x.status_code==200
    assert x.json()['execution_allowed'] is False
    assert x.json()['validated_strategies']==0
    assert c.post('/api/orders',json={'side':'BUY'}).status_code==404
    assert c.post('/api/experiments',json={}).status_code==405
    html=c.get('/');assert html.status_code==200
    assert 'Experiment Lab' in html.text and 'HARD DISABLED' in html.text


def test_ledger_integrity_endpoint_returns_503(tmp_path,monkeypatch):
    import forexlab.server as sv
    root=tmp_path
    p=csv_fixture(tmp_path);ledger=root/'artifacts/experiments/ledger.jsonl';run(p,ledger)
    ledger.write_text(ledger.read_text().replace('trend_following','breakout'))
    monkeypatch.setattr(sv,'ROOT',root)
    res=TestClient(sv.app).get('/api/experiments')
    assert res.status_code==503
    assert 'integrity review' in res.json()['detail']


def test_infinite_and_corrupted_reference_prices_rejected(tmp_path):
    p=csv_fixture(tmp_path);ledger=tmp_path/'journal.jsonl'
    df=pd.read_csv(p);df.loc[15,'EURUSD']=float('inf');df.to_csv(p,index=False)
    with pytest.raises(ValueError,match='nonfinite'):
        run(p,ledger)
    assert not ledger.exists()


def test_fred_missing_indicative_day_is_recorded_not_invented(tmp_path):
    p=csv_fixture(tmp_path);ledger=tmp_path/'journal.jsonl'
    df=pd.read_csv(p);df.loc[15,'EURUSD']=np.nan;df.to_csv(p,index=False)
    result=run_diagnostic_experiment(data_path=p,ledger_path=ledger,
        pair='EURUSD',strategy='trend_following',source_kind='FRED_H10_DAILY_INDICATIVE',
        acknowledge_nontradable=True)
    assert result['observations']==239
    assert result['missing_reference_observations']==1
    assert result['source_is_executable_market_data'] is False
