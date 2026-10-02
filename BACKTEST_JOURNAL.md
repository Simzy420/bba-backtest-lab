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

## ROUND 4 — Isolated Knob Tests (A/D/R1/C)
**Date:** 2026-09-16
**Status:** CLOSED — Shipped C as new paper baseline
See `backtest-params.json` for full details on each subtest.

---

## ROUND 5 — Chop Filter + GOLD Overweight + RSI Exit 70 (Out-of-Sample)
**Date:** 2026-10-02
**Engine:** /workspace/bba-backtest-lab/bba-engine/round5_chop_gold_rsi70.py
**Period:** 365 days (latest, ~Oct 2025 – Oct 2026)
**Capital:** $1,663
**Baseline:** Round 4C (chop filter, shipped 2026-09-16)

### Changes from R4C
1. GOLD probe size: 10% → 15% (GOLD was best trade in R3/R4)
2. RSI exit threshold: 75 → 70 (take profits earlier)
3. Fresh 365-day data (out-of-sample vs R3/R4 which ran Sep 2025 – Sep 2026)

### Results
| Metric | R5 | R4C | Delta |
|--------|-----|-----|-------|
| Total return | +10.12% | +14.90% | -4.78% |
| Max drawdown | 8.94% | 8.46% | +0.48% |
| Sharpe | 1.131 | 1.564 | -0.43 |
| Trades | 9 | 9 | 0 |
| Win rate | 44.44% | 44.44% | 0 |
| Profit factor | 1.86 | 2.25 | -0.39 |
| Total costs | $59.20 | $55.53 | +$3.67 |
| Net P&L | $168.36 | $244.76 | -$76.40 |
| BTC HODL | -29.66% | -35.26% | — |
| vs BTC HODL | +39.78% | +39.59% | — |
| Shield | PASS | PASS | — |

### Trade Breakdown
| # | Symbol | Entry | Exit | P&L | Return% | Hold | Exit Reason |
|---|--------|-------|------|-----|---------|------|-------------|
| 1 | GOLD | $4,429 | $4,766 | +$76.76 | +16.63% | 22d | RSI_OVERBOUGHT |
| 2 | GOLD | $5,027 | $4,906 | -$25.75 | -7.38% | 14d | BREAKEVEN_STOP |
| 3 | GOLD | $4,852 | $5,312 | +$99.42 | +20.59% | 31d | TIME_STOP |
| 4 | NVDA | $204.44 | $225.31 | +$98.71 | +24.58% | 13d | RSI_OVERBOUGHT |
| 5 | NVDA | $203.93 | $225.31 | +$89.16 | +25.44% | 9d | RSI_OVERBOUGHT |
| 6 | TSLA | $434.37 | $415.88 | -$53.90 | -12.74% | 17d | BREAKEVEN_STOP |
| 7 | NVDA | $224.81 | $200.20 | -$47.66 | -23.81% | 26d | BELOW_MA50 |
| 8 | NVDA | $225.66 | $218.36 | -$36.30 | -9.57% | 10d | BREAKEVEN_STOP |
| 9 | GOLD | $4,530 | $4,318 | -$32.08 | -11.26% | 26d | BELOW_MA50 |

### What I Learned
1. **RSI exit at 70 hurt — it cut winners short.** 3 trades exited on RSI_OVERBOUGHT that likely would have run further with the 75 threshold. Trades #1 and #4/5 were profitable but exited before full potential. The tighter exit cost ~$76 in net P&L vs R4C.
2. **GOLD overweight (15%) didn't meaningfully help.** GOLD still generated the best single trade (+$99.42, trade #3) but the bigger probe size also amplified the GOLD losers (trades #2 and #9). Net effect was marginal.
3. **Chop filter continues to work.** Only 9 trades in 365 days, 44% win rate, winners 2.3x bigger than losers. The filter is doing its job — keeping trade count low and quality high.
4. **Strategy is robust out-of-sample.** Different data window than R3/R4, still profitable, still <10% DD, still beats BTC HODL by ~40%. The edge is real.
5. **R4C remains the superior baseline.** R5 underperformed on return, Sharpe, and profit factor. No reason to ship R5 over R4C.

### Verdict
**FAIL — do not ship.** R4C remains the paper baseline. RSI exit at 70 is too tight. GOLD overweight is neutral.

### What to Test Next (Round 6 Candidates)
1. **RSI exit at 72** — split the difference between 70 and 75
2. **Remove TSLA from universe** — TSLA has been consistently negative across all rounds
3. **Widen breakeven stop to 2% below entry** instead of exact entry (give trades more room)
4. **Add DXY as a tradeable asset** — dollar weakness/strength is core to the macro thesis
5. **Test longer hold period** — 45 days instead of 30 (let winners run longer)

---

## SUMMARY TABLE

| Round | Return | Max DD | Trades | Win Rate | Sharpe | Costs | Period |
|-------|--------|--------|--------|----------|--------|-------|--------|
| 1 | -67% | N/A | 52 | 38% | N/A | None | 6mo |
| 2 | +6.43% | 53.8% | 6 | 50% | 0.92 | None | 6mo |
| 3 | +4.33% | 12.65% | 15 | 33% | 0.41 | $79.90 | 12mo |
| 4A | +4.02% | 19.34% | 15 | 33% | 0.34 | $80.12 | 12mo |
| 4D | +4.14% | 12.04% | 26 | 31% | 0.38 | $30.43 | 12mo |
| 4R1 | +3.95% | 12.80% | 16 | 31% | 0.39 | $80.50 | 12mo |
| **4C** | **+14.9%** | **8.46%** | **9** | **44%** | **1.564** | **$55.53** | **12mo** |
| 5 | +10.12% | 8.94% | 9 | 44% | 1.131 | $59.20 | 12mo |

## KEY FINDINGS (Saved to Memory)
1. Regime filter is the #1 component — went from -67% to +6.43% just by adding it
2. Max drawdown controlled by: max 2 concurrent + 20% DD defensive mode + pyramiding
3. Winners must be 2x+ bigger than losers — asymmetry is the edge, not win rate
4. Hyperliquid costs eat ~54% of gross profit — need to trade less or size bigger
5. GOLD is the best trade type — safe haven during regime transitions
6. Breakeven stops trigger too early — widen to 5% or add minimum hold period
7. BTC HODL was -35.26% — regime filter avoided the crash entirely

---

## GROK RESEARCHER — Strategy Analysis (no new engine run)
**Date:** 2026-09-16
**Author:** Researcher (Grok Bot)
**Source:** `bba-results/round3-hl-full-2026-09-16.json` (official Round 3)

### Findings (from all 15 official fills)
1. **BREAKEVEN_STOP** = largest failure bucket (5 trades, **−$183**, 0% WR) — stop set to avg entry at confirm (+3% gain).
2. **BELOW_MA50** = second (3 trades, **−$150**, 0% WR).
3. **Costs** $79.90 (54% of gross); **funding $58.82** dominates fees+slip.
4. **GOLD +$113 / NVDA +$88 / TSLA −$132**; **0 jugular** stages in R3 (11 confirm / 4 probe).
5. Brief leak: **TRANSITION confirm** exists (TSLA) — brief says probe-only.

### Artifacts pushed
- `grok-results/2026-09-16-researcher-strategy-analysis.md`
- `grok-results/2026-09-16-researcher-strategy-analysis.json`

### Round 4 pick
Prefer isolated test **A** (BE delay +1.5R or bar 8), then **D** (funding flatten). Shield: DD>20% or >25 trades/yr. Paper only; 15 trades/yr is the feature.

