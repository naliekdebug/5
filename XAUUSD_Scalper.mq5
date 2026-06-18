//+------------------------------------------------------------------+
//|                                              XAUUSD_Scalper.mq5   |
//|        Expert Advisor for XAUUSD (Gold) on the M1 timeframe       |
//|                                                                  |
//|  Evaluates every closed 1-minute candle and opens a trade only   |
//|  when a trend + momentum + volatility setup aligns. Uses strict  |
//|  ATR-based risk management and per-trade risk sizing.            |
//|                                                                  |
//|  IMPORTANT: No EA can be profitable on *every* candle. This EA   |
//|  trades selectively and manages risk so the account survives a   |
//|  normal run of losers. Always test on a demo account first and   |
//|  forward-test before risking real capital.                       |
//+------------------------------------------------------------------+
#property copyright "Built for keilan403"
#property version   "1.00"
#property strict
#property description "XAUUSD M1 trend/momentum scalper with ATR risk management."

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>
#include <Trade/SymbolInfo.mqh>

//--- Input groups ---------------------------------------------------
input group "=== General ==="
input long     InpMagic            = 990101;     // Magic number (unique EA id)
input bool     InpAllowLong        = true;       // Allow BUY trades
input bool     InpAllowShort       = true;       // Allow SELL trades
input int      InpMaxOpenPositions = 1;          // Max simultaneous positions for this EA
input int      InpSlippagePoints   = 30;         // Max slippage (points)

input group "=== Risk & Money Management ==="
input bool     InpUseRiskPercent   = true;       // Size lots from % risk (else fixed lot)
input double   InpRiskPercent      = 0.5;        // Risk per trade (% of balance)
input double   InpFixedLot         = 0.01;       // Fixed lot (if risk % disabled)
input double   InpMaxLot           = 5.0;        // Hard cap on lot size
input double   InpDailyMaxLossPct  = 4.0;        // Stop trading after this daily loss (% of start balance)
input double   InpDailyProfitPct   = 6.0;        // Stop trading after this daily profit (% of start balance)

input group "=== Entry: Trend Filter ==="
input int      InpFastEMA          = 21;         // Fast EMA period (M1)
input int      InpSlowEMA          = 50;         // Slow EMA period (M1)
input bool     InpUseHTFFilter     = true;       // Use higher-timeframe trend filter
input ENUM_TIMEFRAMES InpHTF       = PERIOD_M15; // Higher timeframe
input int      InpHTFEMA           = 50;         // EMA period on higher timeframe

input group "=== Entry: Momentum & Volatility ==="
input int      InpRSIPeriod        = 14;         // RSI period
input double   InpRSIBuyMax        = 70.0;       // Don't buy if RSI above this (overbought)
input double   InpRSIBuyMin        = 50.0;       // Buy needs RSI above this
input double   InpRSISellMin       = 30.0;       // Don't sell if RSI below this (oversold)
input double   InpRSISellMax       = 50.0;       // Sell needs RSI below this
input int      InpATRPeriod        = 14;         // ATR period (volatility / SL sizing)
input double   InpMinATRPoints     = 80.0;       // Skip if ATR below this (dead market, in points)

input group "=== Exits: Stops & Targets ==="
input double   InpSL_ATR_Mult      = 1.5;        // Stop loss = ATR * this
input double   InpTP_ATR_Mult      = 2.25;       // Take profit = ATR * this (R:R = TP/SL)
input bool     InpUseBreakEven     = true;       // Move SL to break-even after profit
input double   InpBE_ATR_Mult      = 1.0;        // Profit (in ATR) to trigger break-even
input bool     InpUseTrailing      = true;       // Trail stop with ATR
input double   InpTrail_ATR_Mult   = 1.5;        // Trailing distance = ATR * this

input group "=== Filters ==="
input double   InpMaxSpreadPoints  = 50.0;       // Skip if spread above this (points)
input bool     InpUseSession       = true;       // Restrict trading hours (server time)
input int      InpSessionStartHour = 7;          // Session start hour (0-23, server time)
input int      InpSessionEndHour   = 21;         // Session end hour (0-23, server time)
input int      InpCooldownSeconds  = 60;         // Min seconds between trade entries

//--- Globals --------------------------------------------------------
CTrade         trade;
CPositionInfo  posinfo;
CSymbolInfo    sym;

int      hFastEMA  = INVALID_HANDLE;
int      hSlowEMA  = INVALID_HANDLE;
int      hRSI      = INVALID_HANDLE;
int      hATR      = INVALID_HANDLE;
int      hHTFEMA   = INVALID_HANDLE;

