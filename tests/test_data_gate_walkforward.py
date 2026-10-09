import hashlib
import json
import pandas as pd
import pytest
from forexlab.data_gate import qualify_dataset
from forexlab.walkforward import plan_walkforward


def _fixture(tmp_path, kind="BID_ASK_TICK", provider="TEST"):
    p=tmp_path/'ticks.csv'
    if kind=="BID_ASK_TICK":
        p.write_text('timestamp_utc,bid,ask\n2026-03-09T00:01:00Z,1.1,1.1002\n2026-03-09T00:02:00Z,1.2,1.2002\n')
    else:
        p.write_text('datetime,open,high,low,close\n2026-03-09T00:00:00Z,1.1,1.2,1.0,1.15\n2026-03-09T01:00:00Z,1.2,1.3,1.1,1.25\n')
    m=tmp_path/'manifest.json'
    d={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(), 'kind':kind,
       'provider':provider,'pair':'EURUSD','source_url':'https://example.test/data',
       'rights':{'quant_research':True,'ai_training':False,'evidence_url':'https://example.test/license'}}
    m.write_text(json.dumps(d))
    return p,m,d


def test_tick_preflight_is_never_live_authorization(tmp_path):
    p,m,_=_fixture(tmp_path)
    r=qualify_dataset(p,m)
    assert r['technical_ready'] and r['research_ready']
    assert r['details']['has_executable_bid_ask']
    assert not r['source_verified'] and not r['legal_clearance_verified']
    assert not r['execution_allowed'] and not r['lean_engine_verified']


def test_modified_data_fails_hash_check(tmp_path):
    p,m,_=_fixture(tmp_path)
    p.write_text(p.read_text().replace('1.1,1.1002','1.1,1.1402'))
    assert qualify_dataset(p,m)['reason']=='SHA256_MISMATCH'


def test_rights_are_purpose_specific(tmp_path):
    p,m,_=_fixture(tmp_path)
    assert qualify_dataset(p,m,purpose='ai_training')['reason']=='RIGHTS_NOT_DECLARED_FOR_PURPOSE'


def test_fred_ai_use_blocked_even_with_declared_checkbox(tmp_path):
    p,m,d=_fixture(tmp_path,provider='FRED H10')
    d['rights']['ai_training']=True
    m.write_text(json.dumps(d))
    assert qualify_dataset(p,m,purpose='ai_training')['reason']=='FRED_CONTENT_NOT_PERMITTED_FOR_AI_TRAINING'


def test_mid_ohlc_cannot_claim_bidask(tmp_path):
    p,m,_=_fixture(tmp_path,kind='MID_OHLC')
    r=qualify_dataset(p,m)
    assert r['research_ready'] and r['details']['has_executable_bid_ask'] is False
    assert not r['execution_allowed']


def test_invalid_ohlc_rejected(tmp_path):
    p,m,d=_fixture(tmp_path,kind='MID_OHLC')
    p.write_text(p.read_text().replace('1.1,1.2,1.0,1.15','1.1,1.05,1.0,1.15'))
    d['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();m.write_text(json.dumps(d))
    assert qualify_dataset(p,m)['reason']=='DATASET_OR_MANIFEST_INVALID'


def test_non_timezone_tick_rejected(tmp_path):
    p,m,d=_fixture(tmp_path)
    p.write_text(p.read_text().replace('T00:01:00Z','T00:01:00'))
    d['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();m.write_text(json.dumps(d))
    assert qualify_dataset(p,m)['reason']=='DATASET_OR_MANIFEST_INVALID'


def test_no_unsigned_or_missing_evidence_url_accepted(tmp_path):
    p,m,d=_fixture(tmp_path)
    d['rights'].pop('evidence_url');m.write_text(json.dumps(d))
    assert qualify_dataset(p,m)['reason']=='RIGHTS_NOT_DECLARED_FOR_PURPOSE'


def test_walkforward_test_and_holdout_disjoint():
    idx=pd.date_range('2022-01-01',periods=700,freq='h',tz='UTC')
    r=plan_walkforward(idx,min_train=300,test_size=80,embargo=5,label_horizon=2,final_holdout=100)
    for fold in r['folds']:
        tr=fold['train_range_row_exclusive']; em=fold['embargo_range_row_exclusive']; te=fold['test_range_row_exclusive']
        assert tr[1]==em[0] and em[1]==te[0] and te[1]<=r['locked_final_holdout_range_row_exclusive'][0]
        assert te[0]-tr[1]>=2
    assert r['holdout_untouched'] and not r['execution_allowed'] and not r['out_of_sample_verified']


def test_walkforward_cannot_shrink_embargo_under_label_horizon():
    idx=pd.date_range('2022-01-01',periods=700,freq='h',tz='UTC')
    with pytest.raises(ValueError,match='embargo'):
        plan_walkforward(idx,min_train=300,test_size=80,embargo=1,label_horizon=3)


def test_walkforward_rejects_duplicate_unsorted_naive():
    idx=pd.date_range('2022-01-01',periods=700,freq='h',tz='UTC')
    for x in [idx.tz_localize(None),idx.insert(1,idx[1]),idx[::-1]]:
        with pytest.raises(ValueError):plan_walkforward(x,min_train=300,test_size=80)


def test_holdout_never_begins_inside_fold():
    idx=pd.date_range('2022-01-01',periods=700,freq='h',tz='UTC')
    a=plan_walkforward(idx,min_train=300,test_size=80,embargo=5,final_holdout=100)
    b=plan_walkforward(idx,min_train=300,test_size=80,embargo=5,final_holdout=100)
    assert a==b
    assert a['plan_sha256']==b['plan_sha256']
    assert max(f['test_range_row_exclusive'][1] for f in a['folds'])<=600


def test_ml_rejects_fred_and_missing_rights_even_if_scikit_not_installed():
    from forexlab.ml import fit_research_direction_model
    prices=pd.Series([1.1]*400)
    with pytest.raises(ValueError,match='requires source identity'):
        fit_research_direction_model(prices)
    with pytest.raises(ValueError,match='not approved'):
        fit_research_direction_model(prices,source_kind='FRED_H10_DAILY_INDICATIVE',license_evidence_reviewed=True)


def test_data_gate_invalid_source_url_type_fails_closed(tmp_path):
    p,m,d=_fixture(tmp_path)
    d['source_url']=42;m.write_text(json.dumps(d))
    assert qualify_dataset(p,m)['reason']=='MISSING_SOURCE_URL'
