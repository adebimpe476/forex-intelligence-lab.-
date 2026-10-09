# Forex Intelligence Lab · Research foundation v0.2

**Status: RESEARCH ONLY. No live quotes, no AI prediction model, no MT5 account, no actual LEAN integration, and no capability to place trades.**

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

# When your computer has internet access:
forexlab fetch-fred --out data/raw/fred-full --start 1999-01-01 --end 2026-10-09
forexlab audit data/raw/fred-full/fred_h10_merged_daily_indicative.csv

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

## GitHub full-history ingestion workflow
After the v0.2 code is merged into GitHub, use **Actions → Fetch and audit historical FRED daily reference series → Run workflow**. That manually downloads all three daily source histories and stores a 7-day GitHub Actions artifact (not committed to Git history). This workflow has **not run** in the current session, and FRED may refuse or limit remote downloads. Review rate limits and rights. The current container cannot reach FRED directly.

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

