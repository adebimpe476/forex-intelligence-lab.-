"""Chronological research-only ML baseline for daily directional hypotheses.

No strategy has been trained or approved with real historical data in the package.
Daily direction classification accuracy is NOT a tradable FX win rate.
"""
from __future__ import annotations

import pandas as pd
import numpy as np

FEATURE_NAMES = ('return_1d', 'momentum_5d', 'momentum_20d', 'volatility_20d', 'trend_distance_40d')


def make_daily_supervised_sample(prices: pd.Series, horizon: int = 1):
    """At t, features use up-to-t data; label is t+h; never fill unknown future."""
    if not 1 <= horizon <= 5:
        raise ValueError('horizon must be 1..5')
    p = pd.to_numeric(prices, errors='coerce').astype(float)
    r = p.pct_change(fill_method=None)
    features = pd.DataFrame({
        'return_1d': r,
        'momentum_5d': p.pct_change(5, fill_method=None),
        'momentum_20d': p.pct_change(20, fill_method=None),
        'volatility_20d': r.rolling(20, min_periods=20).std(),
        'trend_distance_40d': (p / p.rolling(40, min_periods=40).mean()) - 1,
    }, index=p.index)
    future = p.shift(-horizon) / p - 1
    labels = (future > 0).astype(int)
    valid = features.notna().all(axis=1) & future.notna()
    return features.loc[valid], labels.loc[valid]


def chronological_partitions(X: pd.DataFrame, y: pd.Series, gap: int = 2):
    """70/15/15 strictly ordered split with gap around each boundary."""
    if len(X) < 300 or not X.index.equals(y.index):
        raise ValueError('Need >= 300 aligned training observations')
    n = len(X)
    a, b = int(n*.70), int(n*.85)
    if a - gap < 50 or b - a - 2*gap < 20 or n - b - gap < 20:
        raise ValueError('Insufficient samples after gaps')
    return ((X.iloc[:a-gap], y.iloc[:a-gap]),
            (X.iloc[a+gap:b-gap], y.iloc[a+gap:b-gap]),
            (X.iloc[b+gap:], y.iloc[b+gap:]))


def fit_research_direction_model(prices: pd.Series) -> dict:
    """Fit a fixed baseline. Never tune parameters on final test split."""
    from sklearn.dummy import DummyClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, balanced_accuracy_score

    X, y = make_daily_supervised_sample(prices)
    (Xt, yt), (Xv, yv), (Xe, ye) = chronological_partitions(X, y)
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, random_state=14))
    model.fit(Xt, yt)
    dummy = DummyClassifier(strategy='most_frequent').fit(Xt, yt)
    out = {'trained_rows':len(Xt),'validation_rows':len(Xv),'holdout_rows':len(Xe),
           'model':'fixed LogisticRegression', 'data_type':'indicative daily close only',
           'TRADABLE_STRATEGY':False, 'VALIDATED':False,
           'caution':'Directional classifier, no trading execution or costs; accuracy != trading win rate.'}
    for tag,XX,yy in [('validation',Xv,yv),('untouched_holdout',Xe,ye)]:
        pred=model.predict(XX)
        out[tag]={'accuracy':float(accuracy_score(yy,pred)),
                  'balanced_accuracy':float(balanced_accuracy_score(yy,pred)),
                  'always_majority_accuracy':float(accuracy_score(yy,dummy.predict(XX))),
                  'start':str(XX.index.min().date()),'end':str(XX.index.max().date())}
    return out
