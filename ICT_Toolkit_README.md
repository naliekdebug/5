# ICT Toolkit — PD Arrays, Liquidity & Market Structure (Pine Script v5)

A single TradingView indicator that renders the core **ICT (Inner Circle
Trader)** concepts on your chart. It is **asset- and timeframe-agnostic**: every
tolerance is measured in **ATR or percent**, so the same settings behave
consistently on FX, crypto, indices, stocks, gold, and futures, on any
timeframe from seconds to monthly.

> This is an **analysis / visualization** tool, not a strategy or signal
> service. It marks structure and PD arrays; trade decisions are yours.

---

## What it draws

### Market structure
- **Swing points** (pivot highs/lows) — labeled `H` / `L`.
- **BOS (Break of Structure)** — a close beyond the last swing *in the direction
  of trend*.
- **CHoCH (Change of Character)** — a close beyond the last swing that *flips*
  the trend, often the first sign of reversal.

### PD Arrays (Premium/Discount arrays)
- **Fair Value Gaps (FVG)** — 3-candle imbalances (bullish & bearish), optionally
  filtered by minimum size (× ATR) and auto-removed when **mitigated** (filled).
- **Order Blocks (OB)** — the last opposite-color candle before a structure break.
- **Breaker Blocks** — an order block that gets violated flips role (support↔
  resistance) and recolors automatically.

### Liquidity
- **Buy-side liquidity (BSL)** above swing highs, **Sell-side liquidity (SSL)**
  below swing lows — the resting stops ICT targets.
- **Equal Highs / Lows (EQH / EQL)** — clustered liquidity, detected with an
  ATR-based tolerance.
- **Liquidity sweeps** — marks when price runs a level (wick through) then closes
  back, i.e. a stop hunt.

### Premium / Discount
- The **dealing range** (highest/lowest over a lookback) split into a **Premium**
  zone (upper half, sell area), **Discount** zone (lower half, buy area), and the
  **Equilibrium** (50%) line.

---

## Install

1. Open **TradingView** → any chart → **Pine Editor** (bottom panel).
2. Open `ICT_Toolkit.pine` from this repo, copy its full contents.
3. Paste into the Pine Editor (replace the default template).
4. Click **Save**, then **Add to chart**.
5. Open the indicator's **settings (⚙)** to toggle each module and tune it.

---

## Tuning for your asset / timeframe

Because everything is ATR-relative, defaults work broadly, but you can dial it in:

| Want… | Adjust |
|---|---|
| Bigger / fewer swings | Increase **Swing lookback** |
| Only significant FVGs | Raise **Min FVG size (× ATR)** |
| Stricter equal highs/lows | Lower **Equal H/L tolerance (× ATR)** |
| Wider dealing range context | Increase **Dealing range lookback** |
| Less clutter / better speed | Lower **Max kept per object type** |

**Higher timeframes** (H1+): you may want a larger swing lookback (e.g. 15–20).
**Scalping** (M1–M5): smaller lookback (5–8) reacts faster.

---

## Alerts

Four built-in `alertcondition`s (set them via the ⏰ Alerts dialog):
- Bullish BOS/CHoCH
- Bearish BOS/CHoCH
- Buy-side liquidity swept
- Sell-side liquidity swept

---

## Notes & limits

- Swings (and therefore OB/liquidity anchored to them) confirm **`swingLen` bars
  after** the actual pivot — this is inherent to pivot detection, not a bug.
- Object counts are capped (`max_boxes_count` / `max_lines_count` /
  `max_labels_count` = 500, plus the per-type cap) so very long histories trim
  the oldest drawings.
- ICT concepts are **discretionary**; this tool standardizes their detection but
  cannot replace context (HTF bias, news, session timing). Use accordingly.
