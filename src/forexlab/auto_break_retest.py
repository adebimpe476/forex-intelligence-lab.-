"""Deterministic completed-M5 break/retest signal prototype.

The sole purpose is to make reproducible *candidate* decisions. The strategy
has NOT demonstrated positive expectancy and must not run with real money.
Prices are broker-specific: GC/NQ futures levels are never mixed with spot/CFD.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Side = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class Candle:
    time: int  # UTC epoch seconds, START of a completed M5 candle
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self) -> None:
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("Nonpositive OHLC")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("Inconsistent OHLC")


@dataclass(frozen=True)
class Proposal:
    side: Side
    level: float
    entry_reference: float  # last completed candle CLOSE; never a guaranteed fill
    stop: float
    atr: float
    candle_time: int
    breakout_time: int


@dataclass(frozen=True)
class _Pending:
    side: Side
    level: float
    breakout_time: int


def _atr(bars: list[Candle], period: int = 14) -> float:
    if len(bars) < period + 1:
        return 0.0
    ranges = []
    for a, b in zip(bars[-period - 1:-1], bars[-period:]):
        ranges.append(max(b.high - b.low, abs(b.high - a.close), abs(b.low - a.close)))
    return sum(ranges) / period


class BreakRetestDetector:
    """One setup per symbol; waits for a *later completed candle* to reject.

    Does not infer delta/CVD, liquidity absorption, news, or profitability.
    """
    def __init__(self, lookback: int = 20, expiry_bars: int = 6):
        if lookback < 15 or not 1 <= expiry_bars <= 12:
            raise ValueError("Invalid detector settings")
        self.lookback = lookback
        self.expiry_bars = expiry_bars
        self.pending: dict[str, _Pending] = {}
        self.last_seen: dict[str, int] = {}

    def advance(self, symbol: str, bars: list[Candle]) -> Proposal | None:
        if len(bars) < self.lookback + 2:
            return None
        if any(a.time >= b.time for a, b in zip(bars, bars[1:])):
            raise ValueError("Candle times must strictly increase")
        last = bars[-1]
        if self.last_seen.get(symbol, -1) >= last.time:
            return None
        self.last_seen[symbol] = last.time
        atr = _atr(bars)
        if atr <= 0:
            return None

        pending = self.pending.get(symbol)
        if pending:
            elapsed = last.time - pending.breakout_time
            if elapsed <= 0 or elapsed > self.expiry_bars * 300:
                self.pending.pop(symbol, None)
            elif pending.side == "SELL":
                if last.close > pending.level + 0.55 * atr:
                    self.pending.pop(symbol, None)
                elif (last.high >= pending.level - 0.15 * atr
                      and last.low <= pending.level + 0.15 * atr
                      and last.close <= pending.level - 0.08 * atr
                      and last.close < last.open):
                    self.pending.pop(symbol, None)
                    stop = max(last.high, pending.level + 0.45 * atr) + 0.15 * atr
                    return Proposal("SELL", pending.level, last.close, stop,
                                    atr, last.time, pending.breakout_time)
            else:
                if last.close < pending.level - 0.55 * atr:
                    self.pending.pop(symbol, None)
                elif (last.low <= pending.level + 0.15 * atr
                      and last.high >= pending.level - 0.15 * atr
                      and last.close >= pending.level + 0.08 * atr
                      and last.close > last.open):
                    self.pending.pop(symbol, None)
                    stop = min(last.low, pending.level - 0.45 * atr) - 0.15 * atr
                    return Proposal("BUY", pending.level, last.close, stop,
                                    atr, last.time, pending.breakout_time)
            # While a potential retest is pending, do not open another setup.
            if symbol in self.pending:
                return None

        earlier = bars[-self.lookback - 1:-1]
        support = min(x.low for x in earlier)
        resistance = max(x.high for x in earlier)
        prev = bars[-2]
        threshold = 0.10 * atr

        if last.close < support - threshold and prev.close >= support - threshold:
            self.pending[symbol] = _Pending("SELL", support, last.time)
        elif last.close > resistance + threshold and prev.close <= resistance + threshold:
            self.pending[symbol] = _Pending("BUY", resistance, last.time)
        return None
