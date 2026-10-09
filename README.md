# Forex Intelligence Lab · Research control v0.7

**Status: RESEARCH ONLY. No live quotes, no AI prediction model, no MT5 account, no actual LEAN integration, and no capability to place trades.**

**v0.9 rights update:** Automated FRED downloads are paused after review of current FRED restrictions on AI/system development and training. Do not train ML on the H.10 source. Only rights-reviewed external market feeds may enter future research, and no source is automatically license-verified. See [Data gate and walk-forward documentation](docs/DATA_QUALIFICATION_WALKFORWARD_V0_9.md).

This is the first practical, locally runnable foundation for the longer-term research → LEAN backtesting → AI → approved live signal → MT5 demo/paper → mobile web control system.

## Included today
- Historical reference data source ledger with coverage audit for three FX pairs.
- Sourced Federal Reserve H.10 **24-row** historical reference snapshot (23 valid observations per pair) dated 2026-09-01 to 2026-10-02. Preserves 2026-09-07 as missing.
- Full-history series **audit**: FRED series DEXUSEU, DEXJPUS and DEXUSUK were queried for 1999-01-01 to 2026-10-09. Each had **6,960 valid daily indicative values** to 2026-10-02; this package does **not** bundle all historical observations, only the short snapshot and a downloader.
- A Python downloader for complete FRED daily reference history when external connectivity is available. Source hashes / provenance are written beside downloads.
- Three **research hypotheses** and illustrative daily close-based backtest diagnostics requiring ≥180 observations. They do not constitute verified strategies. They require independently acquired tradable bid/ask tick data for meaningful FX backtests.
- Minimal working read-only FastAPI + mobile dashboard. The only displayed series is the dated snapshot, explicitly labeled not live.
- Regression and data-integrity tests and an example GitHub Actions workflow.
- Research/backlog registry and target LEAN/MT5 architecture.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
pip install -e '.[dev]'
pytest -q
forexlab audit data/raw/fred_h10_daily_snapshot_2026-10-08.csv

# FRED download is now PAUSED pending review of data-rights terms.
# Earlier commands remain in source only as historical diagnostics; do not use in AI workflows.

# A deliberately limited daily indicative-reference diagnostic (NOT strategy verification):
forexlab diagnose data/raw/fred-full/fred_h10_merged_daily_indicative.csv --pair EURUSD --strategy trend_following

