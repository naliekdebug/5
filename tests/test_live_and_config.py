import json
import os
import tempfile

from autotrader import SystemConfig
from autotrader.backtest import build_data_provider, run_backtest
from autotrader.data import ReplayLiveProvider
from autotrader.live import build_live_runner


def test_config_roundtrip():
    cfg = SystemConfig()
    cfg.strategy.name = "donchian_breakout"
    cfg.strategy.params = {"entry_period": 30}
    cfg.data.n_bars = 1234
    d = json.loads(cfg.to_json())
    cfg2 = SystemConfig.from_dict(d)
    assert cfg2.strategy.name == "donchian_breakout"
    assert cfg2.strategy.params["entry_period"] == 30
    assert cfg2.data.n_bars == 1234


def test_config_save_load(tmp_path=None):
    cfg = SystemConfig()
    cfg.data.symbol = "BTCUSD"
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "cfg.json")
        cfg.save(path)
        loaded = SystemConfig.load(path)
        assert loaded.data.symbol == "BTCUSD"


def test_live_runner_matches_backtest():
    """The live runner and the backtester share the engine, so replaying the
    same bars through both must give the same final equity.
    """
    cfg = SystemConfig()
    cfg.data.n_bars = 2000
    cfg.data.volatility = 0.003

    bars = list(build_data_provider(cfg))
    bt = run_backtest(cfg, bars=bars)

    provider = ReplayLiveProvider(bars, speed=0.0)
    runner = build_live_runner(cfg, provider)
    runner.run()
    live_equity = runner.engine.portfolio.equity()

    assert abs(live_equity - bt.report.end_equity) < 1e-6
    assert len(runner.engine.portfolio.trades) == bt.report.num_trades


def test_live_max_bars_stops_early():
    cfg = SystemConfig()
    cfg.data.n_bars = 1000
    bars = list(build_data_provider(cfg))
    runner = build_live_runner(cfg, ReplayLiveProvider(bars))
    runner.run(max_bars=100)
    assert len(runner.engine.portfolio.equity_curve) == 100
