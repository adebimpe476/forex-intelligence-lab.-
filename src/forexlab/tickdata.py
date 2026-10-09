"""Tick data validation and honest multi-timeframe bid/ask OHLC aggregation.

INPUT: timestamp_utc (ISO8601 with explicit timezone), bid, ask; optional source.
OUTPUT: observed-only bars, with bid/ask and derived mid OHLC, tick counts, spreads.

No interpolation, forward fill, simulated quotes, or order submission.
Bar labels denote START time; bars are not available until the interval closes.
UTC-day cutoffs are for ingestion QA and do not represent the New York 17:00 FX session.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ALLOWED_TIMEFRAMES = {"M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h", "D1": "1D"}
NEEDED = ("timestamp_utc", "bid", "ask")


def validate_ticks(ticks: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    missing = [c for c in NEEDED if c not in ticks.columns]
    if missing:
        raise ValueError(f"Required columns missing: {missing}")
    if ticks.empty:
        raise ValueError("No ticks supplied")
    # Require explicit original timezone: accepting naive local timestamps would silently shift sessions.
    original = ticks["timestamp_utc"].astype(str)
    timezone_marked = original.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", case=False, regex=True)
    if not bool(timezone_marked.all()):
        raise ValueError("Every timestamp must include a timezone offset or Z")
    ts = pd.to_datetime(ticks["timestamp_utc"], utc=True, errors="coerce")
    if ts.isna().any():
        raise ValueError("Invalid timestamp")
    if not ts.is_monotonic_increasing:
        raise ValueError("Tick timestamps must be ordered; do not silently sort")
    cleaned = pd.DataFrame({"timestamp_utc":ts})
    for side in ("bid", "ask"):
        original_values = pd.to_numeric(ticks[side], errors="coerce")
        if not np.isfinite(original_values.to_numpy(dtype=float)).all() or (original_values <= 0).any():
            raise ValueError(f"{side} must be finite and positive")
        cleaned[side] = original_values.astype(float).to_numpy()
    if (cleaned["ask"] < cleaned["bid"]).any():
        raise ValueError("Crossed quotes (ask below bid) are not permitted")
    cleaned["mid"] = (cleaned["bid"] + cleaned["ask"]) / 2
    cleaned["spread"] = cleaned["ask"] - cleaned["bid"]
    duplicated = int(ts.duplicated().sum())  # Do not discard same-timestamp updates.
    gaps = cleaned["timestamp_utc"].diff().dropna().dt.total_seconds()
    metadata = {"row_count":len(cleaned), "first":cleaned["timestamp_utc"].iloc[0].isoformat(),
                "last":cleaned["timestamp_utc"].iloc[-1].isoformat(),
                "same_timestamp_updates":duplicated,
                "max_gap_seconds":float(gaps.max()) if len(gaps) else 0.0,
                "max_spread":float(cleaned["spread"].max()),
                "note":"Source tick timestamps required; no synthetic interpolation or fills."}
    return cleaned, metadata


def to_bars(validated_ticks: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    if timeframe not in ALLOWED_TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    # validated input required to avoid bypassing quote integrity checks.
    for col in ("timestamp_utc", "bid", "ask", "mid", "spread"):
        if col not in validated_ticks.columns:
            raise ValueError(f"Missing validated column {col}")
    period = ALLOWED_TIMEFRAMES[timeframe]
    df = validated_ticks.set_index("timestamp_utc")
    if df.index.tz is None:
        raise ValueError("UTC-aware timestamps are mandatory")
    grouped = df.resample(period, label="left", closed="left", origin="epoch")
    bars = grouped.agg({
        "bid":["first", "max", "min", "last"],
        "ask":["first", "max", "min", "last"],
        "mid":["first", "max", "min", "last"],
        "spread":["mean", "max", "last"],
    })
    bars.columns = [f"{side}_{dict(first='open', max='high', min='low', last='close').get(field, field)}" for side,field in bars.columns]
    bars["tick_count"] = grouped["bid"].count().astype("int64")
    bars = bars.loc[bars["tick_count"] > 0].copy()  # No fabricated weekends or quiet intervals.
    bars.index.name = "bar_start_utc"
    bars["bar_end_utc"] = bars.index + pd.Timedelta(period)
    return bars.reset_index()


def resample_tick_csv(input_path: Path, output_dir: Path, timeframes: list[str]) -> dict:
    df = pd.read_csv(input_path, dtype={"timestamp_utc":"string"})
    clean, audit = validate_ticks(df)
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = {}
    for tf in timeframes:
        bars = to_bars(clean, tf)
        destination = output_dir / f"{input_path.stem}_{tf}_bidask.csv"
        bars.to_csv(destination, index=False)
        reports[tf] = {"observed_bars":len(bars),"first":bars["bar_start_utc"].iloc[0].isoformat(),
                       "last":bars["bar_start_utc"].iloc[-1].isoformat(), "file":destination.name}
    manifest = {"input":str(input_path), "timeframes":reports, "tick_audit":audit,
                "bar_label":"bar_start_utc", "bar_available_only_at":"bar_end_utc",
                "session_rule":"UTC anchored; broker 17:00 NY close not implemented",
                "execution_ready":False,
                "warning":"Dataset quality/coverage/rights/spread realism must be reviewed before actual backtesting."}
    (output_dir / "manifest.json").write_text(json.dumps(manifest,indent=2), encoding="utf-8")
    return manifest
