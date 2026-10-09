"""Bounded, research-only conversion of licensed Dukascopy BI5 quote files.

An input file corresponds to ONE UTC hour. The file is not redistributed.
No live price feed, orders, leverage, account or automatic trading.

The documented 20-byte record is: milliseconds since hour start, ask integer,
bid integer, ask volume float32, bid volume float32 (big-endian).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import json
import lzma
import math
import struct

import pandas as pd
from .tickdata import validate_ticks

RECORD = struct.Struct(">IIIff")
SCALES = {"EURUSD": 100_000, "GBPUSD": 100_000, "USDJPY": 1_000}
MAX_COMPRESSED_BYTES = 12 * 1024 * 1024
MAX_RECORDS_PER_HOUR = 2_000_000


def _utc_hour(date_hour: object) -> pd.Timestamp:
    try:
        hour = pd.Timestamp(date_hour)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid start hour") from exc
    if hour.tzinfo is None:
        raise ValueError("A timezone-aware UTC start hour is required")
    hour = hour.tz_convert("UTC")
    if hour.minute != 0 or hour.second != 0 or hour.microsecond != 0 or hour.nanosecond != 0:
        raise ValueError("Input reference must be an exact UTC hour")
    return hour


def decode_bi5(payload: bytes, *, pair: str, hour_utc: object) -> pd.DataFrame:
    """Decode an hourly .bi5 payload to validated bid/ask quotes.

    Reject corrupt, unordered, oversized, and crossed quotes; never interpolate.
    """
    if pair not in SCALES:
        raise ValueError("Unsupported pair; price scales must be audited first")
    hour = _utc_hour(hour_utc)
    if not payload or len(payload) > MAX_COMPRESSED_BYTES:
        raise ValueError("Empty or oversized compressed hourly payload")
    try:
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_AUTO)
        raw = dec.decompress(payload, max_length=RECORD.size * MAX_RECORDS_PER_HOUR + 1)
        if not dec.eof or dec.unused_data:
            raise ValueError("Incomplete, oversized or trailing BI5 payload")
    except lzma.LZMAError as exc:
        raise ValueError("Corrupt LZMA BI5 payload") from exc
    if not raw or len(raw) % RECORD.size:
        raise ValueError("Empty or incomplete BI5 record array")
    if len(raw) > RECORD.size * MAX_RECORDS_PER_HOUR:
        raise ValueError("Too many quotes for bounded one-hour decoder")
    times, bids, asks = [], [], []
    last_ms = -1
    divisor = SCALES[pair]
    for ms, ask, bid, ask_volume, bid_volume in RECORD.iter_unpack(raw):
        if ms >= 3_600_000 or ms < last_ms:
            raise ValueError("Out-of-hour or unsorted quote timestamp")
        last_ms = ms
        if ask < bid or bid <= 0 or not all(math.isfinite(x) and x >= 0 for x in (ask_volume, bid_volume)):
            raise ValueError("Invalid or crossed quote / invalid volume")
        times.append(hour + pd.Timedelta(milliseconds=ms))
        bids.append(bid / divisor)
        asks.append(ask / divisor)
    df = pd.DataFrame({"timestamp_utc": pd.DatetimeIndex(times), "bid": bids, "ask": asks})
    # Shared project contract additionally checks positivity, finite values, and monotonic time.
    cleaned, _ = validate_ticks(df.assign(timestamp_utc=df.timestamp_utc.dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")))
    return cleaned[["timestamp_utc", "bid", "ask"]]


def import_bi5_file(source: Path, destination_dir: Path, *, pair: str,
                    hour_utc: object, license_note: str) -> dict:
    """Import a provider-owned file without uploading it to the public repository.

    license_note is user-supplied proof of review, not a legal determination.
    """
    source = Path(source)
    destination_dir = Path(destination_dir)
    if not license_note or not license_note.strip():
        raise ValueError("Record the reviewed provider terms / rights before import")
    if source.stat().st_size > MAX_COMPRESSED_BYTES:
        raise ValueError("Input source exceeds hourly size limit")
    raw = source.read_bytes()
    quotes = decode_bi5(raw, pair=pair, hour_utc=hour_utc)
    destination_dir.mkdir(parents=True, exist_ok=True)
    stamp = _utc_hour(hour_utc).strftime("%Y%m%dT%H00Z")
    csv_path = destination_dir / f"{pair}_{stamp}_quotes.csv"
    quotes.to_csv(csv_path, index=False, float_format="%.5f")
    record = {"provider": "Dukascopy", "pair": pair, "hour_utc": _utc_hour(hour_utc).isoformat(),
              "source_file": source.name, "raw_sha256": hashlib.sha256(raw).hexdigest(),
              "rows": len(quotes), "csv_file": csv_path.name,
              "license_review_note": license_note, "execution_ready": False,
              "warning": "Provider quotes are not broker MT5 fills; confirm permission, quote coverage, spreads and simulation before use."}
    (destination_dir / f"{pair}_{stamp}_provenance.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record