datetime g_lastBarTime = 0;     // last processed M1 bar
datetime g_lastTradeTime = 0;   // time of last entry (cooldown)
double   g_dayStartBalance = 0; // balance at start of current day
int      g_currentDay = -1;     // day-of-year tracker
bool     g_tradingHalted = false; // daily loss/profit halt

//+------------------------------------------------------------------+
//| Helper: point value and digits                                   |
//+------------------------------------------------------------------+
double Pt() { return SymbolInfoDouble(_Symbol, SYMBOL_POINT); }

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetAsyncMode(false);

   if(!sym.Name(_Symbol))
   {
      Print("ERROR: cannot select symbol ", _Symbol);
      return(INIT_FAILED);
   }

   // Sanity: warn (don't block) if not gold — strategy is tuned for XAUUSD.
   string up = _Symbol;
   StringToUpper(up);
   if(StringFind(up, "XAU") < 0 && StringFind(up, "GOLD") < 0)
      Print("WARNING: This EA is designed for XAUUSD. Current symbol: ", _Symbol);

   hFastEMA = iMA(_Symbol, PERIOD_M1, InpFastEMA, 0, MODE_EMA, PRICE_CLOSE);
   hSlowEMA = iMA(_Symbol, PERIOD_M1, InpSlowEMA, 0, MODE_EMA, PRICE_CLOSE);
   hRSI     = iRSI(_Symbol, PERIOD_M1, InpRSIPeriod, PRICE_CLOSE);
   hATR     = iATR(_Symbol, PERIOD_M1, InpATRPeriod);
   if(InpUseHTFFilter)
      hHTFEMA = iMA(_Symbol, InpHTF, InpHTFEMA, 0, MODE_EMA, PRICE_CLOSE);

   if(hFastEMA == INVALID_HANDLE || hSlowEMA == INVALID_HANDLE ||
      hRSI == INVALID_HANDLE || hATR == INVALID_HANDLE ||
      (InpUseHTFFilter && hHTFEMA == INVALID_HANDLE))
   {
      Print("ERROR: failed to create one or more indicator handles.");
      return(INIT_FAILED);
   }

   g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   g_currentDay = dt.day_of_year;

   Print("XAUUSD_Scalper initialized on ", _Symbol, " / M1. Magic=", InpMagic);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(hFastEMA != INVALID_HANDLE) IndicatorRelease(hFastEMA);
   if(hSlowEMA != INVALID_HANDLE) IndicatorRelease(hSlowEMA);
   if(hRSI     != INVALID_HANDLE) IndicatorRelease(hRSI);
   if(hATR     != INVALID_HANDLE) IndicatorRelease(hATR);
   if(hHTFEMA  != INVALID_HANDLE) IndicatorRelease(hHTFEMA);
}

//+------------------------------------------------------------------+
//| Read one indicator value at a shift                              |
//+------------------------------------------------------------------+
bool GetVal(int handle, int shift, double &out)
{
   double buf[];
   if(CopyBuffer(handle, 0, shift, 1, buf) != 1)
      return(false);
   out = buf[0];
   return(true);
}

//+------------------------------------------------------------------+
//| Count this EA's open positions on this symbol                    |
//+------------------------------------------------------------------+
int CountOpenPositions()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic)
         n++;
   }
   return(n);
}

//+------------------------------------------------------------------+
//| Daily reset + daily loss/profit guard                            |
//+------------------------------------------------------------------+
void UpdateDailyGuard()
{
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   if(dt.day_of_year != g_currentDay)
   {
      g_currentDay      = dt.day_of_year;
      g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      g_tradingHalted   = false;
   }

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double pnlPct = (g_dayStartBalance > 0)
                   ? (equity - g_dayStartBalance) / g_dayStartBalance * 100.0
                   : 0.0;

   if(InpDailyMaxLossPct > 0 && pnlPct <= -InpDailyMaxLossPct)
   {
      if(!g_tradingHalted)
         Print("Daily max loss reached (", DoubleToString(pnlPct,2), "%). Halting new trades today.");
      g_tradingHalted = true;
   }
   if(InpDailyProfitPct > 0 && pnlPct >= InpDailyProfitPct)
   {
      if(!g_tradingHalted)
         Print("Daily profit target reached (", DoubleToString(pnlPct,2), "%). Halting new trades today.");
      g_tradingHalted = true;
   }
}

