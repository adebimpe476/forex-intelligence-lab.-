"""Command line: fetch, quality audit, and conservative diagnostic baseline."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd
from .data import fetch_fred_daily, audit_indicative_csv, SERIES
from .backtest import diagnostic_backtest
from .strategies import STRATEGIES


def main(argv=None):
    parser = argparse.ArgumentParser(prog="forexlab", description="Research-only forex intelligence lab")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fetch-fred", help="Download authentic daily indicative rates, NOT OHLC")
    p.add_argument("--out", default="data/raw/fred-full")
    p.add_argument("--start", default="1999-01-01")
    p.add_argument("--end", default="2026-10-09")
    p = sub.add_parser("audit")
    p.add_argument("file", help="CSV with date,EURUSD,USDJPY,GBPUSD")
    p = sub.add_parser("diagnose")
    p.add_argument("file", help="CSV with date,EURUSD,USDJPY,GBPUSD")
    p.add_argument("--pair", choices=list(SERIES), default="EURUSD")
    p.add_argument("--strategy", choices=list(STRATEGIES), default="trend_following")
    p.add_argument("--cost-bps", type=float, default=2.)
    p = sub.add_parser("import-daily-bi5", help="Decode licensed local daily BI5 file; no downloading or orders")
    p.add_argument("file", help="Local current-layout DD_ticks.bi5")
    p.add_argument("--pair", choices=list(SERIES), required=True)
    p.add_argument("--day-utc", required=True, help="Exact UTC midnight, e.g. 2024-01-02T00:00:00Z")
    p.add_argument("--rights-note", required=True, help="Describe provider permission and allowed local use")
    p.add_argument("--out", default="data/processed/dukascopy-daily")
    p = sub.add_parser("resample-ticks", help="Validate real bid/ask tick CSV and produce observed UTC bars; never trade")
    p.add_argument("file", help="CSV columns timestamp_utc,bid,ask with timezone-aware timestamps")
    p.add_argument("--out", default="data/processed/tick-bars")
    p.add_argument("--timeframes", nargs="+", default=["M15", "M30", "H1", "H4", "D1"])
    p = sub.add_parser("import-bi5", help="Decode one locally acquired and rights-reviewed Dukascopy hourly BI5 file")
    p.add_argument("file", help="Local .bi5 file; tool does not download data")
    p.add_argument("--pair", choices=["EURUSD", "GBPUSD", "USDJPY"], required=True)
    p.add_argument("--hour-utc", required=True, help="ISO UTC start time, e.g. 2024-01-03T12:00:00Z")
    p.add_argument("--rights-note", required=True, help="Document permission/terms review; NOT verification of legal rights")
    p.add_argument("--out", default="data/processed/private-quotes")
    p = sub.add_parser("export-lean-ticks", help="Export licensed CSV bid/ask quotes to LEAN forex tick ZIP format")
    p.add_argument("file", help="Normalized CSV with timestamp_utc,bid,ask")
    p.add_argument("--pair", choices=["EURUSD", "GBPUSD", "USDJPY"], required=True)
    p.add_argument("--market", required=True, help="True source venue ID; do not mislabel as OANDA or FXCM")
    p.add_argument("--out", default="data/processed/lean-staging")
    p = sub.add_parser("research-size", help="Research-only USD FX position sizing; NEVER sends orders")
    p.add_argument("--signal-id", required=True)
    p.add_argument("--pair", choices=["EURUSD", "GBPUSD", "USDJPY"], required=True)
    p.add_argument("--side", choices=["BUY", "SELL"], required=True)
    p.add_argument("--entry", required=True, help="Hypothetical executable ask for BUY / bid for SELL")
    p.add_argument("--stop", required=True, help="Hypothetical executable closing-side stop")
    p.add_argument("--equity-usd", required=True)
    p.add_argument("--day-start-equity-usd", required=True)
    p.add_argument("--daily-realized-pnl-usd", default="0")
    p.add_argument("--daily-unrealized-pnl-usd", default="0")
    p.add_argument("--open-risk-usd", default="0")
    p.add_argument("--open-position", action="append", default=[], help="Repeat existing PAIR:SIDE")
    p.add_argument("--seen-id", action="append", default=[])
    p = sub.add_parser("session-bars", help="Create NY-17 rollover D1/H4 research candles from local tick CSV")
    p.add_argument("file", help="CSV with timezone-aware timestamp_utc,bid,ask")
    p.add_argument("--timeframe", choices=["D1", "H4"], default="D1")
    p.add_argument("--out", default="data/processed/ny-session")
    p = sub.add_parser('experiment-run', help='Append a hashed RESEARCH diagnostic from synthetic/FRED daily CSV; NOT LEAN')
    p.add_argument('file', help='CSV with date and pair columns; not live market candles')
    p.add_argument('--pair', choices=list(SERIES), required=True)
    p.add_argument('--strategy', choices=list(STRATEGIES), required=True)
    p.add_argument('--source-kind', choices=['SYNTHETIC_TEST', 'FRED_H10_DAILY_INDICATIVE'], required=True)
    p.add_argument('--cost-bps', type=float, default=2.0)
    p.add_argument('--ledger', default='artifacts/experiments/ledger.jsonl')
    p.add_argument('--acknowledge-nontradable', action='store_true', required=True,
                   help='Confirm this is an illustrative diagnostic, not a real broker backtest')
    p = sub.add_parser('experiment-audit', help='Verify hash-chain integrity of local research diagnostic ledger')
    p.add_argument('--ledger', default='artifacts/experiments/ledger.jsonl')
    args = parser.parse_args(argv)
    if args.cmd == "fetch-fred":
        result = fetch_fred_daily(Path(args.out), args.start, args.end)
    elif args.cmd == "import-daily-bi5":
        from .dukascopy_daily import import_daily_bi5_file
        result = import_daily_bi5_file(Path(args.file), Path(args.out),
                                       pair=args.pair, day_utc=args.day_utc, license_note=args.rights_note)
    elif args.cmd == "resample-ticks":
        from .tickdata import resample_tick_csv
        result = resample_tick_csv(Path(args.file), Path(args.out), args.timeframes)
    elif args.cmd == "import-bi5":
        from .dukascopy import import_bi5_file
        result = import_bi5_file(Path(args.file), Path(args.out), pair=args.pair,
                                 hour_utc=args.hour_utc, license_note=args.rights_note)
    elif args.cmd == "export-lean-ticks":
        from .lean_format import to_lean_forex_tick_zips
        df = pd.read_csv(args.file, dtype={"timestamp_utc": "string"})
        result = to_lean_forex_tick_zips(df, pair=args.pair,
                                          market=args.market, out_dir=Path(args.out))
    elif args.cmd == "research-size":
        from .risk import assess_risk
        positions = []
        for item in args.open_position:
            parts = item.split(":")
            if len(parts) != 2:
                parser.error("--open-position must be PAIR:SIDE")
            positions.append((parts[0], parts[1]))
        result = assess_risk(signal_id=args.signal_id, pair=args.pair, side=args.side,
                             entry=args.entry, stop=args.stop, equity_usd=args.equity_usd,
                             day_start_equity_usd=args.day_start_equity_usd,
                             day_realized_pnl_usd=args.daily_realized_pnl_usd,
                             day_unrealized_pnl_usd=args.daily_unrealized_pnl_usd,
                             open_risk_usd=args.open_risk_usd,
                             open_positions=positions, seen_signal_ids=args.seen_id)
    elif args.cmd == "session-bars":
        from .tickdata import validate_ticks
        from .fx_sessions import session_bars
        raw = pd.read_csv(args.file, dtype={"timestamp_utc": "string"})
        clean, quality = validate_ticks(raw)
        bars = session_bars(clean, args.timeframe)
        directory = Path(args.out)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{Path(args.file).stem}_{args.timeframe}_ny17_research.csv"
        bars.to_csv(destination, index=False)
        result = {"file": str(destination), "timeframe": args.timeframe,
                  "observed_bars": len(bars), "quality": quality,
                  "session_convention": "NY 17:00; verify vs broker; variable H4 UTC duration at DST",
                  "research_only": True, "execution_allowed": False}
    elif args.cmd == 'experiment-run':
        from .research_lab import run_diagnostic_experiment
        result = run_diagnostic_experiment(
            data_path=Path(args.file), ledger_path=Path(args.ledger),
            pair=args.pair, strategy=args.strategy, source_kind=args.source_kind,
            cost_bps=args.cost_bps, acknowledge_nontradable=args.acknowledge_nontradable)
    elif args.cmd == 'experiment-audit':
        from .research_lab import public_experiments
        result = public_experiments(Path(args.ledger))
    elif args.cmd == "audit":
        result = audit_indicative_csv(Path(args.file))
    else:
        df = pd.read_csv(args.file, parse_dates=["date"]).set_index("date")
        result = diagnostic_backtest(df[args.pair], args.strategy, args.cost_bps)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
