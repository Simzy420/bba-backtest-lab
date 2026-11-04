# Daily BBA paper backtest — 2026-11-03

**Baseline:** R4-C chop filter (paper only)
**Engine:** `grok-engine/fixed_engine.py` wrapping `r4c_chop_filter_engine.py` (VARIANT=r4c)
**Git:** `252295b` on `engine-fix-recheck` (PR #10 still open; no newer baseline shipped)
**Window:** 2025-11-03 → 2026-11-03 (~365d, last market bar 2026-11-03)
**Shield:** veto if max DD > 20% or trades > 25/yr

| ATR | Return | Max DD | Sharpe | Trades | Shield |
|-----|--------|--------|--------|--------|--------|
| 0.9x | -9.17% | 14.80% | -0.938 | 12 | PASS |
| 1.0x **(baseline)** | +10.61% | 8.49% | 1.089 | 9 | PASS |
| 1.1x | +11.51% | 9.26% | 1.012 | 7 | PASS |

## Notes
- Price cache refreshed; new market bar for 11-03.
- All rows vs 2026-11-02: return, DD, trades identical; Sharpe moved by ≤0.003 (window shift).
- No Shield flips. Baseline unchanged, so no group post.
