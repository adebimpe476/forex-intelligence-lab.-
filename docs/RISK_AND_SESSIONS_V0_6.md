# v0.6: Original research-only risk gate and New York-17 session calendar

This is an **offline research interface**. No connected account, broker access, order submission, deployed API, or live trading authorization exists.

## Why build this before obtaining tick data?

Statistical models can issue plausible BUY/SELL candidates while the market is closed, the latest spread is excessive, two USD positions overlap, or the account risk budget is exhausted. We need an independent gate to reject such candidates regardless of model enthusiasm. This module is deliberately separated from a broker adapter, and cannot return `execution_allowed=True`.

### Risk gate: `src/forexlab/risk.py`

The `assess_risk` function supports only EURUSD, GBPUSD, USDJPY and illustrative **USD-denominated** account balances. It calculates volume from (1) account equity, (2) an explicit stop-loss distance, (3) allowed per-trade risk, (4) open-position maximum possible loss, (5) realized and unrealized daily PnL against the **start-of-day** equity, (6) gross USD directional overlap, and (7) broker *assumptions* about contract size, slippage, commissions and minimum lot. Position sizes always round **down** to the nearest lot increment; too-small budgets reject the trade.

Defaults (hypotheses, **not** tailored to any user's financial situation): 0.5% per proposed trade, at most 2% aggregate open stop risk, daily loss threshold 2% of initial equity, minimum 0.01 lot, assumed 100,000 base currency per standard lot, 0.5 pip adverse slippage **per side**, and $7 round-trip commission per standard lot. The assumed stop/entry prices are *executable sides*: ask entry and bid stop for BUY, bid entry and ask stop for SELL. Do **not** charge the full spread a second time. USDJPY stop losses are approximated in USD at the adverse stop-side exchange rate; this is not proof of actual broker conversion or account currency.

**Crucial for future MT5 demo integration:** Obtain `symbol_info` point/tick size, lot step, contract size, profit currency, margin requirements, and actual account currency from the authenticated terminal, and compare estimated results with `mt5.order_calc_profit` and `mt5.order_calc_margin`. Query bid/ask freshness, stops/freeze levels and executable fill policies. Do not reuse default estimates when the broker disagrees. All correlated-risk checks are a basic count of same-direction USD positions, not a complete dynamic covariance or beta model. The risk gate also requires eventually confirmed positions and daily PnL from the actual account—not user-supplied guesses.

Local offline example (not an actual trade):

```bash
forexlab research-size --signal-id example-001 --pair EURUSD --side BUY \
  --entry 1.1002 --stop 1.0982 --equity-usd 2000 --day-start-equity-usd 2000
```

It returns `RESEARCH_SIZE_ONLY` or `BLOCKED`, with `execution_allowed: false` in **every** case.

### FX research sessions: `src/forexlab/fx_sessions.py`

The 17:00 `America/New_York` rollover is one widely used forex convention but **not universal**. Its UTC boundary is 21:00 during US daylight time and 22:00 during US standard time. Under a NY-wall-clock H4 definition, the 01:00–05:00 block on the spring-forward Sunday can last **3 elapsed UTC hours**, and on the fall-back Sunday **5 hours**. The code explicitly tests both transitions and keeps repeated 01:xx updates together. Output stores actual UTC start and end, elapsed hours, and observed-only bid/ask OHLC; it never manufactures missing quote bars.

```bash
forexlab session-bars data/raw/approved/EURUSD_ticks.csv --timeframe H4 --out data/processed/ny-session
```

**Integration warning:** Existing `forexlab.intelligence` enforces fixed 24h D1/4h H4 bar durations. DST-adjusted NY session bars deliberately do **not** satisfy that assumption. We must version a compatible market-calendar contract and test signal parity before using these bars in strategy selection or LEAN. The current session builder is a separate QA/research tool only.

### Next release gate

Acquire rights-cleared genuine bid/ask data; compare UTC and NY-session candles against the chosen broker's actual quote convention; then verify risk math against MT5 demo `order_calc_profit` and `order_calc_margin`. Keep live execution disabled. Never infer a 95% win rate from synthetic unit tests.

Primary vendor references: [MT5 order_calc_profit](https://www.mql5.com/en/docs/python_metatrader5/mt5ordercalcprofit_py); [FXCM rollover convention](https://www.fxcm.com/markets/help/rollover-when-is-rollover-booked/).
