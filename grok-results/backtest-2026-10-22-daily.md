# Daily BBA paper backtest — 2026-10-22

**Baseline:** R4-C chop filter (paper only)
**Engine:** `grok-engine/fixed_engine.py` wrapping `r4c_chop_filter_engine.py` (VARIANT=r4c)
**Git:** `252295b` on `engine-fix-recheck` (PR #10 still open; no newer baseline shipped)
**Window:** 2025-10-22 → 2026-10-22 (~365d; last market bar 2026-10-22)
**Shield:** veto if max DD > 20% or trades > 25/yr

| ATR | Return | Max DD | Sharpe | Trades | Shield |
|-----|--------|--------|--------|--------|--------|
| 0.9x | -10.75% | 14.56% | -1.126 | 12 | PASS |
| 1.0x **(baseline)** | +10.61% | 8.49% | 1.089 | 9 | PASS |
| 1.1x | +11.51% | 9.26% | 1.012 | 7 | PASS |

## Notes
- Fixed engine: daily yfinance (incl. crypto) with carry-forward and end-of-window cash close. Price cache refreshed today.
- Prior daily 2026-10-21: baseline +10.61%/8.49%/1.089/9; ATR 0.9 −10.93%/14.56%/12; ATR 1.1 +11.51%/9.26%/7.
- Change vs prior: none meaningful (baseline identical; small drift on 0.9x only). No Shield flips.
