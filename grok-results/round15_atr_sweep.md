# Round 15 — ATR-hurdle robustness sweep (paper only)
Engine: `grok-engine/round15_atr_sweep.py` (R4-C rules; env `ATR_MULT`, `VARIANT`). Window: latest 365d as of 2026-10-14. All else R4-C. One knob, no blending, no size-up.

| ATR mult | Return | MaxDD | Sharpe | Trades | WR | Cost/Gross | Shield |
|---|---|---|---|---|---|---|---|
| 0.8 | -4.85% | 20.62% | -0.29 | 11 | 36.4% | 42% | **VETO (DD)** |
| 0.9 | -16.75% | 30.49% | -0.49 | 9 | 33.3% | 28% | **VETO (DD)** |
| **1.0 (R4-C rerun)** | +9.56% | 8.52% | 1.10 | 8 | 37.5% | 22% | PASS |
| 1.1 | +12.75% | 8.25% | 1.32 | 6 | 50.0% | 15% | PASS |
| 1.2 | +3.24% | 4.04% | 0.60 | 2 | 50.0% | 23% | PASS |
| side: 1.0 + no TSLA | +10.46% | 7.76% | 1.14 | 8 | 37.5% | 19% | PASS |

Note: R4-C rerun on today's window is +9.56% (vs original +14.90% on the Sep window) — the data window shifted.

**Verdict: knife-edge, not a plateau.** One step looser blows through Shield; tighter thins trades fast (6 → 2). 1.1x looks better but n=6 is noise. No ship; R4-C stays baseline. No-TSLA is +0.9pp from removing one trade, so it's not clearly better.

**Anomaly:** at 0.8x/0.9x, the summed net trade P&L is positive, but final equity is negative. The equity/DD accounting needs a check before anyone trusts the loose-side numbers.
