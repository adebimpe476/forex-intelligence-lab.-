# V0.5 · Daily BI5 format correction and real-source acceptance gate

**No genuine tick dataset has yet been downloaded or tested. No LEAN engine backtest, validated edge, or MT5 connection exists.**

Dukascopy's [Historical Price Data documentation](https://www.dukascopy.com/wiki/en/development/data-export/) describes two distinct layouts:

| Source layout | Example relative path | Timestamp anchor |
|---|---|---|
| Current daily | `EURUSD/2024/00/02_ticks.bi5` | 00:00 UTC; `0 <= ms < 86,400,000` |
| Legacy hourly | `EURUSD/2024/00/02/00h_ticks.bi5` | Hour start; `0 <= ms < 3,600,000` |

The month directory is zero-based. Both use 20-byte big-endian `>IIIff` quote records (millisecond timestamp, ask-int, bid-int, ask-volume, bid-volume). EURUSD/GBPUSD divide integer prices by 100,000; USDJPY uses 1,000. Select the correct decoder explicitly; do not silently infer source formats or combine them.

## Rights-cleared, bounded import (once real source data is available)

1. Review terms for the **specific historical feed** and the intended use; an XML-feed agreement may not authorize commercial BI5 usage. Obtain clarification before commercializing ambiguous data rights.
2. Acquire one genuine daily BI5 file via an authorized provider mechanism to private storage. Check if the offered S3 option charges requester fees before downloading.
3. Preserve the provider link, rights evidence, file SHA256, quote date, source timestamp convention and version. Never upload licensed raw files or derived tick series to public GitHub.
4. Import to a local, untracked directory:

```bash
forexlab import-daily-bi5 ./private-source/02_ticks.bi5 \
  --pair EURUSD --day-utc 2024-01-02T00:00:00Z \
  --rights-note "provider permission reference and scope" \
  --out ./private-output/EURUSD
forexlab resample-ticks ./private-output/EURUSD/EURUSD_20240102_daily_quotes.csv \
  --timeframes M15 M30 H1 H4 D1 --out ./private-output/EURUSD/bars
```

5. Compare resulting sample count, bid/ask spread and candles with the provider and an independently sourced broker history. Determine market weekends, broker H4/D1 candle boundaries, Sunday trading and DST. **UTC midnight D1 is not a 17:00 New York rolling D1 candle**.
6. Verify the exported tick ZIP in an actual pinned LEAN engine build with a deliberately registered provider market, tested market-hours and symbol properties, fees and correct bid/ask fill logic. A ZIP being syntactically correct does not imply LEAN data integration.

## What has been tested

The strict current-layout decoder and CLI have synthetic-fixture unit tests for file path construction, 24-hour millisecond offsets, bid/ask scaling, invalid/crossed prices, corrupt/oversize LZMA data, UTC reference, rights-note requirement and disabled execution.

**Not demonstrated:** provider network access, true BI5 ingestion from the provider, a commercial data license, true LEAN engine run, successful broker integration, actual PnL, or 95% predictive accuracy.
