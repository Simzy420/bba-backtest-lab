# Round 4 R1 — TRANSITION probe-only

**Date:** 2026-09-16 (America/Boise)  
**Test ID:** `round4_R1_transition_probe_only`  
**Knob:** Ban confirm + jugular adds while regime is TRANSITION. Probes still allowed in TRANSITION; confirm/jugular only when RISK-ON. One knob only.

## Verdict

**FAIL vs Round 3 (worse return & Sharpe; DD slightly higher); SHIELD PASS (no veto)**

| Gate | Result |
|------|--------|
| vs Round 3 improvement | **FAIL** — return 3.95% vs 4.33%, DD 12.8% vs 12.65%, Sharpe 0.386 vs 0.415 |
| Shield (DD≤20% and ≤25 trades/yr) | **PASS** — DD 12.8% ≤ 20, trades 16 (16.1/yr) ≤ 25 → `shield_veto=false` |

## Metrics: Round 3 vs Round 4 R1

| Metric | Round 3 | Round 4 R1 | Delta |
|--------|---------|------------|-------|
| Final equity | $1,734.99 | $1,728.68 | -6.31 |
| Total return % | 4.33 | 3.95 | -0.38 |
| Max DD % | 12.65 | 12.8 | +0.15 |
| Sharpe | 0.415 | 0.386 | -0.029 |
| Num trades | 15 | 16 | +1 |
| Win rate % | 33.33 | 31.25 | -2.08 |
| Profit factor | 1.201 | 1.177 | -0.024 |
| Total costs | $79.90 | $80.50 | +0.60 |
| Net P&L | $69.24 | $62.32 | -6.92 |
| Avg hold days | 15.8 | 14.8 | -1.0 |

## Notes

- Standing: paper only; isolated one-knob test; no blending.
- Engine output only — no invented fills. Raw: `grok-results/round4_R1_transition_probe_only_raw.json`.
- Code change: pyramiding gate `regime == "RISK-ON"` (was `regime in ("RISK-ON", "TRANSITION")`). Probe entry scans unchanged.
- Same window/data path as R3 (yfinance/CoinGecko `period=1y`; bench 2025-09-17 → 2026-09-16). Regime distribution identical to R3 (153/83/16).
- Extra +1 trade vs R3: two TRANSITION probe entries on 2026-09-16 (BTC/ETH) closed at BACKTEST_END with tiny fee drag — capital path differed after blocking TRANSITION confirms.
- Shield: DD 12.80% and 16 trades/yr — no veto.

## Files

- Engine: `grok-engine/round4_r1_transition_probe_only.py`
- Summary: `grok-results/round4_R1_transition_probe_only.json`
- Raw: `grok-results/round4_R1_transition_probe_only_raw.json`
