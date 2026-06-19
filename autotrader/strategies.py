"""Trading strategies.

A Strategy consumes bars one at a time and emits Signals. It owns its own
indicator state and must never peek at future data — ``on_bar`` only ever sees
bars up to and including the current one. The engine guarantees signals emitted
on a bar's close are executed no earlier than the next bar's open.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type

from .indicators import ATR, EMA, RSI, RollingExtreme
from .types import Bar, Signal, SignalAction


class Strategy(ABC):
    name: str = "base"

    def __init__(self, symbol: str):
        self.symbol = symbol

    @abstractmethod
    def on_bar(self, bar: Bar) -> List[Signal]:
        """Return zero or more Signals for this bar."""
        ...

    def warmup(self) -> int:
        """Number of bars to ingest before signals are trustworthy."""
        return 0


# --------------------------------------------------------------------------- #
# EMA crossover (trend following)
# --------------------------------------------------------------------------- #
class EMACrossover(Strategy):
    """Go long when the fast EMA crosses above the slow EMA, short on the
    opposite cross. Protective stop/target sized from ATR.
    """
    name = "ema_crossover"

    def __init__(
        self,
        symbol: str,
        fast: int = 12,
        slow: int = 26,
        atr_period: int = 14,
        sl_atr: float = 2.0,
        tp_atr: float = 3.0,
        allow_short: bool = True,
    ):
        super().__init__(symbol)
        if fast >= slow:
            raise ValueError("fast period must be < slow period")
        self.fast = EMA(fast)
        self.slow = EMA(slow)
        self.atr = ATR(atr_period)
        self.sl_atr = sl_atr
        self.tp_atr = tp_atr
        self.allow_short = allow_short
        self._prev_diff: Optional[float] = None
        self._slow_period = slow

    def warmup(self) -> int:
        return self._slow_period + 1

    def on_bar(self, bar: Bar) -> List[Signal]:
        f = self.fast.update(bar.close)
        s = self.slow.update(bar.close)
        a = self.atr.update(bar.high, bar.low, bar.close)
        if f is None or s is None or a is None:
            return []
        diff = f - s
        signals: List[Signal] = []
        if self._prev_diff is not None:
            crossed_up = self._prev_diff <= 0 < diff
            crossed_dn = self._prev_diff >= 0 > diff
            if crossed_up:
                signals.append(Signal(
                    self.symbol, SignalAction.LONG, bar.time,
                    stop_loss=bar.close - self.sl_atr * a,
                    take_profit=bar.close + self.tp_atr * a,
                    reason="EMA cross up",
                ))
            elif crossed_dn and self.allow_short:
                signals.append(Signal(
                    self.symbol, SignalAction.SHORT, bar.time,
                    stop_loss=bar.close + self.sl_atr * a,
                    take_profit=bar.close - self.tp_atr * a,
                    reason="EMA cross down",
                ))
            elif crossed_dn and not self.allow_short:
                signals.append(Signal(self.symbol, SignalAction.CLOSE, bar.time, reason="EMA cross down (exit long)"))
        self._prev_diff = diff
        return signals


# --------------------------------------------------------------------------- #
# RSI mean reversion
# --------------------------------------------------------------------------- #
class RSIReversion(Strategy):
    """Buy oversold, sell overbought, exit back toward the midline. Counter-trend,
    so it pairs well with a ranging filter (not included — keep it honest).
    """
    name = "rsi_reversion"

    def __init__(
        self,
        symbol: str,
        rsi_period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        exit_level: float = 50.0,
        atr_period: int = 14,
        sl_atr: float = 2.5,
        allow_short: bool = True,
    ):
        super().__init__(symbol)
        self.rsi = RSI(rsi_period)
        self.atr = ATR(atr_period)
        self.oversold = oversold
        self.overbought = overbought
        self.exit_level = exit_level
        self.sl_atr = sl_atr
        self.allow_short = allow_short
        self._rsi_period = rsi_period
        self._in: int = 0  # +1 long, -1 short, 0 flat (strategy's own view)

    def warmup(self) -> int:
        return self._rsi_period + 1

    def on_bar(self, bar: Bar) -> List[Signal]:
        r = self.rsi.update(bar.close)
        a = self.atr.update(bar.high, bar.low, bar.close)
        if r is None or a is None:
            return []
        signals: List[Signal] = []
        if self._in == 0:
            if r < self.oversold:
                self._in = 1
                signals.append(Signal(self.symbol, SignalAction.LONG, bar.time,
                                      stop_loss=bar.close - self.sl_atr * a, reason="RSI oversold"))
            elif r > self.overbought and self.allow_short:
                self._in = -1
                signals.append(Signal(self.symbol, SignalAction.SHORT, bar.time,
                                      stop_loss=bar.close + self.sl_atr * a, reason="RSI overbought"))
        elif self._in == 1 and r >= self.exit_level:
            self._in = 0
            signals.append(Signal(self.symbol, SignalAction.CLOSE, bar.time, reason="RSI back to mid"))
        elif self._in == -1 and r <= self.exit_level:
            self._in = 0
            signals.append(Signal(self.symbol, SignalAction.CLOSE, bar.time, reason="RSI back to mid"))
        return signals


# --------------------------------------------------------------------------- #
# Donchian breakout (turtle-style)
# --------------------------------------------------------------------------- #
class DonchianBreakout(Strategy):
    """Enter on a breakout of the prior N-bar high/low, exit on the opposite
    M-bar channel. The channels are computed on *prior* bars (current bar
    excluded) to avoid using the breakout bar itself in its own trigger.
    """
    name = "donchian_breakout"

    def __init__(
        self,
        symbol: str,
        entry_period: int = 20,
        exit_period: int = 10,
        atr_period: int = 14,
        sl_atr: float = 2.0,
        allow_short: bool = True,
    ):
        super().__init__(symbol)
        if exit_period >= entry_period:
            # not fatal, but usually you want a tighter exit channel
            pass
        self.entry_hi = RollingExtreme(entry_period, "max")
        self.entry_lo = RollingExtreme(entry_period, "min")
        self.exit_hi = RollingExtreme(exit_period, "max")
        self.exit_lo = RollingExtreme(exit_period, "min")
        self.atr = ATR(atr_period)
        self.sl_atr = sl_atr
        self.allow_short = allow_short
        self._entry_period = entry_period
        self._in = 0

    def warmup(self) -> int:
        return self._entry_period + 1

    def on_bar(self, bar: Bar) -> List[Signal]:
        a = self.atr.update(bar.high, bar.low, bar.close)
        # Read channels formed by PRIOR bars before updating with this bar.
        eh = self.entry_hi.value
        el = self.entry_lo.value
        xh = self.exit_hi.value
        xl = self.exit_lo.value

        signals: List[Signal] = []
        if a is not None and eh is not None and el is not None:
            if self._in == 0:
                if bar.close > eh:
                    self._in = 1
                    signals.append(Signal(self.symbol, SignalAction.LONG, bar.time,
                                          stop_loss=bar.close - self.sl_atr * a, reason="Donchian breakout up"))
                elif bar.close < el and self.allow_short:
                    self._in = -1
                    signals.append(Signal(self.symbol, SignalAction.SHORT, bar.time,
                                          stop_loss=bar.close + self.sl_atr * a, reason="Donchian breakout down"))
            elif self._in == 1 and xl is not None and bar.close < xl:
                self._in = 0
                signals.append(Signal(self.symbol, SignalAction.CLOSE, bar.time, reason="Donchian exit long"))
            elif self._in == -1 and xh is not None and bar.close > xh:
                self._in = 0
                signals.append(Signal(self.symbol, SignalAction.CLOSE, bar.time, reason="Donchian exit short"))

        # Now fold the current bar into the channels for next time.
        self.entry_hi.update(bar.high)
        self.entry_lo.update(bar.low)
        self.exit_hi.update(bar.high)
        self.exit_lo.update(bar.low)
        return signals


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
STRATEGY_REGISTRY: Dict[str, Type[Strategy]] = {
    EMACrossover.name: EMACrossover,
    RSIReversion.name: RSIReversion,
    DonchianBreakout.name: DonchianBreakout,
}


def build_strategy(name: str, symbol: str, params: Optional[dict] = None) -> Strategy:
    if name not in STRATEGY_REGISTRY:
        raise KeyError(f"Unknown strategy {name!r}. Available: {sorted(STRATEGY_REGISTRY)}")
    return STRATEGY_REGISTRY[name](symbol, **(params or {}))