//+------------------------------------------------------------------+
//| Session filter                                                   |
//+------------------------------------------------------------------+
bool InSession()
{
   if(!InpUseSession) return(true);
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   int h = dt.hour;
   if(InpSessionStartHour <= InpSessionEndHour)
      return(h >= InpSessionStartHour && h < InpSessionEndHour);
   // Overnight wrap (e.g. 22 -> 6)
   return(h >= InpSessionStartHour || h < InpSessionEndHour);
}

//+------------------------------------------------------------------+
//| Current spread in points                                         |
//+------------------------------------------------------------------+
double SpreadPoints()
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   return((ask - bid) / Pt());
}

//+------------------------------------------------------------------+
//| Position size from risk % and stop distance (price units)        |
//+------------------------------------------------------------------+
double CalcLot(double stopDistancePrice)
{
   if(!InpUseRiskPercent)
      return(NormalizeLot(InpFixedLot));

   double balance     = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney   = balance * InpRiskPercent / 100.0;

   double tickValue   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize    = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0 || tickValue <= 0 || stopDistancePrice <= 0)
      return(NormalizeLot(InpFixedLot));

   // Loss per 1.0 lot if stop is hit:
   double lossPerLot = (stopDistancePrice / tickSize) * tickValue;
   if(lossPerLot <= 0)
      return(NormalizeLot(InpFixedLot));

   double lot = riskMoney / lossPerLot;
   return(NormalizeLot(lot));
}

//+------------------------------------------------------------------+
//| Normalize lot to broker constraints                              |
//+------------------------------------------------------------------+
double NormalizeLot(double lot)
{
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(lotStep <= 0) lotStep = 0.01;
   lot = MathFloor(lot / lotStep) * lotStep;

   double cap = MathMin(maxLot, InpMaxLot);
   if(lot > cap)    lot = cap;
   if(lot < minLot) lot = minLot;

   // round to step's decimal precision
   int digits = (int)MathRound(MathLog10(1.0 / lotStep));
   if(digits < 0) digits = 0;
   return(NormalizeDouble(lot, digits));
}

//+------------------------------------------------------------------+
//| Evaluate entry signal: returns +1 buy, -1 sell, 0 none           |
//+------------------------------------------------------------------+
int Signal(double &atrOut)
{
   atrOut = 0;
   // Use the last CLOSED candle (shift 1) for all signal reads.
   double fast1, slow1, fast2, slow2, rsi1, atr1;
   if(!GetVal(hFastEMA, 1, fast1)) return(0);
   if(!GetVal(hSlowEMA, 1, slow1)) return(0);
   if(!GetVal(hFastEMA, 2, fast2)) return(0);
   if(!GetVal(hSlowEMA, 2, slow2)) return(0);
   if(!GetVal(hRSI,     1, rsi1))  return(0);
   if(!GetVal(hATR,     1, atr1))  return(0);
   atrOut = atr1;

   // Volatility floor — skip dead/illiquid conditions.
   if(atr1 / Pt() < InpMinATRPoints)
      return(0);

   // Higher-timeframe trend filter.
   double htf = 0, htfPrice = 0;
   bool htfBull = true, htfBear = true;
   if(InpUseHTFFilter)
   {
      if(!GetVal(hHTFEMA, 0, htf)) return(0);
      htfPrice = iClose(_Symbol, InpHTF, 0);
      htfBull  = (htfPrice > htf);
      htfBear  = (htfPrice < htf);
   }

   // M1 trend: fast vs slow EMA.
   bool m1Bull = (fast1 > slow1);
   bool m1Bear = (fast1 < slow1);

   // Momentum confirmation via fresh EMA separation widening in trend direction.
   bool widenUp   = (fast1 - slow1) > (fast2 - slow2);
   bool widenDown = (slow1 - fast1) > (slow2 - fast2);

   // BUY setup
   if(InpAllowLong && m1Bull && widenUp && htfBull &&
      rsi1 > InpRSIBuyMin && rsi1 < InpRSIBuyMax)
      return(+1);

   // SELL setup
   if(InpAllowShort && m1Bear && widenDown && htfBear &&
      rsi1 < InpRSISellMax && rsi1 > InpRSISellMin)
      return(-1);

   return(0);
}

