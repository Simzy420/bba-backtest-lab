# Earnings beat + swing low v2: top-50 stocks, SPY 200-day filter (2026-10-15)

PAPER ONLY, 1x, long-only. Walk-forward 2022-01-01..2026-10-14, train 2y / test 6mo / step 6mo (10 windows). Settings picked on train only (best Sharpe among configs with DD<=20% and <=50 trades/yr, TPY_CAP=50 as in v1). Same costs (4.5 bps fee + 4.5 bps slippage per side). Holdout: picked on 2024-04-13..2026-04-13, tested 2026-04-14..2026-10-14. Nudge = N, trail, time stop x0.9 / x1.1.
Code: `grok-engine/earnings_v2_top50.py` (reuses `earnings_swinglow.py` and cached EDGAR releases; no new fetching).

**Universe:** the 50 highest 2025 median dollar-volume names among the 71 cached guidance stocks. **Hindsight bias:** chosen by today's (2025) trading volume, which favours this cycle's winners (NVDA, PLTR, HOOD, APP, COIN...). Also current S&P members (survivorship) and GOOG + GOOGL both included.
**Single new change:** market filter = no new entries when SPY close < its 200-day MA (open positions still exit normally).
Beat + raised events in top 50: 67.

| Version | Return | CAGR | Max DD | Sharpe | Trades/yr | 15 / 25 / 50 cap | Cost/gross | Losing windows | Nudge -10% / +10% | Holdout | Shield |
|---|---|---|---|---|---|---|---|---|---|---|---|
| EPS beat | +89.4% | 14.4% | 14.2% | 1.12 | 101.5 | over / over / over | 10.8% | 2/10 | +87.7% / +90.9% | +10.8% (DD 6.2%) | FAIL (trades) |
| EPS beat + SPY filter | +57.7% | 10.0% | 23.2% | 0.80 | 80.9 | over / over / over | 11.3% | 4/10 | +49.7% / +63.7% | +15.7% (DD 5.6%) | FAIL (DD, trades) |
| EPS beat + raised guidance | +20.0% | 3.9% | 7.6% | 0.68 | 3.6 | OK / OK / OK | 3.3% | 6/10 | +15.6% / +18.5% | -2.5% (DD 2.6%) | PASS |
| EPS beat + raised + SPY filter | +23.8% | 4.6% | 7.0% | 0.82 | 3.4 | OK / OK / OK | 2.8% | 4/10 | +18.9% / +21.6% | +2.0% (DD 2.4%) | PASS |
| SPY buy-and-hold | +71.3% | 12.0% | 24.5% | 0.74 | 0.2 | OK / OK / OK | 0.3% | - | - | - | FAIL (DD) |

## Verdict
- EPS beat on the top 50: best numbers yet (+89%, 14% worst drop, Sharpe 1.12, steady when nudged, holdout +11%), but ~100 trades/yr breaks every cap. Hindsight-picked universe likely flatters it.
- SPY filter hurt the EPS-beat version (lower return, worst drop up to 23%): it kept it out of rebounds and changed which settings got picked. It helped the raised-guidance version slightly (+24% vs +20%, 4/10 vs 6/10 losing windows, holdout +2% vs -2.5%).
- Raised guidance + filter passes every rule but makes only ~4.6%/yr, below SPY, on ~3 trades/yr (67 signals in total), too few to trust.
- Not ready for real money. Nothing beats SPY within the rules.
