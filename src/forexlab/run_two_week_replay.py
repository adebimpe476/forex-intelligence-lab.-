"""Two-week source-stamped no-lookahead research CLI. NEVER SUBMITS ORDERS."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from forexlab.orderflow import aggregate_footprints, load_exchange_trade_csv
from forexlab.two_week_replay import (ReplayConfig, load_bars, simulate, verify_manifest)


def _utc(value: str) -> int:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset().total_seconds() != 0:
        raise ValueError("Require UTC timestamps")
    return int(dt.timestamp())


def _load_authorized_footprints(trades: Path, manifest_path: Path, start: int, end: int):
    meta = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {"sha256", "exchange", "contract_month", "tick_size", "source_url",
                "aggressor_side_verified", "research_permission_declared", "rights_evidence_url"}
    if (not isinstance(meta, dict) or not expected.issubset(meta)
            or meta["sha256"] != sha256(trades.read_bytes()).hexdigest()
            or meta["aggressor_side_verified"] is not True
            or meta["research_permission_declared"] is not True
            or not all(meta[k] for k in ("exchange", "contract_month", "source_url", "rights_evidence_url"))):
        raise ValueError("Authentic exchange trade tape rights/side/timestamp provenance not declared")
    prints = load_exchange_trade_csv(
        trades, source_verified=True, rights_approved=True
    )
    bars = aggregate_footprints(
        prints, tick_size=str(meta["tick_size"]), minutes=5,
        # All data can be aggregated for research, but strategy only receives
        # each already-closed footprint timestamp <= its signal decision time.
        as_of_ms=end * 1000
    )
    return {bar.start_ms: bar for bar in bars}, {
        "exchange": meta["exchange"], "contract_month": meta["contract_month"],
        "trade_tape_sha256": meta["sha256"], "source_declaration_only": True,
        "loaded_m5_footprints": len(bars),
        "warning": "Current UTC match uses futures delta only. Futures/CFD basis, contract rolls and rights are NOT independently verified."
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Historical closed-bar M5 backtest; no trading")
    p.add_argument("--bars", type=Path, required=True, help="Private exported broker OHLC+bar spread CSV")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--start", default="2026-09-28T00:00:00Z")
    p.add_argument("--end-exclusive", default="2026-10-10T00:00:00Z")
    p.add_argument("--equity-usd", type=float, default=10000)
    p.add_argument("--risk-fraction", type=float, default=0.0025)
    p.add_argument("--slippage-price", type=float, required=True,
                   help="Adverse *price units* each side, must choose before viewing results")
    p.add_argument("--commission-usd-per-lot", type=float, required=True,
                   help="Roundtrip per 1.0 broker lot, must choose before viewing results")
    p.add_argument("--out", type=Path, required=True, help="New report directory outside Git")
    p.add_argument("--futures-trades", type=Path, help="Optional licensed genuine trades; compare flow-gated against baseline")
    p.add_argument("--futures-trades-manifest", type=Path)
    args = p.parse_args()

    if args.out.exists() and any(args.out.iterdir()):
        raise FileExistsError("Report directory already populated; do not overwrite test results")
    if any((ancestor / ".git").exists() for ancestor in
           (args.out.resolve(), *args.out.resolve().parents)):
        raise ValueError("Keep data, reports and market tape outside Git")
    data, digest = load_bars(args.bars)
    meta = json.loads(args.manifest.read_text(encoding="utf-8"))
    config = ReplayConfig(start_utc=_utc(args.start), end_utc=_utc(args.end_exclusive),
                          symbol=meta["broker_symbol"], point=float(meta["point"]),
                          usd_per_price_unit_per_lot=float(meta["usd_per_price_unit_per_lot"]),
                          equity_usd=args.equity_usd, risk_fraction=args.risk_fraction,
                          slippage_price_per_side=args.slippage_price,
                          commission_usd_per_lot_roundtrip=args.commission_usd_per_lot)
    verify_manifest(args.manifest, digest, config)
    base = simulate(data, config)
    if not base["window_has_at_least_eight_utc_dates"]:
        raise ValueError("INSUFFICIENT_TWO_WEEK_COVERAGE: need >=8 observed UTC dates")
    results = {"candle_only": base}
    source = {"broker_file_sha256": digest,
              "broker_manifest_sha256": sha256(args.manifest.read_bytes()).hexdigest(),
              "contract_derived_currently_not_historical": True,
              "research_data_rights_self_declared": True}
    if bool(args.futures_trades) != bool(args.futures_trades_manifest):
        raise ValueError("Both --futures-trades and its manifest are required")
    if args.futures_trades:
        oflow, prov = _load_authorized_footprints(
            args.futures_trades, args.futures_trades_manifest,
            config.start_utc, config.end_utc
        )
        results["footprint_delta_gate"] = simulate(
            data, ReplayConfig(**{**asdict(config), "require_orderflow": True}),
            orderflow_by_start_ms=oflow)
        source["futures_orderflow"] = prov

    report = {
        "research_type": "TWO_WEEK_M5_PAST_ONLY_REPLAY",
        "source": source,
        "models": results,
        "independent_out_of_sample": False,
        "repeated_test_window_tuning_permitted": False,
        "orderbook_heatmap_tested": False,
        "no_live_orders": True,
        "warnings": [
            "Do not optimize thresholds on these two weeks: use an earlier development window and reserve a NEW unseen interval.",
            "OHLC cannot resolve intrabar order; STOP FIRST if TP and SL hit within same 5m bar.",
            "Bar spread is indicative; execution delay, intrabar bid/ask, swap, and live fill costs are not fully known.",
            "Futures footprint cannot be equated to broker CFD trade prices. L2 heatmap NOT backtested.",
            "Two weeks of history are inadequate to infer stable strategy profitability.",
        ]
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "two_week_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    for label, model in results.items():
        filename = args.out / f"{label}_trades.csv"
        with filename.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=[
                "signal_bar_open_utc", "signal_time_utc", "entry_time_utc", "exit_time_utc",
                "exit_time_precision", "symbol", "side",
                "broken_level", "entry", "original_sl", "tp", "lot",
                "planned_risk_usd_with_15pct_cushion", "exit", "reason",
                "net_usd", "equity_after_usd", "breakeven_attempted"])
            writer.writeheader()
            writer.writerows(model["trades"])
        print(f"{label}: closed={model['trades_closed']} net_realized_USD={model['net_realized_pnl_usd']} "
              f"max_closed_DD_USD={model['max_closed_equity_drawdown_usd']} "
              f"win_rate={model['win_rate_closed']} "
              f"unresolved_MTM={model['unrealized_mark_to_market_usd_estimate']}")
    print("RESEARCH REPORT", args.out / "two_week_report.json")
    print("WARNING: no authentic provider verification, no future-free profitable edge proved, no executed broker trades")


if __name__ == "__main__":
    main()