//+------------------------------------------------------------------+
//| Open a trade in the given direction                              |
//+------------------------------------------------------------------+
void OpenTrade(int dir, double atr)
{
   sym.RefreshRates();
   double price   = (dir > 0) ? sym.Ask() : sym.Bid();
   double slDist  = atr * InpSL_ATR_Mult;
   double tpDist  = atr * InpTP_ATR_Mult;

   // Respect broker minimum stop distance.
   long   stopLevelPts = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDist      = stopLevelPts * Pt();
   if(slDist < minDist) slDist = minDist * 1.5;
   if(tpDist < minDist) tpDist = minDist * 1.5;

   double sl, tp;
   if(dir > 0)
   {
      sl = price - slDist;
      tp = price + tpDist;
   }
   else
   {
      sl = price + slDist;
      tp = price - tpDist;
   }

   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   sl = NormalizeDouble(sl, digits);
   tp = NormalizeDouble(tp, digits);

   double lot = CalcLot(slDist);
   if(lot <= 0) { Print("Lot calc returned 0, skipping."); return; }

   bool ok;
   string comment = "XAUUSD_Scalper";
   if(dir > 0)
      ok = trade.Buy(lot, _Symbol, 0.0, sl, tp, comment);
   else
      ok = trade.Sell(lot, _Symbol, 0.0, sl, tp, comment);

   if(ok)
   {
      g_lastTradeTime = TimeCurrent();
      PrintFormat("OPEN %s lot=%.2f price=%.2f sl=%.2f tp=%.2f atr=%.2f",
                  (dir>0?"BUY":"SELL"), lot, price, sl, tp, atr);
   }
   else
   {
      PrintFormat("Order failed: retcode=%d (%s)", trade.ResultRetcode(),
                  trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| Manage open positions: break-even + ATR trailing                 |
//+------------------------------------------------------------------+
void ManagePositions()
{
   if(!InpUseBreakEven && !InpUseTrailing) return;

   double atr;
   if(!GetVal(hATR, 0, atr) || atr <= 0) return;

   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   long stopLevelPts = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDist = stopLevelPts * Pt();

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      long   type   = PositionGetInteger(POSITION_TYPE);
      double open   = PositionGetDouble(POSITION_PRICE_OPEN);
      double curSL  = PositionGetDouble(POSITION_SL);
      double curTP  = PositionGetDouble(POSITION_TP);

      sym.RefreshRates();
      double bid = sym.Bid();
      double ask = sym.Ask();
      double newSL = curSL;

      if(type == POSITION_TYPE_BUY)
      {
         double profit = bid - open;
         if(InpUseBreakEven && profit >= atr * InpBE_ATR_Mult && curSL < open)
            newSL = open;
         if(InpUseTrailing)
         {
            double trail = bid - atr * InpTrail_ATR_Mult;
            if(trail > newSL) newSL = trail;
         }
         newSL = NormalizeDouble(newSL, digits);
         if(newSL > curSL && (bid - newSL) >= minDist && newSL < bid)
            trade.PositionModify(ticket, newSL, curTP);
      }
      else if(type == POSITION_TYPE_SELL)
      {
         double profit = open - ask;
         if(InpUseBreakEven && profit >= atr * InpBE_ATR_Mult && (curSL > open || curSL == 0))
            newSL = open;
         if(InpUseTrailing)
         {
            double trail = ask + atr * InpTrail_ATR_Mult;
            if(newSL == 0 || trail < newSL) newSL = trail;
         }
         newSL = NormalizeDouble(newSL, digits);
         if((curSL == 0 || newSL < curSL) && (newSL - ask) >= minDist && newSL > ask)
            trade.PositionModify(ticket, newSL, curTP);
      }
   }
}

//+------------------------------------------------------------------+
//| Detect a freshly closed M1 bar                                   |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime t = iTime(_Symbol, PERIOD_M1, 0);
   if(t == 0) return(false);
   if(t != g_lastBarTime)
   {
      g_lastBarTime = t;
      return(true);
   }
   return(false);
}

//+------------------------------------------------------------------+
//| Main tick handler                                                |
//+------------------------------------------------------------------+
void OnTick()
{
   // Manage existing trades on every tick (trailing needs to be responsive).
   ManagePositions();

   // Decisions happen once per closed M1 candle.
   if(!IsNewBar()) return;

   UpdateDailyGuard();
   if(g_tradingHalted) return;
   if(!InSession()) return;

   // Cooldown between entries.
   if(InpCooldownSeconds > 0 &&
      (TimeCurrent() - g_lastTradeTime) < InpCooldownSeconds)
      return;

   // Spread filter.
   if(SpreadPoints() > InpMaxSpreadPoints) return;

   // Respect max positions.
   if(CountOpenPositions() >= InpMaxOpenPositions) return;

   // Evaluate signal on the just-closed candle.
   double atr = 0;
   int dir = Signal(atr);
   if(dir == 0 || atr <= 0) return;

   OpenTrade(dir, atr);
}
//+------------------------------------------------------------------+
