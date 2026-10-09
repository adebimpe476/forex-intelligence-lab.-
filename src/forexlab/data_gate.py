"""Fail-closed technical and rights-declaration gate for *research* datasets.

This only validates declared rights and technical integrity. It is NOT a legal
permission check, external source verification, or approval to execute trades.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .tickdata import validate_ticks

_PURPOSES = {"quant_research", "ai_training"}
_CLASSES = {"BID_ASK_TICK", "MID_OHLC"}


def _reject(reason: str, *, details: dict | None = None) -> dict:
    return {"technical_ready": False, "research_ready": False,
            "source_verified": False, "legal_clearance_verified": False,
            "lean_engine_verified": False, "execution_allowed": False,
            "reason": reason, "details": details or {}}


def _tz_marked(series: pd.Series) -> bool:
    return bool(series.astype(str).str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", case=False, regex=True).all())


def _inspect_candles(frame: pd.DataFrame) -> dict:
    required = {"datetime", "open", "high", "low", "close"}
    if not required.issubset(frame.columns) or frame.empty:
        raise ValueError("OHLC requires nonempty datetime,open,high,low,close")
    if not _tz_marked(frame.datetime):
        raise ValueError("OHLC timestamps require explicit timezone")
    ts = pd.to_datetime(frame.datetime, utc=True, errors="raise")
    if ts.isna().any() or ts.duplicated().any() or not ts.is_monotonic_increasing:
        raise ValueError("OHLC timestamps must be unique, ordered and valid")
    value = frame[list(required - {"datetime"})].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(value.to_numpy(dtype=float)).all() or (value <= 0).any().any():
        raise ValueError("OHLC prices must be positive and finite")
    if ((value.high < value.low) | (value.high < value[["open", "close"]].max(axis=1)) |
        (value.low > value[["open", "close"]].min(axis=1))).any():
        raise ValueError("Invalid OHLC high/low constraints")
    steps = ts.diff().dropna().dt.total_seconds()
    return {"rows":len(frame), "first":ts.iloc[0].isoformat(),
            "last":ts.iloc[-1].isoformat(),
            "max_gap_seconds":float(steps.max()) if len(steps) else 0,
            "has_executable_bid_ask":False,
            "note":"Single-price OHLC; cannot simulate observed bid/ask fills"}


def qualify_dataset(path: Path, manifest_path: Path, *, purpose: str = "quant_research") -> dict:
    """Audit a *local* market CSV against a separate data provenance declaration.

    A successful result is only a technical preflight and source-owner's rights
    declaration. It is NOT independently authenticated source data, commercial
    licensing clearance, a passing execution-quality LEAN run or live trading.
    """
    if purpose not in _PURPOSES:
        return _reject("UNSUPPORTED_PURPOSE")
    try:
        raw = path.read_bytes()
        if not raw or len(raw) > 300_000_000:
            return _reject("EMPTY_OR_OVERSIZED_FILE")
        meta = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            return _reject("INVALID_MANIFEST")
        digest = hashlib.sha256(raw).hexdigest()
        if meta.get("sha256") != digest:
            return _reject("SHA256_MISMATCH", details={"observed_sha256":digest})
        kind = meta.get("kind")
        if kind not in _CLASSES or not meta.get("pair") or not meta.get("provider"):
            return _reject("MISSING_MARKET_PROVENANCE")
        if not isinstance(meta.get("source_url"), str) or not meta["source_url"].startswith(("http://", "https://")):
            return _reject("MISSING_SOURCE_URL")
        frame = pd.read_csv(path, dtype={"timestamp_utc":"string"} if kind == "BID_ASK_TICK" else {"datetime":"string"})
        if kind == "BID_ASK_TICK":
            _, stats = validate_ticks(frame)
            technical = {"rows":stats["row_count"], "first":stats["first"],
                         "last":stats["last"], "max_gap_seconds":stats["max_gap_seconds"],
                         "same_timestamp_updates":stats["same_timestamp_updates"],
                         "max_spread":stats["max_spread"], "has_executable_bid_ask":True}
        else:
            technical = _inspect_candles(frame)
        # FRED explicitly restricts FRED Content for use developing/training AI,
        # as of the documented 2026 terms; a metadata checkbox cannot override it.
        if purpose == "ai_training" and ("fred" in str(meta.get("provider", "")).lower()
                                        or "fred.stlouisfed.org" in str(meta.get("source_url", "")).lower()):
            return _reject("FRED_CONTENT_NOT_PERMITTED_FOR_AI_TRAINING", details=technical)
        rights = meta.get("rights", {})
        allowed = (isinstance(rights, dict)
                   and rights.get(purpose) is True
                   and isinstance(rights.get("evidence_url"), str)
                   and rights["evidence_url"].startswith("https://"))
        if not allowed:
            return _reject("RIGHTS_NOT_DECLARED_FOR_PURPOSE", details=technical)
        return {"technical_ready": True, "research_ready":True,
                "declared_permission_only":True,
                "source_verified":False, "legal_clearance_verified":False,
                "lean_engine_verified":False,"execution_allowed":False,
                "dataset_sha256":digest,"kind":kind,"pair":meta["pair"],
                "provider":meta["provider"],"purpose":purpose,
                "reason":"TECHNICAL_PREFLIGHT_PASSED_MANUAL_SOURCE_REVIEW_REQUIRED",
                "details":technical,
                "warning":"Rights are SELF-DECLARED; source, license and broker comparability require independent review."}
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeError) as exc:
        return _reject("DATASET_OR_MANIFEST_INVALID", details={"error":str(exc)[:200]})
