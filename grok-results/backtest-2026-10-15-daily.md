# Daily BBA paper backtest — 2026-10-15

**Baseline:** R4-C chop filter (paper only)
**Engine:** `grok-engine/fixed_engine.py` wrapping `r4c_chop_filter_engine.py` (VARIANT=r4c)
**Git:** `252295b` on `engine-fix-recheck`
**Window:** 2025-10-15 → 2026-10-15 (~365d)
**Shield:** veto if max DD > 20% or trades > 25/yr

| ATR | Return | Max DD | Sharpe | Trades | Shield |
|-----|--------|--------|--------|--------|--------|
| 0.9x | -11.13% | 14.64% | -1.171 | 12 | PASS |
| 1.0x **(baseline)** | +10.61% | 8.49% | 1.089 | 9 | PASS |
| 1.1x | +11.51% | 9.26% | 1.012 | 7 | PASS |

## Notes
- Chop filter: ATR% below 20-bar median × ATR_MULT **or** |EMA20−EMA50|/close < 0.4%; existing positions not force-exited for chop.
- Fixed engine uses daily yfinance (incl. crypto) with last-price carry-forward and end-of-window cash close.
- Prior daily 2026-10-14: baseline +10.61%/8.49%/9 trades; ATR 0.9 −10.87%/14.49%/12; ATR 1.1 +11.51%/9.26%/7.
