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
    p = sub.add_parser("import-daily-bi5", help="Decode a rights-cleared local daily BI5 file; no network or orders")
    p.add_argument("file", help="Local DD_ticks.bi5 path")
    p.add_argument("--pair", choices=list(SERIES), required=True)
    p.add_argument("--day-utc", required=True, help="Exact UTC midnight e.g. 2024-01-02T00:00:00Z")
    p.add_argument("--rights-note", required=True, help="Provider rights review and permitted research use")
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
    elif args.cmd == "audit":
        result = audit_indicative_csv(Path(args.file))
    else:
        df = pd.read_csv(args.file, parse_dates=["date"]).set_index("date")
        result = diagnostic_backtest(df[args.pair], args.strategy, args.cost_bps)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
