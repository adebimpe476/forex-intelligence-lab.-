# P0: two-week Gold/NASDAQ replay WITHOUT looking into the future

**Status: software research prototype only — no authentic Gold/NASDAQ broker history
or Bookmap/NQ/GC historical order-flow tape is in the repository. No historical
P&L is claimed. No broker orders are ever submitted by this replay.**

## 1. Freeze the test *before* importing past market data
- Pre-registered test dates: **2026-09-28T00:00:00Z through 2026-10-10T00:00:00Z
  exclusive** (Monday Sep 28 through Friday Oct 9, two market weeks).
- Earlier history (default 7 UTC calendar days before test) only warms up the
  detector; it is not counted as an evaluation trade.
- Hypothesis: 20-M5-closed-bar past-high/low breakout + first confirmed later
  completed-M5 rejection on retest, within six bars.
- One trade entry per UTC day, max 0.25% equity risk/trade (default), initial
  2R take-profit, and 1.25R BE decision on a previously completed candle. The
  BE change cannot take effect before the next bar opens.
- Pin risk, slippage, commission, tick/contract specification, and signal parameters
  before looking at results. Do not optimize on these two weeks repeatedly.
- Results from these weeks are a **retrospective demonstration**, NOT an independent
  fresh holdout given the founder has already seen selected Oct 2026 charts.
  A truly unseen forward-demo or later closed historical period is required.

## 2. Past-only guarantee (the 'no crystal ball' test)

For each *completed* 5-minute bar `t`:
1. Receive only market information timestamped no later than the CLOSE of `t`.
   The latest 5-minute OHLC is only published once that bar is complete.
2. Detect breakout/retest using `bars[:t+1]`; prior levels are calculated from
   earlier bars, not future swing highs, current day's high/low, ZigZag hindsight,
   or revised indicators.
3. If a candidate is produced, the earliest fill is **at the following bar's OPEN**,
   plus actual bid/ask proxy and adverse entry slippage; only then determine lot,
   SL and TP.
4. Intrabar events are processed after that entry. If both SL and TP lie inside
   the same M5 range, **count the stop first**; high/low order is unknown from OHLC.
   Stops gapped through execute at the adverse OPEN, not the ideal stop level.
5. A BE trigger seen at completed close `t` may only change stop at next
   bar `t+1`. Do not backdate decisions into bar `t`.
6. Reject stale, nonconsecutive signal-to-entry bars and abandon setup after
   disconnected gaps. Do not fill after dataset end.
7. A research report shows realized P&L separately from any still-open unrealized
   mark-to-market estimate; never silently assume an open trade wins.

Tests check: signal cannot fill on its own forming candle, next-open entry,
future data mutations do not change earlier closed outcomes, both-trigger
conservative SL, breakout cancellation on data gaps and no end-window leakage.

**Important cost-model caveat**: historical MT5 *bar spread points* are NOT
the original bid/ask quote stream at fill milliseconds. Bar-only exits use
simulated quote sides, static point value, and explicit slippage/commission
assumptions. Broker margin, rollover swap, real latency and event slippage
cannot be established from 5m OHLC. The report is therefore a simplified
backtest, not execution-quality realized P&L.

## 3. Export without buying data

On an existing **Windows** computer with desktop MetaTrader 5 installed,
logged into your **USD-denominated broker demo account**, from repository root:

```powershell
pip install -e ".[dev]"
pip install MetaTrader5
python -m forexlab.export_mt5_history --symbol XAUUSD --symbol NAS100 --start 2026-09-28 --end-exclusive 2026-10-10 --output C:\forexlab-private\two-weeks
```

**Replace XAUUSD and NAS100 with the EXACT available broker symbol names**.
This reads only M5 historical bars and contract metadata; **it places no trades**.

Exporter creates per-symbol:
- `<symbol>_M5_BID.csv`, with explicit UTC open, BID OHLC, historic bar spread
  in broker *points*, and warming-up bars.
- `<symbol>_M5_BID.provenance.json` with SHA256, broker server, symbol,
  point size and the current broker-computed approximate $/unit/lot.

Review your broker's research/data use terms. The exporter defaults to
`"research_permission_declared": false` and does NOT assume rights.
Only if truly permitted, change that single setting to `true`.
Do NOT commit original licensed market data, broker account details,
strategy results or provider access credentials into public GitHub.

## 4. Replay and report for each symbol

Choose adverse entry/exit slippage (in GOLD/NASDAQ *price units*) and
roundtrip broker commission USD per 1.0 lot **before** inspecting performance.
Illustrative numbers below are merely explicitly chosen test assumptions,
not verified broker costs:

```powershell
python -m forexlab.run_two_week_replay --bars C:\forexlab-private\two-weeks\XAUUSD_M5_BID.csv --manifest C:\forexlab-private\two-weeks\XAUUSD_M5_BID.provenance.json --slippage-price 0.20 --commission-usd-per-lot 7.00 --out C:\forexlab-private\gold-replay-report

python -m forexlab.run_two_week_replay --bars C:\forexlab-private\two-weeks\NAS100_M5_BID.csv --manifest C:\forexlab-private\two-weeks\NAS100_M5_BID.provenance.json --slippage-price 2.0 --commission-usd-per-lot 7.00 --out C:\forexlab-private\nasdaq-replay-report
```

Replace the demonstration costs with actual verified broker costs; never
interpret these example costs as universal. A broker's CFD point/lot value
may be different. The USD/price-unit/lot estimate is computed at export time
and could differ historically if FX conversion rates change.

