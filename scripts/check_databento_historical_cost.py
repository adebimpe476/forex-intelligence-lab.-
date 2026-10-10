"""Read-only historical CME NQ/GC order-flow cost and availability preflight.

Zero-order / zero-download mode. Queries *metadata only*. No payable request,
no trade data, and no automatic card charge/purchase is initiated by this script.
Set DATABENTO_API_KEY privately in the environment; never commit it to GitHub.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os

DATASET = "GLBX.MDP3"
SYMBOLS = ("NQ.v.0", "GC.v.0")
SCHEMAS = ("trades", "mbp-10", "mbo")
START = "2026-09-28T00:00:00Z"
END = "2026-10-10T00:00:00Z"


def _utc(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset() != timezone.utc.utcoffset(timestamp):
        raise ValueError("Date must have explicit UTC timezone")
    return timestamp


def estimate_costs(client, *, start: str = START, end: str = END,
                   symbols: tuple[str, ...] = SYMBOLS,
                   schemas: tuple[str, ...] = SCHEMAS,
                   remaining_credit_usd: float | None = None) -> dict:
    """Only calls metadata.get_cost/get_dataset_range. NEVER timeseries.get_range."""
    begin, finish = _utc(start), _utc(end)
    if finish <= begin or not symbols or not schemas:
        raise ValueError("Invalid date window or symbols")
    if remaining_credit_usd is not None and (
            not math.isfinite(remaining_credit_usd) or remaining_credit_usd < 0):
        raise ValueError("Remaining credit must be nonnegative and finite")
    available = client.metadata.get_dataset_range(dataset=DATASET)
    results = []
    total = 0.0
    for symbol in symbols:
        if not isinstance(symbol, str) or not symbol.strip() or not symbol.endswith(".v.0"):
            raise ValueError("Only explicitly volume-ranked continuous futures symbols supported")
        for schema in schemas:
            if schema not in SCHEMAS:
                raise ValueError("Unsupported order-flow schema")
            cost = float(client.metadata.get_cost(
                dataset=DATASET,
                start=start,
                end=end,
                symbols=symbol,
                schema=schema,
                stype_in="continuous",
            ))
            if not math.isfinite(cost) or cost < 0:
                raise ValueError("Market data provider returned an invalid estimate")
            results.append({"symbol": symbol, "schema": schema,
                            "estimated_usd": round(cost, 5)})
            total += cost
    return {
        "dataset": DATASET,
        "start_utc": start,
        "end_exclusive_utc": end,
        "source_dataset_range": available,
        "quotes": results,
        "sum_if_all_schemas_requested_usd": round(total, 5),
        "remaining_free_credit_usd_user_supplied": remaining_credit_usd,
        "all_estimates_within_reported_credit": (
            total <= remaining_credit_usd if remaining_credit_usd is not None else None
        ),
        "has_downloaded_market_data": False,
        "has_made_purchase": False,
        "warning": "METADATA QUOTE ONLY: costs and account entitlements must be reviewed. No paid data is fetched; no claim that new-user credits are available or sufficient.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check cost of 2w CME NQ/GC footprint/depth data without purchase"
    )
    parser.add_argument("--start", default=START)
    parser.add_argument("--end-exclusive", default=END)
    parser.add_argument("--remaining-free-credit-usd", type=float,
                        help="Enter the CURRENT credit balance shown in Databento portal")
    args = parser.parse_args()
    key = os.getenv("DATABENTO_API_KEY")
    if not key:
        parser.error("Set DATABENTO_API_KEY in private local environment; do not paste keys into chat")
    try:
        import databento as db
    except ImportError as exc:
        raise SystemExit("Install databento locally: pip install databento") from exc
    client = db.Historical(key)
    result = estimate_costs(client, start=args.start, end=args.end_exclusive,
                            remaining_credit_usd=args.remaining_free_credit_usd)
    print(json.dumps(result, indent=2, default=str))
    print("NO FILES DOWNLOADED; NO PURCHASE AUTHORIZED.")


if __name__ == "__main__":
    main()
