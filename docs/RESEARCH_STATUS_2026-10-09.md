# Forex AI Intelligence — Research and build status
**Date:** 2026-10-09 · **Stage:** runnable read-only research prototype (not a trading system)

## Completed
1. **Architecture chosen**: QuantConnect LEAN (target professional backtesting layer), Python statistical/ML research, MT5 bridge/EA (future bounded actuator), mobile-responsive web UI.
2. **Source-verified long-history audit**: FRED H.10 daily series `DEXUSEU`, `DEXJPUS`, `DEXUSUK` for 1999-01-01 to 2026-10-09; first valid 1999-01-04, last valid 2026-10-02. Each has **6,960** populated daily observations (20,880 total); 280, 281, 281 missing daily placeholders respectively. Series were queried at current vintage 2026-10-08.
3. **Archived source data**: 24-row dated September 1–October 2, 2026 FX snapshot with 23 valid observations per pair. Original missing September 7 row remains missing. Metadata and source attribution included. This is the **only market-price dataset bundled**; complete 1999-2026 data has been audited but not locally archived.
4. **Data retrieval software**: `forexlab fetch-fred` fetches full FRED CSVs and saves checksums/provenance once network access is available.
5. **Three daily baseline hypotheses**: trend-following mean crossover, previous-40-close breakout, mean reversion with coarse sideways filter. None is validated or tradable.
6. **Research diagnostic simulator**: conservative close-lag, hypothetical cost. Not an actual LEAN backtest, no bid/ask fills, no position sizing or swap fees, no acceptable profitability evidence.
7. **Research-only ML baseline**: lag-safe daily features, chronological 70/15/15 split with boundary gaps, fixed Logistic Regression plus majority-class baseline. Not trained here.
8. **Mobile-responsive dashboard**: functional static sampled price graph and read-only API. Live prices, broker orders and '95% win rate' claims are disabled/absent.
9. **Automated verification**: unit tests cover missing data, source audit, strict chronological features, no look-ahead, minimum sample rejection, lagged simulation and holdout partitions.

## Research decisions
- The best strategy must be determined by unseen-data risk-adjusted net results and robustness, **not GitHub popularity**.
- Prioritize (a) trend/time-series momentum; (b) volatility breakouts; (c) regime-conditioned mean reversion. Carry/macro, cross-currency factors and ML are challengers, not automatically superior.
- Keep one authoritative live signal engine. An MT5 EA/bridge may execute approved orders only after passing independent risk checks.
- For M15/M30/H1/H4, secure audited broker-quality timestamps and bid/ask data. Daily H.10 observations do not support those tests.
- A 95% win-rate aspiration does not imply positive expectancy: small frequent wins can be overwhelmed by rare outsized losses; reject martingale and hidden risk.

## Critical blockers
- No complete 1999–2026 raw dataset locally saved in this environment (downloader prepared; network access unavailable to local runtime).
- No tick/M1/M15 OHLC data, no realistic spreads, slippage or carry funding.
- No actual LEAN installed or integrated; no benchmark against other engines.
- No MT5 connected, no broker account, no VPS, no signed-off execution authorization.
- No machine-learning training on a full dataset, no independent out-of-sample profitability verification, no genuine trading signals.
- No GitHub repository created; connected GitHub tooling exposes other projects but does not offer a new-repository creation action. The ZIP is ready to put in a **new private repository** without touching unrelated projects.

## Sources
- Federal Reserve H.10/FRED: https://fred.stlouisfed.org/series/DEXUSEU, https://fred.stlouisfed.org/series/DEXJPUS, https://fred.stlouisfed.org/series/DEXUSUK
- LEAN: https://github.com/QuantConnect/Lean and paid-tier CLI caveat: https://www.quantconnect.com/docs/v2/lean-cli/api-reference/lean-backtest
- MT5 Python API: https://www.mql5.com/en/docs/python_metatrader5
- NautilusTrader alternative: https://github.com/nautechsystems/nautilus_trader
- MQL strategy references (GPLv3): https://github.com/EA31337/EA31337-strategies
- Overfitting / Deflated Sharpe: https://doi.org/10.3905/jpm.2014.40.5.094
