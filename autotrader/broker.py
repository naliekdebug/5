"""Execution layer.

``BrokerBase`` defines the interface the engine talks to. ``PaperBroker`` is a
fully-functional simulator with commission, slippage, next-bar market fills, and
intrabar stop-loss / take-profit handling — usable for both backtesting and
forward (paper) trading. A real broker adapter implements the same interface
around an API (see ``LiveBrokerBase``).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .portfolio import Portfolio
from .types import Bar, Fill, Order, OrderStatus, OrderType, Side


class BrokerBase(ABC):
    @abstractmethod
    def submit(self, order: Order) -> int: ...

    @abstractmethod
    def on_bar_open(self, bar: Bar) -> List[Fill]: ...

    @abstractmethod
    def on_bar_range(self, bar: Bar, portfolio: Portfolio) -> List[Fill]: ...

    def liquidate(self, bar: Bar, portfolio: Portfolio) -> List[Fill]:
        return []


class PaperBroker(BrokerBase):
    """Simulated broker.

    Fill model (no look-ahead):
      * MARKET orders submitted on bar t fill at bar t+1's OPEN (+ slippage).
      * LIMIT / STOP resting orders fill if the bar's range trades through them.
      * A position's attached SL/TP is checked against each bar's high/low; if
        both are touched in one bar we assume the worst case (stop first).
    """

    def __init__(
        self,
        commission_per_unit: float = 0.0,
        commission_rate: float = 0.0,     # fraction of notional, e.g. 0.0002 = 2 bps
        slippage_bps: float = 0.0,        # adverse slippage on market/stop fills
        multiplier: float = 1.0,
    ):
        self.commission_per_unit = commission_per_unit
        self.commission_rate = commission_rate
        self.slippage_bps = slippage_bps
        self.multiplier = multiplier
        self._pending: List[Order] = []   # market orders awaiting next open
        self._working: List[Order] = []   # resting limit/stop orders
        self._next_id = 1

    # -- helpers --------------------------------------------------------- #
    def _commission(self, qty: float, price: float) -> float:
        return self.commission_per_unit * qty + self.commission_rate * qty * price * self.multiplier

    def _slip(self, price: float, side: Side) -> float:
        adj = price * self.slippage_bps / 1e4
        return price + adj if side == Side.BUY else price - adj

    def _make_fill(self, order: Order, price: float, bar: Bar, apply_slip: bool = True) -> Fill:
        fill_price = self._slip(price, order.side) if apply_slip else price
        return Fill(
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            qty=order.qty,
            price=fill_price,
            commission=self._commission(order.qty, fill_price),
            time=bar.time,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            tag=order.tag,
        )

    # -- interface ------------------------------------------------------- #
    def submit(self, order: Order) -> int:
        order.id = self._next_id
        self._next_id += 1
        if order.type == OrderType.MARKET:
            order.status = OrderStatus.PENDING
            self._pending.append(order)
        else:
            order.status = OrderStatus.WORKING
            self._working.append(order)
        return order.id

    def on_bar_open(self, bar: Bar) -> List[Fill]:
        fills: List[Fill] = []
        for order in self._pending:
            if order.symbol != bar.symbol:
                continue
            order.status = OrderStatus.FILLED
            fills.append(self._make_fill(order, bar.open, bar))
        self._pending = [o for o in self._pending if o.symbol != bar.symbol]
        return fills

    def on_bar_range(self, bar: Bar, portfolio: Portfolio) -> List[Fill]:
        fills: List[Fill] = []

        # 1) protective SL/TP on the open position
        pos = portfolio.positions.get(bar.symbol)
        if pos is not None and not pos.is_flat:
            qty = abs(pos.qty)
            if pos.qty > 0:   # long: SL below, TP above
                if pos.stop_loss is not None and bar.low <= pos.stop_loss:
                    fills.append(self._exit_fill(bar, Side.SELL, qty, pos.stop_loss, slip=True, tag="stop_loss"))
                elif pos.take_profit is not None and bar.high >= pos.take_profit:
                    fills.append(self._exit_fill(bar, Side.SELL, qty, pos.take_profit, slip=False, tag="take_profit"))
            else:             # short: SL above, TP below
                if pos.stop_loss is not None and bar.high >= pos.stop_loss:
                    fills.append(self._exit_fill(bar, Side.BUY, qty, pos.stop_loss, slip=True, tag="stop_loss"))
                elif pos.take_profit is not None and bar.low <= pos.take_profit:
                    fills.append(self._exit_fill(bar, Side.BUY, qty, pos.take_profit, slip=False, tag="take_profit"))

        # 2) resting limit / stop orders
        still_working: List[Order] = []
        for order in self._working:
            if order.symbol != bar.symbol:
                still_working.append(order)
                continue
            hit, fill_price, slip = self._resting_hit(order, bar)
            if hit:
                order.status = OrderStatus.FILLED
                fills.append(self._make_fill(order, fill_price, bar, apply_slip=slip))
            else:
                still_working.append(order)
        self._working = still_working
        return fills

    def _resting_hit(self, order: Order, bar: Bar):
        if order.type == OrderType.LIMIT and order.limit_price is not None:
            # buy limit fills if price drops to/below; sell limit if rises to/above
            if order.side == Side.BUY and bar.low <= order.limit_price:
                return True, order.limit_price, False
            if order.side == Side.SELL and bar.high >= order.limit_price:
                return True, order.limit_price, False
        elif order.type == OrderType.STOP and order.stop_price is not None:
            if order.side == Side.BUY and bar.high >= order.stop_price:
                return True, order.stop_price, True
            if order.side == Side.SELL and bar.low <= order.stop_price:
                return True, order.stop_price, True
        return False, 0.0, False

    def _exit_fill(self, bar: Bar, side: Side, qty: float, price: float, slip: bool, tag: str) -> Fill:
        fill_price = self._slip(price, side) if slip else price
        return Fill(
            order_id=0, symbol=bar.symbol, side=side, qty=qty, price=fill_price,
            commission=self._commission(qty, fill_price), time=bar.time, tag=tag,
        )

    def liquidate(self, bar: Bar, portfolio: Portfolio) -> List[Fill]:
        """Emergency close everything at the current bar's close (kill switch)."""
        fills: List[Fill] = []
        for sym, pos in portfolio.positions.items():
            if pos.is_flat:
                continue
            side = Side.SELL if pos.qty > 0 else Side.BUY
            fills.append(self._exit_fill(bar, side, abs(pos.qty), bar.close, slip=True, tag="liquidate"))
        # cancel resting/pending orders too
        self._pending.clear()
        self._working.clear()
        return fills


class LiveBrokerBase(BrokerBase):
    """Interface for a real broker/exchange adapter.

    Implement these against your venue's API. The engine never assumes paper vs
    live — it only calls the BrokerBase methods. A live adapter typically:
      * submit(): place the order via REST/FIX and return the venue order id
      * on_bar_open()/on_bar_range(): poll/receive fills and translate to Fill
      * liquidate(): send flatten orders
    Examples to wire in: ccxt (crypto), Interactive Brokers, Alpaca, MetaTrader5.
    """
    @abstractmethod
    def submit(self, order: Order) -> int: ...
