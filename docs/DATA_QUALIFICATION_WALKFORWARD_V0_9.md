# v0.9 — Rights-aware data qualification and reproducible walk-forward plans

**Status: local smoke-tested implementation, no real bid/ask sample, no LEAN run, no broker/MT5 order access.**

## Why this is the next research gate

The v0.8 reference quote simulator can process synthetic ticks, but its outcomes are not market evidence. We need an independent source-and-quality record before permitting data to influence strategy discovery. Source permission and legal rights CANNOT be established simply by writing a true value in JSON; **a human must verify license documents and provider provenance**.

## 1. Data quality / rights preflight

`forexlab qualify-data data/raw/approved/EURUSD_ticks.csv --manifest /private/path/to/EURUSD_manifest.json --purpose quant_research`

The manifest declares (a) exact SHA256 of source CSV, (b) `kind`: `BID_ASK_TICK` or `MID_OHLC`, (c) pair and genuine provider, (d) provider link and (e) purpose-specific permission with external evidence URL. See `configs/data_manifest_TEMPLATE.json`.

The audit rejects hash mismatch, missing rights declaration, missing source URL, invalid/crossed bid/ask ticks, missing timezone markers, non-monotonic UTC timestamps, invalid OHLC relationships, and unknown ML permissions. A passing result remains `source_verified=false`, `legal_clearance_verified=false`, `lean_engine_verified=false` and `execution_allowed=false` until manual evidence review and real LEAN validation.

A single-price OHLC file is **not** bid/ask: the report explicitly marks `has_executable_bid_ask=false`. Large datasets should be processed in bounded chunks later; this preflight has a 300 MB hard limit.

**FRED licensing alert:** The FRED website's published legal terms prohibit use of FRED Content in connection with development/training of AI/ML systems. The model training path therefore refuses FRED provenance. This does not claim any permission to train on other datasets either—review their actual rights. See <https://fred.stlouisfed.org/legal/>. Prior small H.10 reference snapshots are for the existing context/provenance audit, not AI training data or a commercial trading feed. The former automatic FRED download workflow is disabled pending legal-use review.

## 2. Locked chronological walk-forward planning

`forexlab walkforward-plan data/raw/approved/EURUSD_ticks.csv --timestamp-column timestamp_utc --min-train 300 --test-size 60 --embargo 5 --label-horizon 1 --final-holdout 100 --out artifacts/research/EURUSD_split.json`

This produces expanding training folds, separated embargo rows, non-overlapping next test segments, a **reserved final holdout** and a reproducible timestamp/plan hash. All indices are start-inclusive/end-exclusive. The minimum embargo (in rows) must be >= the future-label horizon; overlapping feature windows or longer position horizons may require longer purging. Distinct folds and a locked holdout do **not** alone prove independence if a researcher tunes repeatedly on the fold results.

**No tuning, AI training, LEAN engine run, after-cost strategy ranking, or valid market-profit figure is performed by these commands.** They only define auditable inputs and experiment boundaries.

## 3. What we still require

1. Acquire one genuine EUR/USD bid/ask sample from a provider offering acceptable storage/research/ML licensing, with source provenance and manual rights sign-off.
2. Make our quote simulator and actual pinned LEAN engine run on the same independent data; compare signal timing, bid/ask fills, commission/financing assumptions and missing events.
3. Record ALL candidate parameter trials in the experiment journal; evaluate unseen segments and isolate a genuinely untouched final holdout.
4. Only after independent review, add an authenticated DEMO MT5 bridge and position reconciliation; no live trading until distinct approval.

A high win rate without positive after-cost expectancy, statistically meaningful trade count, and downside control is never an acceptance criterion by itself.