Outputs:
- `two_week_report.json`: sample and data caveats, trade counts, win rate,
  net realized USD after modeled costs, profit factor, realized-equity drawdown,
  rejected setups and unreconciled end-of-sample positions.
- `candle_only_trades.csv`: each hypothetical setup with dated signal-bar
  opening, candle-close decision, next-bar fill, SL/TP, size, exit reason, P&L.

**Do not use sample fixtures, chart screenshots, FRED daily FX fixings,
GBPUSD/EURUSD ticks or guessed NQ/GC futures prints as substitutes for these
two-week broker files.**

## 5. Two separate 'with vs without order flow' comparisons

For a genuine NQ/GC **licensed exchange trade tape**, with actual UTC
timestamps, unique increasing sequence IDs, true trade quantity and
provider-trusted aggressor BUY/SELL, use the optional side-aware input.
A self-declared CSV+manifest is a technical gate only, not a license check.
The optional trade tape manifest must declare its full SHA256, actual
`exchange`, `contract_month`, `tick_size`, `source_url`,
`rights_evidence_url`, `research_permission_declared: true` and
`aggressor_side_verified: true`.

```powershell
python -m forexlab.run_two_week_replay --bars C:\forexlab-private\two-weeks\XAUUSD_M5_BID.csv --manifest C:\forexlab-private\two-weeks\XAUUSD_M5_BID.provenance.json --slippage-price 0.20 --commission-usd-per-lot 7.00 --out C:\forexlab-private\gold-with-flow-report --futures-trades C:\forexlab-private\GC_trades.csv --futures-trades-manifest C:\forexlab-private\GC_trades.provenance.json
```

This compares a basic candle replay with a **preliminary completed-bar delta +
imbalance confirmation filter** using the same broker OHLC execution model.
The algorithm never sees future footprint bars when choosing an entry.

**This is NOT a true complete footprint/Bookmap trading system yet.**
Historical full-depth L2 snapshot/replay feeds are required to test Bookmap
liquidity pull/stack, support walls or event-based iceberg behavior. Such feeds
have not been acquired/connected. Futures vs CFD basis, session clocks,
futures roll, data gaps and real feed rights must be verified independently.
Missing order-flow data means this mode rejects signals; it may not fill with
invented positive delta.

## 6. Judging whether the experiment worked
Report by market, in order, actual data coverage, no-lookahead tests,
number of qualifying signals, number of fills, modeled gross profit,
modeled costs, net USD, average expectancy in R, wins/losses,
max drawdown (intratrade conservative estimate if tick data available),
profit factor and sample-size uncertainty.

We should NOT say "we would have made $X" until authenticated market
history is processed. Even with a positive two-week result, reserve
a fresh untouched multi-week period, test realistic adverse costs, then
forward-test live market data on a demo account before considering any
live-money deployment.

## 7. Historical futures footprint / Bookmap source acquisition (October 10, 2026)

**No NQ/GC historical exchange data has been downloaded yet.** The two
realistic paths for zero *additional* payment are:

1. **Already recorded Bookmap feeds**: inspect the Windows machine's
   `C:\\Bookmap\\Feeds` folder for genuine `.bmf` market-data recordings for
   September 28–October 9. Bookmap's File > Record / File > Export supports
   saved market data with depth and trade prints. Past market hours that were
   never recorded are not magically recreated by Replay. Distinguish historical
   recordings from the short backfill cache and confirm license terms.

2. **New-user Databento historical credits**: Databento publicly advertises
   $125 startup credits toward historical market data for eligible newly
   registered accounts. This is **not** unrestricted free order-book history,
   nor proof that the user has credits or that signup needs no payment method.
   The historical CME/COMEX feed is `GLBX.MDP3`, and the volume-ranked
   front-month continuous symbols `NQ.v.0`, `GC.v.0` must be mapped to
   actual native contract IDs on each trading day. The `trades` schema
   supports footprints/CVD with producer-provided aggressor side, subject to
   `side=N` exclusions. `mbp-10` gives top-ten depth and `mbo` is full
   order event granularity. Prices must not be merged across roll without
   contract normalization.

   **First quote historical cost, without downloading or purchasing:**

   ```powershell
   pip install databento
   # Set $env:DATABENTO_API_KEY through your private OS secret configuration.
   python scripts/check_databento_historical_cost.py --remaining-free-credit-usd 125
   ```

   Replace 125 with the **actual credit remaining** as displayed in the
   provider's account portal. The script ONLY calls historical metadata
   `get_cost` and `get_dataset_range`. It performs no orders, trade-tape
   downloads, registration or billing operations. Review each schema and
   instrument estimate separately; start with **trades only** rather than
   blindly requesting all three expensive schemas.

   Before a downstream orderflow backtest, genuine trade prints must be
   converted with proper native `A=SELL`, `B=BUY`, `N=UNKNOWN` mapping
   and verified exchange timestamp + sequence/day resets, which this project
   does NOT yet implement for Databento DBN. No claim of complete CME/COMEX
   absorption/heatmap is made from trades-only history.

Provider documentation:
- Databento free credits and cost estimation: https://databento.com/pricing
- Databento historical cost method: https://databento.com/docs/api-reference-historical
- Databento trade aggressor conventions: https://databento.com/docs/standards-and-conventions
- Bookmap feed recording/export: https://bookmap.com/knowledgebase/docs/KB-SettingUpAndOperating-ExportImportBookmapFiles
