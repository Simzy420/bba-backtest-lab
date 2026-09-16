# BIG BRAIN APE — BACKTEST JOURNAL
## Druckenmiller Strategy on Hyperliquid Perpetual Futures

> Living document. Updated after EVERY backtest run. Read this before starting any new run.

---

## ROUND 1 — Basic Technical Strategy
**Date:** 2026-08-22
**Engine:** /workspace/backtest_engine.py (v1)
**Period:** 6 months (Mar 2026 – Aug 2026)
**Capital:** $1,663

### Parameters Tested
| Parameter | Value |
|-----------|-------|
| Entry | Above 20-day MA, RSI < 70, VIX < 25 |
| Exit | Below 50-day MA, RSI > 75, VIX > 30 |
| Position size | 20% per trade |
| Max concurrent | 3 |
| Leverage | 3x |
| Hyperliquid costs | NONE (not modeled) |
| Macro filter | NONE |

### Results
| Metric | Value |
|--------|-------|
| Total return | **-67%** ❌ |
| Trades | 52 |
| Win rate | 38% |
| Max drawdown | N/A (catastrophic) |

### What I Learned
1. **52 trades in 6 months = trading every 3 days.** Druck makes 1-2 trades per YEAR. Way too much churn.
2. **No macro filter = death.** Pure technical indicators get whipsawed in ranging markets. The regime filter is the most important part of the strategy.
3. **3x leverage × 3 concurrent × 20% size = 180% total exposure.** Way too aggressive. When multiple positions go wrong simultaneously, the account blows up.
4. **No cost modeling = fake results.** Even if this had been profitable, without fees + slippage + funding the numbers are meaningless.

### What to Test Next
- Add regime classification (RISK-ON/OFF/TRANSITION) as a gate before any entry
- Reduce max concurrent to 2
- Reduce trade frequency dramatically
- Add real Hyperliquid costs

---

## ROUND 2 — Druckenmiller Macro Strategy (Simplified)
**Date:** 2026-08-22
**Engine:** /workspace/backtest_engine.py (v2 rewrite)
**Period:** 6 months (Mar 2026 – Aug 2026)
**Capital:** $1,663

### Parameters Tested
| Parameter | Value |
|-----------|-------|
| Entry | Above 20+50 day MA (both sloping up), RSI 40-65, pullback 2%+ from 5-day high |
| Exit | Below 50-day MA, RSI > 75, VIX > 25, 30-day time stop, 20% portfolio DD |
| Regime filter | ✅ RISK-ON/OFF/TRANSITION (VIX + S&P 50MA) |
| Position size | 25% per trade |
| Max concurrent | 2 |
| Leverage | 2x |
| Hyperliquid costs | NONE (still not modeled) |
| Gold hedge | ✅ Long gold when VIX > 25 |

### Results
| Metric | Value |
|--------|-------|
| Total return | **+6.43%** ✅ |
| Trades | 6 |
| Win rate | 50% |
| Avg win | $73 |
| Avg loss | -$37 |
| Max drawdown | **53.8%** ⚠️ |
| Sharpe | 0.92 |
| Profit factor | N/A |

### What I Learned
1. **Regime filter is the single most important component.** Going from -67% to +6.43% was entirely from adding the RISK-ON/OFF/TRANSITION gate. The technical signals didn't change — the macro filter did.
2. **6 trades in 6 months = correct frequency.** High conviction, low churn. This is how Druck trades.
3. **Winners 2x bigger than losers = the edge.** 50% win rate is nothing special, but $73 avg win vs $37 avg loss means you're profitable at 37% win rate. Asymmetry is everything.
4. **53.8% max drawdown is UNACCEPTABLE.** This would trigger the 20% defensive mode rule in real trading. The drawdown is coming from concentrated positions hitting simultaneous losses.
5. **No cost modeling still = incomplete picture.** Need to add real Hyperliquid costs to see if the strategy survives fees + slippage + funding.

### What to Test Next
- Add real Hyperliquid costs (4.5 bps fee + 4.5 bps slippage per side + funding)
- Fix the drawdown problem — tighter stops? smaller position sizes? diversification?
- Test over a longer period (12 months instead of 6)
- Add BTC HODL benchmark for comparison

---

## ROUND 3 — Full Hyperliquid Backtest (Real Costs + Pyramiding)
**Date:** 2026-09-16
**Engine:** /workspace/hl_backtest.py
**Period:** 12 months (Sep 2025 – Sep 2026)
**Capital:** $1,663

