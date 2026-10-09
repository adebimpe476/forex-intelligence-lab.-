# Implementation backlog

## P0 — completed in prototype
- [x] Select first three instruments and data provenance format.
- [x] Verify FRED H.10 daily series coverage for each from 1999 through 2026-10-02 (full query).
- [x] Archive reproducible latest-date short source snapshot with missing data preserved.
- [x] Create fetch/re-audit CLI for complete daily reference files when network is available.
- [x] Implement three simple inspectable signal hypotheses (daily only).
- [x] Provide lagged indicative-price diagnostic simulator, explicitly NOT LEAN or broker-equivalent.
- [x] Establish automated data and no-lookahead unit tests.
- [x] Create functioning read-only mobile web dashboard prototype and safety-disabled server.

## P1 — research / data blocker before meaningful strategy selection
- [ ] Fetch & retain complete 1999–2026 FRED daily reference series with hashes; run checks and provenance review.
- [ ] Acquire authorized bid/ask tick/M1 datasets for three pairs; record earliest verified coverage and legal usage.
- [ ] Build resampling pipeline from timestamps with deterministic UTC/session boundaries for M15/M30/H1/H4/D1.
- [ ] Compare at least two quote sources and record outliers, gaps, timezone rules, weekend behavior and DST effects.
- [ ] Integrate LEAN locally; validate simulator vs transparent Python reference, including costs.
- [ ] Extend three baselines to tradeable OHLC bid/ask tick-quality strategy definitions.

## P2 — credible model discovery
- [ ] Register full strategy search space and each trial (prevent winner's curse).
- [ ] Walk-forward, purge/embargo as appropriate, final holdout, cross-broker check.
- [ ] Baselines vs ML; include regime detection / trend / carry / macro / cross-currency challengers.
- [ ] Stress-test spreads, gaps, swaps, fees, partial fills, slippage, outages and correlated exposures.
- [ ] Publish reproducible net performance, drawdown and confidence intervals, including all failed ideas.

## P3 — authorized live feed and paper execution
- [ ] Windows MT5 terminal on trusted server; demo account and broker permissions.
- [ ] One source of truth for approved signal; read-only live data collector before enabling order method.
- [ ] Safety gate: idempotency, stale tick, symbol validation, spread check, account cap, daily stop, kill switch.
- [ ] Reconcile account positions and errors; dry-run and demo order reports.
- [ ] Authenticated mobile app/dashboard with charts and alerting; maintain action audit log.

**GO-LIVE** requires independent, documented approval, not a target win-rate claim.

## P0 additional foundation
- [x] Research-only supervised feature generator and fixed directional classification baseline, with chronology gaps and separate untouched test split. No trained model or profitability finding bundled.

## V0.2 foundation completed (2026-10-09)
- [x] Add quote integrity checks for timezone-aware bid/ask ticks and preserve repeated timestamps.
- [x] Implement UTC-anchored M15/M30/H1/H4/D1 observed-only resampling, with bar completion timestamps and spread metrics.
- [x] Add automated tests for crossed/invalid quotes, ordering, no future leakage, no fake missing candles and file output.
- [ ] Obtain and audit authentic licensed tick data for all three pairs; nothing in V0.2 asserts this data has been collected.
- [ ] Implement configurable FX market-session boundaries / NY 17:00 daily rolls and compare results with broker charts.
