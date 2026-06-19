"""Risk management: position sizing + account-level kill switches.

The RiskManager is the only component allowed to turn a Signal into an Order.
It sizes every entry off a fixed fraction of equity and the trade's stop
distance, caps gross exposure, and halts new entries when daily-loss or
max-drawdown limits are breached.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from .portfolio import Portfolio
from .types import Bar, Order, OrderType, Side, Signal, SignalAction

_EPS = 1e-9


class RiskManager:
    def __init__(
        self,
        risk_per_trade: float = 0.01,        # fraction of equity risked per trade
        max_gross_exposure: float = 1.0,     # cap: position notional / equity
        multiplier: float = 1.0,             # contract value per 1.0 price move
        max_daily_loss: float = 0.05,        # halt if daily loss exceeds this fraction
        max_drawdown: float = 0.25,          # halt if equity falls this far from peak
        fallback_stop_pct: float = 0.02,     # stop distance if a signal omits one
        min_qty: float = 1e-6,
        flatten_on_halt: bool = True,        # liquidate when a kill switch trips
    ):
        self.risk_per_trade = risk_per_trade
        self.max_gross_exposure = max_gross_exposure
        self.multiplier = multiplier
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown
        self.fallback_stop_pct = fallback_stop_pct
        self.min_qty = min_qty
        self.flatten_on_halt = flatten_on_halt

        self._day: Optional[date] = None
        self._day_start_equity: float = 0.0
        self._peak_equity: float = 0.0
        self.halted: bool = False
        self.just_halted: bool = False
        self.halt_reason: str = ""

    # -- kill switches --------------------------------------------------- #
    def update(self, portfolio: Portfolio, bar: Bar) -> bool:
        """Call once per bar after marking to market. Returns True if new entries
        are currently disallowed.
        """
        equity = portfolio.equity()
        d = bar.time.date()
        if self._day != d:
            self._day = d
            self._day_start_equity = equity
            # a new day clears a *daily-loss* halt but not a drawdown halt
            if self.halt_reason == "daily_loss":
                self.halted = False
                self.halt_reason = ""
        self._peak_equity = max(self._peak_equity, equity) if self._peak_equity else equity

        self.just_halted = False
        if not self.halted:
            daily_dd = (equity - self._day_start_equity) / self._day_start_equity if self._day_start_equity else 0.0
            total_dd = (equity - self._peak_equity) / self._peak_equity if self._peak_equity else 0.0
            if self.max_daily_loss > 0 and daily_dd <= -self.max_daily_loss:
                self.halted = True
                self.halt_reason = "daily_loss"
                self.just_halted = True
            elif self.max_drawdown > 0 and total_dd <= -self.max_drawdown:
                self.halted = True
                self.halt_reason = "max_drawdown"
                self.just_halted = True
        return self.halted

    # -- sizing ---------------------------------------------------------- #
    def size_order(self, signal: Signal, portfolio: Portfolio, bar: Bar) -> Optional[Order]:
        pos = portfolio.position(signal.symbol)
        price = bar.close
        equity = portfolio.equity()

        if signal.action == SignalAction.CLOSE:
            target = 0.0
        else:
            stop = signal.stop_loss
            if stop is not None and abs(price - stop) > _EPS:
                stop_dist = abs(price - stop)
            else:
                stop_dist = price * self.fallback_stop_pct
            if stop_dist <= _EPS:
                return None
            risk_amount = equity * self.risk_per_trade
            qty = risk_amount / (stop_dist * self.multiplier)

            # cap gross exposure
            if self.max_gross_exposure > 0 and price > 0:
                max_qty = (equity * self.max_gross_exposure) / (price * self.multiplier)
                qty = min(qty, max_qty)

            if qty < self.min_qty:
                return None
            target = qty if signal.action == SignalAction.LONG else -qty

        dq = target - pos.qty
        if abs(dq) < self.min_qty:
            return None

        side = Side.BUY if dq > 0 else Side.SELL
        return Order(
            symbol=signal.symbol,
            side=side,
            qty=abs(dq),
            type=OrderType.MARKET,
            stop_loss=signal.stop_loss if target != 0 else None,
            take_profit=signal.take_profit if target != 0 else None,
            tag=signal.action.value,
            created_time=bar.time,
        )
