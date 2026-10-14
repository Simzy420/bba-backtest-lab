# Walk-forward v1 — 2026-10-14 (PAPER ONLY)

Harness: `grok-engine/walkforward.py`. Daily yfinance data, as-of aligned to the ^GSPC grid, 2020-01 → 2026-10-13. **Train 2y / test 6mo / step 6mo** gives 10 OOS windows (2022-01 → 2026-10, about 4.8 yrs stitched). Params are picked on train only (best Sharpe among Shield-passing configs). Same cost model: 4.5 bps fee + 4.5 bps slippage per side, plus funding per 8h. R4-C and R3 run through the lab scripts (book sizing, ≤3x pyramid). The simple strategies run as equal-weight 1/6 sleeves across BTC/ETH/SOL/GOLD/NVDA/TSLA at 1x, long-only. Robustness: OOS return with the picked param scaled ×0.9 and ×1.1. Shield: DD > 20% or > 25 trades/yr.

| Rank | Strategy | OOS return | CAGR | Max DD | Sharpe | Trades/yr | Cost/Gross | ±10% returns | Shield |
|---|---|---|---|---|---|---|---|---|---|
| 1 | RSI mean-reversion | +16.18% | +3.20% | 17.74% | 0.32 | 4.2 | 27.0% | x0.9:+9.2% / x1.1:+2.2% | PASS |
| 2 | Donchian trend | +89.50% | +14.38% | 24.62% | 0.72 | 17.4 | 27.8% | x0.9:+134.3% / x1.1:+111.6% | VETO |
| 3 | Breakout >200MA | +38.74% | +7.12% | 21.76% | 0.58 | 22.7 | 32.0% | x0.9:+36.6% / x1.1:+41.8% | VETO |
| 4 | Trend MA cross | +46.58% | +8.37% | 36.88% | 0.44 | 7.6 | 40.4% | x0.9:+37.6% / x1.1:+37.3% | VETO |
| 5 | R4-C Druckenmiller | +32.89% | +6.16% | 30.06% | 0.42 | 12.0 | 26.1% | x0.9:-5.6% / x1.1:-4.4% | VETO |
| 6 | BTC buy-and-hold | +5.16% | +1.06% | 69.17% | 0.28 | 0.0 | 43.7% | — | VETO |
| 7 | R3 Druckenmiller | -10.75% | -2.36% | 29.77% | -0.01 | 19.1 | 139.4% | x0.9:-24.3% / x1.1:-19.3% | VETO |

## R4-C per-window picks (ATR_MULT)
| Train | Test | Pick | OOS ret | Trades |
|---|---|---|---|---|
| 2020-01-01..2022-01-01 | 2022-01-01..2022-07-01 | 1.1 | -3.83% | 1 |
| 2020-07-01..2022-07-01 | 2022-07-01..2023-01-01 | 1.1 | +0.00% | 0 |
| 2021-01-01..2023-01-01 | 2023-01-01..2023-07-01 | 1.0 | -15.59% | 8 |
| 2021-07-01..2023-07-01 | 2023-07-01..2024-01-01 | 1.0 | +10.76% | 12 |
| 2022-01-01..2024-01-01 | 2024-01-01..2024-07-01 | 1.0 | -11.64% | 11 |
| 2022-07-01..2024-07-01 | 2024-07-01..2025-01-01 | 1.0 | +26.45% | 8 |
| 2023-01-01..2025-01-01 | 2025-01-01..2025-07-01 | 1.1 | -0.40% | 2 |
| 2023-07-01..2025-07-01 | 2025-07-01..2026-01-01 | 1.1 | +11.72% | 8 |
| 2024-01-01..2026-01-01 | 2026-01-01..2026-07-01 | 1.1 | +20.21% | 6 |
| 2024-07-01..2026-07-01 | 2026-07-01..2026-10-13 | 1.1 | -1.10% | 1 |

## Read
- **R4-C, out of sample:** +32.9% (6.2% CAGR), DD 30.1%, Sharpe 0.42, 12 trades/yr. Shield vetoes it on DD. It is also fragile: moving ATR ±10% off the picked value gives about −5%. The 1-year in-sample +15% does not hold across 2022–2026.
- **No strategy clearly beats R4-C on a Shield-passing basis.** RSI mean-reversion is the only one that passes, but it returns less (+16.2%, Sharpe 0.32) and isn't robust (±10% → +9% / +2%).
- **Donchian trend** has the best numbers (+89.5%, Sharpe 0.72, DD 24.6%) but fails Shield on DD, and its ±10% spread is wide (+134% / +112%). **Breakout >200MA** is the most robust (±3pp) at Sharpe 0.58, but its DD is 21.8% (veto) and it runs 22.7 trades/yr. These are the leads worth a DD-control follow-up.
- **R3** loses OOS (−10.8%; costs exceed gross). BTC buy-and-hold: +5.2% with a 69% DD.

Caveats: GC=F is a futures proxy for GOLD. SOL data starts 2020-04. The simple-strategy trade counts are entries summed across sleeves. The lab scripts run with about 110 days of warm-up before each test, and trades are counted by entry date. Positions opened in the warm-up can carry into the test window.
