# Real quote-data acquisition gate · v0.4

## What was implemented

The new code can decode a **locally supplied**, legally acquired Dukascopy BI5 *hourly* file into UTC bid/ask quotes, preserve its source SHA-256 and quality manifest, then export native LEAN *forex quote tick* ZIP files into a provider-named staging folder. Tests use **synthetic binary fixtures only**; the current development runtime could not contact the Dukascopy datafeed. **No genuine intraday data or successful LEAN engine backtest is claimed.**

## Source research (not a statement of permission)

- Official Dukascopy JForex historical data documentation: https://www.dukascopy.com/wiki/en/development/strategy-api/historical-data/overview-historical-data/
- Third-party open-source format and example downloader: https://github.com/Leo4815162342/dukascopy-node and https://www.dukascopy-node.app/downloading-tick-data
- LEAN native Forex tick ZIP schema: https://www.quantconnect.com/docs/v2/lean-engine/data-format/forex-and-cfd

**Important:** An MIT license on a downloader does **not** grant us redistribution or commercial rights to the underlying provider's price data. Confirm provider terms and permitted research usage before collecting or storing real quotes. Do not commit BI5 files, full tick CSVs, or licensing-restricted data into the public GitHub repository.

## Bounded one-hour local sample workflow

First acquire a single legally permitted one-hour binary file and verify its true UTC hour, symbol, price precision and source provenance. The binary decoder expects the documented record format `>IIIff`: offset milliseconds, ask ticks, bid ticks, ask volume, bid volume. The price divisor is 100,000 for EURUSD/GBPUSD and 1,000 for USDJPY. We explicitly reject unsupported symbols and invalid, unordered, crossed or non-finite quote data. The importer is capped at 12 MiB compressed and 2 million records/hour to avoid uncontrolled memory use.

```bash
# Import one locally available licensed hourly file; no provider downloads occur.
forexlab import-bi5 /secure/data/12h_ticks.bi5 \
  --pair EURUSD --hour-utc 2024-01-03T12:00:00Z \
  --rights-note 'Source rights reviewed for this research use; record terms separately' \
  --out /secure/forexlab/processed/EURUSD

# Produce bid/ask OHLC research bars from actual quoted history, after review.
forexlab resample-ticks /secure/forexlab/processed/EURUSD/EURUSD_20240103T1200Z_quotes.csv \
  --out /secure/forexlab/aggregated/EURUSD --timeframes M15 M30 H1 H4 D1

# Produce quote tick LEAN storage files; this is NOT an actual LEAN backtest.
forexlab export-lean-ticks /secure/forexlab/processed/EURUSD/EURUSD_20240103T1200Z_quotes.csv \
  --pair EURUSD --market dukascopy --out /secure/forexlab/lean-staging
```

The ZIPs use paths `forex/dukascopy/tick/eurusd/YYYYMMDD_quote.zip`, internal `YYYYMMDD_eurusd_tick_quote.csv`, and rows `ms_since_UTC_midnight,bid,ask`. The `dukascopy` market name is **not** presumed to be built into stock LEAN. Before loading the data we must register the provider's exchange/market ID, market hours, timezone, symbol properties and the appropriate data config, then test actual LEAN reading. Do not falsely label Dukascopy prices as `oanda` or `fxcm` to trick LEAN into accepting the files. Cross-provider data and broker orders are not identical.

## Acceptance before strategy comparisons

1. Verify tick source, usage rights, true first/last coverage, timestamps, spread levels, same-ms duplicate behavior, holidays, outages, DST and source anomalies.
2. Run side-by-side EUR/USD comparisons with independent same-venue candles; then expand to GBP/USD and USD/JPY.
3. Pin a LEAN engine version; verify actual tick subscription and bar consolidators, market-hour/session alignment and commission/financing models. Record all mismatches.
4. Implement an independent Python execution simulator using executable bid/ask fills and compare LEAN results. The existing `diagnostic_backtest` is only an illustrative FRED study and is not adequate.
5. Perform walk-forward and untouched holdout evaluation with all tests logged. No evaluation is authorized on live money.

## What is explicitly NOT delivered in v0.4

- A licensed downloadable 1999–2026 dataset or a complete historical archive.
- Tested integration that runs a LEAN backtest; exported files alone do not constitute integration.
- MT5 terminal connection or broker orders.
- Proven strategy win rates, profitable AI, or verified live trade signals.
