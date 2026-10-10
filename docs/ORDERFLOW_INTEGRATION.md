# Gold + NASDAQ order-flow integration under a zero-new-subscription constraint
**Status: researched and computation skeleton implemented; NO live NQ/GC order-flow feed connected and NO live execution.**

## Trading signals must include order flow, but only when genuine feed rights and quality exist

The current demo-order runner uses broker M5 OHLC *only*. It does **not** call
`orderflow.py` or `orderbook.py` and must not be labeled "order-flow validated".
Do not confuse an MT5 broker's CFD tick volume with centralized CME executed trade volume.

### Measurements and provenance
- `orderflow.py`: for an exchange-trade tape with explicit UTC timestamps, unique
  increasing sequence IDs, tick-aligned trade price, actual quantity and trusted
  aggressor side (BUY lifting ask, SELL hitting bid). Computes 1m/5m/15m bid-vs-ask
  footprint at price, delta, cumulative volume delta, POC, diagonal imbalances and
  stacked imbalances. Simple unvalidated *observations* can describe price/delta
  divergences or aggressive selling without a new low. These are NOT proof of
  absorption or predictive edge.
- `orderbook.py`: for independently sourced full-depth L2 *snapshots*, computes
  top-of-book, visible bids/asks, resting-volume imbalance and changes between
  successive snapshots. It does not know whether a volume decrease came from a
  cancellation, execution or data reset without event reconciliation.
- **Heatmap/icebergs**: a true Bookmap-style heatmap requires a *continuous
  time-indexed depth stream* and correct replay; iceberg/hidden liquidity
  inference usually requires richer MBO/market-by-order events and specialized
  validation. These are NOT implemented and cannot be reconstructed from OHLC.
- NQ and MNQ are CME equity futures, GC and MGC are COMEX gold futures.
  A futures order-flow signal used to trade NAS100 or XAUUSD **CFDs** needs an
  explicitly measured, broker-specific basis/lead-lag and matched instrument
  contract roll/session clock; never directly apply the futures price as CFD entry.

### Feeds: available paths
**Best zero-additional-expense possibility:** reuse the user's existing Bookmap
and footprint software subscriptions/data entitlements, *provided* they allow
programmatic onTrade/onDepth callbacks or recording under the applicable license.
Bookmap offers public L1 API examples for onTrade/onDepth:
https://github.com/BookmapAPI/ai-skills/tree/main/references
https://github.com/BookmapAPI/python-api
This requires an on-machine add-on/bridge with a verified API version. The
existing charts alone do not prove that an accessible or redistributable feed exists.

**Fallback:** with no currently entitled CME/COMEX real-time feed, use exported
historical trades only if licensed; automated **demo candle strategy can run
separately but MUST be labeled "NO_ORDERFLOW_DATA"**. No paid data is purchased
without the user's authorization.

**Free trade/depth plumbing test:** some crypto spot exchanges expose public
trades and depth. It may test ingestion/stack imbalance arithmetic, but is NOT
CME NQ/GC market data and may not validate a Gold/NASDAQ futures strategy.

Official source notes:
- CME market data access and market depth:
  https://www.cmegroup.com/market-data/real-time-and-historical-data.html
- Bookmap depth and trade display:
  https://bookmap.com/knowledgebase/docs/KB-SettingUpAndOperating-HeatmapMainChart
- MT5 COPY_TICKS_TRADE vs quote updates:
  https://www.mql5.com/en/docs/series/copyticks

### Prerequisite conditions before an order-flow strategy can authorize even a demo fill
1. Known, documented **source ID, data rights and exchange**; P0 fail without them.
2. Genuine source-side aggressor marks, trade sizes and timestamps; no guessing
   from candles, MT5 ticks or screenshot colors.
3. Stable symbol, contract month, tick size, exchange clock and synchronized basis
   against the execution broker. Explicitly reject stale feeds or session rolls.
4. Reliable data-gap detection, depth sequence continuity, duplicate rejection.
5. Independent historical labeled backtest with full costs, then forward demo.
6. Strategy should issue `WAIT` when delta/CVD/footprint feed is unavailable
   rather than silently treat nonexistent confirmation as positive.
7. The existing MT5 runner remains demo-only until those conditions pass.

### Progress made
Implemented computation and quality guards for completed 1m/5m/15m
footprints and cumulative delta, as well as basic L2 liquidity measures.
Added offline tests using **synthetic prints/snapshots for software correctness
only**. NO external provider is connected, no user signal is confirmed,
and no claim of live order-flow trading is justified.

## Next implementation
Write a local Bookmap L1 bridge and event recorder **only after** verifying the
installed version, user entitlements, source license and the exact API callbacks.
The bridge should forward schema-versioned events into the Python footprint/depth
pipeline; the MT5 risk engine should fail closed on missing/invalid evidence.
