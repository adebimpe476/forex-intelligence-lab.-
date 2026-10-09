# v0.7 · Experiment journal and mobile research control

**Research-only.** No LEAN backtest, no broker account, no training on licensed intraday data, no live quote feed, no order execution, no profitability findings. This is a testable software foundation.

## What we built

- The standalone five-timeframe research policy and quantitative risk calculations from previous versions remain offline prototypes.
- `research_lab.py` runs already-existing, intentionally limited **daily reference diagnostics** on synthetic or Federal Reserve H.10 daily observations. Each experiment captures input byte hash, strategy name, cost assumption, dates, programmatic status, and results; no parameter search or machine learning occurs here.
- Each JSONL record stores a chained SHA-256 digest of the previous record. The local ledger rejects corrupt or duplicate records; concurrent writers receive a fail-fast lock error. **This detects accidental alteration but is not cryptographically tamper-proof:** an attacker who can rewrite the file could recalculate the hashes; signed remote anchors and access controls remain to be implemented.
- Read-only `GET /api/experiments` exposes metadata about already-recorded runs. It does not run experiments or accept POST submissions. If ledger integrity fails, return HTTP 503 instead of serving the records.
- Dashboard has Overview, Experiment Lab, Pipeline tabs; FX historical chart is a dated **24-row FRED sample, not a live chart**. The trading scanner always displays WAIT without market connectivity.

## Run the local demo (software workflow, NOT a strategy evaluation)

```bash
pip install -e '.[dev]'
pytest -q
python scripts/create_synthetic_fixture.py --out artifacts/synthetic_daily_fixture.csv
forexlab experiment-run artifacts/synthetic_daily_fixture.csv \
  --pair EURUSD --strategy trend_following --source-kind SYNTHETIC_TEST \
  --acknowledge-nontradable
forexlab experiment-run artifacts/synthetic_daily_fixture.csv \
  --pair EURUSD --strategy breakout --source-kind SYNTHETIC_TEST \
  --acknowledge-nontradable
forexlab experiment-audit
uvicorn forexlab.server:app --host 127.0.0.1 --port 8000
```

Browse `http://127.0.0.1:8000` on the same trusted computer. `artifacts/experiments/ledger.jsonl` remains private to that machine and is ignored by Git. The generated synthetic fixture is also ignored. **Do not deploy this open prototype to the public internet.** No authentication, HTTPS, browser session security, rate limiting, brokerage credentials, or network isolation is present yet.

## Interpret records correctly

- `diagnostic_backtest` uses one daily fixing and hypothetical basis point turnover costs; there is no OHLC, bid/ask, slippage, swaps, margin, broker order sizing or real fill simulation.
- These data can test code behavior and learn how experiment logging works. Even the field `last_20pct_untouched_diagnostic` is not a genuinely sealed holdout once reviewed repeatedly in strategy selection.
- `validated = false`, `execution_allowed = false`, and `out_of_sample_verified = false` cannot be flipped by this ledger.
- 95% winning trades can produce negative net expectancy; win rate is not a target to optimize without risk and return context.

## Future experiment engine tasks

1. Source-approved tick/quote data with content hashes and reproducible market-session rules.
2. Pin LEAN engine SHA and simulator configuration, compare independent benchmark fills.
3. Implement walk-forward purging, an experiment registry for all attempts, transaction-cost and broker spread simulation, and an untouched final evaluation split.
4. Enforce strategy promotion gates: no demo automation before validated results and explicit approval.
5. Build authenticated mobile access with separate research, paper and eventual live permissions, broker reconciliation and independent risk circuit breakers.
