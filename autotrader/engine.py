"""The trading engine: a single per-bar pipeline shared by backtest and live.

The whole point of this class is that *one* code path drives both modes. A
backtest feeds it bars from history as fast as possible; the live runner feeds
it bars from a streaming feed as they close. The trading logic is identical, so
what you test is what you trade.

Per-bar order of operations (designed to avoid look-ahead bias):
  1. Fill MARKET orders submitted on the *previous* bar, at this bar's open.
  2. Check intrabar SL/TP and resting limit/stop orders against this bar.
  3. Mark to market at the close.
  4. Run risk kill-switches; liquidate if a switch just tripped.
  5. Ask the strategy for signals (it sees data up to this close).
  6. Size signals into orders and submit them (they fill no earlier than the
     next bar's open).
  7. Record equity.
"""
from __future__ import annotations

import logging
from typing import Iterable, List, Optional

from .broker import BrokerBase
from .portfolio import Portfolio
from .risk import RiskManager
from .strategies import Strategy
from .types import Bar, Fill

log = logging.getLogger("autotrader.engine")


class TradingEngine:
    def __init__(
        self,
        strategy: Strategy,
        portfolio: Portfolio,
        broker: BrokerBase,
        risk: RiskManager,
        warmup: Optional[int] = None,
    ):
        self.strategy = strategy
        self.portfolio = portfolio
        self.broker = broker
        self.risk = risk
        self.warmup = warmup if warmup is not None else strategy.warmup()
        self._bar_count = 0
        self.fills: List[Fill] = []

    def step(self, bar: Bar) -> None:
        self._bar_count += 1

        # 1) market orders from the previous bar fill at this open
        for f in self.broker.on_bar_open(bar):
            self.portfolio.on_fill(f)
            self.fills.append(f)

        # 2) intrabar protective exits + resting orders
        for f in self.broker.on_bar_range(bar, self.portfolio):
            self.portfolio.on_fill(f)
            self.fills.append(f)

        # 3) mark to market
        self.portfolio.mark(bar.symbol, bar.close)

        # 4) risk kill-switches
        halted = self.risk.update(self.portfolio, bar)
        if self.risk.just_halted:
            log.warning("Risk halt (%s) at %s — liquidating.", self.risk.halt_reason, bar.time)
            for f in self.broker.liquidate(bar, self.portfolio):
                self.portfolio.on_fill(f)
                self.fills.append(f)

        # 5) strategy decision (always feed it so indicators stay warm)
        signals = self.strategy.on_bar(bar)

        # 6) route signals -> orders (skipped while warming up or halted)
        if self._bar_count > self.warmup and not halted:
            for sig in signals:
                order = self.risk.size_order(sig, self.portfolio, bar)
                if order is not None:
                    self.broker.submit(order)

        # 7) record equity at the close
        self.portfolio.record_equity(bar.time)

    def run(self, bars: Iterable[Bar]) -> Portfolio:
        for bar in bars:
            self.step(bar)
        return self.portfolio
