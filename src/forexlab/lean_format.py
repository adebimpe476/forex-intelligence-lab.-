"""Export normalized, validated quote ticks to LEAN forex quote tick ZIP structure.

This is a STORAGE FORMAT conversion only, NOT a LEAN engine integration or a
simulation. A non-standard provider market, such as 'dukascopy', additionally
needs explicit market-hours, symbol-properties and data settings in LEAN. Never
mislabel provider quotes as OANDA/FXCM to make them appear broker-native.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import re
import zipfile
import pandas as pd
import numpy as np
from .tickdata import validate_ticks

SCALE = {"EURUSD": 5, "GBPUSD": 5, "USDJPY": 3}
VALID_MARKET = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


def to_lean_forex_tick_zips(df: pd.DataFrame, *, pair: str, market: str, out_dir: Path) -> dict:
    """Write LEAN-native bid/ask quote tick ZIP files (UTC market timestamps).

    No fills, spreads estimates, broker connection or order execution. All
    input rows are validated, but integrity cannot establish feed accuracy.
    """
    if pair not in SCALE:
        raise ValueError("Unsupported symbol, price scale review required")
    if not VALID_MARKET.fullmatch(market):
        raise ValueError("Market must be a named and documented lowercase provider ID")
    if market in ("oanda", "fxcm"):
        raise ValueError("Do not relabel external quotes as OANDA or FXCM")
    if not isinstance(df, pd.DataFrame) or not {"timestamp_utc", "bid", "ask"}.issubset(df.columns):
        raise ValueError("Required normalized tick fields missing")
    # Avoid silently shifting local computer timestamps to UTC.
    time_text = df["timestamp_utc"].astype(str)
    if not time_text.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True, case=False).all():
        raise ValueError("All source tick timestamps must be timezone-aware")
    tdf = df[["timestamp_utc", "bid", "ask"]].copy()
    tdf["timestamp_utc"] = pd.to_datetime(tdf["timestamp_utc"], utc=True)
    ts = tdf.timestamp_utc.dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    validated, audit = validate_ticks(tdf.assign(timestamp_utc=ts))
    out_dir = Path(out_dir)
    created=[]
    for day, ticks in validated.groupby(validated.timestamp_utc.dt.strftime("%Y%m%d"), sort=True):
        relative = Path("forex") / market / "tick" / pair.lower() / f"{day}_quote.zip"
        dest = out_dir / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        csvname = f"{day}_{pair.lower()}_tick_quote.csv"
        ms = (ticks.timestamp_utc - ticks.timestamp_utc.dt.normalize()).dt.total_seconds().mul(1000).round().astype("int64")
        precision = SCALE[pair]
        rows = [f"{t},{bid:.{precision}f},{ask:.{precision}f}\n"
                for t,bid,ask in zip(ms,ticks.bid,ticks.ask)]
        # Deterministic zip timestamps for reproducible dataset hashes.
        info=zipfile.ZipInfo(csvname, date_time=(1980,1,1,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr(info,"".join(rows).encode("utf-8"))
        created.append({"date":day,"file":str(relative),"rows":len(rows),"first_ms":int(ms.iloc[0]),"last_ms":int(ms.iloc[-1])})
    manifest={"format":"LEAN forex quote tick ZIP", "provider_market":market, "symbol":pair,
              "timezone":"UTC", "data":created, "raw_input_audit":audit,
              "verified_with_lean":False, "execution_ready":False,
              "requirements_before_lean_backtest":["Register the provider market in LEAN market-hours and symbol-properties databases", "Verify calendar/session cutoffs and quote-price precision", "Pin LEAN version and test actual data loading; then test realistic fills and fee/financing model"],
              "warning":"File format exported only. Not proof of a successfully loaded LEAN dataset or tradable PnL."}
    (out_dir / f"{pair}_{market}_lean_export_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest
