# Verified format correction · Current daily Dukascopy BI5

**Research-only. No real dataset is bundled or licensed by this repository. No live orders.**

On 2026-10-09 the Dukascopy Historical Price Data documentation described a *daily* `.bi5` layout: `SYMBOL/YEAR/(MONTH-1)/DD_ticks.bi5`. Each quote uses a 20-byte big-endian record (`>IIIff`), with `ms` measured **since UTC midnight** and price scale 100000 for EURUSD/GBPUSD and 1000 for USDJPY. This differs materially from our v0.4 **legacy hourly** converter (`YYYY/(MONTH-1)/DD/HHh_ticks.bi5`) where `ms` means milliseconds since the hour.

Original provider reference: https://www.dukascopy.com/wiki/en/development/data-export/

## Why this matters

A daily record at `01:15:00 UTC` has offset 4,500,000 ms, which a legacy hourly decoder would incorrectly reject as exceeding 3,600,000; worse, any offsets below one hour might look valid under both formats but be **misdated** if the hour anchor is not midnight. Do not auto-guess the source layout.

## Locally authorized input workflow

1. Independently review provider terms and verify that you may download/use/store the **specific dataset** and intended purpose; other provider XML conditions might not govern historical BI5 archives. For commercial usage, obtain permission if terms are ambiguous. Do not publish third-party raw data or source-derived tick streams in public GitHub.
2. Acquire one genuine day to a private data volume and verify exact source path and SHA256. If the provider only offers a paid/requester-pays S3 path, **confirm fees before connecting**.
3. Import with explicit date/layout and rights evidence:

```bash
forexlab import-daily-bi5 ./private-input/02_ticks.bi5 \
    --pair EURUSD --day-utc 2024-01-02T00:00:00Z \
    --rights-note "provider data license ID and permitted local-research use" \
    --out ./private-output/EURUSD
forexlab resample-ticks ./private-output/EURUSD/EURUSD_20240102_daily_quotes.csv \
    --out ./private-output/EURUSD/bars --timeframes M15 M30 H1 H4 D1
```

4. Compare quote counts and source file checksum with provider, then independently compare output to a verified broker candle series. Check weekend/rollover, spread spikes and 17:00 America/New_York session cutoffs. Our UTC-based daily candle is **not** automatically equivalent to a broker's daily candle.
5. Use `forexlab export-lean-ticks` to stage quote data only after confirming LEAN provider market registration; validate it in the *actual LEAN engine* with matching trading-session and symbol properties. No backtest or broker trading can be claimed from a format export.

## Security and QA status

- The daily decoder rejects bad prices, out-of-day timestamps, reversed timestamps, nonfinite volumes, excessive decompressed output, bad time zones, and oversized/trailing/corrupt LZMA streams.
- The decoder does not make network calls, execute trades, or redistribute third-party quotes.
- Synthetic binary fixture tests verify strict time anchoring, price scaling, rejects, and manifest output. **These are not a substitute for a real-source smoke test.**
- No LEAN integration, real historical BI5 quote load or validated statistical edge has yet been demonstrated.