# Local read-only dashboard:
uvicorn forexlab.server:app --host 127.0.0.1 --port 8000
# Browse http://127.0.0.1:8000
```

## Known data limitations
FRED H.10 provides one indicative New York noon rate per date, **not every movement**. It contains no bid/ask order book, broker spreads, executable fills or intraday OHLC. It is suitable for exploratory long-horizon context and ingestion testing, **not** credible M15 scalping performance or broker trading results. A global list of every FX transaction does not exist because the OTC forex market is decentralized.

## 95% win-rate ambition
Win rate can be manufactured by tiny profit targets and catastrophic loss limits, or by fitting noise. Project admission criteria require net-of-cost expectancy, ample trades, drawdown, statistical uncertainty, unseen holdout, live-demo consistency and risk controls. No performance claim is made in this prototype.

## Strategy/data/opensource roadmap
See `docs/ARCHITECTURE.md`, `docs/BUILD_BACKLOG.md`, `docs/SOURCE_REGISTRY.csv` and `docs/OPEN_SOURCE_REGISTRY.csv`.

## Security
Never commit API keys, trading account passwords or broker credentials. Live order endpoints are intentionally absent. No code path in this repository can place an order. Before any live/paper adapter, implement and test authenticated access, an independently enforceable risk gate and emergency disablement.

## ML research scaffold
Optional `pip install -e '.[ml]'`. `forexlab.ml.make_daily_supervised_sample` generates strictly historical daily features and future direction labels; `fit_research_direction_model` produces time-ordered classification diagnostics, **not** a tradable strategy. It is not trained with the short snapshot and has no live/paper-trading privileges. All hyperparameter experiments must be logged and a final holdout must remain untouched until the final research evaluation.

## FRED source-rights gate
The old FRED historical download workflow is no longer enabled for data extraction. The current published FRED terms prohibit using FRED Content for software/AI development and training; we need a separate rights-reviewed forex quote provider for ML and any commercial product. No new FRED data has been downloaded by v0.9.

## V0.2 progress: bid/ask tick validation and multi-timeframe conversion

The project now includes `src/forexlab/tickdata.py`, which validates broker tick CSVs with timezone-aware timestamps, rejects crossed/invalid quotes, preserves same-timestamp updates, and creates observed-only bid, ask and mid OHLC bars for **M15, M30, H1, H4 and D1**. The output stores bar availability boundaries, spreads and a quality manifest. **This is a data-processing feature, not an MT5/LEAN strategy or live-data integration.**

Once *real* tick data with verified rights and provenance becomes available:

```bash
forexlab resample-ticks data/raw/approved/EURUSD_ticks.csv --out data/processed/EURUSD --timeframes M15 M30 H1 H4 D1
```

See [`docs/TICK_DATA_SPEC.md`](docs/TICK_DATA_SPEC.md) for limitations and acceptance checks. Do **not** feed the FRED daily series into this tick resampler: they contain no intraday quotes or spreads.

## GitHub handoff (2026-10-09)

The linked repository is `adebimpe476/forex-intelligence-lab.-` (note the trailing `.-`). It was created **public**. Publishing the research-only code requires no brokerage credentials; change repository visibility to private before adding proprietary experiments or data whose license forbids public redistribution. The development branch is `feature/research-foundation-v0-2`. The branch is for review and should not be merged before CI checks pass.

## Original trading intelligence v0.3 (research-only)

In addition to open-source infrastructure, the project now contains **our own** five-timeframe [regime and signal hypothesis](src/forexlab/intelligence.py), an [after-cost R-multiple expectancy audit](src/forexlab/edge_audit.py), and [nine targeted synthetic regression tests](tests/test_intelligence.py). The [research rationale, limitations, references and validation conditions](docs/ORIGINAL_RESEARCH_INTELLIGENCE.md) are documented. These modules do **not** connect to a broker or claim proven signals. A candidate BUY or SELL is never an executable order.


## v0.4 — Real quote data format pipeline (provider data not yet acquired)

An original bounded parser for Dukascopy hourly BI5 bid/ask quote files and a deterministic native LEAN Forex quote-tick ZIP exporter are now implemented and regression tested. They work on **locally supplied, rights-reviewed files**, not by automatically harvesting the provider feed. No genuine source file was downloaded in this environment, and no actual LEAN backtest was run. See [data acquisition acceptance and exact commands](docs/DATA_ACQUISITION_V0_4.md). Data files and generated ZIPs are excluded from Git.

## V0.5: Current daily BI5 layout correction (research-only)

Official Dukascopy documentation distinguishes daily files (`DD_ticks.bi5`, milliseconds since UTC midnight) from older hourly BI5 files (milliseconds since the UTC hour). Use `forexlab import-daily-bi5` for explicitly licensed daily files; do **not** feed them into the hourly decoder. See [daily BI5 import instructions](docs/DAILY_BI5_IMPORT_V0_5.md). Both versions are exercised with synthetic fixtures; actual provider downloads, LEAN engine simulation and MT5 orders have **not** been performed.

## V0.6: original portfolio risk checks and session-clock QA (research-only)

Added [illustrative USD-account risk gate](src/forexlab/risk.py) and [DST-aware New York 17:00 session aggregation](src/forexlab/fx_sessions.py), with CLI tools `forexlab research-size` and `forexlab session-bars`. All output stays **non-executable**, and sample inputs are not live trading signals. The risk gate includes duplicate detection, stop budget/round-down, realized+unrealized daily drawdown, open-risk cap and overlapping USD directional positions. See [limitations and checks](docs/RISK_AND_SESSIONS_V0_6.md). Market-session bars are not yet compatible with the fixed-duration existing strategy signal engine across DST; this is deliberately not wired into live execution or backtesting.

## V0.7: Mobile research control + experiment laboratory

Now includes a redesigned responsive **read-only** research console with Overview / Experiment Lab / Pipeline sections. The experiment journal stores CSV source hashes, fixed strategy/cost inputs, and hashed previous-record links, and refuses duplicate or corrupted research runs. **These runs are NOT LEAN simulations or validated broker-tradable strategy results.** Three example commands and limitations are documented in [docs/EXPERIMENT_LAB_V0_7.md](docs/EXPERIMENT_LAB_V0_7.md). A deterministic **synthetic** fixture generator is included for local QA. No account, orders, live quotes or artificial win-rate promises are present.

## V0.8: Quote-side reference simulator (synthetic tests only)

Added [M15 EMA cross bid/ask reference simulator](src/forexlab/quote_simulator.py) with completed-bar signals, observed quote-side fills, modeled adverse slippage, commission and no-hindsight stop/target checks. It is an independent **research diagnostic**, NOT the LEAN engine, market-data license, broker backtest, account, live signal or executable strategy.

See [docs/QUOTE_SIMULATOR_V0_8.md](docs/QUOTE_SIMULATOR_V0_8.md). A new CLI command accepts only a real or synthetic tick CSV with timestamp_utc,bid,ask and an explicit timezone:

```bash
forexlab simulate-quotes /path/to/rights-reviewed/EURUSD_ticks.csv --pair EURUSD --out artifacts/reference/EURUSD.json
```

The actual input is independently checked by `forexlab.tickdata.validate_ticks`; FRED H.10 daily rates MUST NOT be passed to this CLI. Outputs always include `source_verified=false`, `strategy_validated=false` and `execution_allowed=false`. All published tests currently use synthetic quote fixtures.

## v0.9 — Research dataset qualification and walk-forward validation plans
The original [data qualification gate](src/forexlab/data_gate.py) verifies input hashes, format, timestamp integrity and purpose-specific declared rights **without falsely certifying a license**. The [walk-forward planner](src/forexlab/walkforward.py) prepares expanding training/test segments with embargo and a reserved final holdout. Both are research-only. Examples and remaining blockers: [docs/DATA_QUALIFICATION_WALKFORWARD_V0_9.md](docs/DATA_QUALIFICATION_WALKFORWARD_V0_9.md).

## V1.0 — Historical tick ZIP intake + LEAN build preflight

Added an original [HistData generic ASCII bid/ask tick ZIP reader](src/forexlab/histdata.py) with fixed **EST/UTC−05 (no DST)** conversion and strict archive/date/quote guards; it never fetches, distributes or approves source data rights. Added a [LEAN prerequisite probe](src/forexlab/lean_preflight.py) that always reports whether actual engine execution has *not* occurred. Use `forexlab import-histdata --help` and `forexlab lean-preflight --help`. See [data-provider permissions, exact instructions and evidence requirements](docs/REAL_DATA_AND_LEAN_V1_0.md). **All vendor-format fixtures are synthetic.**

## v1.1: One-command private EUR/USD first-replay preparation

Added [`forexlab first-replay`](docs/FIRST_EURUSD_REPLAY_V1_1.md): given a **locally obtained** HistData EURUSD tick ZIP and an explicit private rights declaration, this stages timestamp-normalized bid/ask quotes, technical quality checks, a **reference simulator** report, LEAN-format ZIPs and linked integrity/provenance manifests. Nothing is downloaded, published, traded or described as an actual LEAN backtest. Real provider quote data and independent license verification are still pending.
