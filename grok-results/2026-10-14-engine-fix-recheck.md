# Engine-fix recheck (phase 1, walk-forward rebuild) — PAPER ONLY

Harness: `grok-engine/fixed_engine.py` wraps each lab round script unchanged. It loads daily yfinance data for every asset, including crypto (BTC-USD, ETH-USD, SOL-USD), instead of CoinGecko's 4-day 365d candles, as-of aligned to the ^GSPC date grid. This means no missing-row MTM/forced-close loss. Final equity = cash after closes. Every run reconciles (gap ≤ $0.02).
R4-C logic: `grok-engine/r4c_chop_filter_engine.py` (the lab's R4-C script lineage; env ATR_MULT, EMA_GAP). Shield: DD > 20% or > 25 trades.

## Old vs fixed (ret / DD / Sharpe / trades)
| Test | Old reported (Sep window) | Fixed, original window 2025-09-16..2026-09-16 | Shield | Fixed, today 2025-10-13..2026-10-13 | Shield |
|---|---|---|---|---|---|
| R3 baseline | +4.33% / 12.65% / 0.41 / 15 | -14.11% / 18.73% / -1.17 / 14 | PASS | -11.38% / 17.82% / -1.09 / 15 | PASS |
| R4-C chop filter | +14.90% / 8.46% / 1.56 / 9 | +15.05% / 8.49% / 1.58 / 10 | PASS | +14.45% / 8.48% / 1.40 / 10 | PASS |
| R4-A BE delay | +4.02% / 19.34% / 0.34 / 15 | -14.11% / 18.70% / -1.17 / 14 | PASS | -10.30% / 16.97% / -0.87 / 15 | PASS |
| R4-D funding flatten | +4.14% / 12.04% / 0.38 / 26 | +4.17% / 3.21% / 0.96 / 31 | VETO | +2.50% / 4.09% / 0.58 / 33 | VETO |
| R4-R1 TRANSITION probe-only | +3.95% / 12.80% / 0.39 / 16 | -14.11% / 18.73% / -1.17 / 14 | PASS | -11.38% / 17.82% / -1.09 / 15 | PASS |

## PR #5 chop-filter 3x3 grid, original window (old ret/DD/trades → fixed ret/DD/Sharpe/trades)
| ATR × median | EMA gap | Old (PR #5) | Fixed |
|---|---|---|---|
| 0.75 | 0.30% | -13.31% / 14.68% / 19 | -13.13% / 17.00% / -1.23 / 14 |
| 0.75 | 0.40% | -13.31% / 14.68% / 19 | -13.13% / 17.00% / -1.23 / 14 |
| 0.75 | 0.50% | -11.73% / 13.12% / 18 | -13.13% / 17.00% / -1.23 / 14 |
| 1.0 | 0.30% | +14.76% / 8.80% / 10 | +15.05% / 8.49% / 1.58 / 10 |
| 1.0 | 0.40% | +14.76% / 8.80% / 10 | +15.05% / 8.49% / 1.58 / 10 |
| 1.0 | 0.50% | +14.76% / 8.80% / 10 | +15.05% / 8.49% / 1.58 / 10 |
| 1.25 | 0.30% | +0.37% / 4.04% / 3 | +3.24% / 4.04% / 0.60 / 2 |
| 1.25 | 0.40% | +0.37% / 4.04% / 3 | +3.24% / 4.04% / 0.60 / 2 |
| 1.25 | 0.50% | +0.37% / 4.04% / 3 | +3.24% / 4.04% / 0.60 / 2 |

## Read
- **R4-C holds up:** +15.05% / DD 8.49% / Sharpe 1.58 on the original window, and +14.45% / 8.48% / 1.40 on today's. It is still the best and still the baseline.
- **R3 baseline flips:** +4.33% → −14.11% on the original window. Its old result depended on the CoinGecko 4-day-candle data and the broken accounting. NVDA, TSLA and ETH lose money in the fixed run.
- **No rejected test beats fixed R4-C.** A loses DD 19.34% → 18.70%, still under Shield's 20% limit, but returns −14.1% (the same as R3). D has low DD but 31 to 33 trades, so Shield vetoes it. R1 matches R3, since no TRANSITION confirms fire.
- **Grid:** EMA gap is still inert. ATR 0.75× loses about 13% and 1.25× trades only 2 times. The ATR hurdle is still the sensitive knob.
