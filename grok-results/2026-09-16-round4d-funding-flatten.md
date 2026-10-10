# Round 4 Test D — FUNDING_FLATTEN after 48h unless ≥ +1R

**Date:** 2026-09-16  
**Test ID:** `round4_D_funding_flatten`  
**Knob:** Flatten longs with adverse (net-cost) funding after hold ≥ 48h unless gross unrealized P&L is already ≥ +1R. One knob only. BE stops unchanged.

## Verdict

**FAIL vs Round 3 (return/Sharpe worse; trade count exploded); SHIELD VETO (26 trades > 25)**

| Gate | Result |
|------|--------|
| vs Round 3 improvement | **FAIL** — return 4.14% vs 4.33%, Sharpe 0.384 vs 0.415, net P&L $66.12 vs $69.24 |
| Shield (DD≤20% and ≤25 trades) | **VETO** — DD 12.04% ≤ 20, but **trades 26 > 25** → `shield_veto=true` |
| Researcher D success (cost/gross ≤35%, n≤15, return≥0) | **FAIL** — cost/gross 31.53% and return +4.14% pass, but **n=26** fails n≤15 and trips the >25 kill |

## 1R definition (documented)

Official R3 engine has **no explicit initial risk stop** at probe/confirm. The only priced risk distance in the pyramid is the **+3% probe-gain gate** that arms confirmation and premature BE.

- **1R** = 3% of `avg_entry` applied to current notional → dollar 1R = `0.03 * total_notional`
- Unrealized R uses **gross price P&L** vs that 1R (funding is the cost being cut, not part of the R tape)
- Adverse funding = cumulative funding paid is a net cost (`funding_so_far > 0`). Engine longs always pay the average 8h rate, so this is true for every long with `hold_days > 0`
- Daily bars: `hold_days >= 2` maps to ≥ 48 calendar hours
- Same-bar priority: MA50 / RSI / 30d time stop / BE stop still fire first; FUNDING_FLATTEN is additive

## Metrics: Round 3 vs Round 4D

| Metric | Round 3 | Round 4D | Delta |
|--------|---------|----------|-------|
| Final equity | $1,734.99 | $1,731.81 | -3.18 |
| Total return % | 4.33 | 4.14 | -0.19 |
| Max DD % | 12.65 | 12.04 | -0.61 |
| Sharpe | 0.415 | 0.384 | -0.031 |
| Num trades | 15 | 26 | +11 |
| Win rate % | 33.33 | 30.77 | -2.56 |
| Profit factor | 1.201 | 1.594 | +0.393 |
| Avg win | $82.85 | $22.17 | -60.68 |
| Avg loss | -$34.50 | -$6.18 | +28.32 |
| Best trade | $139.39 | $145.18 | +5.79 |
| Worst trade | -$57.65 | -$17.05 | +40.60 |
| Avg hold days | 15.8 | 3.0 | -12.8 |
| Total costs | $79.90 | $30.43 | -49.47 |
| Total funding | $58.82 | $10.85 | -47.97 |
| Gross P&L | $149.13 | $96.51 | -52.62 |
| Net P&L | $69.24 | $66.12 | -3.12 |
| Cost / gross % | 53.58 | 31.53 | -22.05 |

## What the knob did

- **23 / 26** exits were `FUNDING_FLATTEN` (net **−$77.88** on that bucket).
- One home-run survived because it was already ≥ +1R: NVDA 2026-05-04 → 2026-05-14, `RSI_OVERBOUGHT`, **+$145.18**.
- Two `BACKTEST_END` probes on 2026-09-16 (hold 0d; funding flatten not eligible).
- Costs collapsed as intended (funding $58.82 → $10.85; cost/gross 53.6% → 31.5%).
- Flattening recycled the 2 concurrent slots every ~2 days, so **trade count rose 15 → 26**. That is a shield kill and violates standing (“~15 trades/year is the feature”).
- Cutting slow GOLD/NVDA holds also cut the R3 right tail that had paid the funding bill. Profit factor rose because losers got smaller, but winners got smaller too (avg win $82.85 → $22.17).

## Notes

- Standing: paper only; isolated one-knob test; **not blended with Test A BE delay**.
- Engine output only — no invented fills. Raw: `grok-results/round4_D_funding_flatten_raw.json`.
- Same 365d window, same HL costs schedule, same 7-name universe as Round 3.
- Regime mix unchanged vs R3: RISK-ON 153 / TRANSITION 83 / RISK-OFF 16.
- BTC HODL still −35.26%; strategy still outperforms HODL by ~+39.4pp.

## Files

- Engine: `grok-engine/round4d_funding_flatten.py`
- Summary: `grok-results/round4_D_funding_flatten.json`
- Raw: `grok-results/round4_D_funding_flatten_raw.json`
