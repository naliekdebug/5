# Stop-Loss Liquidity Map & Trade Planner (Pine Script v5)

A TradingView indicator that **analyzes the chart for where stop-loss orders
most likely rest**, clusters them into weighted **stop pools**, then builds a
concrete **Entry / Stop / Take-Profit plan around those levels** — with R:R and
position sizing.

Works on **any asset and any timeframe**: every tolerance is ATR- or
percent-based, nothing is hardcoded in pips/ticks.

> Analysis/visualization tool — **not financial advice**. The plan is a
> structured suggestion; confirm it with your own context and risk rules.

---

## Why this finds "the most likely stop losses"

Stops don't sit randomly — they cluster **just beyond protective levels**, which
is exactly the resting liquidity that price gets drawn toward. The indicator
collects candidate levels from:

| Source | Stops rest… | Weight |
|---|---|---|
| Swing low | just **below** it (longs' stops = sell-side) | 1 |
| Swing high | just **above** it (shorts' stops = buy-side) | 1 |
| Equal highs / lows | same, but stronger pool | 2 |
| Previous day High/Low | beyond it | 2 |
| Previous week High/Low | beyond it | 2.5 |
| Round numbers (optional) | at the level | 1 |

Nearby candidates **merge into one pool** and their weights add up, so a level
hit by several swings + an equal high + the prior-day high becomes a **high-
strength pool** (thicker, more opaque line, higher `x` score). Those are the
magnets price hunts.

Each pool is labeled, e.g. `▲ buy-side stops x3.0 EQ HTF` (strength 3, contains
an equal high and a higher-timeframe level).

---

## How the trade plan is built

1. **Bias** — `Auto` (price vs an EMA), or force `Long` / `Short`.
2. **Stop loss is placed *beyond* the nearest pool**, not at it — so a routine
   liquidity sweep doesn't tag you. Extra cushion = `Stop beyond pool (× ATR)`.
3. **Take-profits target the opposite pools** (TP1 = nearest, TP2 = next), the
   places price is being pulled toward. If no qualifying pool exists, it falls
   back to a configurable R:R.
4. **Entry**:
   - `Market` — plan from current price.
   - `Limit at pullback pool` — entry at the nearest pool in the pullback
     direction (buy the dip into sell-side liquidity / sell the rip into
     buy-side), with the stop moved beyond the *next* pool.
5. A **summary table** shows Bias, Entry, SL, TP1/TP2 with R-multiples, price
   risk, dollar risk, and a **suggested position size**.

Lines drawn: **Entry** (blue), **SL** (red dashed), **TP1** (green), **TP2**
(green dotted), plus shaded risk and reward zones.

---

## Install

1. TradingView → **Pine Editor**.
2. Paste the contents of `StopLoss_Liquidity_Planner.pine`.
3. **Save** → **Add to chart**.
4. Open ⚙ settings to tune detection, the planner, and sizing.

---

## Key settings

| Setting | Default | What it does |
|---|---|---|
| `Swing lookback` | 8 | Pivot sensitivity (lower = more, smaller swings) |
| `Stop sits beyond level (× ATR)` | 0.10 | Where the crowd's stops sit past a swing |
| `Cluster merge tolerance (× ATR)` | 0.30 | How aggressively nearby levels merge into one pool |
| `Min pool strength for plan` | 2.0 | Planner ignores weak single-swing pools |
| `Stop beyond pool (× ATR)` | 0.25 | Cushion past the pool for your own SL |
| `Round-number step` | 0 (off) | e.g. `1` indices, `0.0010` FX, `100` BTC |
| `Account size / Risk % / $ per point` | 10000 / 1% / 1 | Position-size math |
| `Directional bias` | Auto | Auto / Long / Short |
| `Entry` | Market | Market or limit-at-pullback-pool |

**Scaling tips:** raise `Swing lookback` (12–20) on H1+; lower it (4–8) for
M1–M5 scalps. Tighten `Cluster merge tolerance` for fewer, cleaner pools.

---

## Alerts

- **Approaching upper / lower stop pool** — price within `× ATR` of a pool (sweep
  likely).
- **Upper / lower stop pool swept** — price ran the pool then closed back
  (stop-hunt rejection — a common reversal trigger).

---

## Honest limits

- Swing-anchored pools confirm `swingLen` bars after the pivot (inherent to
  pivot detection).
- "Most likely" stop locations are a **probabilistic model of crowd behavior**,
  not certainty — real stops are unknowable. Treat pools as high-interest zones,
  not guarantees.
- The planner is mechanical; it has no view on news, higher-timeframe bias, or
  session timing. Use it to *structure* a trade, not to fire blindly.
