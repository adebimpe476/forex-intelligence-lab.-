"""Current-layout daily Dukascopy BI5 decoder (research only; no orders).

Daily filename DD_ticks.bi5, 20-byte >IIIff records, timestamp milliseconds
from 00:00 UTC. Do not mix with legacy hourly HHh_ticks.bi5 files.
Network acquisition, redistribution rights and broker comparisons are separate.
"""
from __future__ import annotations
import hashlib
import json
import lzma
import math
from pathlib import Path
import pandas as pd
from .dukascopy import RECORD, SCALES
from .tickdata import validate_ticks

MAX_COMPRESSED_BYTES = 32 * 1024 * 1024
MAX_TICKS_PER_DAY = 3_000_000
MILLIS_PER_DAY = 86_400_000

def _day_utc(day_utc: object) -> pd.Timestamp:
    try:
        ts = pd.Timestamp(day_utc)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid UTC day") from exc
    if ts.tzinfo is None:
        raise ValueError("Daily BI5 reference day must be timezone-aware")
    ts = ts.tz_convert("UTC")
    if ts != ts.normalize():
        raise ValueError("Daily BI5 reference must be exactly 00:00 UTC")
    return ts

def daily_bi5_relative_path(pair: str, day_utc: object) -> str:
    """Source-relative path; not a verified download URL."""
    if pair not in SCALES:
        raise ValueError("Unreviewed pair scale")
    day = _day_utc(day_utc)
    return f"{pair}/{day.year}/{day.month-1:02d}/{day.day:02d}_ticks.bi5"

def decode_daily_bi5(payload: bytes, *, pair: str, day_utc: object) -> pd.DataFrame:
    """Decode and bound checked quote ticks; layout must be explicitly selected."""
    if pair not in SCALES:
        raise ValueError("Unsupported FX pair scale")
    day = _day_utc(day_utc)
    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_COMPRESSED_BYTES:
        raise ValueError("Empty, invalid or oversized daily compressed payload")
    try:
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_AUTO)
        raw = decoder.decompress(payload, max_length=MAX_TICKS_PER_DAY * RECORD.size + 1)
        if not decoder.eof or decoder.unused_data:
            raise ValueError("Incomplete, too large or trailing daily BI5 stream")
    except (lzma.LZMAError, EOFError) as exc:
        raise ValueError("Invalid LZMA daily BI5 stream") from exc
    if not raw or len(raw) % RECORD.size or len(raw) > MAX_TICKS_PER_DAY * RECORD.size:
        raise ValueError("Invalid daily BI5 record length or count")
    times, bids, asks = [], [], []
    previous = -1
    for ms, ask, bid, ask_vol, bid_vol in RECORD.iter_unpack(raw):
        if ms >= MILLIS_PER_DAY or ms < previous:
            raise ValueError("Out-of-day or out-of-order quote timestamp")
        if bid <= 0 or ask < bid:
            raise ValueError("Nonpositive or crossed quotes")
        if not all(math.isfinite(v) and v >= 0 for v in (ask_vol, bid_vol)):
            raise ValueError("Invalid quote volume")
        previous = ms
        times.append(day + pd.Timedelta(milliseconds=ms))
        bids.append(bid / SCALES[pair])
        asks.append(ask / SCALES[pair])
    df = pd.DataFrame({"timestamp_utc": pd.DatetimeIndex(times), "bid": bids, "ask": asks})
    cleaned, _ = validate_ticks(df.assign(timestamp_utc=df.timestamp_utc.dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")))
    return cleaned[["timestamp_utc", "bid", "ask"]]

def import_daily_bi5_file(source: Path, out_dir: Path, *, pair: str,
                          day_utc: object, license_note: str) -> dict:
    """Import one locally held, rights-checked file with SHA256 provenance."""
    if not license_note or not license_note.strip():
        raise ValueError("Document provider data-use rights before importing")
    source = Path(source)
    if source.stat().st_size > MAX_COMPRESSED_BYTES:
        raise ValueError("Daily source file exceeds compressed size limit")
    raw = source.read_bytes()
    ticks = decode_daily_bi5(raw, pair=pair, day_utc=day_utc)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = _day_utc(day_utc)
    stem = f"{pair}_{day:%Y%m%d}_daily_quotes"
    csv_path = out_dir / f"{stem}.csv"
    ticks.to_csv(csv_path, index=False)
    manifest = {"source": "Dukascopy", "source_layout": "daily_bi5", "pair": pair,
                "day_utc": day.isoformat(), "expected_relative_path": daily_bi5_relative_path(pair, day),
                "source_file": source.name, "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "tick_count": len(ticks), "first_timestamp": ticks.timestamp_utc.min().isoformat(),
                "last_timestamp": ticks.timestamp_utc.max().isoformat(),
                "csv_file": csv_path.name, "data_rights_review": license_note,
                "execution_ready": False, "lean_backtest_verified": False,
                "warning": "Local import only. Not verified with live source, LEAN, MT5, or broker fills."}
    (out_dir / f"{stem}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
