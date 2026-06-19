"""Configuration objects and JSON (de)serialization.

A single ``SystemConfig`` fully describes a run: which data feed, which strategy
(by name + params), broker costs, risk limits, and account settings. Configs can
be built in code or loaded from a JSON file, so backtests are reproducible.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional


@dataclass
class DataConfig:
    provider: str = "synthetic"             # "synthetic" | "csv"
    symbol: str = "XAUUSD"
    # synthetic
    n_bars: int = 5000
    start_price: float = 2000.0
    drift: float = 0.00001
    volatility: float = 0.0012
    timeframe_minutes: int = 1
    seed: Optional[int] = 7
    # csv
    path: Optional[str] = None
    time_col: Optional[str] = None


@dataclass
class StrategyConfig:
    name: str = "ema_crossover"
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrokerConfig:
    commission_per_unit: float = 0.0
    commission_rate: float = 0.0002         # 2 bps of notional
    slippage_bps: float = 1.0               # 1 bp adverse slippage
    multiplier: float = 1.0


@dataclass
class RiskConfig:
    risk_per_trade: float = 0.01
    max_gross_exposure: float = 1.0
    max_daily_loss: float = 0.05
    max_drawdown: float = 0.25
    fallback_stop_pct: float = 0.02
    flatten_on_halt: bool = True


@dataclass
class AccountConfig:
    starting_cash: float = 100_000.0
    multiplier: float = 1.0


@dataclass
class SystemConfig:
    data: DataConfig = field(default_factory=DataConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    account: AccountConfig = field(default_factory=AccountConfig)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent)

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            f.write(self.to_json())

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SystemConfig":
        return cls(
            data=DataConfig(**d.get("data", {})),
            strategy=StrategyConfig(**d.get("strategy", {})),
            broker=BrokerConfig(**d.get("broker", {})),
            risk=RiskConfig(**d.get("risk", {})),
            account=AccountConfig(**d.get("account", {})),
        )

    @classmethod
    def load(cls, path: str) -> "SystemConfig":
        with open(path) as f:
            return cls.from_dict(json.load(f))
