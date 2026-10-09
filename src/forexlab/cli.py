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
    p = sub.add_parser("resample-ticks", help="Validate real bid/ask tick CSV and produce observed UTC bars; never trade")
    p.add_argument("file", help="CSV columns timestamp_utc,bid,ask with timezone-aware timestamps")
    p.add_argument("--out", default="data/processed/tick-bars")
    p.add_argument("--timeframes", nargs="+", default=["M15", "M30", "H1", "H4", "D1"])
    args = parser.parse_args(argv)
    if args.cmd == "fetch-fred":
        result = fetch_fred_daily(Path(args.out), args.start, args.end)
    elif args.cmd == "resample-ticks":
        from .tickdata import resample_tick_csv
        result = resample_tick_csv(Path(args.file), Path(args.out), args.timeframes)
    elif args.cmd == "audit":
        result = audit_indicative_csv(Path(args.file))
    else:
        df = pd.read_csv(args.file, parse_dates=["date"]).set_index("date")
        result = diagnostic_backtest(df[args.pair], args.strategy, args.cost_bps)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
