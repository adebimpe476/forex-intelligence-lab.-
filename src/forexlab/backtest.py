"""Conservative *research diagnostics*, not LEAN or an executable FX backtest.

FRED H.10 has one indicative fixing/day and no spread. The cost model is
hypothetical. No results from it should be interpreted as real tradable PnL.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from .strategies import STRATEGIES

MIN_OBS = 180


def diagnostic_backtest(prices: pd.Series, strategy: str,
                        cost_bps_per_position_unit: float = 2.0) -> dict:
    """Signals at close[t], presumed filled close[t+1], earn return t+1 -> t+2.

    Position held on return[t] is signal[t-2] rather than signal[t].
    Costs are illustrative basis points on absolute position change.
    """
    p = pd.to_numeric(prices, errors="coerce").dropna().astype(float)
    if len(p) < MIN_OBS:
        raise ValueError(f"Only {len(p)} observations: need >= {MIN_OBS} for diagnostic baseline")
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy}")
    signal = STRATEGIES[strategy](p)
    position = signal.shift(2).fillna(0).astype(int)
    daily_return = p.pct_change().fillna(0)
    changes = position.diff().abs().fillna(position.abs())
    fees = changes * (cost_bps_per_position_unit / 10000)
    pnl = position * daily_return - fees
    # Independent time ordered split; no optimization performed.
    split = max(1, int(len(pnl) * 0.8))
    def metrics(x, pos):
        x = x.astype(float)
        compound = (1 + x).cumprod()
        drawdown = compound / compound.cummax() - 1
        active = pos != 0
        return {"days": len(x), "active_days": int(active.sum()),
                "net_compounded_return": float(compound.iloc[-1] - 1) if len(x) else 0,
                "max_drawdown": float(drawdown.min()) if len(x) else 0,
                "annualized_sharpe_naive": float(np.sqrt(252) * x.mean() / x.std())
                 if len(x) > 1 and x.std() > 0 else None}
    return {"strategy": strategy, "observations": len(p),
            "signal_lag": "2 daily close steps; conservative fill timing",
            "cost_bps_per_position_unit": cost_bps_per_position_unit,
            "in_sample_diagnostic": metrics(pnl.iloc[:split], position.iloc[:split]),
            "last_20pct_untouched_diagnostic": metrics(pnl.iloc[split:], position.iloc[split:]),
            "VALIDATED": False,
            "warning": "Illustrative FRED indicative-fixing daily model: NOT LEAN, no tradable bid/ask, swaps or actual fills. Not performance evidence."}
