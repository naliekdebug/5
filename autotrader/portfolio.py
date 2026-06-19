"""Portfolio: cash, positions, mark-to-market equity, and trade bookkeeping.

A single netted position is kept per symbol (a buy into a short reduces/flips
it). The ``multiplier`` scales price moves into account currency so the same
code works for spot (mult=1), FX, or futures contracts (mult=contract value).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .types import Fill, TradeRecord

_EPS = 1e-9


@dataclass
class Position:
    symbol: str
    qty: float = 0.0                 # signed: + long, - short
    avg_price: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    @property
    def is_flat(self) -> bool:
        return abs(self.qty) < _EPS

    def apply(self, dq: float, price: float) -> float:
        """Apply a signed quantity change at ``price``. Returns realized PnL in
        *price units* (caller multiplies by the contract multiplier).
        """
        q = self.qty
        realized = 0.0
        if abs(q) < _EPS:
            self.qty = dq
            self.avg_price = price
        elif (q > 0) == (dq > 0):
            # adding in the same direction -> weighted average entry
            new_q = q + dq
            self.avg_price = (self.avg_price * q + price * dq) / new_q
            self.qty = new_q
        else:
            # opposite direction: realize PnL on the closed portion
            closed = min(abs(dq), abs(q))
            direction = 1.0 if q > 0 else -1.0
            realized = (price - self.avg_price) * closed * direction
            new_q = q + dq
            if abs(new_q) < _EPS:
                self.qty = 0.0
                self.avg_price = 0.0
            elif (new_q > 0) == (q > 0):
                # partial close, same side remains; avg unchanged
                self.qty = new_q
            else:
                # flipped through zero; remainder opens at this price
                self.qty = new_q
                self.avg_price = price
        return realized


class Portfolio:
    def __init__(self, starting_cash: float = 100_000.0, multiplier: float = 1.0):
        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.multiplier = multiplier
        self.positions: Dict[str, Position] = {}
        self.last_prices: Dict[str, float] = {}
        self.realized_pnl = 0.0
        self.total_commission = 0.0
        self.equity_curve: List[tuple[datetime, float]] = []
        self.trades: List[TradeRecord] = []
        self._open: Dict[str, dict] = {}   # in-flight round-trip per symbol

    # -- positions ------------------------------------------------------- #
    def position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol)
        return self.positions[symbol]

    def has_open_positions(self) -> bool:
        return any(not p.is_flat for p in self.positions.values())

    # -- fills ----------------------------------------------------------- #
    def on_fill(self, fill: Fill) -> None:
        pos = self.position(fill.symbol)
        dq = fill.signed_qty
        old_qty = pos.qty
        realized_price = pos.apply(dq, fill.price)
        realized = realized_price * self.multiplier

        self.cash -= dq * fill.price * self.multiplier
        self.cash -= fill.commission
        self.realized_pnl += realized
        self.total_commission += fill.commission

        self._book_trade(fill, old_qty, pos, realized)

        # attach / clear protective levels on the resulting position
        if not pos.is_flat:
            if fill.stop_loss is not None:
                pos.stop_loss = fill.stop_loss
            if fill.take_profit is not None:
                pos.take_profit = fill.take_profit
        else:
            pos.stop_loss = None
            pos.take_profit = None

    def _book_trade(self, fill: Fill, old_qty: float, pos: Position, realized: float) -> None:
        sym = fill.symbol
        new_qty = pos.qty
        op = self._open.get(sym)
        flipped = (abs(old_qty) > _EPS and abs(new_qty) > _EPS and (old_qty > 0) != (new_qty > 0))

        if abs(old_qty) < _EPS and abs(new_qty) > _EPS:
            # fresh open
            self._open[sym] = dict(direction=1 if new_qty > 0 else -1,
                                   entry_time=fill.time, entry_price=fill.price,
                                   qty=abs(new_qty), pnl=-fill.commission)
        elif abs(new_qty) < _EPS and op is not None:
            # full close
            op["pnl"] += realized - fill.commission
            self._record_close(sym, fill, op)
            self._open.pop(sym, None)
        elif flipped:
            # close the old trade, open a new one at the remainder
            if op is not None:
                op["pnl"] += realized - fill.commission
                self._record_close(sym, fill, op)
            self._open[sym] = dict(direction=1 if new_qty > 0 else -1,
                                   entry_time=fill.time, entry_price=fill.price,
                                   qty=abs(new_qty), pnl=0.0)
        elif op is not None:
            # same-direction add or partial reduce
            op["pnl"] += realized - fill.commission
            if abs(new_qty) > abs(old_qty):
                op["qty"] = abs(new_qty)
                op["entry_price"] = pos.avg_price

    def _record_close(self, sym: str, fill: Fill, op: dict) -> None:
        direction = op["direction"]
        entry = op["entry_price"]
        exit_price = fill.price
        ret = ((exit_price / entry) - 1.0) * direction if entry else 0.0
        self.trades.append(TradeRecord(
            symbol=sym,
            direction="long" if direction > 0 else "short",
            entry_time=op["entry_time"], entry_price=entry,
            exit_time=fill.time, exit_price=exit_price,
            qty=op["qty"], pnl=op["pnl"], return_pct=ret,
        ))

    # -- valuation ------------------------------------------------------- #
    def mark(self, symbol: str, price: float) -> None:
        self.last_prices[symbol] = price

    def equity(self) -> float:
        eq = self.cash
        for sym, pos in self.positions.items():
            if not pos.is_flat:
                px = self.last_prices.get(sym, pos.avg_price)
                eq += pos.qty * px * self.multiplier
        return eq

    def record_equity(self, time: datetime) -> None:
        self.equity_curve.append((time, self.equity()))

    def unrealized_pnl(self) -> float:
        total = 0.0
        for sym, pos in self.positions.items():
            if not pos.is_flat:
                px = self.last_prices.get(sym, pos.avg_price)
                total += (px - pos.avg_price) * pos.qty * self.multiplier
        return total
