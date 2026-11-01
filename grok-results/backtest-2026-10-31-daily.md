# Daily BBA paper backtest — 2026-10-31

**Baseline:** R4-C chop filter (paper only)
**Engine:** `grok-engine/fixed_engine.py` wrapping `r4c_chop_filter_engine.py` (VARIANT=r4c)
**Git:** `252295b` on `engine-fix-recheck` (PR #10 still open; no newer baseline shipped)
**Window:** 2025-10-31 → 2026-10-31 (~365d, last market bar 2026-10-30)
**Shield:** veto if max DD > 20% or trades > 25/yr

| ATR | Return | Max DD | Sharpe | Trades | Shield |
|-----|--------|--------|--------|--------|--------|
| 0.9x | -11.44% | 14.94% | -1.208 | 12 | PASS |
| 1.0x **(baseline)** | +10.61% | 8.49% | 1.092 | 9 | PASS |
| 1.1x | +11.51% | 9.26% | 1.014 | 7 | PASS |

## Notes
- Price cache refreshed today.
- Prior daily 2026-10-30: returns, DD, and trades identical; Sharpe moved by ~0.003 (window shift only).
- Change vs prior: none meaningful. No Shield flips. No group post.
