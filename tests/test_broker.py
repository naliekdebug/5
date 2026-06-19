from datetime import datetime, timezone

from autotrader.broker import PaperBroker
from autotrader.portfolio import Portfolio
from autotrader.types import Bar, Order, OrderType, Side


def _bar(o, h, l, c, i=0, sym="X"):
    return Bar(sym, datetime(2024, 1, 1, 0, i, tzinfo=timezone.utc), o, h, l, c)


def test_market_order_fills_next_open():
    b = PaperBroker()
    p = Portfolio(10_000.0)
    b.submit(Order("X", Side.BUY, 1, OrderType.MARKET))
    # same bar: nothing should fill on submit; fills happen on the next bar open
    fills_open = b.on_bar_open(_bar(100, 101, 99, 100, 0))
    assert len(fills_open) == 1
    assert fills_open[0].price == 100.0  # at the open


def test_slippage_is_adverse():
    b = PaperBroker(slippage_bps=10.0)  # 0.1%
    b.submit(Order("X", Side.BUY, 1, OrderType.MARKET))
    f = b.on_bar_open(_bar(100, 101, 99, 100, 0))[0]
    assert f.price > 100.0  # buyer pays up
    b2 = PaperBroker(slippage_bps=10.0)
    b2.submit(Order("X", Side.SELL, 1, OrderType.MARKET))
    f2 = b2.on_bar_open(_bar(100, 101, 99, 100, 0))[0]
    assert f2.price < 100.0  # seller gets less


def test_long_stop_loss_triggers():
    b = PaperBroker()
    p = Portfolio(10_000.0)
    # open a long via fill, attach SL at 95
    b.submit(Order("X", Side.BUY, 1, OrderType.MARKET, stop_loss=95.0, take_profit=110.0))
    for f in b.on_bar_open(_bar(100, 101, 99, 100, 0)):
        p.on_fill(f)
    assert p.position("X").qty == 1.0
    # next bar dips to 94 -> stop hit
    fills = b.on_bar_range(_bar(99, 100, 94, 96, 1), p)
    assert len(fills) == 1
    assert fills[0].tag == "stop_loss"
    for f in fills:
        p.on_fill(f)
    assert p.position("X").is_flat


def test_long_take_profit_triggers():
    b = PaperBroker()
    p = Portfolio(10_000.0)
    b.submit(Order("X", Side.BUY, 1, OrderType.MARKET, stop_loss=95.0, take_profit=110.0))
    for f in b.on_bar_open(_bar(100, 101, 99, 100, 0)):
        p.on_fill(f)
    fills = b.on_bar_range(_bar(101, 112, 100, 109, 1), p)
    assert len(fills) == 1
    assert fills[0].tag == "take_profit"
    assert fills[0].price == 110.0  # TP filled exactly, no slippage


def test_commission_charged_on_fill():
    b = PaperBroker(commission_rate=0.001)  # 0.1%
    b.submit(Order("X", Side.BUY, 2, OrderType.MARKET))
    f = b.on_bar_open(_bar(100, 101, 99, 100, 0))[0]
    assert abs(f.commission - 0.001 * 2 * f.price) < 1e-9


def test_liquidate_closes_position():
    b = PaperBroker()
    p = Portfolio(10_000.0)
    b.submit(Order("X", Side.BUY, 3, OrderType.MARKET))
    for f in b.on_bar_open(_bar(100, 101, 99, 100, 0)):
        p.on_fill(f)
    fills = b.liquidate(_bar(100, 101, 99, 100, 1), p)
    for f in fills:
        p.on_fill(f)
    assert p.position("X").is_flat
    assert fills[0].tag == "liquidate"
