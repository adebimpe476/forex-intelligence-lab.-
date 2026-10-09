# v1.0 — Authentic-data intake and LEAN feasibility gate

**2026-10-09 status: code tested against SYNTHETIC files. Genuine data NOT acquired. No actual LEAN engine run and no validated trading strategy.**

## Sources and specific rights questions

- **TrueFX:** https://www.truefx.com/truefx-terms-and-conditions/ permits an authorized user's *internal* historical-data analysis and prohibits redistribution. Historical ticks are indicative, not necessarily executable at the eventual MT5 broker. The user must accept/observe the applicable terms; do NOT create an account or accept them automatically. Commercial product, onward redistribution, AI model training and API usage require separate review.
- **HistData:** https://www.histdata.com/f-a-q/data-files-detailed-specification/ documents bid/ask generic ASCII historical ticks. The timestamp is `YYYYMMDD HHMMSSmmm` in fixed EST = UTC-05:00 *without DST adjustment*. Our importer handles that explicitly. Permission to store, use in ML, redistribute or operate commercially must be independently established; no public raw archive may be checked into Git.
- **Dukascopy:** the existing daily and hourly BI5 decoders are synthetic-fixture tested. Do not assume an agreement covering Dukascopy XML feed covers raw historical BI5 or any AI-training purpose.

## Local data flow

1. Confirm permissions with the provider for internal quantitative backtesting and the intended use. Manually download an authorized EURUSD monthly **generic ASCII tick** ZIP. Avoid placing vendor data into public GitHub.
2. With the package installed, run:

```bash
forexlab import-histdata /secure/EURUSD_202403.zip --pair EURUSD --out data/processed/private-histdata
forexlab lean-preflight --data-manifest data/processed/private-histdata/EURUSD_202403_manifest.json
```

3. The converter rejects malformed archives/quotes, wrong month and pair, bad timestamps, too much data and crossed bid/ask. It writes a normalized timestamp/bid/ask file and SHA256 source metadata. **It does not verify a license or certify the source.**
4. Compare the normalized sample with the source archive and published time specifications. Run `forexlab qualify-data` only after supplying a separate rights declaration and source-evidence record; self-declaration is NOT legal clearance.

## Open-source LEAN route

The official LEAN CLI `lean backtest` requires a paid QuantConnect organization, according to its official docs: https://www.quantconnect.com/docs/v2/lean-cli/backtesting/deployment

The separately open-sourced engine can be built from https://github.com/QuantConnect/Lean with a compatible pinned .NET SDK. The official source README documents this alternative. On a machine with dependency-download access:

```bash
git clone https://github.com/QuantConnect/Lean.git
cd Lean
git rev-parse HEAD                  # pin the exact revision and save it in the experiment journal
dotnet --version                    # compare with the SDK version declared by the checkout
dotnet build QuantConnect.Lean.sln --configuration Release
```

To run the engine, additionally configure its Launcher, *the actual provider market*, market hours, symbol properties, dataset folder, quote reader, fees, fills, and dates. Custom provider quotes must not be misrepresented as OANDA or FXCM. Our LEAN ZIP exporter is **format staging**, not proof of an engine run. A no-order data ingestion smoke test precedes any portfolio simulation.

## Do not assert equivalence without actual execution evidence

Required: rights-authorized and audited source ticks, raw/normalized SHA256, a pinned LEAN engine SHA, LEAN logs and data-read counts, exact bid/ask and clock parity, fill/slippage/commission/financing terms, and a locked out-of-sample holdout. No capital/order execution in any of these research steps. None of these final acceptance requirements has passed yet.
