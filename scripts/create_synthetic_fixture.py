"""Generate explicitly synthetic daily data for *software QA only*.

Never confuse this with forex quotes, historical market observations or trade signals.
"""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic, nontradable software QA fixture")
    parser.add_argument('--out', default='artifacts/synthetic_daily_fixture.csv')
    parser.add_argument('--rows', type=int, default=320)
    args = parser.parse_args()
    if not 180 <= args.rows <= 10000:
        parser.error('--rows must be between 180 and 10,000')
    index = pd.date_range('2020-01-01', periods=args.rows, freq='B')
    t = np.arange(args.rows)
    # Completely artificial wave trajectories; explicitly not sampled from a broker.
    prices = {
        'date': index,
        'EURUSD': 1.12 * np.exp(.0002*t + .02*np.sin(t/9)),
        'USDJPY': 111 * np.exp(.0001*t + .013*np.sin(t/7+.3)),
        'GBPUSD': 1.30 * np.exp(.00015*t + .024*np.sin(t/11+.8)),
    }
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(prices).to_csv(target, index=False)
    print('SYNTHETIC QA ONLY: generated', args.rows, 'invented daily reference-style rows in', target)

if __name__=='__main__':main()
