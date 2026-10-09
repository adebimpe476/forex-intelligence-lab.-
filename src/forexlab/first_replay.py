"""One-command, non-executing historical EURUSD research intake and replay.

No network access, data-provider login, order execution, LEAN verification, or
legal determination. All private quote files and results must stay outside Git.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlparse

import pandas as pd

from .data_gate import qualify_dataset
from .histdata import decode_histdata_tick_zip
from .lean_format import to_lean_forex_tick_zips
from .quote_simulator import simulate_quotes, SimulatorConfig


def _safe_declaration(path: Path, pair: str) -> dict:
    """Require an explicit, reviewable rights declaration; never infer approval."""
    declaration = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(declaration, dict):
        raise ValueError('Expected a JSON rights declaration object')
    if declaration.get('provider') != 'HistData' or declaration.get('pair') != pair:
        raise ValueError('Source declaration provider/pair mismatch')
    source_url = declaration.get('source_url')
    rights = declaration.get('rights')
    if (not isinstance(source_url, str)
            or urlparse(source_url).scheme != 'https'
            or not isinstance(rights, dict)
            or rights.get('quant_research') is not True
            or not isinstance(rights.get('evidence_url'), str)
            or urlparse(rights['evidence_url']).scheme != 'https'):
        raise ValueError('Missing declared research permission or HTTPS evidence URLs')
    # An unverified yes-checkbox cannot be used to claim independent clearance.
    return {'provider': 'HistData', 'pair': pair, 'source_url': source_url,
            'rights': {'quant_research': True, 'evidence_url': rights['evidence_url']}}


def _profile_quotes(df: pd.DataFrame) -> dict:
    """Descriptive quote coverage for acceptance review; not broker verification."""
    t = pd.to_datetime(df['timestamp_utc'], utc=True)
    bid = pd.to_numeric(df['bid'], errors='raise')
    ask = pd.to_numeric(df['ask'], errors='raise')
    pip = 0.0001
    spreads = (ask - bid) / pip
    weekdays = t[t.dt.weekday < 5]
    buckets = t.dt.floor('15min')
    # UTC time buckets are a generic source-coverage diagnostic, not FX session cutoff.
    return {'ticks': int(len(df)),
            'weekday_dates_with_quotes': int(weekdays.dt.date.nunique()),
            'observed_m15_buckets': int(buckets.nunique()),
            'first_utc': t.iloc[0].isoformat(),
            'last_utc': t.iloc[-1].isoformat(),
            'median_spread_pips': round(float(spreads.median()), 4),
            'p95_spread_pips': round(float(spreads.quantile(.95)), 4),
            'max_spread_pips': round(float(spreads.max()), 4),
            'weekend_tick_count': int((t.dt.weekday >= 5).sum()),
            'same_timestamp_updates': int(t.duplicated().sum()),
            'max_observed_gap_seconds': round(float(t.diff().dropna().dt.total_seconds().max()), 3)
                         if len(t) > 1 else None,
            'source_coverage_is_not_broker_comparability': True}


def prepare_first_replay(archive: Path, declaration_path: Path, output_dir: Path,
                         *, pair: str = 'EURUSD') -> dict:
    """Stage a private source-linked reference replay with explicitly limited status.

    Fail closed on a bad rights declaration, mismatched ZIP content, insufficient
    tick/bar coverage, malformed quotes or output collisions. Results do not
    prove profitable backtesting or imply actual LEAN engine execution.
    """
    if pair != 'EURUSD':
        raise ValueError('First audited replay is explicitly limited to EURUSD')
    archive, declaration_path, output_dir = map(Path, (archive, declaration_path, output_dir))
    # Keep licensed quote files outside Git checkouts, including public ones.
    destination = output_dir.resolve()
    if any((folder / '.git').exists() for folder in (destination, *destination.parents)):
        raise ValueError('PRIVATE_OUTPUT_REQUIRED: output must be outside any Git repository')
    source = _safe_declaration(declaration_path, pair)
    if output_dir.exists():
        raise FileExistsError('Refusing to overwrite or mix with existing research outputs')
    df, source_audit = decode_histdata_tick_zip(archive, pair=pair)
    quality = _profile_quotes(df)
    # This is a *minimum QA fixture gate*, not an adequate historical strategy
    # sample: a full research evaluation needs months/years and separate feeds.
    if quality['ticks'] < 50 or quality['observed_m15_buckets'] < 20:
        raise ValueError('INSUFFICIENT_REPLAY_SAMPLE: need >=50 ticks in >=20 M15 buckets')
    if quality['median_spread_pips'] <= 0 or quality['p95_spread_pips'] > 10:
        raise ValueError('SUSPICIOUS_SPREAD_PROFILE_REQUIRES_MANUAL_REVIEW')

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.forexlab-stage-', dir=output_dir.parent) as stage_name:
        stage = Path(stage_name)
        normalized = stage / 'EURUSD_normalized_ticks.csv'
        df.to_csv(normalized, index=False)
        digest = sha256(normalized.read_bytes()).hexdigest()
        rights_manifest = {**source, 'kind': 'BID_ASK_TICK', 'sha256': digest}
        (stage / 'declared_data_rights.json').write_text(json.dumps(rights_manifest, indent=2), encoding='utf-8')
        qualification = qualify_dataset(normalized, stage / 'declared_data_rights.json', purpose='quant_research')
        if not qualification.get('technical_ready') or not qualification.get('research_ready'):
            raise ValueError('DATA_QUALIFICATION_FAILED: ' + str(qualification.get('reason')))
        reference = simulate_quotes(df, SimulatorConfig(pair=pair))
        (stage / 'reference_simulation.json').write_text(json.dumps(reference, indent=2), encoding='utf-8')
        lean = to_lean_forex_tick_zips(df, pair=pair, market='histdata', out_dir=stage / 'lean-staging')
        report = {'pipeline': 'private_histdata_eurusd_quote_reference_v1_1',
                  'source_archive_sha256': source_audit['source_sha256'],
                  'normalized_sha256': digest,
                  'rights_declaration_sha256': sha256(declaration_path.read_bytes()).hexdigest(),
                  'source_audit': source_audit,
                  'technical_quote_profile': quality,
                  'qualification': qualification,
                  'reference': {'file': 'reference_simulation.json',
                                'model': 'M15 EMA-crossover quote-side diagnostic; no financing or broker fills'},
                  'lean_staging': {'file': 'lean-staging/EURUSD_histdata_lean_export_manifest.json',
                                   'zips': len(lean['data']),
                                   'market_registration_needed': True},
                  'actual_lean_run': False,
                  'historical_source_externally_verified': False,
                  'rights_independently_verified': False,
                  'performance_validated': False,
                  'execution_allowed': False,
                  'warning': 'SELF-DECLARED permission only; sample is not a LEAN-verified, broker-executable or profitable backtest.'}
        (stage / 'intake_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        os.rename(stage, output_dir)
    return report
