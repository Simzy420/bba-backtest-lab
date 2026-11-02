# Daily BBA paper backtest — 2026-11-01

**Baseline:** R4-C chop filter (paper only)
**Engine:** `grok-engine/fixed_engine.py` wrapping `r4c_chop_filter_engine.py` (VARIANT=r4c)
**Git:** `252295b` on `engine-fix-recheck` (PR #10 still open; no newer baseline shipped)
**Window:** 2025-11-01 → 2026-11-01 (~365d, last market bar 2026-10-30)
**Shield:** veto if max DD > 20% or trades > 25/yr

| ATR | Return | Max DD | Sharpe | Trades | Shield |
|-----|--------|--------|--------|--------|--------|
| 0.9x | -9.17% | 14.80% | -0.942 | 12 | PASS |
| 1.0x **(baseline)** | +10.61% | 8.49% | 1.094 | 9 | PASS |
| 1.1x | +11.51% | 9.26% | 1.017 | 7 | PASS |

## Notes
- Price cache refreshed today (weekend; no new market bar since 10-30).
- Baseline vs 2026-10-31: return, DD, trades identical; Sharpe +0.002 (window shift).
- ATR 0.9x robustness row improved (-11.44% → -9.17%, DD 14.94% → 14.80%) as an early-window losing trade rolled out; still negative, trades unchanged.
- No Shield flips. Baseline unchanged, so no group post.
