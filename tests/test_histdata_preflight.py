"""Vendor-format fixtures are synthetic, not recorded historical prices."""
from pathlib import Path
import zipfile
import json
import pytest
from forexlab.histdata import decode_histdata_tick_zip, import_histdata_tick_zip
from forexlab.lean_preflight import inspect_lean_environment


def mkzip(tmp_path, lines, name="DAT_ASCII_EURUSD_T_202403.csv"):
    z=tmp_path/'sample.zip'
    with zipfile.ZipFile(z,'w') as out:
        out.writestr(name, '\n'.join(lines)+'\n')
    return z


def test_fixed_est_not_new_york_dst(tmp_path):
    z=mkzip(tmp_path,["20240310 015959500,1.08411,1.08427,0",
                     "20240310 030001000,1.08413,1.08430,0"])
    ticks,meta=decode_histdata_tick_zip(z,pair='EURUSD')
    assert ticks.timestamp_utc.tolist()==['2024-03-10T06:59:59.500Z','2024-03-10T08:00:01.000Z']
    assert meta['original_timezone']=="EST_FIXED_UTC_MINUS_05_NO_DST"
    assert meta['execution_allowed'] is False


def test_import_writes_hash_and_never_claims_legal_clearance(tmp_path):
    z=mkzip(tmp_path,["20240312 090000001,1.08001,1.08019,0"])
    report=import_histdata_tick_zip(z,tmp_path/'out',pair='EURUSD')
    assert len(report['source_sha256'])==64
    assert (tmp_path/'out'/report['normalized_file']).is_file()
    assert report['licensed_rights_verified_externally'] is False
    with pytest.raises(FileExistsError):
        import_histdata_tick_zip(z,tmp_path/'out',pair='EURUSD')


def test_reject_crossed_and_out_of_order(tmp_path):
    z=mkzip(tmp_path,["20240312 090000001,1.10000,1.09900,0"])
    with pytest.raises(ValueError,match='Crossed'):
        decode_histdata_tick_zip(z,pair='EURUSD')
    z=mkzip(tmp_path,["20240312 090001001,1.1,1.1002,0","20240312 090000001,1.1,1.1002,0"])
    with pytest.raises(ValueError,match='ordered'):
        decode_histdata_tick_zip(z,pair='EURUSD')


def test_reject_month_pair_path_and_multiple_files(tmp_path):
    for name in ('DAT_ASCII_GBPUSD_T_202403.csv','DAT_ASCII_EURUSD_T_202402.csv','foo/DAT_ASCII_EURUSD_T_202403.csv'):
        z=mkzip(tmp_path,['20240312 090000001,1.1,1.1002,0'],name)
        with pytest.raises(ValueError):
            decode_histdata_tick_zip(z,pair='EURUSD')
    z=tmp_path/'many.zip'
    with zipfile.ZipFile(z,'w') as out:
        out.writestr('DAT_ASCII_EURUSD_T_202403.csv','20240312 090000001,1.1,1.1002,0\n')
        out.writestr('two.csv','20240312 090000001,1.1,1.1002,0\n')
    with pytest.raises(ValueError,match='exactly one'):
        decode_histdata_tick_zip(z,pair='EURUSD')


def test_missing_and_corrupted_timestamp_quote(tmp_path):
    for row in ('20240312 0900000,1.1,1.1002,0','20240312 090000001,NaN,1.1002,0','20240312 090000001,1.1,1.1002', '20241312 090000001,1.1,1.1002,0'):
        z=mkzip(tmp_path,[row])
        with pytest.raises(ValueError):
            decode_histdata_tick_zip(z,pair='EURUSD')


def test_lean_preflight_never_fakes_success(tmp_path):
    assert inspect_lean_environment()['lean_backtest_executed'] is False
    assert 'NO_DATA_PROVENANCE_MANIFEST' in inspect_lean_environment()['prerequisite_blockers']
    path=tmp_path/'manifest.json'
    path.write_text(json.dumps({'source_sha256':'abc','licensed_rights_verified_externally':False,'provenance_verified_externally':False}))
    result=inspect_lean_environment(data_manifest=str(path))
    assert 'MANUAL_SOURCE_AND_RIGHTS_VERIFICATION_PENDING' in result['prerequisite_blockers']
    assert result['lean_results_verified'] is False
