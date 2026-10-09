"""Auditable FRED H.10 daily indicative exchange rate data ingestion.

NOT OHLC, ticks, real-time, or broker executable. This module never places orders.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import requests

SERIES = {"EURUSD": "DEXUSEU", "USDJPY": "DEXJPUS", "GBPUSD": "DEXUSUK"}
BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def _parse_fred_csv(raw: bytes, series: str) -> pd.Series:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    fields = reader.fieldnames or []
    date_col = next((c for c in fields if c.lower() in ("date", "observation_date")), None)
    value_col = next((c for c in fields if c.lower() == series.lower()), None)
    if not date_col or not value_col:
        raise ValueError(f"Unexpected FRED CSV headers: {fields!r}")
    dates, values = [], []
    for row in reader:
        dates.append(pd.Timestamp(row[date_col]))
        v = row[value_col]
        values.append(float(v) if v and v != "." else float("nan"))
    result = pd.Series(values, index=pd.DatetimeIndex(dates), name=series, dtype="float64")
    if result.index.has_duplicates or not result.index.is_monotonic_increasing:
        raise ValueError(f"Duplicate/unsorted observations for {series}")
    if (result.dropna() <= 0).any():
        raise ValueError(f"Invalid non-positive price for {series}")
    return result


def fetch_fred_daily(out_dir: Path, start: str = "1999-01-01", end: str = "2026-10-09") -> dict[str, Any]:
    """Fetch complete observed daily *fixings*, preserving source bytes and SHA256.

    Network is required. Do not treat these data as executable bid/ask or intraday bars.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    series_map = {}
    for pair, series in SERIES.items():
        raw = None
        error = None
        for attempt in range(3):
            try:
                resp = requests.get(BASE_URL, params={"id": series}, timeout=40,
                                    headers={"User-Agent": "forex-intelligence-lab/0.1 (research)"})
                resp.raise_for_status()
                raw = resp.content
                break
            except requests.RequestException as exc:
                error = exc
                if attempt < 2:
                    time.sleep(attempt + 1)
        if raw is None:
            raise RuntimeError(f"Could not fetch {pair} from FRED: {error}")
        vals = _parse_fred_csv(raw, series).loc[start:end]
        if vals.empty:
            raise ValueError(f"No rows for {pair} in requested period")
        raw_path = out_dir / f"{series}.csv"
        raw_path.write_bytes(raw)
        series_map[pair] = vals.rename(pair)
        valid = vals.dropna()
        records.append({"pair": pair, "series": series,
                        "source_url": f"https://fred.stlouisfed.org/series/{series}",
                        "file": raw_path.name, "sha256": hashlib.sha256(raw).hexdigest(),
                        "first_date": str(valid.index.min().date()) if len(valid) else None,
                        "last_date": str(valid.index.max().date()) if len(valid) else None,
                        "valid": int(vals.count()), "missing": int(vals.isna().sum()),
                        "observations": int(len(vals))})
    merged = pd.concat(series_map.values(), axis=1).sort_index()
    merged.index.name = "date"
    merged.to_csv(out_dir / "fred_h10_merged_daily_indicative.csv", float_format="%.6f")
    manifest = {"source": "FRB H.10 via FRED", "frequency": "daily",
                "description": "Noon New York indicative buying rates; NOT bid/ask, OHLC or tradable historical prices",
                "query_dates": [start, end], "retrieved_on": date.today().isoformat(),
                "series": records, "merged_file": "fred_h10_merged_daily_indicative.csv",
                "redistribution_note": "Review FRB/FRED source copyright and citation terms before sharing data."}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def audit_indicative_csv(path: Path) -> dict[str, Any]:
    df = pd.read_csv(path, parse_dates=["date"])
    if df["date"].duplicated().any() or not df["date"].is_monotonic_increasing:
        raise ValueError("Dates must be unique and ascending")
    if any(c not in df.columns for c in SERIES):
        raise ValueError("Expected three pair columns: " + ", ".join(SERIES))
    report = {"file": str(path), "rows": len(df), "pairs": {}}
    for pair in SERIES:
        v = pd.to_numeric(df[pair], errors="coerce")
        if (v.dropna() <= 0).any():
            raise ValueError(f"Invalid non-positive data for {pair}")
        valid_dates = df.loc[v.notna(), "date"]
        report["pairs"][pair] = {"valid": int(v.count()), "missing": int(v.isna().sum()),
                                  "first_valid": str(valid_dates.min().date()) if len(valid_dates) else None,
                                  "last_valid": str(valid_dates.max().date()) if len(valid_dates) else None}
    report["data_quality"] = "FRED H.10 daily indicative values only; missing rows are preserved"
    return report
