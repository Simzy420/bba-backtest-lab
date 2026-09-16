# Round 4 Test A — BE_STOP_DELAY=3d

**Date:** 2026-09-16 (America/Boise)  
**Test ID:** `round4_A_be_stop_delay`  
**Knob:** Delayed breakeven stop arm (+3 calendar days after confirmation pyramid). Jugular trail unchanged. One knob only.

## Verdict

**FAIL vs Round 3 (worse return & higher DD); SHIELD PASS (no veto)**

| Gate | Result |
|------|--------|
| vs Round 3 improvement | **FAIL** — return 4.02% vs 4.33%, DD 19.34% vs 12.65%, Sharpe 0.342 vs 0.415 |
| Shield (DD≤20% and ≤25 trades) | **PASS** — DD 19.34% ≤ 20, trades 15 ≤ 25 → `shield_veto=false` |

## Metrics: Round 3 vs Round 4A

| Metric | Round 3 | Round 4A | Delta |
|--------|---------|----------|-------|
| Final equity | $1,734.99 | $1,729.88 | -5.11 |
| Total return % | 4.33 | 4.02 | -0.31 |
| Max DD % | 12.65 | 19.34 | +6.69 |
| Sharpe | 0.415 | 0.342 | -0.073 |
| Num trades | 15 | 15 | +0 |
| Win rate % | 33.33 | 33.33 | +0.00 |
| Profit factor | 1.201 | 1.186 | -0.015 |
| Net P&L | $69.24 | $65.08 | -4.16 |
| Avg hold days | 15.8 | 15.3 | -0.5 |

## Notes

- Standing: paper only; isolated one-knob test; no blending.
- Engine output only — no invented fills. Raw: `grok-results/round4_A_be_stop_delay_raw.json`.
- Delayed BE stop slightly hurt: some winners held longer into deeper pullbacks before BE armed, lifting max DD toward the shield line (19.34% vs 12.65%).
- Trade count unchanged at 15.

## Files

- Engine: `grok-engine/round4a_be_stop_delay.py`
- Summary: `grok-results/round4_A_be_stop_delay.json`
- Raw: `grok-results/round4_A_be_stop_delay_raw.json`
