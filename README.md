# XAUUSD M1 Scalper — MetaTrader 5 Expert Advisor

An Expert Advisor (EA) for **MetaTrader 5** that trades **XAUUSD (gold)** on the
**1-minute (M1)** timeframe. It evaluates **every closed 1-minute candle** and
opens a trade only when a trend + momentum + volatility setup lines up, with
strict ATR-based risk management.

---

## ⚠️ Read this first — honest expectations

**No EA can make a profitable trade on every candle.** That is not possible in
any real market:

- Price movement on the 1-minute timeframe is largely noise.
- Every trade pays the **spread** (and often commission), so trading blindly
  every minute is a guaranteed slow bleed.
- Any system will have losing trades and losing streaks.

What this EA actually does — and what "profitable" realistically means — is:

1. **Look at every M1 candle** as you asked.
2. **Trade only when the odds are reasonable** (trend aligned across timeframes,
   momentum confirming, volatility sufficient).
3. **Cut losers fast and let winners run** via an ATR stop loss and a larger
   take profit (positive risk:reward), break-even, and trailing stop.
4. **Cap risk** per trade and per day so the account survives bad runs.

Edge comes from *risk management and selectivity*, not from predicting every
candle. **Test on a demo account and forward-test before risking real money.**
Past performance does not guarantee future results.

---

## Strategy logic

A trade is opened on a closed M1 candle when **all** of these agree:

| Component | Condition (BUY) | Condition (SELL) |
|---|---|---|
| M1 trend | Fast EMA(21) above Slow EMA(50) | Fast EMA below Slow EMA |
| Momentum | EMA spread widening upward | EMA spread widening downward |
| Higher-TF trend (M15) | Price above EMA(50) | Price below EMA(50) |
| RSI(14) | between 50 and 70 | between 30 and 50 |
| Volatility | ATR(14) ≥ minimum floor | same |
| Spread | ≤ max allowed | same |
| Session/cooldown/daily-guard | all pass | same |

**Exits:** Stop loss = `ATR × 1.5`, Take profit = `ATR × 2.25` (≈ 1:1.5 R:R),
plus optional break-even and ATR trailing stop.

**Position sizing:** By default risks **0.5% of balance per trade**, computed
from the ATR stop distance so risk stays constant regardless of volatility.

---

## Installation

1. Open **MetaTrader 5**.
2. Menu **File → Open Data Folder**.
3. Go into `MQL5/Experts/`.
4. Copy **`XAUUSD_Scalper.mq5`** into that folder.
5. In MT5 open the **MetaEditor** (F4), find the file in the Navigator, and
   click **Compile** (F7). It should compile with no errors.
6. Back in MT5, open a **XAUUSD M1 chart**.
7. Drag **XAUUSD_Scalper** from Navigator → Expert Advisors onto the chart.
8. In the dialog, enable **Allow Algo Trading** and confirm the inputs.
9. Make sure the **Algo Trading** button in the toolbar is green.

> Your broker may name gold `XAUUSD`, `GOLD`, `XAUUSD.`, `XAUUSDm`, etc. Attach
> the EA to whichever symbol *is* spot gold. The EA prints a warning if the
> symbol name doesn't look like gold, but still runs.

---

## Backtesting (do this before going live)

1. In MT5 open **View → Strategy Tester** (Ctrl+R).
2. Select **XAUUSD_Scalper**, symbol **XAUUSD**, timeframe **M1**.
3. Use **"Every tick based on real ticks"** modeling for realistic results.
4. Set a date range with enough history (e.g. the last 6–12 months).
5. Set a realistic **spread** (use "Current" or a fixed value matching your broker).
6. Run, then review the report: profit factor, max drawdown, win rate,
   expected payoff. Optimize inputs only against a portion of data and validate
   on unseen data (walk-forward) to avoid curve-fitting.

---

## Key inputs

| Input | Default | Meaning |
|---|---|---|
| `InpRiskPercent` | 0.5 | Risk per trade as % of balance |
| `InpUseRiskPercent` | true | Size by risk % (off = fixed lot) |
| `InpFixedLot` | 0.01 | Lot used when risk % is off |
| `InpDailyMaxLossPct` | 4.0 | Stop trading for the day after this loss |
| `InpDailyProfitPct` | 6.0 | Stop trading for the day after this gain |
| `InpFastEMA` / `InpSlowEMA` | 21 / 50 | M1 trend EMAs |
| `InpUseHTFFilter` / `InpHTF` | true / M15 | Higher-timeframe trend filter |
| `InpRSIPeriod` | 14 | RSI momentum filter |
| `InpATRPeriod` | 14 | ATR for SL/TP/sizing |
| `InpSL_ATR_Mult` / `InpTP_ATR_Mult` | 1.5 / 2.25 | Stop / target as ATR multiples |
| `InpUseBreakEven` / `InpUseTrailing` | true | Stop management |
| `InpMaxSpreadPoints` | 50 | Skip when spread too wide |
| `InpUseSession` + hours | true, 7–21 | Trade only in active hours (server time) |
| `InpCooldownSeconds` | 60 | Minimum gap between entries |

Tune the session hours to your broker's **server time** so it covers the
liquid London/New York gold sessions.

---

## Safety notes

- Start on a **demo account**.
- Keep `InpRiskPercent` small (0.25–1%).
- The daily loss guard (`InpDailyMaxLossPct`) is your circuit breaker — keep it on.
- Gold spreads widen around news (NFP, CPI, FOMC); the spread filter helps but
  consider pausing the EA around major releases.
- This is trading software, **not financial advice**. You are responsible for
  any trades it places.
