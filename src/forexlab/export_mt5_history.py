"""Export owned MT5 BROKER M5 BID bars for retrospective *research*, no trades.

Uses local Windows MetaTrader5 Python module and terminal. Writes raw historical
OHLC/spread plus an explicit self-declared rights checklist OUTSIDE the repo.
MT5 spread is bar proxy, not a historical bid/ask tick fill. Only USD accounts
currently supported for estimating USD point value.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path


def _midnight(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _outside_git(path: Path) -> None:
    destination = path.resolve()
    if any((ancestor / ".git").exists() for ancestor in (destination, *destination.parents)):
        raise ValueError("Save licensed market data OUTSIDE your Git checkout")
    if path.exists() and any(path.iterdir()):
        raise FileExistsError("Output folder must be new or empty")


def export(symbols: list[str], start: str, end_exclusive: str,
           output: Path, warmup_days: int = 7) -> list[Path]:
    begin, end = _midnight(start), _midnight(end_exclusive)
    if not begin < end or not 1 <= warmup_days <= 30:
        raise ValueError("Invalid UTC research dates or warmup days")
    _outside_git(output)
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise RuntimeError("Windows MT5 Python package required: pip install MetaTrader5") from exc
    if not mt5.initialize():
        raise RuntimeError(f"Could not initialize desktop MT5: {mt5.last_error()}")
    files: list[Path] = []
    try:
        account = mt5.account_info()
        if account is None or account.currency != "USD":
            raise ValueError("Current replay requires USD account base currency to size USD risk")
        output.mkdir(parents=True, exist_ok=True)
        for symbol in symbols:
            if not mt5.symbol_select(symbol, True):
                raise ValueError(f"Broker symbol unavailable: {symbol!r}")
            info = mt5.symbol_info(symbol)
            tick = mt5.symbol_info_tick(symbol)
            if info is None or tick is None or info.point <= 0:
                raise ValueError(f"Missing broker contract metadata: {symbol}")
            # Actual order_calc_profit references broker's current conversion, not history.
            usd_per_unit = mt5.order_calc_profit(
                mt5.ORDER_TYPE_BUY, symbol, 1.0, tick.ask, tick.ask + 1.0
            )
            if usd_per_unit is None or usd_per_unit <= 0:
                raise ValueError(f"Cannot determine USD value of one price unit for {symbol}")
            rows = mt5.copy_rates_range(
                symbol, mt5.TIMEFRAME_M5, begin - timedelta(days=warmup_days),
                end - timedelta(seconds=1)
            )
            if rows is None or len(rows) < 200:
                raise ValueError(f"Insufficient MT5 M5 history for {symbol}: {mt5.last_error()}")
            if symbol != Path(symbol).name or "/" in symbol or "\\" in symbol:
                raise ValueError("Unsafe symbol filename")
            csv_path = output / f"{symbol}_M5_BID.csv"
            manifest_path = output / f"{symbol}_M5_BID.provenance.json"
            if csv_path.exists() or manifest_path.exists():
                raise FileExistsError(f"Refuse overwrite: {symbol}")
            with csv_path.open("w", encoding="utf-8", newline="") as file:
                w = csv.writer(file)
                w.writerow(["datetime_utc", "open", "high", "low", "close", "spread_points"])
                for row in rows:
                    ts = datetime.fromtimestamp(int(row["time"]), timezone.utc)
                    # Preserve the broker's actual history, including 0 spreads if present,
                    # so replay can fail rather than quietly invent a cost.
                    w.writerow([ts.isoformat(), float(row["open"]), float(row["high"]),
                                float(row["low"]), float(row["close"]), int(row["spread"])])
            checksum = hashlib.sha256(csv_path.read_bytes()).hexdigest()
            meta = {
                "provider": "OWN_MT5_BROKER_EXPORT",
                "broker_symbol": symbol,
                "broker_server": account.server,
                "timeframe": "M5", "price_side": "BID",
                "account_currency": "USD", "point": float(info.point),
                "usd_per_price_unit_per_lot": float(usd_per_unit),
                "contract_value_derived_at_export_time_not_historical": True,
                "historical_spread_is_proxy": True,
                "research_permission_declared": False,
                "permissions_note": "Review your broker's local research/redistribution terms; only then manually set research_permission_declared true.",
                "sha256": checksum,
                "start_utc": start, "end_utc_exclusive": end_exclusive,
                "warmup_days": warmup_days, "bars": int(len(rows)),
            }
            manifest_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            files.extend([csv_path, manifest_path])
        return files
    finally:
        mt5.shutdown()


def main() -> None:
    p = argparse.ArgumentParser(description="Research-only M5 broker export (no orders)")
    p.add_argument("--symbol", action="append", required=True,
                   help="Exact broker Gold/NASDAQ symbol; use multiple --symbol flags")
    p.add_argument("--start", default="2026-09-28")
    p.add_argument("--end-exclusive", default="2026-10-10")
    p.add_argument("--warmup-days", type=int, default=7)
    p.add_argument("--output", type=Path, required=True,
                   help="Local private output, outside any Git checkout")
    args = p.parse_args()
    for path in export(args.symbol, args.start, args.end_exclusive,
                       args.output, args.warmup_days):
        print("WROTE PRIVATE RESEARCH FILE", path)


if __name__ == "__main__":
    main()
