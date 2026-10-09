"""Auditable, append-only local strategy *diagnostic* experiment registry.

No order execution, no AI training, no claimed alpha. This is intentionally
limited to synthetic daily fixtures and FRED H.10 daily *indicative* fixings.
Do not label diagnostics as broker-executable backtests.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .backtest import diagnostic_backtest
from .strategies import STRATEGIES
from .data import SERIES

KINDS = frozenset({"SYNTHETIC_TEST", "FRED_H10_DAILY_INDICATIVE"})
GENESIS = "0" * 64
SCHEMA = "fxlab.research_diagnostic.v1"


def _json(v: dict) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(v: dict) -> str:
    return hashlib.sha256(_json(v)).hexdigest()


def read_ledger(path: Path) -> list[dict]:
    """Read and check hash-link integrity; corruption fails loudly, not silently."""
    if not path.exists():
        return []
    prev = GENESIS
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"Empty ledger row {line_no}")
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid ledger JSON row {line_no}") from exc
            if not isinstance(row, dict) or row.get("schema") != SCHEMA:
                raise ValueError(f"Unexpected ledger schema row {line_no}")
            signature = row.get("entry_hash")
            unsigned = {k: v for k, v in row.items() if k != "entry_hash"}
            if row.get("prev_entry_hash") != prev or signature != _digest(unsigned):
                raise ValueError(f"Hash-chain integrity failure row {line_no}")
            prev = signature
            rows.append(row)
    return rows


def append_ledger(path: Path, record: dict) -> dict:
    """One writer at a time via fail-fast mkdir lock, then fsync durable append.

    Hash-chaining detects editing of stored rows but is *not tamper-proof* against
    rewriting/re-signing the whole file. Stronger guarantees need signed offsite
    anchors, durable backups and identity management in later versions.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lockdir = path.with_name(path.name + ".lock")
    try:
        lockdir.mkdir()
    except FileExistsError as exc:
        raise RuntimeError("Experiment ledger is busy or a stale lock needs review") from exc
    try:
        prior = read_ledger(path)
        if any(x["experiment_id"] == record["experiment_id"] for x in prior):
            raise ValueError("Experiment already recorded; do not duplicate")
        payload = {"schema": SCHEMA, **record,
                   "prev_entry_hash": prior[-1]["entry_hash"] if prior else GENESIS}
        payload["entry_hash"] = _digest(payload)
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(_json(payload).decode("utf-8") + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return payload
    finally:
        lockdir.rmdir()


def run_diagnostic_experiment(*, data_path: Path, ledger_path: Path,
                              pair: str, strategy: str, source_kind: str,
                              cost_bps: float = 2.0,
                              acknowledge_nontradable: bool = False) -> dict:
    """Run a fixed-parameter reference diagnostic with explicit source lineage.

    Caller must expressly acknowledge that indicative data is not tradable FX.
    Both in-sample and last-20% results are diagnostics only, *not* an untouched
    holdout if the researcher later uses them to select/tune strategies.
    """
    if not acknowledge_nontradable:
        raise ValueError("Must acknowledge diagnostic is not a tradable backtest")
    if source_kind not in KINDS or pair not in SERIES or strategy not in STRATEGIES:
        raise ValueError("Unsupported data kind, pair or strategy")
    if not np.isfinite(cost_bps) or cost_bps < 0:
        raise ValueError("cost_bps must be finite and >= 0")
    content = data_path.read_bytes()
    frame = pd.read_csv(data_path)
    if "date" not in frame or pair not in frame:
        raise ValueError("CSV must contain date and requested pair column")
    dates = pd.to_datetime(frame["date"], errors="raise")
    if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError("Dates must be valid, unique and increasing")
    original = pd.to_numeric(frame[pair], errors="coerce")
    # Missing FRED fixing (e.g. US federal holiday) is legitimate. Malformed
    # nonblank observations, infinities and synthetic missing values are not.
    malformed = frame[pair].notna() & original.isna()
    if malformed.any() or np.isinf(original.to_numpy(dtype=float)).any():
        raise ValueError("Invalid, nonfinite or malformed reference observations")
    if source_kind == "SYNTHETIC_TEST" and original.isna().any():
        raise ValueError("Synthetic research fixtures must not contain missing observations")
    series = pd.Series(original.to_numpy(dtype=float), index=dates, name=pair).dropna()
    if series.empty or (series <= 0).any():
        raise ValueError("Missing valid, positive observations")
    diagnostics = diagnostic_backtest(series, strategy, cost_bps)
    data_sha = hashlib.sha256(content).hexdigest()
    recipe = {"schema": SCHEMA, "data_sha256": data_sha, "source_kind": source_kind,
              "pair": pair, "strategy": strategy, "cost_bps": cost_bps,
              "fixed_parameters": "built-in defaults; not tuned on this dataset"}
    return append_ledger(ledger_path, {"experiment_id": _digest(recipe),
        "recipe": recipe, "observations": len(series),
        "missing_reference_observations": int(original.isna().sum()),
        "first_date": str(series.index[0].date()),
        "last_date": str(series.index[-1].date()),
        "diagnostic": diagnostics,
        "evaluation_label": "EXPLORATORY_DIAGNOSTIC_ONLY",
        "source_is_executable_market_data": False, "out_of_sample_verified": False,
        "live_strategy_validated": False, "execution_allowed": False})


def public_experiments(path: Path) -> dict:
    """Strictly read-only presentation and an explicit global research status."""
    rows = read_ledger(path)
    return {"mode": "RESEARCH_ONLY", "is_live": False,
            "validated_strategies": 0, "broker_connected": False,
            "execution_allowed": False, "records": list(reversed(rows[-40:])),
            "total_records": len(rows), "source_warning":
            "Synthetic and FRED indicative daily diagnostics only; never executable quotes or validated performance."}
