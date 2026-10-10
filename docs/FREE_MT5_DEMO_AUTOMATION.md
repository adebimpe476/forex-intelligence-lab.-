# Free MT5 demo automation: what is implemented and what is not

**Status (2026-10-09): code added for review. Not installed, compiled, connected, forward-tested or deployed. The strategy has NO proven edge. DEMO ACCOUNT ONLY.**

## Cost reality

- Code, Python, MetaTrader 5 desktop, a broker demo account and local Strategy Tester are available without a software subscription.
- A **Windows computer must stay powered, connected and logged into MT5** while this Python runner trades. Mobile MT5 does not host Python bots. Electricity and Internet are not literally free.
- Broker spreads, commission, swaps, slippage and any eventual live account funding are real costs.
- A 24/7 rented VPS usually costs money. Broker-sponsored no-fee VPS access is sometimes available, but is not guaranteed.
- Professional real-time NQ/GC futures order flow, Bookmap or exchange data are NOT included free or used here. **This prototype only reads broker M5 OHLC**.

## What runs automatically (on DEMO)

1. Read the *completed* 5-minute candles directly from each symbol in the logged-in MT5 terminal.
2. Detect a 20-candle prior-high/low **closing breakout** with 0.1xATR minimum displacement.
3. Wait up to six completed M5 candles for the broken level to be retested and rejected with a directional candle.
4. Require the latest quote to be fresh, spread <= 0.15xATR and market execution price within 0.2xATR of the confirmed candle close. Decline chase entries.
5. Calculate side-aware entry using MT5 bid/ask, stop beyond the retest candle and 2R target. **This prototype does not filter intermediate support/resistance, macro news, CVD or footprint.**
6. Compute equity-budgeted lots using broker-specific `order_calc_profit`, volume min/max/step, margin and a 15% estimated costs cushion.
7. Safety gates: hard DEMO-only account check, no existing account positions or pending orders when submitting, max 1 entry attempt per UTC day, per-trade 0.25% of equity by default, halt new entries after 1% equity drawdown from first start of the UTC day, server order_check, bracket SL+TP, no auto retry, 1.25R breakeven attempt on fills by this script.
8. Save local trade-attempt state under ignored `artifacts/mt5_demo_state.json`. The one-attempt lock persists across restarts.

**Limitations of the daily-loss gate:** It anchors to the equity when first launched on that UTC day; it cannot retrospectively account for losses made before launch. Existing-position checks avoid simultaneous new orders but do not remove all account-level hazards. Use a separate *dedicated* demo account.

**Important:** Stops can slip in gaps or thin conditions. The 15% cushion does NOT cap realized losses. The baseline is an unvalidated mechanistic hypothesis, not a substitute for a backtest, paper evidence, or discretionary order-flow confirmation.

## How to run on a free Windows computer

1. Install MetaTrader 5 desktop from your MT5 broker, open a **dedicated DEMO** account, log in and keep desktop open.
2. In MT5 enable algorithmic trading and check the exact broker symbols in Market Watch, for example `XAUUSD`, `GOLD`, `USTEC`, `NAS100`. Symbol names vary by broker; **do not copy this example without checking**.
3. Install Python 3.11+ and project dependencies from repository root:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e ".[dev]"
   pip install MetaTrader5
   python -m pytest tests/test_mt5_demo_automation.py -q
   ```
4. Run **signal-only** on two symbols (replace placeholders with your broker's exact names):
   ```powershell
   python -m forexlab.mt5_demo_runner --symbol XAUUSD --symbol NAS100
   ```
5. On a verified DEMO account only, use fully automated simulated order placement:
   ```powershell
   python -m forexlab.mt5_demo_runner --symbol XAUUSD --symbol NAS100 --demo-execute
   ```
6. View terminal output and MT5 History/Journal. Stop with Ctrl+C. The safety lock refuses REAL/contest accounts even if `--demo-execute` is given.

## Before any live-money system

Mandatory: realistic broker spread/commission/funding data; reproducible walk-forward backtests; weeks of forward-demo fills; live broker order and position reconciliation across reconnects/restarts; news calendar filter; account-wide risk reconciliation; accurate volatility/session controls; per-symbol fill policies; explicit user approval. A deterministic approved signal engine with a separate execution/risk actuator is the intended longer-term architecture.

**No actual MT5 connection or order was made during this repository change. No claims of backtest profitability or test execution are made until CI/local evidence is inspected.**
