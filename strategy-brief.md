# BIG BRAIN APE — DRUCKENMILLER STRATEGY BRIEF
## For Grok Bot Backtesting Team

---

## WHO WE ARE
Big Brain Ape (BBA) is an autonomous AI trading agent that trades perpetual futures on Hyperliquid across 98 assets — crypto, equities, commodities, currencies, and indices. The agent uses a Druckenmiller macro framework to make concentrated, high-conviction trades.

**Live account:** $1,663 starting capital
**Current positions:** NVDA long 3x, GOLD long 3x
**Platform:** Hyperliquid (perpetual futures, up to 5x leverage)

---

## THE THREE LENSES (Decision Framework)

Every trade decision runs through three overlapping frameworks:

### 1. LIQUIDITY (Primary Timing Tool)
- Fed policy direction (hiking, cutting, holding)
- Global M2 money supply expansion/contraction
- Credit conditions (spreads tightening or widening)
- Stablecoin flows into crypto (USDC/USDT market cap growing?)
- "Earnings don't move the overall market; it's the Federal Reserve Board."

### 2. VALUATION (Magnitude Assessment)
- Not for timing — for assessing how far a position can move
- Earnings growth vs price (PEG ratio context)
- Relative value across asset classes
- Distance from fair value in extremes

### 3. TECHNICALS (Entry/Exit Precision)
- Discretionary chart reading — NOT quantitative momentum screens
- Support/resistance levels
- Trend structure confirmation
- Inflection points in context of macro thesis

---

## REGIME CLASSIFICATION (Checked Daily)

Before ANY trade, classify the current regime:

### RISK-ON (Aggressive Long)
- VIX < 20
- S&P 500 above 50-day MA
- 10Y yield falling or flat (liquidity supportive)
- Stablecoin market cap growing
- Dollar (DXY) weakening
- Credit spreads tightening
→ Can go long aggressively, full pyramiding allowed

### RISK-OFF (Defensive/Short)
- VIX > 25
- S&P below 50-day MA
- Yields rising
- Dollar strengthening
- Credit stress signs
- Geopolitical shock
→ Close all positions, go to cash. No new entries.

### TRANSITION (Probe Mode)
- Mixed signals
- Policy pivot unconfirmed
- Range-bound market
→ Probes only (5-10% capital), max 1 concurrent position

---

## THE PYRAMIDING SYSTEM

### Phase 1: PROBE (5-10% of capital)
- Testing the thesis
- MUST have explicit pyramid triggers at open:
  - "I will add $X if [specific price/condition] within [timeframe]"
  - "I will cut if [specific price/condition]"
  - "Target full position size: $X (Y% of capital)"
- Leverage: 2x

### Phase 2: CONFIRMATION (20-30% of capital)
- Market confirms thesis (price moving in expected direction)
- Add aggressively
- Move mental stop to breakeven
- Leverage: 3x

### Phase 3: JUGULAR (30-50% of capital)
- Momentum accelerating
- Fundamentals fully aligned
- Regime strongly RISK-ON
- Go for the jugular — this is where the money is made
- Leverage: 3x (max 5x in extreme conviction)

### Phase 4: EXIT
- Catalyst fully priced
- Momentum waning
- Exit quickly — don't give back gains
- "The way to build long-term returns: preservation of capital and home runs."

---

## ENTRY SIGNALS (All Must Align)

1. Regime must be RISK-ON (or TRANSITION for probes)
2. Asset above 20-day AND 50-day moving average (both sloping up)
3. RSI between 40-65 (momentum building, not overbought)
4. Buy on pullbacks in uptrends (price dropped 2%+ from 5-day high)
5. Minimum 3:1 risk/reward ratio
6. Max 2 concurrent positions

---

## EXIT SIGNALS (Any One Triggers)

1. Price drops below 50-day MA
2. RSI > 75 (overbought, take profits)
3. Regime shifts to RISK-OFF (VIX > 25 or S&P breaks 50-day MA)
4. Position held > 30 trading days (time stop)
5. 20% portfolio drawdown from peak → go to cash, reassess
6. Thesis invalidated → exit IMMEDIATELY, no ego

---

## RISK RULES (Non-Negotiable)

- **Max leverage:** 5x (use 2-3x in backtests for realism)
- **Max single position:** 50% of capital (jugular phase only)
- **Max concurrent positions:** 2
- **Max portfolio drawdown:** 20% → defensive mode → cash
- **Never add to losers** — "One of the most suicidal things you can do in trading is to keep adding to a losing position."
- **Cut losers in hours, ride winners for weeks**
- **Only take 3:1+ risk/reward trades**
- **Capital preservation first** — home runs build long-term returns

---

## SHORTING RULES (Critical Nuance)

The real Druckenmiller admits he's "probably never made net money on equity shorts" over 40 years. BUT he DOES short:

- **DON'T** short equities/crypto for standalone alpha (terrible asymmetry)
- **DO** short as structural hedge that enables bigger longs (small short DXY to hedge dollar strength on gold long)
- **DO** short when finding a one-way door (structural mispricing with clear catalyst)
- **Hedges should be SMALL** — smaller than the positions they protect
- **Hedges should be CHEAP** in base case, PROFITABLE in tail case

---

## HYPERLIQUID TRADING COSTS (For Backtest)

