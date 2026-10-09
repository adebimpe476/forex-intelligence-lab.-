# Architecture Decision Record — 2026-10-09

## Objective
Mobile-controlled, research-first foreign exchange quantitative system with reproducible historical tests, strategy discovery, machine-learning filters and eventually supervised/exclusively approved MT5 demo execution.

## Final intended architecture
1. **Data plane**: immutable raw files + provenance; bid/ask bars and tick streams from licensed FX providers; point-in-time macro releases; UTC normalization; broker contract specification; quality and latency metrics.
2. **Research plane**: Python feature computation; versioned hypotheses; strictly time-ordered train/validation/test; strategy search accounting for all trials; regime and correlation filters.
3. **Simulation plane**: QuantConnect LEAN research/backtesting adapter; independent Python reference simulator for parity tests; spread, slippage, swaps and broker-specific fill model.
4. **Signal plane**: version-pinned approved strategies only; M15/M30/H1/H4/D1 cross-timeframe features; timestamped BUY/SELL/WAIT; no trading from research agent suggestions without validation.
5. **Execution plane**: independent MT5 bridge/EA, paper first; approved broker + contract specifications; position reconciliation; idempotency key/order de-duplication; stale quote reject; connection-loss safe state; max-loss circuit breakers; kill switch. Not implemented.
6. **Control plane**: FastAPI + Next.js/Lightweight Charts mobile-friendly interface, RBAC/2FA, audit trail, alerts. Current prototype serves static sample history read-only through FastAPI; Next.js is not yet included.

## Important constraints
- Mobile MT5 apps do **not** run custom EAs. Orders must execute on a trusted Windows terminal/VPS or supported server, not on a sleeping phone.
- LEAN and MT5 do not form a ready-to-run officially supported integrated solution; adapter is an engineering task.
- FRED H.10 is *one daily indicative observation*, not an OHLC bar, order flow, transaction database or valid M15 backtest source.
- No full 1999–2026 bytes are archived in this repo yet. We verified full-series coverage through authenticated data retrieval and archived a short, dated, verifiable snapshot. `forexlab fetch-fred` is provided to archive full daily series on a machine with network access.
- Spot FX decentralization means no public dataset of every market order worldwide exists.
- All live execution remains off until test evidence, authorized broker credentials, broker constraints and explicit user permission.

## Strategy search / qualification
- Define hypothesis BEFORE research; log every tested variant.
- Clean price series; normalize missing data correctly. Never fill missing OHLC/tick data with invented prices.
- Use expanding or purged walk-forward validation and reserve a strictly untouched chronological final holdout.
- Include realistic bid/ask, transaction costs, financing, spreads, market hours, outage and gap scenarios.
- Test performance by pair, era, volatility regime and broker environment.
- Evaluate net expectancy, profit factor, total return, max drawdown, calibration, trade sample, error bars and turnover. Win rate alone never sufficient.
- Prohibit martingale/loss recovery/infinite averaging as a shortcut to high win rates.

## Execution decision
Start demo and read-only feed after baseline audit. Only one controlling live signal authority. EA is a bounded broker actuator and safety layer, not an independent second trading brain.
