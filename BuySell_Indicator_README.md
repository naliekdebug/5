# Buy/Sell Indicator — Trend + Momentum (Pine Script)

A TradingView indicator (**Pine Script v5**) that prints **BUY** and **SELL**
labels directly on the chart when trend, momentum, and (optionally) the
higher timeframe all agree. Works on any symbol and any timeframe.

---

## ⚠️ Read this first — honest expectations

No indicator predicts the market. Signals here mean *"trend and momentum are
aligned right now"* — nothing more. Expect losing signals, especially in
sideways/choppy markets (that is what the volatility filter is for). Always
test on historical data and paper-trade before risking real money. This is
not financial advice.

---

## Signal logic

A **BUY** fires on a closed bar when **all** enabled filters agree
(mirror the conditions for a **SELL**):

| Component | Condition (BUY) | Condition (SELL) |
|---|---|---|
| Trend | Fast EMA(21) above Slow EMA(50) | Fast EMA below Slow EMA |
| Momentum | RSI(14) between 50 and 70 | RSI between 30 and 50 |
| Higher-TF (optional) | Price above 4H EMA(50) | Price below 4H EMA(50) |
| Volatility (optional) | ATR(14) ≥ 0.8 × its average | same |

Signals alternate — after a BUY, the next signal can only be a SELL (and vice
versa), so you don't get repeated buys stacked on the same move. A signal can
fire on the exact EMA cross **or later**, once a lagging filter (RSI / higher
TF) catches up and everything aligns.

Signals are evaluated on **bar close only** (`barstate.isconfirmed`), and the
higher-timeframe EMA uses the **last closed** higher-TF bar, so signals do
**not repaint**.

**Extras:**

- Bar coloring by trend direction (teal = bullish, red = bearish).
- Optional ATR-based **SL/TP guide lines** at each signal
  (default SL = 1.5 × ATR, TP = 2.25 × ATR ≈ 1:1.5 R:R).
- Three `alertcondition`s: *Buy signal*, *Sell signal*, *Any signal* — usable
  with app/email notifications or webhooks.

---

## Installation

1. Open [TradingView](https://tradingview.com) and any chart.
2. Open the **Pine Editor** (bottom panel).
3. Delete the boilerplate and paste the contents of **`BuySell_Indicator.pine`**.
4. Click **Add to chart**. Save the script (name it whatever you like).

## Setting alerts

1. Right-click the chart → **Add alert** (or press `Alt+A`).
2. Condition: **Buy/Sell Indicator — Trend + Momentum** → pick
   *Buy signal*, *Sell signal*, or *Any signal*.
3. Set **"Once per bar close"** so alerts match the non-repainting signals.
4. Choose notification channel (app, email, webhook) and create.

---

## Key inputs

| Input | Default | Meaning |
|---|---|---|
| Fast / Slow EMA length | 21 / 50 | Trend definition; larger = fewer, slower signals |
| Use RSI filter | on | Require momentum to agree; blocks overbought buys / oversold sells |
| Skip buys when RSI above | 70 | Overbought cutoff |
| Skip sells when RSI below | 30 | Oversold cutoff |
| Use higher-TF trend filter | on | Only trade with the higher-timeframe trend |
| Higher timeframe / EMA length | 240 (4H) / 50 | The higher-TF trend reference |
| Require minimum volatility | off | Skip signals in flat markets (ATR below its average) |
| Show SL/TP guide lines | on | Draw ATR-based stop/target levels at each signal |
| Stop loss / Take profit (× ATR) | 1.5 / 2.25 | Size of the guide levels |

**Tuning tips:**

- Scalping (1–15 min charts): consider Fast/Slow = 9/21 and a 1H higher TF.
- Swing trading (4H–1D charts): keep 21/50 and use a 1W higher TF.
- Too many signals in chop? Turn **on** the volatility filter.
- Too few signals? Turn **off** the higher-TF filter (expect lower quality).
