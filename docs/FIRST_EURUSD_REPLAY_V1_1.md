# First EUR/USD private replay — v1.1

**State:** Code tested only with synthetic HistData-format data. No genuine vendor file has been received. No LEAN backtest, ML training, broker or account connection has been completed. This is NOT a strategy recommendation.

## How to obtain the first authorized sample

1. Manually review the current data provider's applicable terms and obtain any necessary permission for internal quantitative research. For HistData's documented generic ASCII ticks, download a **EURUSD** one-month generic ASCII TICK ZIP (not a one-minute OHLC file). Follow the provider's instructions; do not disclose credentials to the project or automate terms acceptance.
2. Keep original ZIPs in a private local folder, outside the publicly visible GitHub repository. Preserve any invoice, rights evidence, and download URL as private records.
3. Make a **private** JSON declaration file, for example `~/private/eurusd_rights.json`:

```json
{
  "provider": "HistData",
  "pair": "EURUSD",
  "source_url": "https://www.histdata.com/",
  "rights": {
    "quant_research": true,
    "evidence_url": "https://www.histdata.com/f-a-q/"
  }
}
```

**These links are examples of locations to review, NOT statements that the vendor has granted your requested rights.** Only set `quant_research` to true after independently reviewing the applicable terms or receiving authorization. Commercial redistribution and ML training are NOT authorized by this declaration.

4. With the package installed, run:

```bash
pip install -e '.[dev]'
forexlab first-replay ~/private/DAT_ASCII_EURUSD_T_202403.zip \
  --declaration ~/private/eurusd_rights.json \
  --out ~/private/forexlab-replay-202403
```

Output is a **new private folder** containing the normalized UTC quote CSV, self-declared data-rights manifest, `reference_simulation.json`, LEAN-formatted ZIPs under `lean-staging/`, and `intake_report.json` linking their hashes.

The acceptance gate requires at least 50 source ticks over 20 observed M15 buckets and rejects impossible or extreme spread profiles. This tiny threshold is a **pipeline smoke-test threshold**, NOT enough history for strategy optimization or profitability. Long gaps and quote-feed differences remain explicit limitations. HistData fixed EST (`UTC−05:00`) timestamps are *not* US Eastern local time with DST. Market metadata must be independently compared with the actual file and provider docs.

## What the completed CLI test proves

- Correct parsing of a synthetic generic ASCII ZIP and UTC conversion;
- Deterministic file hashes, explicit private rights declaration, quote validation and spread/coverage descriptive audit;
- Run of our **reference** quote-side simulator; creation of LEAN quote-tick ZIPs without falsely labelling the quotes as FXCM/OANDA;
- Refusal of duplicate target folders, mismatched pairs, unlicensed declarations and bad data.

## What it does NOT prove

- That the data are authentic or legally usable for all purposes;
- That LEAN can read the custom market without registered market-hours and symbol properties;
- That historical PnL is profitable, realistic, out of sample, or reproducible on another broker;
- That AI training or commercial use is approved; or
- That any order can be placed.

`actual_lean_run`, `historical_source_externally_verified`, `rights_independently_verified`, `performance_validated` and `execution_allowed` all remain **false**. The next gate is to feed the identical **approved** quote files into a pinned LEAN engine, record read counts and compare timeline/fills.

**LEAN build CI:** `.github/workflows/lean-oss-build-smoke.yml` pins upstream source revision `80e7843f645673bcbeaab963049f76f20f6785e1`. A successful compiler run does not satisfy the end-to-end data/backtest gate.
