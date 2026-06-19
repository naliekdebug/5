"""Command-line interface.

    python -m autotrader demo                 # quick synthetic backtest
    python -m autotrader backtest -c cfg.json # backtest from a config file
    python -m autotrader paper -c cfg.json    # paper-trade (replayed live feed)
    python -m autotrader make-config cfg.json # write a default config to edit
    python -m autotrader strategies           # list available strategies
"""
from __future__ import annotations

import argparse
import logging
import sys

from .backtest import build_data_provider, run_backtest
from .config import SystemConfig
from .data import ReplayLiveProvider
from .live import build_live_runner
from .strategies import STRATEGY_REGISTRY


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def cmd_demo(args) -> int:
    cfg = SystemConfig()
    cfg.data.n_bars = args.bars
    if args.strategy:
        cfg.strategy.name = args.strategy
    result = run_backtest(cfg)
    print(f"Strategy: {cfg.strategy.name}   Symbol: {cfg.data.symbol}   Bars: {result.bars}")
    print(result.report.pretty())
    return 0


def cmd_backtest(args) -> int:
    cfg = SystemConfig.load(args.config)
    result = run_backtest(cfg)
    print(f"Strategy: {cfg.strategy.name}   Symbol: {cfg.data.symbol}   Bars: {result.bars}")
    print(result.report.pretty())
    return 0


def cmd_paper(args) -> int:
    cfg = SystemConfig.load(args.config)
    bars = list(build_data_provider(cfg))
    provider = ReplayLiveProvider(bars, speed=args.speed)
    runner = build_live_runner(cfg, provider)

    def tick(engine):
        eq = engine.portfolio.equity()
        print(f"\r equity={eq:,.2f}  trades={len(engine.portfolio.trades)}  "
              f"halted={engine.risk.halted}", end="", flush=True)

    runner.engine  # noqa
    runner.on_bar = tick
    runner.run(max_bars=args.max_bars)
    print()
    from .metrics import compute_metrics
    report = compute_metrics(runner.engine.portfolio.equity_curve,
                             runner.engine.portfolio.trades,
                             runner.engine.portfolio.total_commission)
    print(report.pretty())
    return 0


def cmd_make_config(args) -> int:
    cfg = SystemConfig()
    cfg.save(args.path)
    print(f"Wrote default config to {args.path}")
    return 0


def cmd_strategies(args) -> int:
    print("Available strategies:")
    for name in sorted(STRATEGY_REGISTRY):
        print(f"  - {name}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="autotrader", description="Automated trading system")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="quick synthetic backtest")
    d.add_argument("--bars", type=int, default=5000)
    d.add_argument("--strategy", default=None)
    d.set_defaults(func=cmd_demo)

    b = sub.add_parser("backtest", help="backtest from a config file")
    b.add_argument("-c", "--config", required=True)
    b.set_defaults(func=cmd_backtest)

    pa = sub.add_parser("paper", help="paper-trade against a replayed feed")
    pa.add_argument("-c", "--config", required=True)
    pa.add_argument("--speed", type=float, default=0.0, help="seconds between bars")
    pa.add_argument("--max-bars", type=int, default=None)
    pa.set_defaults(func=cmd_paper)

    mc = sub.add_parser("make-config", help="write a default config file")
    mc.add_argument("path")
    mc.set_defaults(func=cmd_make_config)

    s = sub.add_parser("strategies", help="list strategies")
    s.set_defaults(func=cmd_strategies)

    args = p.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
