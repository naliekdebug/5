from datetime import datetime, timezone

from autotrader.portfolio import Portfolio
from autotrader.risk import RiskManager
from autotrader.types import Bar, Side, Signal, SignalAction


def _bar(c, day=1, sym="X"):
    return Bar(sym, datetime(2024, 1, day, 12, 0, tzinfo=timezone.utc), c, c, c, c)


def test_size_order_respects_risk_per_trade():
    p = Portfolio(100_000.0)
    p.mark("X", 100.0)
    r = RiskManager(risk_per_trade=0.01, max_gross_exposure=10.0)
    sig = Signal("X", SignalAction.LONG, _bar(100).time, stop_loss=98.0)  # 2.0 risk/unit
    order = r.size_order(sig, p, _bar(100))
    # risk budget = 1000; stop distance 2 -> 500 units
    assert order is not None
    assert order.side == Side.BUY
    assert abs(order.qty - 500.0) < 1e-6


def test_gross_exposure_cap():
    p = Portfolio(100_000.0)
    p.mark("X", 100.0)
    r = RiskManager(risk_per_trade=1.0, max_gross_exposure=1.0)  # huge risk, but capped
    sig = Signal("X", SignalAction.LONG, _bar(100).time, stop_loss=99.99)
    order = r.size_order(sig, p, _bar(100))
    # cap: equity*1.0 / price = 100000/100 = 1000 units max
    assert order is not None
    assert order.qty <= 1000.0 + 1e-6


def test_close_signal_targets_flat():
    p = Portfolio(100_000.0)
    p.position("X").apply(10.0, 100.0)
    p.mark("X", 100.0)
    r = RiskManager()
    sig = Signal("X", SignalAction.CLOSE, _bar(100).time)
    order = r.size_order(sig, p, _bar(100))
    assert order is not None
    assert order.side == Side.SELL
    assert abs(order.qty - 10.0) < 1e-9


def test_daily_loss_halt():
    p = Portfolio(100_000.0)
    r = RiskManager(max_daily_loss=0.05, max_drawdown=0.99)
    # day 1 baseline
    p.mark("X", 100.0)
    assert r.update(p, _bar(100, day=1)) is False
    # simulate a 6% loss same day
    p.cash -= 6_000.0
    assert r.update(p, _bar(100, day=1)) is True
    assert r.halt_reason == "daily_loss"
    assert r.just_halted is True
    # new day clears the daily-loss halt
    assert r.update(p, _bar(100, day=2)) is False


def test_drawdown_halt_persists():
    p = Portfolio(100_000.0)
    r = RiskManager(max_daily_loss=0.99, max_drawdown=0.10)
    p.mark("X", 100.0)
    r.update(p, _bar(100, day=1))
    p.cash -= 11_000.0  # 11% drawdown
    assert r.update(p, _bar(100, day=1)) is True
    assert r.halt_reason == "max_drawdown"
    # next day: drawdown halt should NOT clear
    assert r.update(p, _bar(100, day=2)) is True
