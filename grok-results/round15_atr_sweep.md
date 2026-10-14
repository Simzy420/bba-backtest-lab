# Round 15 — ATR-hurdle robustness sweep (paper only) — v2, accounting fixed
Engine: `grok-engine/round15_atr_sweep.py` (R4-C rules; env `ATR_MULT`, `VARIANT`). Window: latest 365d as of 2026-10-14. All else R4-C.

## Accounting bug (fixed in v2)
The engine looked up prices by exact date. CoinGecko's 365-day OHLC returns **4-day candles**, so BTC/ETH/SOL had no row on most days. When a crypto position had no row:
1. MTM left out its margin and unrealized P&L, so equity dropped and the drawdown was phantom.
2. That phantom DD set off DD-defense. The defensive (and RISK-OFF) close hit `continue` on the missing row, then ran `positions = []`. **The position was deleted without its margin going back to cash.** At 0.9x on 2026-09-25 this deleted a BTC position (~$163 + ~$80 confirm margin plus its gain), which explains the −$279 equity against the +$128 trade P&L.

Fix: assets are as-of aligned to the regime date grid (last known close), forced closes fall back to the last price, and final equity is cash after BACKTEST_END closes. Every run now reconciles: final equity − start = sum of trade net P&L.
Side effect: crypto entries can now fire on days that used to be blank, so trade sets shift slightly (R4-C rerun now includes ETH/SOL). Trade counts include 2 BACKTEST_END closes in the 0.8x, 0.9x, 1.0x and no-TSLA rows.

| ATR mult | Return | MaxDD | Sharpe | Trades | WR | Cost/Gross | Shield |
|---|---|---|---|---|---|---|---|
| 0.8 | +5.62% | 12.81% | 0.56 | 13 | 38.5% | 43% | PASS |
| 0.9 | +9.32% | 9.81% | 1.01 | 11 | 36.4% | 28% | PASS |
| **1.0 (R4-C rerun)** | +9.46% | 8.60% | 1.09 | 10 | 30.0% | 23% | PASS |
| 1.1 | +12.75% | 8.25% | 1.32 | 6 | 50.0% | 15% | PASS |
| 1.2 | +3.24% | 4.04% | 0.60 | 2 | 50.0% | 23% | PASS |
| side: 1.0 + no TSLA | +10.37% | 7.84% | 1.13 | 10 | 30.0% | 20% | PASS |

**Verdict:** the "knife-edge" in v1 was mostly the bug. 0.9x through 1.1x is a reasonable plateau. 0.8x degrades (DD 12.8%, cost/gross 43%) and 1.2x starves (2 trades). 1.1x looks best but rests on 6 trades. No ship; R4-C stays baseline.
