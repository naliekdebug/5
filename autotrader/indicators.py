"""Incremental technical indicators, implemented from scratch (stdlib only).

Each indicator is a small stateful object with an ``update(...)`` method that
takes one new data point and returns the current indicator value (or ``None``
until it has enough data to be valid). Incremental form means strategies update
in O(1) per bar and work identically in backtest and live streaming.
"""
from __future__ import annotations

from collections import deque
from typing import Optional


class SMA:
    def __init__(self, period: int):
        if period < 1:
            raise ValueError("period must be >= 1")
        self.period = period
        self._buf: deque[float] = deque(maxlen=period)

    def update(self, x: float) -> Optional[float]:
        self._buf.append(x)
        if len(self._buf) < self.period:
            return None
        return sum(self._buf) / self.period

    @property
    def value(self) -> Optional[float]:
        if len(self._buf) < self.period:
            return None
        return sum(self._buf) / self.period

    @property
    def ready(self) -> bool:
        return len(self._buf) >= self.period


class EMA:
    """Exponential moving average, seeded with an SMA over the first `period`."""
    def __init__(self, period: int):
        if period < 1:
            raise ValueError("period must be >= 1")
        self.period = period
        self.alpha = 2.0 / (period + 1.0)
        self.value: Optional[float] = None
        self._count = 0
        self._seed_sum = 0.0

    def update(self, x: float) -> Optional[float]:
        self._count += 1
        if self.value is None:
            self._seed_sum += x
            if self._count >= self.period:
                self.value = self._seed_sum / self.period
            return self.value
        self.value = self.alpha * x + (1.0 - self.alpha) * self.value
        return self.value

    @property
    def ready(self) -> bool:
        return self.value is not None


class RSI:
    """Wilder's RSI."""
    def __init__(self, period: int = 14):
        if period < 1:
            raise ValueError("period must be >= 1")
        self.period = period
        self._prev: Optional[float] = None
        self.avg_gain: Optional[float] = None
        self.avg_loss: Optional[float] = None
        self._count = 0
        self._g = 0.0
        self._l = 0.0
        self.value: Optional[float] = None

    def update(self, x: float) -> Optional[float]:
        if self._prev is None:
            self._prev = x
            return None
        change = x - self._prev
        self._prev = x
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        self._count += 1
        if self.avg_gain is None:
            self._g += gain
            self._l += loss
            if self._count < self.period:
                return None
            self.avg_gain = self._g / self.period
            self.avg_loss = self._l / self.period
        else:
            self.avg_gain = (self.avg_gain * (self.period - 1) + gain) / self.period
            self.avg_loss = (self.avg_loss * (self.period - 1) + loss) / self.period
        if self.avg_loss == 0.0:
            self.value = 100.0
        else:
            rs = self.avg_gain / self.avg_loss
            self.value = 100.0 - 100.0 / (1.0 + rs)
        return self.value

    @property
    def ready(self) -> bool:
        return self.value is not None


class ATR:
    """Wilder's Average True Range. Needs high/low/close each bar."""
    def __init__(self, period: int = 14):
        if period < 1:
            raise ValueError("period must be >= 1")
        self.period = period
        self._prev_close: Optional[float] = None
        self.value: Optional[float] = None
        self._count = 0
        self._seed_sum = 0.0

    def update(self, high: float, low: float, close: float) -> Optional[float]:
        if self._prev_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - self._prev_close), abs(low - self._prev_close))
        self._prev_close = close
        self._count += 1
        if self.value is None:
            self._seed_sum += tr
            if self._count >= self.period:
                self.value = self._seed_sum / self.period
            return self.value
        self.value = (self.value * (self.period - 1) + tr) / self.period
        return self.value

    @property
    def ready(self) -> bool:
        return self.value is not None


class RollingExtreme:
    """Rolling max or min over `period` samples (Donchian channel building block)."""
    def __init__(self, period: int, kind: str = "max"):
        if period < 1:
            raise ValueError("period must be >= 1")
        if kind not in ("max", "min"):
            raise ValueError("kind must be 'max' or 'min'")
        self.period = period
        self.kind = kind
        self._buf: deque[float] = deque(maxlen=period)

    def update(self, x: float) -> Optional[float]:
        self._buf.append(x)
        return self.value

    @property
    def value(self) -> Optional[float]:
        if len(self._buf) < self.period:
            return None
        return max(self._buf) if self.kind == "max" else min(self._buf)

    @property
    def ready(self) -> bool:
        return len(self._buf) >= self.period


class RollingStd:
    """Sample standard deviation over a rolling window."""
    def __init__(self, period: int):
        if period < 2:
            raise ValueError("period must be >= 2")
        self.period = period
        self._buf: deque[float] = deque(maxlen=period)

    def update(self, x: float) -> Optional[float]:
        self._buf.append(x)
        if len(self._buf) < self.period:
            return None
        mean = sum(self._buf) / self.period
        var = sum((v - mean) ** 2 for v in self._buf) / (self.period - 1)
        return var ** 0.5
