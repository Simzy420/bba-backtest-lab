# Round 4 Test D — FUNDING_FLATTEN after 48h unless ≥ +1R

**Date:** 2026-09-16 (America/Boise)  
**Test ID:** `round4_D_funding_flatten`  
**Knob:** Flatten adverse funding after ≥2 calendar days unless unrealized ≥ +1R. One knob only. BE stops untouched.

**1R definition:** Official engine has no protective-stop R unit (20d swing-low risk is computed at entry for logging only). 1R = **3.0% of current avg entry**, matching the probe→confirm promotion threshold in `bba-engine/hl_backtest.py`. Unrealized is price gain vs avg entry, not net of funding.

## Verdict

**FAIL vs Round 3 (lower return, worse Sharpe, Shield veto on trade count)**

| Gate | Result |
|------|--------|
| vs Round 3 improvement | **FAIL** — return 4.14% vs 4.33%; Sharpe 0.384 vs 0.415. Cost/gross *did* improve (31.53% vs 53.58%) but that is not enough: `pass_vs_round3` requires return ≥ R3 **and** (cost/gross or Sharpe improves) **without** Shield fail. |
| Shield (DD≤20% and ≤25 trades) | **FAIL / veto** — DD 12.04% ≤ 20, but **26 trades > 25/year** → `shield_veto=true` |
| Success target (cost/gross ≤35%, n≤15) | **Mixed** — cost/gross 31.53% ≤ 35%; n=26 > 15 |
| Kill (cost/gross >45% or >25 RT/yr) | **KILL on volume** — 26 RT/yr > 25 (cost/gross is not >45%) |

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
| Net P&L | $69.24 | $66.12 | -3.12 |
| Gross P&L | $149.13 | $96.52 | -52.61 |
| Total costs | $79.90 | $30.43 | -49.47 |
| Funding $ | $58.82 | $10.85 | -47.97 |
| Cost / gross % | 53.58 | 31.53 | -22.05 |
| Avg hold days | 15.8 | 3.0 | -12.8 |

## What the knob actually did

Engine output only — no invented fills. Raw: `grok-results/round4_D_funding_flatten_raw.json`. Same ~365d window / assets / HL cost rates as R3 (BTC HODL still 2025-09-17 → 2026-09-16, −35.26%).

- **23 / 26 exits are `FUNDING_FLATTEN`** (net **−$77.88** on that bucket). Remaining: 1× `RSI_OVERBOUGHT` (NVDA +$145.18) and 2× `BACKTEST_END` scratches.
- Funding drag fell as intended ($58.82 → $10.85) because avg hold collapsed 15.8d → 3.0d.
- Flattening dead longs **recycled the 2 concurrent slots**, so the book printed **11 extra probes** and tripped the 25-trade Shield line.
- R3’s GOLD home runs (23d RSI exit +$69.95, 31d TIME_STOP +$79.13) never reached +3% by day 2, so they were flattened as small scratches instead of being held. The only surviving right-tail was NVDA 2026-05-04 → 05-14, which confirmed at +4.7% and stayed ≥ +1R until RSI>75.
- Post-pyramid avg-entry lift can drop unrealized below 1R (e.g. TSLA confirm 2025-12-18 then flatten 12-19 at +0.66% vs new avg). That is consistent with the stated 1R-vs-avg-entry rule; it is not a second knob.

## Notes

- Standing: paper only; isolated one-knob test; no blending; BE stops unchanged.
- Cost/gross hit the 35% *target* by cutting hold time, not by keeping the R3 winner path. Volume kill (>25 RT/yr) is binding.
- Do not treat 31.53% cost/gross as a Round 4 winner: return and Shield both fail.

## Files

- Engine: `grok-engine/round4d_funding_flatten.py`
- Summary: `grok-results/round4_D_funding_flatten.json`
- Raw: `grok-results/round4_D_funding_flatten_raw.json`
