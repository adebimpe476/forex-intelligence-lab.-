import io
import zipfile
import pandas as pd
import pytest
from forexlab.lean_format import to_lean_forex_tick_zips


def sample():
    return pd.DataFrame({"timestamp_utc":["2026-03-01T23:59:59.999Z", "2026-03-02T00:00:00.001Z", "2026-03-02T00:00:00.001Z"],
                         "bid":[1.10001,1.10002,1.10003],"ask":[1.10021,1.10022,1.10023]})


def test_lean_quote_tick_zip_layout_and_row_integrity(tmp_path):
    result=to_lean_forex_tick_zips(sample(), pair="EURUSD",market="dukascopy",out_dir=tmp_path)
    assert len(result['data'])==2
    assert result['verified_with_lean'] is False
    f=tmp_path/'forex/dukascopy/tick/eurusd/20260302_quote.zip'
    with zipfile.ZipFile(f) as z:
        assert z.namelist()==['20260302_eurusd_tick_quote.csv']
        assert z.read(z.namelist()[0]).decode().splitlines()==[
            '1,1.10002,1.10022', '1,1.10003,1.10023']
    old= f.read_bytes()
    to_lean_forex_tick_zips(sample(),pair='EURUSD',market='dukascopy',out_dir=tmp_path)
    assert f.read_bytes()==old


def test_broker_venue_mislabel_is_forbidden(tmp_path):
    for v in ('oanda','fxcm','../../temp',''):
        with pytest.raises(ValueError):
            to_lean_forex_tick_zips(sample(),pair='EURUSD',market=v,out_dir=tmp_path)


def test_naive_crossed_and_unsorted_ticks_rejected(tmp_path):
    original=sample()
    x=original.copy();x.loc[1,'ask']=0.1
    with pytest.raises(ValueError):
        to_lean_forex_tick_zips(x,pair='EURUSD',market='dukascopy',out_dir=tmp_path)
    x=original.copy();x.loc[1,'timestamp_utc']='2026-03-01T23:58:00Z'
    with pytest.raises(ValueError):
        to_lean_forex_tick_zips(x,pair='EURUSD',market='dukascopy',out_dir=tmp_path)
    x=original.copy();x.loc[1,'timestamp_utc']='2026-03-02T00:00:00'
    with pytest.raises(ValueError):
        to_lean_forex_tick_zips(x,pair='EURUSD',market='dukascopy',out_dir=tmp_path)
