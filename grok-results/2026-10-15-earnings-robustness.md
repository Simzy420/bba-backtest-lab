# Earnings beat + swing low: robustness (2026-10-15)

Plan: EPS beat (reported > consensus) + uptrend + swing-low entry; no guidance filter, no SPY filter. Paper, 1x, long-only. Cap 100 trades/yr, max DD <= 20%.
Universe: point-in-time S&P 500 (fja05680/sp500), 763 tickers ever in index since 2016; 602 had Yahoo prices+EPS (161 delisted/renamed names missing -> some survivorship remains). Entries allowed only while a member. Data through 2026-10-14.
Grid: N {20,40,60} x trail {8,12%} x time stop {20,40} x slots {10,5} x min surprise {0,5,10%}; pick = best training Sharpe with DD<=20% and <=100/yr.

| Test | Current fees (9 bps/side) | Robinhood (0 comm + 5 bps slip) | SPY buy & hold |
|---|---|---|---|
| 1. PIT walk-forward 2022-today | -14.2%, DD 31.9%, 97.3/yr, losing 5/10, beat SPY 3/10 | -9.1%, DD 30.4%, losing 5/10, beat SPY 3/10 | +72.3%, DD 24.5% |
| 2. Frozen pick, in-sample 2022-24 | +3.8%, DD 18.3% | +7.9%, DD 16.9% | +28.7%, DD 24.5% |
| 2. Unseen 2018-21 | -1.4%, DD 37.1% | +3.8%, DD 35.8% | +90.4%, DD 33.7% |
| 2. Unseen 2025-26 | +26.7%, DD 18.1% | +29.9%, DD 17.6% | +33.6%, DD 18.8% |
| 3. Monte Carlo shuffle x1000: DD p5/p50/p95 | 12.45/17.66/24.18% (return fixed -7.61%) | 11.03/16.23/22.58% (return -4.13%) | - |
| 3. Bootstrap x1000: return p5/p50/p95 | -27.6/-8.92/16.45%; P(loss) 71.5% | -24.08/-4.59/26.78%; P(loss) 59.9% | - |
| 4. Random entry x200 (avg trade) | plan -0.146% vs random median 0.538%; beats 1.5% of runs | plan -0.066% vs 0.68%; beats 3.0% | - |
| 5. Nudge settings x0.8/0.9/1.1/1.2 (walk-forward) | x0.8: +7.6% (DD 31%) / x0.9: +17.6% (DD 26%) / x1.1: -2.2% (DD 27%) / x1.2: -23.4% (DD 31%) | x0.8: +14.8% (DD 30%) / x0.9: +24.9% (DD 25%) / x1.1: +3.4% (DD 27%) / x1.2: -19.2% (DD 31%) | - |

Verdict: no real edge. On the honest point-in-time list the plan loses to SPY in every test, breaks the 20% DD limit in walk-forward and 2018-21, and does worse than random entries on the same stocks (beats only 1.5-3% of random runs; needed 95%). The earlier +89% top-50 result came from hindsight in the stock list. Monte Carlo: return is order-independent in this model; ~18-26% of reshuffles exceed 20% DD.

Notes: Monte Carlo/random-entry use a simplified model (each trade = 1/10 of equity, compounded). Random entries keep each trade's stock and holding length, random start date while the stock was a member, 2022-today. Earlier run with base grid only (K=10, no throttle) traded ~169/yr (over the 100 cap): walk-forward +16.0% (current fees) / +23.1% (Robinhood), max DD 26.3% / 24.5%, beat SPY in 2/10 windows; random-entry percentile 10.5% / 11.0%.
