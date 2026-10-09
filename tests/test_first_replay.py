"""Fixture-only tests; no license or historical authenticity represented."""
import json
import math
from pathlib import Path
import zipfile

import pytest

from forexlab.first_replay import prepare_first_replay


def fixture(tmp_path, count=100, pair='EURUSD', spread=.0002):
    src = tmp_path / 'vendor.zip'
    # HistData timestamps are fixed EST, no daylight-saving conversion.
    lines=[]
    for i in range(count):
        hh, minute = divmod(i*15,60)
        hours = hh%24
        day = 4 + hh//24
        px = 1.085 + .001*math.sin(i / 9)
        lines.append(f'202403{day:02d} {hours:02d}{minute:02d}00000,{px:.5f},{px+spread:.5f},0')
    with zipfile.ZipFile(src, 'w') as z:
        z.writestr(f'DAT_ASCII_{pair}_T_202403.csv', '\n'.join(lines)+'\n')
    declaration = tmp_path / 'declaration.json'
    declaration.write_text(json.dumps({
        'provider':'HistData','pair':pair,
        'source_url':'https://www.histdata.com/',
        'rights':{'quant_research':True, 'evidence_url':'https://www.histdata.com/f-a-q/'}}))
    return src, declaration


def test_first_replay_creates_auditable_nonexecuting_outputs(tmp_path):
    archive, rights = fixture(tmp_path)
    target=tmp_path/'private'/ 'run_1'
    report=prepare_first_replay(archive,rights,target)
    assert report['technical_quote_profile']['observed_m15_buckets']>=20
    assert report['source_audit']['source_month']=='202403'
    assert report['qualification']['technical_ready'] is True
    assert report['qualification']['legal_clearance_verified'] is False
    assert report['actual_lean_run'] is False
    assert report['execution_allowed'] is False
    assert (target/'EURUSD_normalized_ticks.csv').exists()
    assert (target/'reference_simulation.json').exists()
    assert list((target/'lean-staging'/'forex'/'histdata'/'tick'/'eurusd').glob('*_quote.zip'))
    with pytest.raises(FileExistsError):
        prepare_first_replay(archive, rights, target)


def test_requires_declared_rights_and_matching_pair(tmp_path):
    archive, rights = fixture(tmp_path)
    for override in ({'provider':'HistData','pair':'GBPUSD'},
                     {'provider':'HistData','pair':'EURUSD','source_url':'http://invalid.test',
                      'rights':{'quant_research':True,'evidence_url':'https://www.histdata.com/'}},
                     {'provider':'HistData','pair':'EURUSD','source_url':'https://www.histdata.com/',
                      'rights':{'quant_research':False,'evidence_url':'https://www.histdata.com/'}}):
        rights.write_text(json.dumps(override))
        with pytest.raises(ValueError):
            prepare_first_replay(archive, rights, tmp_path/'invalid')
        assert not (tmp_path/'invalid').exists()


def test_tiny_and_bad_spreads_rejected_before_writing(tmp_path):
    archive, rights=fixture(tmp_path, count=10)
    with pytest.raises(ValueError, match='INSUFFICIENT_REPLAY_SAMPLE'):
        prepare_first_replay(archive,rights,tmp_path/'tiny')
    archive, rights=fixture(tmp_path,count=100,spread=.002)
    with pytest.raises(ValueError, match='SPREAD_PROFILE'):
        prepare_first_replay(archive,rights,tmp_path/'spready')


def test_zip_pair_does_not_match_requested_pair(tmp_path):
    archive, rights=fixture(tmp_path,count=100,pair='GBPUSD')
    with pytest.raises(ValueError, match='pair'):
        prepare_first_replay(archive,rights,tmp_path/'bad')


def test_refuses_output_inside_any_git_checkout(tmp_path):
    archive, rights = fixture(tmp_path)
    project = tmp_path / 'public_project'
    (project / '.git').mkdir(parents=True)
    with pytest.raises(ValueError, match='PRIVATE_OUTPUT_REQUIRED'):
        prepare_first_replay(archive, rights, project / 'data' / 'private_quotes')
    assert not (project / 'data').exists()
