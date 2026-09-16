# Round 4 Test C — CHOP FILTER

**Date:** 2026-09-16  
**Test ID:** `round4_C_chop_filter`  
**Knob:** Skip new entries / new probes when daily ATR% < 20-bar median **OR** |EMA20−EMA50|/close < 0.4%. Existing exits unchanged. One knob only.

Definitions used (daily official engine — Boss text said “1h ATR%”; this engine is daily):
- ATR% = ATR(14 Wilder) / close × **100** (percent units; 1.5 = 1.5%)
- 20-bar median of ATR% on that symbol (rolling, includes current bar)
- EMA20 / EMA50 on close (`span`, `adjust=False`); chop if `abs(EMA20−EMA50)/close < 0.004`

## Verdict

**PASS vs Round 3; SHIELD PASS (no veto)**

| Gate | Result |
|------|--------|
| vs Round 3 improvement | **PASS** — return 14.90% vs 4.33% |
| Shield (DD≤20% and ≤25 trades) | **PASS** — DD 8.46% ≤ 20, trades 9 (9.03/yr) ≤ 25 → `shield_veto=false` |

## Metrics: Round 3 vs Round 4C

| Metric | Round 3 | Round 4C | Delta |
|--------|---------|----------|-------|
| Final equity | $1,734.99 | $1,910.71 | +175.72 |
| Total return % | 4.33 | 14.90 | +10.57 |
| Max DD % | 12.65 | 8.46 | −4.19 |
| Sharpe | 0.415 | 1.564 | +1.149 |
| Num trades | 15 | 9 | −6 |
| Win rate % | 33.33 | 44.44 | +11.11 |
| Profit factor | 1.201 | 2.247 | +1.046 |
| Total costs | $79.90 | $55.53 | −24.37 |
| Cost / gross % | 53.58 | 18.49 | −35.09 pp |
| Net P&L | $69.24 | $244.76 | +175.52 |
| Avg hold days | 15.8 | 18.2 | +2.4 |

## Success hypothesis (honest)

| Criterion | Result |
|-----------|--------|
| Sharpe ≥ 0.55 | **MET** (1.564) |
| cost% ↓ vs R3 | **MET** (18.49% vs 53.58%) |
| MDD ≤ R3 + 2pp | **MET** (8.46% vs 12.65%+2pp) |

All three hypothesis checks met on this isolated C run. Still paper-only; Boss ships or rejects.

## Chop skips (would-have-entered under R3 rules)

- Count: **15** candidate new entries blocked
- Reasons: 13× `atr_below_median`, 2× `both` (ATR% below median **and** EMA gap < 0.4%). Zero skips were EMA-gap-only.
- Notable R3 fills blocked: TSLA 2025-12-09 / 2025-12-17 (opened the R3 book; both losers), Aug 2026 NVDA cluster (2026-08-10 through 2026-08-21), GOLD 2026-03-03/04, last-bar BTC/ETH/SOL probes on 2026-09-16.

Path-dependent **new** fill vs R3 (not invented): NVDA 2026-08-31 confirm, because skipping the Aug 10–21 NVDA cluster left a concurrent slot open. GOLD 2026-08-28 still entered (ATR% was not below median that bar).

## Notes

- Standing: paper only; isolated one-knob test; no blending with A / D / R1 (all prior rejects).
- Engine output only — no invented fills. Raw: `grok-results/round4_C_chop_filter_raw.json`.
- Same ~365d live fetch as R3 (CoinGecko `days=365` / yfinance `period=1y`). Regime distribution identical (RISK-ON 153 / TRANSITION 83 / RISK-OFF 16). BTC HODL identical (−35.26%, $116,763 → $75,590, 2025-09-17 → 2026-09-16).
- Chop filter is an **entry** gate only. BE stops, pyramids, regime, sizes, HL costs, universe, and 20% DD circuit were not changed. Existing positions were not flattened for chop.
- 9 trades/yr is below the R3 15-trade cadence (that cadence is a feature, not a C kill rule). Shield kill is n>25, which did not fire.
- Last GOLD print on 2026-09-16 can differ vs the R3 snapshot (this run exited GOLD BELOW_MA50 at 4288.70; R3 last GOLD MTM used 4384.20). Mid-window GOLD/NVDA prints that overlap R3 (4837.50, 4905.90, 5311.60, 235.20) match.

## Files

- Engine: `grok-engine/round4c_chop_filter.py`
- Summary: `grok-results/round4_C_chop_filter.json`
- Raw: `grok-results/round4_C_chop_filter_raw.json`
