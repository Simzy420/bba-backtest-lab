# Round 4 R1 — TRANSITION probe-only

**Date:** 2026-09-16  
**Test ID:** `round4_R1_transition_probe_only`  
**Knob:** Current daily regime == TRANSITION → no confirm/jugular adds. One knob only.

**Gate rule chosen:** `current_daily_regime` (not `regime_at_entry`). TRANSITION-entry probes may later confirm iff current regime is RISK-ON. RISK-ON probes cannot add if regime flips to TRANSITION mid-trade.

## Verdict

**FAIL vs Round 3; SHIELD PASS**

| Gate | Result |
|------|--------|
| vs Round 3 improvement | **FAIL** — return 3.96% vs published R3 4.33%. `pass_vs_round3` is true only if return ≥ R3. TRANSITION confirm/jugular still present (current-regime gate allows promote once RISK-ON). |
| Shield (DD≤20% and ≤25 trades) | **PASS** — DD 12.79% ≤ 20, trades 16 ≤ 25 → `shield_veto=false` |
| Researcher kill (return drop >3pp AND MDD improvement <1pp) | **did not fire** — return drop 0.37pp vs published R3, MDD improvement -0.14pp |

## Metrics: Round 3 vs Round 4 R1

| Metric | Round 3 (published) | Round 4 R1 | Delta vs published R3 |
|--------|---------------------|------------|-----------------------|
| Final equity | $1,734.99 | $1,728.80 | -6.19 |
| Total return % | 4.33 | 3.96 | -0.37 |
| Max DD % | 12.65 | 12.79 | +0.14 |
| Sharpe | 0.415 | 0.386 | -0.029 |
| Num trades | 15 | 16 | +1 |
| Win rate % | 33.33 | 31.25 | -2.08 |
| Profit factor | 1.201 | 1.178 | -0.023 |
| Net P&L | $69.24 | $62.45 | -6.79 |
| Avg hold days | 15.8 | 14.8 | -1.0 |

Same-session official control (knob OFF, identical bars): return 3.96%, DD 12.79%, n=16, net $62.45. Same-session official control is identical to R1 — the knob did not change any fills on this snapshot.

## What the knob actually did

Engine output only — no invented fills. Raw: `grok-results/round4_R1_transition_probe_only_raw.json`. Window 2025-09-17 → 2026-09-16.

- Phase mix R1: confirm 11, probe 5 (published R3 was 11 confirm / 4 probe / 0 jugular).
- Skipped pyramid add events (would-have-fired during TRANSITION): 0.
- Unique blocked promotions: none.
- Executed TRANSITION-origin promotions: 2025-12-18 TSLA confirm current=RISK-ON entry=TRANSITION +3.45%.
- TSLA leak check: TSLA confirm on 2025-12-18 while current_regime=RISK-ON (regime_at_entry=TRANSITION, +3.45%).
- TRANSITION-entry trades remaining at confirm/jugular: 1 (published R3 had 1).
- TRANSITION confirm/jugular still present (current-regime gate allows promote once RISK-ON).
- Same-session official control is identical to R1 — the knob did not change any fills on this snapshot.

Published-R3 deltas can include last-bar GOLD/crypto drift (live Sep-16 print vs the earlier R3 snapshot). Do not attribute those deltas to the knob unless they also appear vs same-session control.

## Notes

- Standing: paper only; isolated one-knob test; no blending.
- return 3.96% < R3 4.33% (pass_vs_round3 requires return ≥ R3 even if DD/Sharpe improve); DD 12.79% vs R3 12.65%; Sharpe 0.386 vs R3 0.415; TRANSITION confirm/jugular still present: TSLA 2025-12-17 confirm
- Researcher kill did not fire.

## Files

- Engine: `grok-engine/round4r1_transition_probe_only.py`
- Summary: `grok-results/round4_R1_transition_probe_only.json`
- Raw: `grok-results/round4_R1_transition_probe_only_raw.json`
