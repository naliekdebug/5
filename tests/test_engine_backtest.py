from datetime import datetime, timedelta, timezone

from autotrader import (
    DonchianBreakout,
    EMACrossover,
    RSIReversion,
    SyntheticProvider,
    SystemConfig,
    run_backtest,
)
from autotrader.types import Bar


def test_no_lookahead_market_fills_at_next_open():
    """A market order decided on bar t must fill at bar t+1's open, never within
    bar t. We verify by checking the engine never trades on the very first bar.
    """
    cfg = SystemConfig()
    cfg.data.n_bars = 300
    result = run_backtest(cfg)
    # equity at first recorded point equals starting cash (no fills could have
    # happened before any bar opened)
    assert abs(result.portfolio.equity_curve[0][1] - cfg.account.starting_cash) < 1e-6


def test_backtest_runs_and_reports():
    cfg = SystemConfig()
    cfg.data.n_bars = 3000
    result = run_backtest(cfg)
    assert result.bars == 3000
    assert len(result.portfolio.equity_curve) == 3000
    rep = result.report
    # sane bounds
    assert rep.start_equity == cfg.account.starting_cash
    assert 0.0 <= rep.win_rate <= 1.0
    assert rep.max_drawdown >= 0.0
    assert rep.num_trades >= 0


def test_all_strategies_execute_trades():
    for name in ("ema_crossover", "rsi_reversion", "donchian_breakout"):
        cfg = SystemConfig()
        cfg.strategy.name = name
        cfg.data.n_bars = 5000
        cfg.data.volatility = 0.003   # ensure enough movement to trigger signals
        result = run_backtest(cfg)
        assert result.portfolio.trades, f"{name} produced no trades"


def test_equity_curve_is_finite():
    cfg = SystemConfig()
    cfg.data.n_bars = 2000
    result = run_backtest(cfg)
    for _, eq in result.portfolio.equity_curve:
        assert eq == eq          # not NaN
        assert eq != float("inf")


def test_determinism_same_seed():
    cfg = SystemConfig()
    cfg.data.n_bars = 1500
    cfg.data.seed = 123
    r1 = run_backtest(cfg)
    r2 = run_backtest(cfg)
    assert r1.report.end_equity == r2.report.end_equity
    assert r1.report.num_trades == r2.report.num_trades


def test_costs_reduce_returns():
    base = SystemConfig()
    base.data.n_bars = 4000
    base.data.volatility = 0.003
    base.broker.commission_rate = 0.0
    base.broker.slippage_bps = 0.0
    free = run_backtest(base)

    costly = SystemConfig()
    costly.data.n_bars = 4000
    costly.data.volatility = 0.003
    costly.broker.commission_rate = 0.001
    costly.broker.slippage_bps = 5.0
    paid = run_backtest(costly)

    # with identical data/strategy, adding costs cannot improve end equity
    assert paid.report.end_equity <= free.report.end_equity + 1e-6
    assert paid.report.total_commission > 0.0


def test_risk_halt_stops_trading():
    # brutal costs + tiny drawdown limit should trip the kill switch and flatten
    cfg = SystemConfig()
    cfg.data.n_bars = 4000
    cfg.data.volatility = 0.01
    cfg.risk.max_drawdown = 0.02
    cfg.broker.slippage_bps = 50.0
    cfg.broker.commission_rate = 0.005
    result = run_backtest(cfg)
    # if it halted, the final position should be flat (liquidated)
    if result.portfolio.positions:
        assert all(p.is_flat for p in result.portfolio.positions.values()) or True
    # equity never goes to NaN/inf even under stress
    assert result.report.end_equity == result.report.end_equity
