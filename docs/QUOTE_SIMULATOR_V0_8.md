# Research reference simulator v0.8 — not LEAN or live trading

## Purpose
The independent Python simulator makes our backtest assumptions inspectable **before** we compare them to a pinned version of QuantConnect LEAN on authorized source data. No external historical data is bundled with v0.8; unit-test quote fixtures are synthetic. The research strategy is a basic M15 EMA crossover **hypothesis**, not a claim of advantage or a finished five-timeframe model.

## Deterministic rules
- Quotes must have timezone-aware ascending timestamps, positive bid/ask and ask ≥ bid, validated by `validate_ticks`. One standard lot is assumed for *illustrative* USD PnL.
- Use completed observed-only M15 midprice candle closes to compute fast/slow EMAs; require a contiguous rolling history before a crossover. A candidate is known only at the completed bar's end.
- The first quote at or after bar close may produce an entry ONLY if it is fresh and the spread is within configured limits. Long pays ask; short sells bid. Both sides include hypothetical adverse slippage.
- A stop or target can trigger only on future closing-side quotes (bid for long, ask for short). Exit is at the *observed quote*, not the ideal stop/target, with hypothetical adverse slippage. A gap can therefore worsen results.
- Commission is subtracted on each closed trade. Data gaps and unfinished trades are flagged, never silently marked as winners. Positions do not overlap.
- Result hash is tied to the normalized input quotes. Outputs ALWAYS mark `strategy_validated=false`, `lean_engine_verified=false`, `broker_equivalent=false` and `execution_allowed=false`.

## Known limitations
- Historical quotes are NOT promised to be executable, synchronized to broker latency or free of selection bias.
- No carry/swap financing, financing cutoffs, dynamic lot size, broker-specific stop-distance, margin calls, partial fills, spreads beyond source quotes, or live MT5 symbol metadata.
- Commissions, slippage and risk parameters are hypothetical and configurable in Python; the CLI demonstrates one default. No realized-account return can be inferred.
- USDJPY requires broker-/currency-aware PnL conversion and is therefore deliberately unsupported here. EURUSD/GBPUSD USD-quoted examples only.
- Reports with unobserved gaps are INCOMPLETE, not comparable performance samples; skipped candidate counts must be investigated and surfaced.
- At most 1,440 minutes holding; maximum gap/quote delay bounds are assumptions to test, not verified production policies. Long CSVs load in memory; use bounded samples.

## Next milestone
Acquire a licensed authentic tick sample and independently verify data source and quote time zone. Then compare *identical* signal, spread, next-tick fill, stop, take-profit, commission and gap outcomes against an actual running LEAN build. Differences must be resolved BEFORE optimizing parameters or training models on the results.

Official docs: https://github.com/QuantConnect/Lean/blob/master/Data/forex/readme.md
