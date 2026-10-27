# Daily BBA paper backtest — 2026-10-26

**Baseline:** R4-C chop filter (paper only)
**Engine:** `grok-engine/fixed_engine.py` wrapping `r4c_chop_filter_engine.py` (VARIANT=r4c)
**Git:** `252295b` on `engine-fix-recheck` (PR #10 still open; no newer baseline shipped)
**Window:** 2025-10-26 → 2026-10-26 (~365d; last market bar 2026-10-26)
**Shield:** veto if max DD > 20% or trades > 25/yr

| ATR | Return | Max DD | Sharpe | Trades | Shield |
|-----|--------|--------|--------|--------|--------|
| 0.9x | -11.44% | 14.94% | -1.208 | 12 | PASS |
| 1.0x **(baseline)** | +10.61% | 8.49% | 1.092 | 9 | PASS |
| 1.1x | +11.51% | 9.26% | 1.014 | 7 | PASS |

## Notes
- Fixed engine: daily yfinance (incl. crypto) with carry-forward and end-of-window cash close. Price cache refreshed today.
- Prior daily 2026-10-25: baseline +10.61%/8.49%/1.094/9; ATR 0.9 −11.25%/14.75%/12; ATR 1.1 +11.51%/9.26%/7.
- Change vs prior: none meaningful (baseline return/DD/trades identical; ATR 0.9 small drift −11.25→-11.44%; tiny Sharpe drift). No Shield flips.
