# Bid/ask tick data contract · V0.2

Status: **ingestion pipeline ready; no authentic tick datasets collected yet**.

## Required data format

CSV columns: `timestamp_utc,bid,ask`; optional source metadata must be recorded separately. Timestamps **must have an explicit timezone** (`Z` or `+00:00`); rows must arrive in chronological order. Repeated timestamps are permitted because some feeds publish more than one quote update within the same time unit. Quotes must be finite/positive and `ask >= bid`.

Commands after acquiring a properly licensed and verified source:

```bash
forexlab resample-ticks <broker_quotes.csv> --out data/processed/<source>/<pair> --timeframes M15 M30 H1 H4 D1
```

The command generates bid/ask/mid `open,high,low,close`, mean/max/closing spread, and observed tick count per bar. Missing bars are **omitted**, not filled; the resulting manifest includes the largest timestamp gap and number of same-timestamp quote updates.

## Precautions before modeling

1. Source identity, subscription/license, permitted storage, pair, quote precision, timestamp definition and coverage must be recorded. This module does not check those metadata claims.
2. Current bar intervals are **midnight UTC anchored**. These are not broker-dependent 17:00 New York daily candles, and DST handling for session-based daily/H4 bars is not implemented. Broker matching must be added before trading-strategy evaluations.
3. An output bar is available **only at or after `bar_end_utc`** (never at `bar_start_utc`). Live signals based on closed bars must use this rule.
4. Data must be checked for abnormal spread spikes, session gaps, quote outages, bid/ask precision, pair contract specifications, rollovers and DST issues against a second source.
5. A mid-price candle is **not** an executable candle. Long entries normally pay the ask and exits sell to bid; short entries sell bid and cover ask. Financing, commissions, outages, slippage and latency are not represented by the resampler.
6. Large real tick datasets should ultimately use partitioned Parquet/streaming processing. The first CSV implementation is deliberately simple, not optimized for decades of tick data.
7. No LEAN integration, MT5 broker connection, account control or order submission is implemented.

## Next acceptance gate

Accept one **real**, properly permitted broker quote sample for EUR/USD, run the UTC resampler, audit gaps and spreads, and compare bars with the same broker's terminal. Then extend this to USD/JPY and GBP/USD, implement configurable session boundaries, and only then begin execution-aware LEAN backtesting.
