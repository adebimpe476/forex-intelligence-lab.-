# V1.0 real-data intake and LEAN feasibility gate

**Status 2026-10-09: Source formats verified against documentation, code tested using synthetic fixtures only. NO genuine sample acquired; NO actual LEAN backtest run.**

## Real data options (independently reviewed; not licenses acquired)

1. **TrueFX**: https://www.truefx.com/truefx-terms-and-conditions/ offers historical FX data for an authorized user's *internal research/analysis* and forbids redistribution. Prices are *indicative*, not broker executable. User must follow registration/agreement; do not automate acceptance of terms. Any AI-training, commercial product, or data sharing needs separate rights review.
2. **HistData generic ASCII tick quotes**: https://www.histdata.com/f-a-q/data-files-detailed-specification/ explicitly documents timestamp `YYYYMMDD HHMMSSmmm`, bid, ask, volume and the crucial **fixed EST / UTC−05 with NO DST adjustment**. A local ZIP importer is now provided; permission to analyze/store/train/publish must be established separately. Download from the provider through its stated process and never add vendor quotes to GitHub.
3. **Dukascopy**: its daily BI5 and legacy hourly formats are in existing modules. Do not assume Dukascopy XML data agreements extend to tick `.bi5` files, nor that the files are free for AI training/commercial usage.

## User-approved manual data intake (no secrets)

After confirming your rights with the provider, download **one small EURUSD generic ASCII tick ZIP**. Place it outside the public repository or under ignored local data. For example:

```bash
forexlab import-histdata /secure/source/EURUSD_202403.zip --pair EURUSD --out data/processed/private-histdata
forexlab lean-preflight --data-manifest data/processed/private-histdata/EURUSD_202403_manifest.json
```

The importer rejects mismatched file months, invalid prices, crossed quotes, unsafe archive paths, huge input, unordered timestamps and unsupported pairs. It computes SHA-256 on raw/normalized files, preserves bid and ask and timestamps, but **does not assert legal clearance**. Check the provider's time conventions against actual file specifications before production use.

## LEAN from open-source source, without paid CLI

The official Lean CLI (`lean backtest`) requires a paid QuantConnect organization (https://www.quantconnect.com/docs/v2/lean-cli/backtesting/deployment). The *engine source* is available via https://github.com/QuantConnect/Lean and officially documents building on Linux with dotnet SDK and running the compiled Launcher. These are different products. Verify the required SDK version against a **pinned Git SHA** before building:

```bash
# On a machine permitted to download dependencies and run .NET:
git clone https://github.com/QuantConnect/Lean.git
cd Lean
git rev-parse HEAD  # record and pin this version
dotnet --version
# Use SDK version specified by this checkout. Build; expect dependency downloads.
dotnet build QuantConnect.Lean.sln --configuration Release
# The Launcher requires its own verified configuration, data folder, algorithm and provider market config.
```

An imported provider market is NOT interchangeable with `oanda` or `fxcm`, and native LEAN QuoteTick ZIP staging is not proof of an actual LEAN run. Configure market hours, symbol specifications, quote tick data reader, fees/fills, and timestamps; run an **orders-disabled ingest smoke test first**, record its logs, then compare signals and fills against our independent reference engine. Genuine bid/ask quotes are still indicative relative to the eventual execution broker.

## Evidence gate before claiming LEAN equivalence

Require (1) provider rights evidence; (2) immutable raw and normalized SHA256; (3) archived LEAN source git SHA and output logs/results; (4) timestamp/quote parity counts; (5) fully declared fill/commission/slippage/swap assumptions; (6) independent holdout; (7) no-live-order guarantee. 

**Do not claim a 95% win rate, proven AI model, actual LEAN execution, or broker integration before these evidence gates pass.**