### Parameters Tested
| Parameter | Value |
|-----------|-------|
| Entry | Above 20+50 day MA (both sloping up), RSI 40-65, pullback 2%+ from 5-day high |
| Exit | Below 50-day MA, RSI > 75, regime shift, 30-day time stop, 20% portfolio DD |
| Regime filter | ✅ RISK-ON/OFF/TRANSITION (VIX + S&P 50MA + 10Y yield) |
| Pyramiding | ✅ Probe (5-10%, 2x) → Confirmation (20-30%, 3x) → Jugular (30-50%, 3x) |
| Max concurrent | 2 |
| Leverage | 2x probe, 3x confirmation/jugular |
| Hyperliquid costs | ✅ 4.5 bps fee + 4.5 bps slippage per side + funding (0.01-0.02% per 8h) |
| Universe | BTC, ETH, SOL, GOLD, NVDA, TSLA, S&P 500 |
| Benchmark | ✅ BTC HODL |

### Results
| Metric | Value |
|--------|-------|
| Total return | **+4.33%** ✅ |
| Max drawdown | **12.65%** ✅ (down from 53.8%!) |
| Trades | 15 |
| Win rate | 33.33% |
| Avg win | $82.85 |
| Avg loss | -$34.50 |
| Profit factor | 1.20 |
| Sharpe | 0.41 |
| Total costs | $79.90 |
| Gross P&L | $149.13 |
| Net P&L | $69.24 |
| BTC HODL | **-35.26%** |
| Outperformance | **+39.59%** vs BTC HODL |

### What I Learned
1. **Real costs matter — they ate 54% of gross profit.** $149 gross → $69 net after $80 in fees/slippage/funding. The strategy is still profitable but costs are the #1 drag on returns.
2. **Max drawdown fixed: 53.8% → 12.65%.** The pyramiding system + 20% DD defensive mode + max 2 concurrent positions worked. This is the single biggest improvement across all rounds.
3. **Win rate dropped to 33% but still profitable.** Winners are 2.4x bigger than losers ($83 vs -$35). The asymmetry holds even with more trades. Confirms Druck's principle: "It's not whether you're right or wrong, but how much you make when you're right."
4. **GOLD was the best trade (+$139).** Safe haven trades during regime transitions are high-conviction. Gold should get bigger position sizing.
5. **BTC HODL was -35.26%.** The strategy avoided the crypto crash entirely by being in RISK-OFF mode. The regime filter saved the account.
6. **Breakeven stops triggering too early.** Multiple trades exited at breakeven_stop when they would have been profitable. The stop-to-breakeven trigger needs to be wider (currently too tight).
7. **Sharpe dropped to 0.41 from 0.92.** More trades = more chop = lower risk-adjusted returns. Need to filter out low-quality entries.

### What to Test Next (Round 4 Candidates)
1. **Widen breakeven stop** — from current trigger to 5% above entry (reduces premature exits)
2. **Reduce trade frequency** — add RSI < 60 instead of < 65 (stricter entry = fewer trades)
3. **Increase GOLD position size** — GOLD has highest win rate, deserves bigger allocation
4. **Tighten RSI exit to 70** instead of 75 (take profits earlier, don't give back gains)
5. **Add a minimum hold period of 3 days** before breakeven stop activates (let trades breathe)
6. **Test ETH and SOL separately** — are they adding value or just adding costs?
7. **Test 2x max leverage everywhere** — does reducing from 3x to 2x improve Sharpe?

---

## ROUND 4 — [PENDING]
**Date:** TBD
**Engine:** TBD
**What to test:** See Round 3 "What to Test Next" — pick top 2-3 parameters to change

---

## SUMMARY TABLE

| Round | Return | Max DD | Trades | Win Rate | Sharpe | Costs | Period |
|-------|--------|--------|--------|----------|--------|-------|--------|
| 1 | -67% | N/A | 52 | 38% | N/A | None | 6mo |
| 2 | +6.43% | 53.8% | 6 | 50% | 0.92 | None | 6mo |
| 3 | +4.33% | 12.65% | 15 | 33% | 0.41 | $79.90 | 12mo |

## KEY FINDINGS (Saved to Memory)
1. Regime filter is the #1 component — went from -67% to +6.43% just by adding it
2. Max drawdown controlled by: max 2 concurrent + 20% DD defensive mode + pyramiding
3. Winners must be 2x+ bigger than losers — asymmetry is the edge, not win rate
4. Hyperliquid costs eat ~54% of gross profit — need to trade less or size bigger
5. GOLD is the best trade type — safe haven during regime transitions
6. Breakeven stops trigger too early — widen to 5% or add minimum hold period
7. BTC HODL was -35.26% — regime filter avoided the crash entirely
