"""Backtest orchestration: wire a SystemConfig into the engine and report.

``run_backtest`` builds every component from config, streams historical bars
through the shared :class:`TradingEngine`, and returns the portfolio plus a
:class:`PerformanceReport`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .broker import PaperBroker
from .config import SystemConfig
from .data import CSVProvider, DataProvider, SyntheticProvider
from .engine import TradingEngine
from .metrics import PerformanceReport, compute_metrics
from .portfolio import Portfolio
from .risk import RiskManager
from .strategies import build_strategy
from .types import Bar


def build_data_provider(cfg: SystemConfig) -> DataProvider:
    d = cfg.data
    if d.provider == "synthetic":
        return SyntheticProvider(
            symbol=d.symbol, n_bars=d.n_bars, start_price=d.start_price,
            drift=d.drift, volatility=d.volatility,
            timeframe_minutes=d.timeframe_minutes, seed=d.seed,
        )
    if d.provider == "csv":
        if not d.path:
            raise ValueError("csv provider requires data.path")
        return CSVProvider(d.path, symbol=d.symbol, time_col=d.time_col)
    raise ValueError(f"Unknown data provider {d.provider!r}")


def build_engine(cfg: SystemConfig) -> TradingEngine:
    portfolio = Portfolio(cfg.account.starting_cash, multiplier=cfg.account.multiplier)
    broker = PaperBroker(
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
    return TradingEngine(strategy, portfolio, broker, risk)


@dataclass
class BacktestResult:
    portfolio: Portfolio
    report: PerformanceReport
    bars: int


def run_backtest(cfg: SystemConfig, bars: Optional[List[Bar]] = None) -> BacktestResult:
    engine = build_engine(cfg)
    data = bars if bars is not None else list(build_data_provider(cfg))
    engine.run(data)
    report = compute_metrics(
        engine.portfolio.equity_curve,
        engine.portfolio.trades,
        total_commission=engine.portfolio.total_commission,
    )
    return BacktestResult(portfolio=engine.portfolio, report=report, bars=len(data))
