"""Entire BI5 suite uses synthetic in-memory files; zero provider data redistribution."""
import lzma
import struct
import json
import pandas as pd
import pytest
from forexlab.dukascopy import decode_bi5, import_bi5_file
from forexlab.tickdata import validate_ticks, to_bars

HOUR = "2024-01-03T12:00:00Z"


def pack(records):
    return lzma.compress(b"".join(struct.pack(">IIIff", *r) for r in records))


def test_eurusd_ask_bid_time_and_volume_decoder():
    data = pack([(0, 110020, 110000, 1.0, 2.0), (900000, 110050, 110025, 0.5, 1.0),
                 (900000, 110052, 110026, 0.0, 0.0)])
    quotes = decode_bi5(data, pair="EURUSD", hour_utc=HOUR)
    assert len(quotes) == 3
    assert quotes.iloc[0].bid == pytest.approx(1.10000)
    assert quotes.iloc[0].ask == pytest.approx(1.10020)
    assert quotes.iloc[1].timestamp_utc == pd.Timestamp("2024-01-03T12:15:00Z")
    assert quotes.iloc[1].ask == pytest.approx(1.10050)


def test_usdjpy_scale_is_different():
    x = decode_bi5(pack([(0, 145230, 145210, 1.0, 1.0)]), pair="USDJPY", hour_utc=HOUR)
    assert x.iloc[0].bid == pytest.approx(145.210)
    assert x.iloc[0].ask == pytest.approx(145.230)


def test_bad_payload_and_unsupported_symbol_fail():
    with pytest.raises(ValueError):
        decode_bi5(b"not_lzma", pair="EURUSD", hour_utc=HOUR)
    with pytest.raises(ValueError, match="Unsupported pair"):
        decode_bi5(pack([(0, 1, 1, 0., 0.)]), pair="XAUUSD", hour_utc=HOUR)
    with pytest.raises(ValueError, match="timezone-aware"):
        decode_bi5(pack([(0, 110100, 110050, 1., 1.)]), pair="EURUSD", hour_utc="2024-01-03T12:00:00")


@pytest.mark.parametrize("rows", [
    [(3600000, 110020, 110000, 1., 1.)],
    [(500, 110020, 110000, 1., 1.), (400, 110030, 110010, 1., 1.)],
    [(0, 109900, 110000, 1., 1.)],
    [(0, 110020, 110000, float("nan"), 1.)],
])
def test_invalid_records_rejected(rows):
    with pytest.raises(ValueError):
        decode_bi5(pack(rows), pair="EURUSD", hour_utc=HOUR)


def test_round_trip_into_five_research_timeframes():
    raw = pack([(0, 110020, 110000, 1., 1.), (900000, 110050, 110020, 1., 1.),
                (1800000, 110060, 110030, 1., 1.)])
    df = decode_bi5(raw, pair="EURUSD", hour_utc=HOUR)
    check,_ = validate_ticks(df.assign(timestamp_utc=df.timestamp_utc.dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")))
    for tf in ("M15", "M30", "H1", "H4", "D1"):
        bars = to_bars(check,tf)
        assert int(bars.tick_count.sum()) == 3
        assert bars.bar_end_utc.min() > bars.bar_start_utc.min()


def test_provenance_manifest_and_rights_review_required(tmp_path):
    p=tmp_path/"12h_ticks.bi5"
    p.write_bytes(pack([(0,110020,110000,1.,1.)]))
    with pytest.raises(ValueError, match="terms"):
        import_bi5_file(p,tmp_path/"research",pair="EURUSD",hour_utc=HOUR,license_note="")
    result=import_bi5_file(p,tmp_path/"research",pair="EURUSD",hour_utc=HOUR,
                           license_note="Synthetic test fixture; no real provider material")
    assert result["rows"]==1 and result["execution_ready"] is False
    manifest=json.loads((tmp_path/"research"/"EURUSD_20240103T1200Z_provenance.json").read_text())
    assert manifest["raw_sha256"]==result["raw_sha256"]
