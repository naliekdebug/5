"""autotrader — a fully automated trading system built from the ground up.

Public API:

    from autotrader import SystemConfig, run_backtest
    result = run_backtest(SystemConfig())
    print(result.report.pretty())

Layers (all pure standard library):
    types        domain primitives (Bar, Order, Fill, Signal, Position)
    indicators   incremental EMA / RSI / ATR / Donchian
    data         pluggable market-data feeds
    strategies   pluggable signal generators
    portfolio    cash + positions + trade bookkeeping
    risk         sizing + daily-loss / drawdown kill switches
    broker       PaperBroker simulator + live broker interface
    engine       the shared per-bar pipeline (backtest == live)
    metrics      performance reporting
    backtest     orchestration
    live         live / paper runner
    config       reproducible run configuration
"""
from .backtest import BacktestResult, build_engine, run_backtest
from .broker import BrokerBase, LiveBrokerBase, PaperBroker
from .config import (
    AccountConfig,
    BrokerConfig,
    DataConfig,
    RiskConfig,
    StrategyConfig,
    SystemConfig,
)
from .data import CSVProvider, DataProvider, ReplayLiveProvider, SyntheticProvider
from .engine import TradingEngine
from .live import LiveRunner, build_live_runner
from .metrics import PerformanceReport, compute_metrics
from .portfolio import Portfolio, Position
from .risk import RiskManager
from .strategies import (
    STRATEGY_REGISTRY,
    DonchianBreakout,
    EMACrossover,
    RSIReversion,
    Strategy,
    build_strategy,
)
from .types import (
    Bar,
    Fill,
    Order,
    OrderStatus,
    OrderType,
    Side,
    Signal,
    SignalAction,
    TradeRecord,
)

__version__ = "0.1.0"

__all__ = [
    "Bar", "Order", "Fill", "Signal", "SignalAction", "Side", "OrderType", "OrderStatus",
    "TradeRecord", "DataProvider", "SyntheticProvider", "CSVProvider", "ReplayLiveProvider",
    "Strategy", "EMACrossover", "RSIReversion", "DonchianBreakout", "STRATEGY_REGISTRY",
    "build_strategy", "Portfolio", "Position", "RiskManager", "BrokerBase", "PaperBroker",
    "LiveBrokerBase", "TradingEngine", "PerformanceReport", "compute_metrics", "run_backtest",
    "build_engine", "BacktestResult", "LiveRunner", "build_live_runner", "SystemConfig",
    "DataConfig", "StrategyConfig", "BrokerConfig", "RiskConfig", "AccountConfig", "__version__",
]
