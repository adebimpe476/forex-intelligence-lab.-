"""Synthetic binary fixtures only; do not mistake these for historical FX ticks."""
import lzma
import pytest
import pandas as pd
from forexlab.dukascopy import RECORD
from forexlab.dukascopy_daily import (
    decode_daily_bi5, daily_bi5_relative_path, import_daily_bi5_file,
    MILLIS_PER_DAY,
)

DAY = "2024-01-02T00:00:00Z"

def payload(offsets=(0, 3_601_000, 86_399_999), spreads=(12, 12, 12)):
    raw = b"".join(RECORD.pack(t, 110000 + sp, 110000, 0.2, 0.3)
                   for t, sp in zip(offsets, spreads))
    return lzma.compress(raw, format=lzma.FORMAT_ALONE)

def test_daily_month_zero_based():
    assert daily_bi5_relative_path("EURUSD", DAY) == "EURUSD/2024/00/02_ticks.bi5"
    assert daily_bi5_relative_path("USDJPY", "2024-12-30T00:00:00Z") == "USDJPY/2024/11/30_ticks.bi5"

def test_daily_offsets_decode_past_first_hour():
    v = decode_daily_bi5(payload(), pair="EURUSD", day_utc=DAY)
    assert len(v) == 3
    assert v.timestamp_utc.iloc[1] == pd.Timestamp("2024-01-02T01:00:01Z")
    assert v.timestamp_utc.iloc[-1] == pd.Timestamp("2024-01-02T23:59:59.999Z")
    assert v.ask.iloc[0] == pytest.approx(1.10012)

def test_day_rejects_bad_offsets_and_naive_times():
    for offsets in ((MILLIS_PER_DAY,), (3_200_000, 20)):
        with pytest.raises(ValueError, match="Out-of-day|out-of-order"):
            decode_daily_bi5(payload(offsets, [12]*len(offsets)), pair="EURUSD", day_utc=DAY)
    with pytest.raises(ValueError, match="00:00"):
        decode_daily_bi5(payload(), pair="EURUSD", day_utc="2024-01-02T11:00:00Z")
    with pytest.raises(ValueError, match="timezone-aware"):
        decode_daily_bi5(payload(), pair="EURUSD", day_utc="2024-01-02")

def test_daily_rejects_corruption_crossed_quotes_and_oversize():
    with pytest.raises(ValueError, match="crossed"):
        decode_daily_bi5(payload((2,), (-1,)), pair="EURUSD", day_utc=DAY)
    with pytest.raises(ValueError, match="LZMA"):
        decode_daily_bi5(b"not compressed", pair="EURUSD", day_utc=DAY)
    with pytest.raises(ValueError, match="oversized"):
        decode_daily_bi5(b"0"*(33*1024*1024), pair="EURUSD", day_utc=DAY)

def test_import_local_file_requires_rights_note_and_is_not_executable(tmp_path):
    src = tmp_path / "02_ticks.bi5"
    src.write_bytes(payload())
    with pytest.raises(ValueError, match="rights"):
        import_daily_bi5_file(src, tmp_path/"out", pair="EURUSD", day_utc=DAY, license_note="")
    report = import_daily_bi5_file(src, tmp_path/"out", pair="EURUSD", day_utc=DAY,
                                   license_note="Synthetic-only fixture")
    assert report["source_layout"] == "daily_bi5"
    assert report["tick_count"] == 3 and report["execution_ready"] is False
    assert (tmp_path/"out"/report["csv_file"]).exists()

def test_cli_daily_mode(tmp_path, capsys):
    from forexlab.cli import main
    src = tmp_path/"02_ticks.bi5"
    src.write_bytes(payload())
    main(["import-daily-bi5", str(src), "--pair", "EURUSD", "--day-utc", DAY,
          "--rights-note", "Synthetic fixture", "--out", str(tmp_path/"out")])
    assert '"source_layout": "daily_bi5"' in capsys.readouterr().out
