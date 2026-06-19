"""Core value types for the autotrader system.

Everything here is a small, immutable-ish dataclass with no behaviour beyond
trivial helpers. Keeping the domain primitives in one place lets every layer
(data, strategy, risk, execution) speak the same language.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Side(Enum):
    BUY = 1
    SELL = -1

    @property
    def sign(self) -> int:
        return self.value


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class OrderStatus(Enum):
    PENDING = "pending"     # market order waiting for next bar open
    WORKING = "working"     # resting limit/stop order
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class SignalAction(Enum):
    LONG = "long"
    SHORT = "short"
    CLOSE = "close"


@dataclass
class Bar:
    """A single OHLCV candle."""
    symbol: str
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def __post_init__(self):
        # Defensive: a malformed bar (high < low, etc.) breaks intrabar logic.
        if self.high < self.low:
            raise ValueError(f"Bar high {self.high} < low {self.low} at {self.time}")


@dataclass
class Signal:
    """A strategy's intent for a symbol on a given bar.

    Strategies express *what they want* (go long / short / flat) plus an
    optional protective stop and target as absolute prices. The RiskManager
    turns this into a correctly-sized Order.
    """
    symbol: str
    action: SignalAction
    time: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strength: float = 1.0
    reason: str = ""
    meta: dict = field(default_factory=dict)


@dataclass
class Order:
    symbol: str
    side: Side
    qty: float                       # always positive; side carries direction
    type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    stop_loss: Optional[float] = None        # attaches to the resulting position
    take_profit: Optional[float] = None
    tag: str = ""
    id: int = 0
    status: OrderStatus = OrderStatus.PENDING
    created_time: Optional[datetime] = None

    @property
    def signed_qty(self) -> float:
        return self.qty * self.side.sign


@dataclass
class Fill:
    order_id: int
    symbol: str
    side: Side
    qty: float                       # absolute quantity filled
    price: float
    commission: float
    time: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    tag: str = ""

    @property
    def signed_qty(self) -> float:
        return self.qty * self.side.sign


@dataclass
class TradeRecord:
    """A completed round-trip trade, used for performance statistics."""
    symbol: str
    direction: str                   # "long" | "short"
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    qty: float
    pnl: float                       # net of commissions, in account currency
    return_pct: float
