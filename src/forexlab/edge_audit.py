"""Original realized-trade diagnostic: high win rate alone is not evidence of edge.

R-multiples MUST be NET of realized spreads, commissions, slippage and swaps.
No claim of out-of-sample provenance or production readiness is made here.
"""
from __future__ import annotations

from collections.abc import Sequence
import math
import numpy as np


def _wilson_lower(wins: int, total: int, z: float = 1.959963984540054) -> float:
    """95% approximate lower confidence bound on win probability (nonzero outcomes)."""
    if total == 0:
        return 0.0
    p = wins / total
    denominator = 1 + z * z / total
    centre = p + z*z/(2*total)
    margin = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total))
    return float((centre - margin) / denominator)


def audit_net_r(trades_net_r: Sequence[float], *, min_trades: int = 100) -> dict:
    """Realized-trade metrics in risk units; diagnostic only, NOT portfolio PnL.

    Requires chronological trade outcomes net of ALL execution costs.
    Drawdown is in cumulative R, not cash, annualized return, or equity %.
    No stats override the disabled-trading state.
    """
    arr = np.asarray(trades_net_r, dtype=float)
    if arr.ndim != 1 or len(arr) == 0 or not np.isfinite(arr).all():
        raise ValueError("Require a nonempty 1D sequence of finite net R outcomes")
    if not isinstance(min_trades, int) or min_trades <= 0:
        raise ValueError("min_trades must be a positive integer")
    won = arr[arr > 0]
    lost = arr[arr < 0]
    decided = len(won) + len(lost)
    equity_r = np.concatenate(([0.0], np.cumsum(arr)))
    max_drawdown_r = float(np.max(np.maximum.accumulate(equity_r) - equity_r))
    # This simplistic R diagnostic never substitutes for bid/ask fill simulation,
    # independent out-of-sample provenance or portfolio cash accounting.
    expectancy = float(arr.mean())
    enough = len(arr) >= min_trades
    return {"trades": len(arr), "wins": len(won), "losses": len(lost),
            "breakeven": int(len(arr) - decided),
            "win_rate_excluding_breakevens": float(len(won)/decided) if decided else None,
            "win_rate_lower_95_wilson": _wilson_lower(len(won), decided) if decided else None,
            "expectancy_net_r_per_trade": expectancy,
            "total_net_r": float(arr.sum()),
            "mean_win_r": float(won.mean()) if len(won) else None,
            "mean_loss_r": float(lost.mean()) if len(lost) else None,
            "profit_factor_net_r": float(won.sum() / -lost.sum()) if len(lost) else None,
            "max_drawdown_cumulative_r": max_drawdown_r,
            "passes_minimum_sample_and_positive_expectancy": bool(enough and expectancy > 0),
            "independently_verified_out_of_sample": False,
            "validated": False, "execution_allowed": False,
            "warning": "R diagnostic only; no per-trade risk weighting, FX conversion, cash equity or independent holdout verification."}
