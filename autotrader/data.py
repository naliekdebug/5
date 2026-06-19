"""Market data providers.

A provider is just an iterable of :class:`Bar`. This keeps the rest of the
system agnostic about *where* data comes from — a CSV, a synthetic generator,
or (in live mode) a streaming feed that blocks until the next candle closes.

Included:
  * SyntheticProvider  — deterministic GBM-ish OHLCV generator (offline demos/tests)
  * CSVProvider        — load OHLCV from a CSV file
  * ReplayLiveProvider — wrap any bar list to emulate a live streaming feed

To connect a real exchange/broker, implement ``DataProvider.__iter__`` (or
``stream``) around its websocket/REST API and yield closed bars.
"""
from __future__ import annotations

import csv
import math
import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Iterable, Iterator, List, Optional

from .types import Bar


class DataProvider(ABC):
    """Base class. Subclasses yield Bars in chronological order."""

    symbol: str

    @abstractmethod
    def __iter__(self) -> Iterator[Bar]:
        ...

    def load(self) -> List[Bar]:
        return list(self)


class SyntheticProvider(DataProvider):
    """Generate realistic-looking OHLCV bars with a geometric random walk plus
    optional drift and volatility clustering. Deterministic given a seed, so it
    is ideal for tests and reproducible demos.
    """

    def __init__(
        self,
        symbol: str = "SYNTH",
        n_bars: int = 2000,
        start_price: float = 100.0,
        drift: float = 0.00002,
        volatility: float = 0.0015,
        timeframe_minutes: int = 1,
        seed: Optional[int] = 42,
        start_time: Optional[datetime] = None,
    ):
        self.symbol = symbol
        self.n_bars = n_bars
        self.start_price = start_price
        self.drift = drift
        self.volatility = volatility
        self.timeframe_minutes = timeframe_minutes
        self.seed = seed
        self.start_time = start_time or datetime(2024, 1, 1, tzinfo=timezone.utc)

    def __iter__(self) -> Iterator[Bar]:
        rng = random.Random(self.seed)
        price = self.start_price
        vol = self.volatility
        t = self.start_time
        step = timedelta(minutes=self.timeframe_minutes)
        for _ in range(self.n_bars):
            # Volatility clustering: vol mean-reverts but gets shocked.
            vol = max(1e-6, vol * 0.97 + self.volatility * 0.03 + abs(rng.gauss(0, self.volatility * 0.25)))
            o = price
            ret = self.drift + rng.gauss(0.0, vol)
            c = max(1e-6, o * math.exp(ret))
            # Wicks: extend beyond the open/close by a fraction of the move.
            span = abs(c - o) + o * vol * 0.5
            hi = max(o, c) + abs(rng.gauss(0, span * 0.5))
            lo = min(o, c) - abs(rng.gauss(0, span * 0.5))
            lo = max(1e-6, lo)
            volume = abs(rng.gauss(1000, 300))
            yield Bar(self.symbol, t, o, hi, lo, c, volume)
            price = c
            t = t + step


class CSVProvider(DataProvider):
    """Load OHLCV bars from a CSV.

    Expected columns (case-insensitive): time/date/timestamp, open, high, low,
    close, and optionally volume. The time column may be an ISO string or a
    unix epoch (seconds or milliseconds).
    """

    def __init__(self, path: str, symbol: str = "CSV", time_col: Optional[str] = None):
        self.path = path
        self.symbol = symbol
        self.time_col = time_col

    @staticmethod
    def _parse_time(raw: str) -> datetime:
        raw = raw.strip()
        # numeric epoch?
        try:
            num = float(raw)
            if num > 1e12:       # milliseconds
                num /= 1000.0
            return datetime.fromtimestamp(num, tz=timezone.utc)
        except ValueError:
            pass
        # ISO-8601
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError as e:
            raise ValueError(f"Unrecognized time format: {raw!r}") from e

    def __iter__(self) -> Iterator[Bar]:
        with open(self.path, newline="") as f:
            reader = csv.DictReader(f)
            field_map = {k.lower().strip(): k for k in (reader.fieldnames or [])}
            tcol = self.time_col or next(
                (field_map[c] for c in ("time", "date", "timestamp", "datetime") if c in field_map),
                None,
            )
            if tcol is None:
                raise ValueError("CSV must have a time/date/timestamp column")

            def col(row, *names):
                for n in names:
                    if n in field_map:
                        return row[field_map[n]]
                raise KeyError(names)

            for row in reader:
                t = self._parse_time(row[tcol])
                o = float(col(row, "open", "o"))
                h = float(col(row, "high", "h"))
                low = float(col(row, "low", "l"))
                c = float(col(row, "close", "c"))
                try:
                    v = float(col(row, "volume", "vol", "v"))
                except (KeyError, ValueError):
                    v = 0.0
                yield Bar(self.symbol, t, o, h, low, c, v)


class ReplayLiveProvider(DataProvider):
    """Emulate a live streaming feed by replaying pre-loaded bars one at a time,
    optionally sleeping between them. Lets the live runner be exercised offline
    with the exact same code path a real feed would use.
    """

    def __init__(self, bars: Iterable[Bar], speed: float = 0.0):
        self._bars = list(bars)
        self.symbol = self._bars[0].symbol if self._bars else ""
        self.speed = speed  # seconds to sleep between bars (0 = as fast as possible)

    def __iter__(self) -> Iterator[Bar]:
        import time as _time
        for bar in self._bars:
            yield bar
            if self.speed > 0:
                _time.sleep(self.speed)
