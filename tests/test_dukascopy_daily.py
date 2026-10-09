"""Daily BI5 path and timestamp tests use SYNTHETIC binary fixtures only."""
import lzma
import pytest
import pandas as pd
from forexlab.dukascopy import RECORD
from forexlab.dukascopy_daily import (decode_daily_bi5, daily_bi5_relative_path,
                                      import_daily_bi5_file, MILLIS_PER_DAY)

DAY = "2024-01-02T00:00:00Z"


def payload(offsets=(0, 3_601_000, 86_399_999), spreads=(12, 12, 12)):
    return lzma.compress(b"".join(RECORD.pack(t, 110000+sp, 110000, 0.2, 0.3)
                                  for t, sp in zip(offsets, spreads)), format=lzma.FORMAT_ALONE)


def test_current_daily_path_is_zero_based_month():
    assert daily_bi5_relative_path("EURUSD", DAY) == "EURUSD/2024/00/02_ticks.bi5"
    assert daily_bi5_relative_path("USDJPY", "2024-12-30T00:00:00Z") == "USDJPY/2024/11/30_ticks.bi5"


def test_day_decoder_preserves_subhour_and_day_boundaries():
    ticks = decode_daily_bi5(payload(), pair="EURUSD", day_utc=DAY)
    assert len(ticks) == 3
    assert ticks.timestamp_utc.iloc[1] == pd.Timestamp("2024-01-02T01:00:01Z")
    assert ticks.timestamp_utc.iloc[2] == pd.Timestamp("2024-01-02T23:59:59.999Z")
    assert ticks.ask.iloc[0] == pytest.approx(1.10012)


def test_bad_timestamps_and_mixed_layout_rejected():
    for t in [(MILLIS_PER_DAY,), (3200000, 20)]:
        with pytest.raises(ValueError, match="out-of-order|Out-of-day|out-of-order"):
            decode_daily_bi5(payload(offsets=t, spreads=[12]*len(t)), pair="EURUSD", day_utc=DAY)
    with pytest.raises(ValueError, match="00:00"):
        decode_daily_bi5(payload(), pair="EURUSD", day_utc="2024-01-02T11:00:00Z")
    with pytest.raises(ValueError, match="timezone-aware"):
        decode_daily_bi5(payload(), pair="EURUSD", day_utc="2024-01-02")


def test_invalid_quotes_or_corrupt_files_rejected():
    with pytest.raises(ValueError, match="crossed"):
        decode_daily_bi5(payload(offsets=(2,), spreads=(-1,)), pair="EURUSD", day_utc=DAY)
    with pytest.raises(ValueError, match="LZMA"):
        decode_daily_bi5(b"not compressed", pair="EURUSD", day_utc=DAY)
    with pytest.raises(ValueError, match="oversized"):
        decode_daily_bi5(b"0" * (33*1024*1024), pair="EURUSD", day_utc=DAY)


def test_bounded_import_writes_private_local_provenance(tmp_path):
    src = tmp_path / "02_ticks.bi5"
    src.write_bytes(payload())
    with pytest.raises(ValueError, match="rights"):
        import_daily_bi5_file(src, tmp_path / "out", pair="EURUSD", day_utc=DAY, license_note="")
    result = import_daily_bi5_file(src, tmp_path / "out", pair="EURUSD", day_utc=DAY,
                                   license_note="Synthetic-only rights QA")
    assert result["source_layout"] == "daily_bi5" and result["tick_count"] == 3
    assert result["execution_ready"] is False
    assert (tmp_path / "out" / result["csv_file"]).exists()


def test_cli_exposes_separate_explicit_daily_mode(tmp_path, capsys):
    from forexlab.cli import main
    file = tmp_path / "02_ticks.bi5"
    file.write_bytes(payload())
    main(["import-daily-bi5", str(file), "--pair", "EURUSD", "--day-utc", DAY,
          "--rights-note", "Synthetic fixture", "--out", str(tmp_path / "target")])
    assert '"source_layout": "daily_bi5"' in capsys.readouterr().out
