# autotrader — a fully automated trading system, built from the ground up

A complete, modular algorithmic-trading system written in **pure Python
standard library** (no numpy/pandas required). It does data ingestion → signal
generation → risk-managed sizing → simulated execution → performance reporting,
and the **exact same engine drives both backtesting and live/paper trading** —
so what you test is what you trade.

```
┌──────────┐   bars   ┌───────────┐ signals ┌──────────────┐ orders ┌──────────┐ fills ┌────────────┐
│ Data feed │ ───────▶ │ Strategy   │ ──────▶ │ RiskManager   │ ─────▶ │ Broker    │ ────▶ │ Portfolio   │
│ (synth/   │          │ (EMA/RSI/  │         │ sizing + kill │        │ (paper/   │       │ cash, P&L,  │
│  CSV/live)│          │  Donchian) │         │ switches)     │        │  live)    │       │ trades      │
└──────────┘          └───────────┘         └──────────────┘        └──────────┘       └────────────┘
                                   shared per-bar pipeline: autotrader/engine.py
```

> **Honest framing.** This is real trading *infrastructure*, not a money
> printer. The bundled strategies are sound, classic templates; on random-walk
> synthetic data they score ~break-even after costs (exactly as theory predicts).
> Edge comes from *your* research on *real* data — this system gives you a
> rigorous, no-look-ahead place to find and validate it, and a safe paper-trading
> path before any live capital. Trading risks real loss; nothing here is advice.

---

## Quick start

```bash
# no install needed — pure stdlib
python -m autotrader strategies                 # list strategies
python -m autotrader demo --bars 8000           # synthetic backtest + report
python -m autotrader make-config cfg.json        # write a config to edit
python -m autotrader backtest -c cfg.json        # backtest from config
python -m autotrader paper -c cfg.json --max-bars 2000   # paper-trade a replayed feed

python examples/backtest_demo.py                 # compare all three strategies
```

From Python:

```python
from autotrader import SystemConfig, run_backtest

cfg = SystemConfig()
cfg.strategy.name = "donchian_breakout"
cfg.data.symbol   = "XAUUSD"
cfg.data.n_bars   = 20_000
result = run_backtest(cfg)
print(result.report.pretty())
```

---

## What's included

| Module | Responsibility |
|---|---|
| `types.py` | Domain primitives: `Bar`, `Order`, `Fill`, `Signal`, `Position` |
| `indicators.py` | Incremental `EMA`, `RSI`, `ATR`, Donchian, rolling std (hand-written, O(1)/bar) |
| `data.py` | `SyntheticProvider`, `CSVProvider`, `ReplayLiveProvider` + base interface |
| `strategies.py` | `EMACrossover`, `RSIReversion`, `DonchianBreakout` + a registry |
| `portfolio.py` | Netted positions, cash, mark-to-market equity, round-trip trade log |
| `risk.py` | Per-trade sizing from stop distance; daily-loss & max-drawdown kill switches |
| `broker.py` | `PaperBroker` (commission, slippage, SL/TP, liquidation) + `LiveBrokerBase` |
| `engine.py` | The shared per-bar pipeline used by backtest **and** live |
| `metrics.py` | Sharpe, Sortino, CAGR, max drawdown, profit factor, expectancy, … |
| `backtest.py` / `live.py` | Orchestration for each mode |
| `config.py` | Reproducible JSON configuration |
| `cli.py` | `python -m autotrader …` |

---

## Design decisions that matter

**No look-ahead bias.** A signal is computed on a bar's *close*; the resulting
market order fills no earlier than the **next bar's open**. Stops and targets are
checked against each bar's high/low. This is enforced in `engine.step()` and
covered by a test.

**One engine, two modes.** `TradingEngine.step(bar)` contains all the logic. The
backtester feeds it history; the live runner feeds it a stream. A test
(`test_live_runner_matches_backtest`) asserts both produce identical equity on
the same bars.

**Risk first.** The `RiskManager` is the only thing that turns a signal into an
order. It sizes every entry so that hitting the stop loses a fixed fraction of
equity (`risk_per_trade`), caps gross exposure, and **flattens everything** when
a daily-loss or drawdown limit trips.

**Realistic costs.** The `PaperBroker` charges commission (per-unit and/or bps of
notional) and applies adverse slippage to market/stop fills. A test confirms
adding costs can only *reduce* returns on identical data.

**Asset/timeframe agnostic.** Stops are ATR-based; a `multiplier` scales price
moves into account currency (1.0 spot/FX, contract value for futures). Works on
gold, crypto, indices, equities, any timeframe.

---

## Going live (for real)

The system never assumes paper vs live — the engine only calls the `BrokerBase`
interface. To trade a real venue:

1. Implement `LiveBrokerBase` (in `broker.py`) against your API — `submit()`
   places the order, `on_bar_open()/on_bar_range()` translate venue fills into
   `Fill` objects, `liquidate()` flattens. Good targets: **ccxt** (crypto),
   **Alpaca**, **Interactive Brokers**, **MetaTrader 5**.
2. Implement a streaming `DataProvider` that yields a `Bar` when each candle
   closes.
3. `build_live_runner(cfg, your_provider, broker=your_broker)` and `.run()`.

**Before risking a cent:** backtest on real historical data, then paper-trade
forward for a meaningful period. Keep `risk_per_trade` small (0.25–1%) and leave
the kill switches on.

---

## Configuration reference (`SystemConfig`)

```jsonc
{
  "data":     { "provider": "synthetic", "symbol": "XAUUSD", "n_bars": 5000,
                "volatility": 0.0012, "timeframe_minutes": 1, "seed": 7,
                "path": null /* set for provider:"csv" */ },
  "strategy": { "name": "ema_crossover", "params": { "fast": 12, "slow": 26 } },
  "broker":   { "commission_rate": 0.0002, "slippage_bps": 1.0, "multiplier": 1.0 },
  "risk":     { "risk_per_trade": 0.01, "max_gross_exposure": 1.0,
                "max_daily_loss": 0.05, "max_drawdown": 0.25 },
  "account":  { "starting_cash": 100000.0, "multiplier": 1.0 }
}
```

Run on your own data by setting `data.provider = "csv"` and `data.path` to a CSV
with `time, open, high, low, close[, volume]` columns.

---

## Tests

```bash
pip install pytest      # only dependency, and only for running tests
python -m pytest -q
```

39 tests cover indicators, position/PnL math, broker fills & SL/TP, risk sizing
& kill switches, the no-look-ahead guarantee, determinism, cost monotonicity,
and backtest/live equivalence.

---

## Extending it

Add a strategy by subclassing `Strategy`, implementing `on_bar(bar) -> [Signal]`,
and registering it:

```python
from autotrader.strategies import Strategy, STRATEGY_REGISTRY
from autotrader.types import Signal, SignalAction

class MyStrategy(Strategy):
    name = "my_strategy"
    def on_bar(self, bar):
        # ... update your indicators, decide ...
        return [Signal(self.symbol, SignalAction.LONG, bar.time, stop_loss=bar.close*0.99)]

STRATEGY_REGISTRY[MyStrategy.name] = MyStrategy
```

That's it — sizing, execution, risk, and reporting come for free.