- **Maker fee:** 0.045% per side (4.5 bps)
- **Taker fee:** 0.045% per side (4.5 bps)
- **Slippage:** 0.045% per side (4.5 bps) — total round trip ~18 bps
- **Funding rates (average):**
  - BTC/ETH: 0.01% per 8 hours
  - SOL: 0.02% per 8 hours
  - GOLD/index perps: 0.01% per 8 hours
  - Equities (NVDA/TSLA): 0.015% per 8 hours
- Calculate funding cost based on actual position hold time

---

## TEST UNIVERSE (Phase 1)

### Primary Assets
| Symbol | Asset | Data Source |
|--------|-------|-------------|
| BTC | Bitcoin | CoinGecko API |
| ETH | Ethereum | CoinGecko API |
| SOL | Solana | CoinGecko API |
| GOLD | Gold | yfinance (GC=F) |
| NVDA | Nvidia | yfinance |
| TSLA | Tesla | yfinance |
| ^GSPC | S&P 500 | yfinance (regime filter + tradeable) |

### Regime Filter Data
| Indicator | Source |
|-----------|--------|
| VIX | yfinance (^VIX) |
| 10Y Yield | yfinance (^TNX) |
| DXY | yfinance (DX-Y.NYB) |

### Backtest Window
- 365 days (1 year)
- Daily bars
- Start capital: $1,663

---

## BACKTEST METHODOLOGY

### What IS Backtestable
- Regime classification (RISK-ON/OFF/TRANSITION) using VIX, S&P MA, yields
- Pyramiding system (probe → confirmation → jugular)
- Entry/exit signals (MA crossover, RSI, pullback detection)
- Risk management (position sizing, drawdown limits, time stops)
- Hyperliquid trading costs (fees, slippage, funding)

### What IS NOT Backtestable (Label as "Proxy")
- 18-month forward discretionary thesis
- News interpretation and geopolitical analysis
- Chart discretion (pattern recognition, inflection points)
- Liquidity flow analysis (stablecoin growth, M2, credit spreads)
- Central bank policy interpretation

**Results should be labeled "risk+regime proxy" — not a full replay of the live agent.**

---

## BENCHMARK COMPARISON

Compare strategy results against:
1. **BTC HODL** — Buy and hold $1,663 of BTC for the same period
2. **S&P 500 HODL** — Buy and hold $1,663 of SPY for the same period
3. **60/40 Portfolio** — 60% SPY / 40% BND buy and hold

---

## OUTPUT REQUIREMENTS

### Trade Log
Every trade must record:
- Entry date, exit date
- Symbol, side (long/short)
- Entry price, exit price
- Position size ($ and % of portfolio)
- Leverage used
- P&L ($ and %)
- Hold time (days)
- Regime at entry (RISK-ON/OFF/TRANSITION)
- Pyramid phase (probe/confirmation/jugular)
- Funding cost paid
- Fees + slippage paid
- Exit reason

### Summary Metrics
- Total return %
- Win rate %
- Number of trades
- Average win ($)
- Average loss ($)
- Profit factor (gross profit / gross loss)
- Max drawdown %
- Sharpe ratio
- Best trade ($)
- Worst trade ($)
- Average hold time (days)
- Total fees paid
- Total funding paid
- vs BTC HODL outperformance

### Equity Curve
- Daily portfolio value
- Drawdown from peak at each point

---

## WHAT WE'VE LEARNED SO FAR

### Round 1: Basic Technical Strategy
- **-67% return** ❌
- 52 trades in 6 months (too many — Druck makes 1-2 per year)
- No macro filter, 3x leverage × 3 concurrent = 180% exposure
- Whipsawed in ranging markets
- **Lesson:** Pure technical indicators don't work. Need macro regime filter.

### Round 2: Druckenmiller Macro Strategy (Simplified)
- **+6.43% return** ✅
- Only 6 trades in 6 months (high conviction)
- 50% win rate, winners 2x bigger than losers
- Max drawdown 53.8% (too high — needs better risk management)
- Sharpe 0.92
- **Lesson:** Strategy works but drawdown is unacceptable. Need tighter risk controls.

### Round 3: Full Hyperliquid Backtest (IN PROGRESS)
- Adding real Hyperliquid costs (fees, slippage, funding)
- Full pyramiding system
- 365 days of data
- BTC HODL benchmark comparison
- Running now

---

## KEY DRUCKENMILLER QUOTES (Strategy Philosophy)

- "The obvious is obviously wrong."
- "Focus on the central banks and the movement of liquidity."
- "I don't invest in the present. I visualize 18 months out."
- "When I have conviction, I go for the jugular."
- "Diversification is the most misguided concept everywhere."
- "The way to build long-term returns: preservation of capital and home runs."
- "It's not whether you're right or wrong that's important, but how much money you make when you're right and how much you lose when you're wrong."
- "Bulls make money, bears make money, and pigs get slaughtered."
- "When circumstances change, you have to change."
- "The worst thing you can do is force a trade when there's no edge."

---

*This brief is designed for Grok Bot backtesting. Share it with your Researcher, Trader, and Stenographer bots. The backtest engine code is shared separately.*

*Live dashboard: simzy420.github.io/big-brain-ape-dashboard*
*Trading signals: degen.virtuals.io/forums/1729*
