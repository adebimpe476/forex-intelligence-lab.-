# Genuine FRED daily FX reference baseline — 1999–2026

**Retrieved 2026-10-09; indicative noon-rate observations only; NOT tradable bid/ask OHLC or an intraday trading backtest. No investment recommendation, verified edge, or model accuracy claim.**

## Raw source inventory

| Pair | H.10 / FRED series | Valid reference observations | Missing (published '.') | First–last valid |
|---|---|---:|---:|---|
| EURUSD | DEXUSEU | 6960 | 280 | 1999-01-04 – 2026-10-02 |
| USDJPY | DEXJPUS | 6960 | 281 | 1999-01-04 – 2026-10-02 |
| GBPUSD | DEXUSUK | 6960 | 281 | 1999-01-04 – 2026-10-02 |

Sources: [DEXUSEU](https://fred.stlouisfed.org/series/DEXUSEU), [DEXJPUS](https://fred.stlouisfed.org/series/DEXJPUS), [DEXUSUK](https://fred.stlouisfed.org/series/DEXUSUK). Original releases: US Federal Reserve Board H.10. FRED current-vintage values may revise; observation dates and provider's real-time date need to be archived. USDJPY is yen per USD, not USD per yen.

## Basic volatility and cross-currency diagnostics

Log returns calculated from consecutive **valid** observation dates (shared across all three pairs). Days with published '.' remain missing and are **not forward-filled**. Sample length: **6959 aligned changes**. Volatility uses `stdev(log_return) × sqrt(252)` and should be understood as approximate *daily-reference-rate* volatility rather than a broker's intraday volatility.

| Period | Aligned changes | EURUSD annualized vol % | USDJPY % | GBPUSD % | Cor(EURUSD, GBPUSD) | Cor(EURUSD, USDJPY) | Cor(GBPUSD, USDJPY) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1999-2007 | 2264 | 9.38 | 9.90 | 7.96 | 0.700 | -0.349 | -0.322 |
| 2008-2014 | 1757 | 10.72 | 11.24 | 10.61 | 0.642 | -0.151 | 0.016 |
| 2015-2019 | 1249 | 8.30 | 8.77 | 9.73 | 0.515 | -0.432 | -0.110 |
| 2020-2026 | 1689 | 7.33 | 9.61 | 8.70 | 0.727 | -0.480 | -0.421 |

Whole-period descriptive return correlations: EURUSD/GBPUSD **0.647**, EURUSD/USDJPY **-0.318**, GBPUSD/USDJPY **-0.196**. These estimates are backward-looking, depend on daily noon fixing conventions, and do not predict future correlations.

## Architecture implications (hypotheses to test)

1. **Correlation-aware exposure:** buying EURUSD and GBPUSD is often overlapping short-USD exposure; buying USDJPY is positive USD exposure. A portfolio risk engine must translate quote/base currency into actual USD risk and gross/net factor exposures, not simply count positions.
2. **Regime adaptation:** the distinct period volatilities and correlations justify testing regime-conditioned position sizing. However, fitting volatility or correlation on the whole historical period would introduce look-ahead; estimate using trailing windows only.
3. **Cost and frequency separation:** H.10 fixings cannot justify an M15 or H1 strategy. High-resolution, timestamped bid/ask quotes and realistic execution fees, swap, spreads and slippage remain mandatory.
4. **Unseen data:** first preregister strategy variants and risk parameters, record every experiment, then evaluate holdouts only once. A 95% observed win rate alone is not a success criterion.

## Calculations & limitations

Data acquired via FRED series observations with `observation_start=1999-01-01`, `observation_end=2026-10-09`, current-vintage date as delivered, and no temporal fill. Log return at date `t` is `ln(price_t / price_previous_valid_observation)`; weekends and holidays are multi-day elapsed changes, so **not every return spans 24 hours**. No risk-free-rate subtraction, position sizing, commission or execution simulation. Period analysis uses shared-date returns selected by return-date; the first return inside a period can bridge its boundary.

This document records *descriptive data research*, not performance or an externally verified tradable model.
