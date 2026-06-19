from datetime import datetime, timezone

from autotrader.portfolio import Portfolio, Position
from autotrader.types import Fill, Side


def _t(i=0):
    return datetime(2024, 1, 1, 0, i, tzinfo=timezone.utc)


def fill(symbol, side, qty, price, commission=0.0, sl=None, tp=None, time=None):
    return Fill(0, symbol, side, qty, price, commission, time or _t(), stop_loss=sl, take_profit=tp)


def test_position_long_roundtrip_pnl():
    pos = Position("X")
    assert pos.apply(1.0, 100.0) == 0.0
    realized = pos.apply(-1.0, 110.0)
    assert abs(realized - 10.0) < 1e-9
    assert pos.is_flat


def test_position_short_roundtrip_pnl():
    pos = Position("X")
    pos.apply(-2.0, 100.0)        # short 2 @ 100
    realized = pos.apply(2.0, 90.0)  # cover @ 90 -> +20
    assert abs(realized - 20.0) < 1e-9
    assert pos.is_flat


def test_position_average_in():
    pos = Position("X")
    pos.apply(1.0, 100.0)
    pos.apply(1.0, 120.0)
    assert abs(pos.avg_price - 110.0) < 1e-9
    assert pos.qty == 2.0


def test_position_flip():
    pos = Position("X")
    pos.apply(1.0, 100.0)         # long 1 @100
    realized = pos.apply(-3.0, 110.0)  # sell 3: close 1 (+10), flip to short 2 @110
    assert abs(realized - 10.0) < 1e-9
    assert pos.qty == -2.0
    assert abs(pos.avg_price - 110.0) < 1e-9


def test_portfolio_cash_and_equity_long():
    p = Portfolio(starting_cash=1000.0)
    p.on_fill(fill("X", Side.BUY, 2, 100.0))   # spend 200
    assert abs(p.cash - 800.0) < 1e-9
    p.mark("X", 105.0)
    assert abs(p.equity() - (800.0 + 2 * 105.0)) < 1e-9   # 1010
    p.on_fill(fill("X", Side.SELL, 2, 105.0))  # receive 210
    assert abs(p.cash - 1010.0) < 1e-9
    assert abs(p.realized_pnl - 10.0) < 1e-9
    assert p.equity() == p.cash


def test_portfolio_records_trade():
    p = Portfolio(starting_cash=1000.0)
    p.on_fill(fill("X", Side.BUY, 1, 100.0, commission=1.0, time=_t(0)))
    p.on_fill(fill("X", Side.SELL, 1, 110.0, commission=1.0, time=_t(5)))
    assert len(p.trades) == 1
    tr = p.trades[0]
    assert tr.direction == "long"
    assert abs(tr.pnl - (10.0 - 2.0)) < 1e-9   # net of 2 commissions
    assert abs(tr.return_pct - 0.10) < 1e-9


def test_commission_reduces_cash():
    p = Portfolio(starting_cash=1000.0)
    p.on_fill(fill("X", Side.BUY, 1, 100.0, commission=5.0))
    assert abs(p.cash - (1000.0 - 100.0 - 5.0)) < 1e-9
    assert abs(p.total_commission - 5.0) < 1e-9


def test_sl_tp_attached_and_cleared():
    p = Portfolio(starting_cash=1000.0)
    p.on_fill(fill("X", Side.BUY, 1, 100.0, sl=95.0, tp=110.0))
    pos = p.position("X")
    assert pos.stop_loss == 95.0 and pos.take_profit == 110.0
    p.on_fill(fill("X", Side.SELL, 1, 110.0))
    assert pos.stop_loss is None and pos.take_profit is None


def test_multiplier_scales_pnl():
    p = Portfolio(starting_cash=10_000.0, multiplier=10.0)
    p.on_fill(fill("X", Side.BUY, 1, 100.0))
    p.on_fill(fill("X", Side.SELL, 1, 101.0))
    # 1 point * multiplier 10 = 10 profit
    assert abs(p.realized_pnl - 10.0) < 1e-9
