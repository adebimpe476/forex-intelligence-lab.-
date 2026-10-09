# Original research intelligence v0.3 — hypotheses, not signals

**Source: original implementation by this project's research assistant, informed by academic quantitative research.** These models are uncalibrated; no profit or predictive-power claim is made. Trading and account execution remain permanently disabled at this stage.

## Why this code exists

Collecting EAs is not a systematic trading edge. We require a reproducible *selection policy* that observes market conditions, evaluates candidate strategies and can refuse trades. The first proprietary module (`src/forexlab/intelligence.py`) uses precisely all five requested timeframes:

- **D1:** broad trailing return direction, observed from a closed daily bar only.
- **H4:** Kaufman-style path efficiency (absolute net price movement divided by absolute price-path length) to select trend, range or uncertain regimes. Thresholds 0.38/0.20 are research assumptions, NOT optimized or accepted strategy parameters.
- **H1:** eight-bar direction for trend alignment; 20-bar z-score for *candidate* mean reversion in ranges.
- **M30:** six-bar direction confirmation.
- **M15:** breakout beyond 20 *previous* closes for trend candidate, or one-bar reversal as a potential range entry filter.

The selector refuses to issue a BUY/SELL candidate when data is missing, bar times are naive, data is stale, bar duration differs from the specified timeframe, bid/ask is malformed, recent spread proxy is too large, or timeframes conflict. Outputs are explicitly `research_only=True`, `execution_allowed=False` regardless of result. A BUY/SELL candidate is NOT a validated trade or an order.

## 95% win-rate trap

`src/forexlab/edge_audit.py` independently calculates win rate, net expectancy in R, profit factor, cumulative-R drawdown, and an approximate Wilson 95% *lower confidence bound* for win rate. It illustrates a counterexample: 95 wins of +0.01R and five losses of -1R means 95% win rate, but **negative** total R. Even positive diagnostics never set `validated=True` or allow execution; genuine out-of-sample provenance is not established by a metric function.

## Why not claim a live AI model yet?

This deterministic policy is a testable research hypothesis. We will compare against simpler fixed-strategy controls using independent high-quality historical bid/ask series, realistic fills and untouched evaluation splits. Only then will we test regime classifiers or machine-learning meta-label filters. Model selection must account for multiple-hypothesis search: record *every* trial, not just winners, and guard the held-out test against repeated tuning.

## Evidence to investigate

1. Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum*, Journal of Financial Economics. DOI: `10.1016/j.jfineco.2011.11.003`. Momentum documented over horizons of months in futures including currencies; it does **not** establish M15 forex profitability.
2. Bailey & López de Prado (2014), *The Deflated Sharpe Ratio*, Journal of Portfolio Management. DOI: `10.3905/jpm.2014.40.5.094`. Correcting for selection bias and non-normality is crucial when comparing numerous strategies.
3. QuantConnect LEAN official documentation, consolidating data, warmup, no trading during warmup: https://www.quantconnect.com/docs/v2/writing-algorithms/historical-data/warm-up-periods

## Acceptance criteria before further claims

- Acquire licensed intraday bid/ask data with source metadata, timezone cutoffs and quality reports.
- Compare actual trade simulation to a pinned LEAN revision; no H.10 daily fixing used to claim executable intraday fills.
- Pin and preregister training/validation/test splits, with purging or embargo for overlapping labels.
- Estimate out-of-sample after-cost results across pairs, market regimes and source feeds, including changes to execution latency and spread.
- Use independent forward demo testing with risk caps and emergency stop. No live account access until explicitly approved.
