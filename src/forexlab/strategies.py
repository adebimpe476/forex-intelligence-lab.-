"""Three transparent baseline *hypotheses*, NOT verified profitable strategies.

Signal is calculated at the *close* of date t using information up to t.
Backtest deliberately delays execution to the NEXT daily close to prevent
receiving returns from the bar whose close generated a signal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _prepare(prices: pd.Series) -> pd.Series:
    x = pd.to_numeric(prices, errors="coerce").astype(float)
    if (x.dropna() <= 0).any():
        raise ValueError("Prices must be positive")
    return x


def trend_following(prices: pd.Series, fast: int = 20, slow: int = 80) -> pd.Series:
    """Fast/slow trailing means; 0 until both are fully warm."""
    if not 2 <= fast < slow:
        raise ValueError("Require 2 <= fast < slow")
    p = _prepare(prices)
    a = p.rolling(fast, min_periods=fast).mean()
    b = p.rolling(slow, min_periods=slow).mean()
    s = pd.Series(np.where(a > b, 1, np.where(a < b, -1, 0)), index=p.index, dtype=int)
    return s.where(a.notna() & b.notna(), 0).rename("trend")


def breakout(prices: pd.Series, window: int = 40) -> pd.Series:
    """New closing breakout past prior N observed closes (no future bars)."""
    if window < 5:
        raise ValueError("window must be >= 5")
    p = _prepare(prices)
    prior_high = p.rolling(window, min_periods=window).max().shift(1)
    prior_low = p.rolling(window, min_periods=window).min().shift(1)
    return pd.Series(np.where(p > prior_high, 1, np.where(p < prior_low, -1, 0)),
                     index=p.index, dtype=int, name="breakout")


def mean_reversion(prices: pd.Series, window: int = 40, entry_z: float = 1.5) -> pd.Series:
    """Contrarian extreme relative to trailing mean (daily indicative research only)."""
    if window < 10 or entry_z <= 0:
        raise ValueError("Require window >= 10 and entry_z > 0")
    p = _prepare(prices)
    mean = p.rolling(window, min_periods=window).mean()
    std = p.rolling(window, min_periods=window).std().replace(0, np.nan)
    z = (p - mean) / std
    # Range/regime eligibility (small SMA separation); experiment, not validated.
    trend_gap = (p.rolling(10).mean() - p.rolling(window).mean()).abs() / p.rolling(window).mean()
    rolling_vol = p.pct_change().rolling(window).std()
    sideways = (trend_gap < 1.5 * rolling_vol * np.sqrt(window)) & rolling_vol.notna()
    return pd.Series(np.where((z < -entry_z) & sideways, 1,
                              np.where((z > entry_z) & sideways, -1, 0)),
                     index=p.index, dtype=int, name="mean_reversion")


STRATEGIES = {"trend_following": trend_following, "breakout": breakout, "mean_reversion": mean_reversion}
