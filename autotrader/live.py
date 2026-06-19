"""Live / paper trading runner.

Drives the *same* :class:`TradingEngine` used for backtesting, but off a
streaming data feed instead of a fixed history. By default it runs against the
``PaperBroker`` (no real money). Point it at a ``LiveBrokerBase`` implementation
and a real streaming ``DataProvider`` to go live — the engine code does not
change.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from .broker import BrokerBase, PaperBroker
from .config import SystemConfig
from .data import DataProvider
from .engine import TradingEngine
from .portfolio import Portfolio
from .risk import RiskManager
from .strategies import build_strategy

log = logging.getLogger("autotrader.live")


class LiveRunner:
    def __init__(
        self,
        provider: DataProvider,
        engine: TradingEngine,
        on_bar: Optional[Callable[[TradingEngine], None]] = None,
    ):
        self.provider = provider
        self.engine = engine
        self.on_bar = on_bar

    def run(self, max_bars: Optional[int] = None) -> Portfolio:
        count = 0
        for bar in self.provider:
            self.engine.step(bar)
            count += 1
            if self.on_bar is not None:
                self.on_bar(self.engine)
            if max_bars is not None and count >= max_bars:
                break
        return self.engine.portfolio


def build_live_runner(
    cfg: SystemConfig,
    provider: DataProvider,
    broker: Optional[BrokerBase] = None,
) -> LiveRunner:
    portfolio = Portfolio(cfg.account.starting_cash, multiplier=cfg.account.multiplier)
    broker = broker or PaperBroker(
        commission_per_unit=cfg.broker.commission_per_unit,
        commission_rate=cfg.broker.commission_rate,
        slippage_bps=cfg.broker.slippage_bps,
        multiplier=cfg.broker.multiplier,
    )
    risk = RiskManager(
        risk_per_trade=cfg.risk.risk_per_trade,
        max_gross_exposure=cfg.risk.max_gross_exposure,
        multiplier=cfg.account.multiplier,
        max_daily_loss=cfg.risk.max_daily_loss,
        max_drawdown=cfg.risk.max_drawdown,
        fallback_stop_pct=cfg.risk.fallback_stop_pct,
        flatten_on_halt=cfg.risk.flatten_on_halt,
    )
    strategy = build_strategy(cfg.strategy.name, cfg.data.symbol, cfg.strategy.params)
    engine = TradingEngine(strategy, portfolio, broker, risk)
    return LiveRunner(provider, engine)
