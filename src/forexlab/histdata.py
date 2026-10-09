"""Bounded local import of HistData generic ASCII bid/ask tick ZIP files.

Source timestamps are fixed EST (UTC-05:00), WITHOUT daylight savings.
There is no automatic download, inferred permission, AI training, or execution.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

import pandas as pd
from .tickdata import validate_ticks

PAIR_RE = re.compile(r"^DAT_ASCII_([A-Z]{6})_T_(\d{6})\.csv$", re.I)
DATE_RE = re.compile(r"^(\d{8})\s(\d{6})(\d{3})$")
FIXED_EST = timezone(timedelta(hours=-5))
MAX_COMPRESSED_BYTES = 120_000_000
MAX_UNCOMPRESSED_BYTES = 250_000_000
MAX_ROWS = 1_000_000


def decode_histdata_tick_zip(source: Path, *, pair: str) -> tuple[pd.DataFrame, dict]:
    """Decode ONE locally obtained quote CSV in a ZIP, preserving bid and ask."""
    if pair not in {"EURUSD", "USDJPY", "GBPUSD"}:
        raise ValueError("Unsupported reviewed pair")
    source = Path(source)
    if not source.is_file() or source.stat().st_size > MAX_COMPRESSED_BYTES:
        raise ValueError("Source missing or archive exceeds size limit")
    raw_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    ticks: list[tuple[str, float, float]] = []
    with zipfile.ZipFile(source) as archive:
        eligible = [item for item in archive.infolist() if item.filename.lower().endswith(".csv")]
        if len(eligible) != 1:
            raise ValueError("Archive must contain exactly one tick CSV")
        member = eligible[0]
        if member.file_size > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("CSV uncompressed size exceeds safety limit")
        if Path(member.filename).name != member.filename:
            raise ValueError("Nested paths in tick archive are not accepted")
        match = PAIR_RE.fullmatch(member.filename)
        if match is None or match.group(1).upper() != pair:
            raise ValueError("Tick CSV name or currency pair does not match expected vendor format")
        month = match.group(2)
        with archive.open(member) as byte_stream:
            with io.TextIOWrapper(byte_stream, encoding="utf-8-sig", newline="") as stream:
                for i, row in enumerate(csv.reader(stream)):
                    if i >= MAX_ROWS:
                        raise ValueError("Tick row limit exceeded")
                    if len(row) != 4:
                        raise ValueError("Expected HistData four-column tick record")
                    m = DATE_RE.fullmatch(row[0].strip())
                    if not m or m.group(1)[:6] != month:
                        raise ValueError("Invalid tick timestamp or date outside named month")
                    try:
                        est = datetime.strptime("".join(m.groups()), "%Y%m%d%H%M%S%f").replace(tzinfo=FIXED_EST)
                        utc = est.astimezone(timezone.utc)
                        bid, ask = float(row[1]), float(row[2])
                    except (OverflowError, ValueError) as exc:
                        raise ValueError("Malformed bid/ask quote or date") from exc
                    ticks.append((utc.isoformat(timespec="milliseconds").replace("+00:00","Z"),bid,ask))
    if not ticks:
        raise ValueError("No tick observations in input")
    normalized = pd.DataFrame(ticks, columns=["timestamp_utc","bid","ask"])
    _, quality = validate_ticks(normalized)
    return normalized, {"source_file":source.name, "source_sha256":raw_hash,
                        "source_format":"HistData generic ASCII ticks (bid,ask)",
                        "source_month":month, "original_timezone":"EST_FIXED_UTC_MINUS_05_NO_DST",
                        "rows":len(normalized), "technical_quality":quality,
                        "historical_quotes_only":True,
                        "provenance_verified_externally":False,
                        "licensed_rights_verified_externally":False,
                        "lean_engine_verified":False, "execution_allowed":False}


def import_histdata_tick_zip(source: Path, out_dir: Path, *, pair: str) -> dict:
    """Store normalized ticks outside Git-controlled source folders when possible."""
    frame, manifest = decode_histdata_tick_zip(source, pair=pair)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{pair}_{manifest['source_month']}_histdata_bidask.csv"
    if dest.exists():
        raise FileExistsError("Refuse to overwrite an existing normalized dataset")
    frame.to_csv(dest, index=False)
    manifest.update(normalized_file=dest.name,
                    normalized_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
                    rights_note="Review current vendor terms and obtain any necessary approval before research, AI training or commercial reuse. No approval is inferred by downloading.")
    (out_dir / f"{pair}_{manifest['source_month']}_manifest.json").write_text(
        json.dumps(manifest, indent=2),encoding="utf-8")
    return manifest
