# Daily BBA paper backtest — 2026-10-17

**Baseline:** R4-C chop filter (paper only)
**Engine:** `grok-engine/fixed_engine.py` wrapping `r4c_chop_filter_engine.py` (VARIANT=r4c)
**Git:** `252295b` on `engine-fix-recheck` (PR #10 not yet merged to main; no newer baseline shipped)
**Window:** 2025-10-17 → 2026-10-17 (~365d; last market bar 2026-10-16, Saturday run)
**Shield:** veto if max DD > 20% or trades > 25/yr

| ATR | Return | Max DD | Sharpe | Trades | Shield |
|-----|--------|--------|--------|--------|--------|
| 0.9x | -11.15% | 14.66% | -1.176 | 12 | PASS |
| 1.0x **(baseline)** | +10.61% | 8.49% | 1.092 | 9 | PASS |
| 1.1x | +11.51% | 9.26% | 1.014 | 7 | PASS |

## Notes
- Chop filter: ATR% below 20-bar median × ATR_MULT **or** |EMA20−EMA50|/close < 0.4%; existing positions not force-exited for chop.
- Fixed engine uses daily yfinance (incl. crypto) with last-price carry-forward and end-of-window cash close. Price cache refreshed today.
- Prior daily 2026-10-16: baseline +10.61%/8.49%/1.089/9 trades; ATR 0.9 −11.04%/14.55%/12; ATR 1.1 +11.51%/9.26%/7.
- Change vs prior: none meaningful (baseline return/DD/trades identical, Sharpe +0.003; 0.9x tiny drift from window start shifting one day). No Shield flips.
