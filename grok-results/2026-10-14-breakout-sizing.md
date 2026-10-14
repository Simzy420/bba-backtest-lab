# Breakout >200MA — position sizing test (2026-10-14, PAPER ONLY)

One change: sleeve size × factor (or ATR-scaled: min(1, 2.5%/ATR14%), fixed at entry). Long-only, 1x max, 6-asset equal split, same signals/costs as walkforward-v1. Walk-forward 2y train / 6mo test / 6mo step, 10 windows, picks on train only (n∈{20,40,60}). Holdout: tuned on 2024-04-13..2026-04-13, tested 2026-04-14..2026-10-13 untouched. Data through 2026-10-13.

| Size | OOS ret | CAGR | MaxDD | Sharpe | Trades/yr | Cost/gross | Nudge -10% / +10% | Losing windows | Holdout ret / DD (14 trades) | Shield |
|---|---|---|---|---|---|---|---|---|---|---|
| size_1.0 | 38.74% | 7.12% | 21.76% | 0.577 | 22.7 | 32.0% | 36.58% / 41.76% | 5/10 | -9.12% / 10.6% | VETO |
| size_0.9 | 48.44% | 8.66% | 19.75% | 0.715 | 24.2 | 27.9% | 49.27% / 51.67% | 5/10 | -8.22% / 9.57% | PASS |
| size_0.8 | 42.6% | 7.74% | 17.7% | 0.715 | 24.2 | 27.9% | 43.34% / 45.35% | 5/10 | -7.32% / 8.54% | PASS |
| size_0.7 | 36.87% | 6.82% | 15.62% | 0.715 | 24.2 | 27.9% | 37.51% / 39.17% | 5/10 | -6.42% / 7.49% | PASS |
| size_0.6 | 31.24% | 5.88% | 13.5% | 0.715 | 24.2 | 27.9% | 31.78% / 33.12% | 5/10 | -5.51% / 6.44% | PASS |
| size_0.5 | 25.73% | 4.93% | 11.34% | 0.715 | 24.2 | 27.9% | 26.17% / 27.22% | 5/10 | -4.6% / 5.39% | PASS |
| size_atr_2.5pct | 41.72% | 7.6% | 12.83% | 0.856 | 23.3 | 26.1% | 41.7% / 43.36% | 5/10 | -7.12% / 8.44% | PASS |

Notes: at 1.0x the train-side Shield vetoed some configs, so window picks differ from the reduced sizes (hence 1.0x < 0.9x). Below 1.0x, picks are identical, so return/DD just scale with size; Sharpe is unchanged. Holdout lost money at every size (n=60 picked); 14 trades in 6 months ≈ 28/yr annualized, over the 25 cap for that period alone. 5/10 test windows lost money at every size.

Verdict: 0.7x–0.9x and ATR-scaled clear the full-period Shield, and ATR-scaled has the best Sharpe (0.86, 12.8% DD). But half the windows lose money and the untouched last 6 months lost 5–9%. Smaller bets fix the drop size, not whether the strategy works. Not ready to promote; keep it on paper/watch.
