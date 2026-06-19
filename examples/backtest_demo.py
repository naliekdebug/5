"""Run a few strategies on synthetic data and print performance reports.

    python examples/backtest_demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autotrader import SystemConfig, run_backtest


def main():
    for strat in ("ema_crossover", "rsi_reversion", "donchian_breakout"):
        cfg = SystemConfig()
        cfg.strategy.name = strat
        cfg.data.symbol = "XAUUSD"
        cfg.data.n_bars = 20_000
        cfg.data.volatility = 0.0015
        cfg.broker.commission_rate = 0.0002   # 2 bps
        cfg.broker.slippage_bps = 1.0
        cfg.risk.risk_per_trade = 0.01

        result = run_backtest(cfg)
        print("\n" + "=" * 40)
        print(f"Strategy: {strat}  |  bars: {result.bars}  |  trades: {result.report.num_trades}")
        print("=" * 40)
        print(result.report.pretty())


if __name__ == "__main__":
    main()
