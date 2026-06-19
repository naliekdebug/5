"""Performance metrics computed from an equity curve and trade list.

Pure standard library. Annualization factors are inferred from the median bar
spacing so the same code gives sensible Sharpe numbers on M1 or daily data.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Tuple

from .types import TradeRecord


@dataclass
class PerformanceReport:
    start_equity: float
    end_equity: float
    total_return: float
    cagr: float
    max_drawdown: float
    sharpe: float
    sortino: float
    volatility_annual: float
    num_trades: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    expectancy: float
    largest_win: float
    largest_loss: float
    total_commission: float

    def as_dict(self) -> dict:
        return asdict(self)

    def pretty(self) -> str:
        pct = lambda x: f"{x * 100:8.2f}%"
        lines = [
            "──────── Performance ────────",
            f"Start equity      {self.start_equity:14,.2f}",
            f"End equity        {self.end_equity:14,.2f}",
            f"Total return      {pct(self.total_return)}",
            f"CAGR              {pct(self.cagr)}",
            f"Max drawdown      {pct(self.max_drawdown)}",
            f"Volatility (ann)  {pct(self.volatility_annual)}",
            f"Sharpe            {self.sharpe:9.2f}",
            f"Sortino           {self.sortino:9.2f}",
            "──────── Trades ─────────────",
            f"Trades            {self.num_trades:9d}",
            f"Win rate          {pct(self.win_rate)}",
            f"Profit factor     {self.profit_factor:9.2f}",
            f"Avg win           {self.avg_win:14,.2f}",
            f"Avg loss          {self.avg_loss:14,.2f}",
            f"Expectancy/trade  {self.expectancy:14,.2f}",
            f"Largest win       {self.largest_win:14,.2f}",
            f"Largest loss      {self.largest_loss:14,.2f}",
            f"Total commission  {self.total_commission:14,.2f}",
            "─────────────────────────────",
        ]
        return "\n".join(lines)


def _infer_periods_per_year(times: List[datetime]) -> float:
    if len(times) < 3:
        return 252.0
    deltas = sorted((times[i + 1] - times[i]).total_seconds() for i in range(len(times) - 1))
    median = deltas[len(deltas) // 2]
    if median <= 0:
        return 252.0
    seconds_per_year = 365.25 * 24 * 3600
    return seconds_per_year / median


def _max_drawdown(equity: List[float]) -> float:
    peak = equity[0]
    mdd = 0.0
    for e in equity:
        peak = max(peak, e)
        if peak > 0:
            mdd = min(mdd, (e - peak) / peak)
    return -mdd  # positive magnitude


def compute_metrics(
    equity_curve: List[Tuple[datetime, float]],
    trades: List[TradeRecord],
    total_commission: float = 0.0,
    risk_free_rate: float = 0.0,
) -> PerformanceReport:
    if not equity_curve:
        raise ValueError("empty equity curve")

    times = [t for t, _ in equity_curve]
    equity = [e for _, e in equity_curve]
    start_eq = equity[0]
    end_eq = equity[-1]
    total_return = (end_eq / start_eq - 1.0) if start_eq else 0.0

    # time span in years
    span_seconds = max((times[-1] - times[0]).total_seconds(), 1.0)
    years = span_seconds / (365.25 * 24 * 3600)
    cagr = ((end_eq / start_eq) ** (1.0 / years) - 1.0) if (start_eq > 0 and end_eq > 0 and years > 0) else 0.0

    # per-bar simple returns
    rets = [(equity[i] / equity[i - 1] - 1.0) for i in range(1, len(equity)) if equity[i - 1] > 0]
    ppy = _infer_periods_per_year(times)
    if rets:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / len(rets)
        std = math.sqrt(var)
        downside = [min(r, 0.0) for r in rets]
        dvar = sum(d * d for d in downside) / len(downside)
        dstd = math.sqrt(dvar)
        rf_per_period = risk_free_rate / ppy
        sharpe = ((mean - rf_per_period) / std * math.sqrt(ppy)) if std > 0 else 0.0
        sortino = ((mean - rf_per_period) / dstd * math.sqrt(ppy)) if dstd > 0 else 0.0
        vol_annual = std * math.sqrt(ppy)
    else:
        sharpe = sortino = vol_annual = 0.0

    mdd = _max_drawdown(equity)

    # trade stats
    n = len(trades)
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl < 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    win_rate = len(wins) / n if n else 0.0
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    avg_win = (gross_win / len(wins)) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0
    expectancy = (sum(t.pnl for t in trades) / n) if n else 0.0
    largest_win = max((t.pnl for t in trades), default=0.0)
    largest_loss = min((t.pnl for t in trades), default=0.0)

    return PerformanceReport(
        start_equity=start_eq, end_equity=end_eq, total_return=total_return, cagr=cagr,
        max_drawdown=mdd, sharpe=sharpe, sortino=sortino, volatility_annual=vol_annual,
        num_trades=n, win_rate=win_rate, profit_factor=profit_factor,
        avg_win=avg_win, avg_loss=avg_loss, expectancy=expectancy,
        largest_win=largest_win, largest_loss=largest_loss, total_commission=total_commission,
    )
