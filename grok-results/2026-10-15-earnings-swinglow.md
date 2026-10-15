# Earnings beat + swing low, walk-forward (2026-10-15)

PAPER ONLY, 1x, long-only, equal weight, max concurrent slots. Walk-forward: train 2y / test 6mo / step 6mo, 10 windows 2022-01-01..2026-10-14. Settings picked on TRAIN only (best Sharpe among configs passing DD<=20% and <=50 trades/yr; if none pass, best Sharpe). Costs: same 4.5 bps fee + 4.5 bps slippage per side (no funding on stocks). Holdout: settings picked on 2024-04-13..2026-04-13, tested 2026-04-14..2026-10-14.
Code: `grok-engine/earnings_swinglow.py` (strategy + harness), `earnings_data.py` (S&P 500 list, prices, EPS history), `guidance_edgar.py` (SEC 8-K press-release guidance flags), `report_earnings.py`. Donchian trend removed from `walkforward.py` STRATS (Casey rejected it).

## Rules
- Universe: S&P 500 **current** members (503 tickers, Wikipedia list) -> survivorship bias (yesterday's losers that got dropped from the index are missing; flatters results).
- Signal: **EPS beat vs consensus** (yfinance `get_earnings_dates`: Reported EPS > EPS Estimate). This is a stand-in for "beat guidance"; company guidance history is not in free data. Pre-market reports are tradable that day, after-close reports the next session.
- Uptrend: close > 200-day MA and 50-day MA > 200-day MA.
- Entry: within N trading days of the beat (N tuned in 20/40/60), swing low = low touched the 20-day MA in the last 3 bars OR a 3-bar pivot low at t-1, then a close above the prior close -> buy next open. One entry per beat; if more signals than slots, biggest EPS surprise first.
- Exit: stop 1% below the 3-bar swing low (intraday), trailing stop on closes (8% / 12%, exit next open), time stop (20 / 40 bars). 12-config grid. Nudge test scales N, trail and time stop by 0.9x / 1.1x.
- Variants: 10 slots all beats; throttled = 4 slots and EPS surprise >= 10%.
- Guidance variant: EPS beat AND the company's earnings press release (SEC EDGAR 8-K Item 2.02, Exhibit 99) contains "raised/increased ... guidance/outlook" language. Ran on the 71 most-traded S&P names (2025 median dollar volume, which is itself hindsight): 1,719 releases, 1,320 with readable exhibit text, 167 flagged "raised", 1,299 EPS beats matched to a release, **147 beat+raised events**. Did NOT measure "beat the prior guidance range" (would need number parsing per company); keyword flags will have some false positives/negatives. Firecrawl was not needed (EDGAR is free); zero Firecrawl credits used.

## Scoreboard (existing rows from 2026-10-15 50/yr run, Donchian removed)
| Strategy | Return | CAGR | Max DD | Sharpe | Trades/yr | 25/yr / 50/yr cap | Cost/gross | Losing windows | Nudge -10% / +10% | Holdout (last 6 mo) | DD shield |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **NEW** Earnings beat + swing low (10 slots, all beats) | +109.9% | 16.9% | 23.3% | 1.05 | 170.0 | over / over | 14.5% | 3/10 | 72.88% / 94.83% | +2.2% (DD 13.1%) | FAIL |
| **NEW** Earnings beat + swing low, throttled (4 slots, surprise >=10%) | +77.5% | 12.8% | 28.2% | 0.74 | 51.3 | over / over | 12.4% | 5/10 | 71.58% / 106.25% | +9.7% (DD 22.9%) | FAIL |
| **NEW** EPS beat, throttled, guidance-subset stocks only | +122.2% | 18.3% | 20.6% | 1.06 | 37.8 | over / OK | 7.6% | 2/10 | 116.7% / 89.57% | +13.5% (DD 14.1%) | FAIL |
| **NEW** EPS beat + RAISED guidance (EDGAR), throttled | +48.4% | 8.7% | 11.5% | 0.90 | 9.5 | OK / OK | 4.2% | 5/10 | 36.94% / 51.23% | -3.6% (DD 6.3%) | PASS |
| R4-C Druckenmiller (50/yr run) | +32.9% | 6.2% | 30.1% | 0.42 | 12.0 | OK / OK | 26.1% | 5/10 | -5.59% / -4.37% | - | FAIL |
| R3 Druckenmiller (50/yr run) | -10.8% | -2.4% | 29.8% | -0.01 | 19.1 | OK / OK | 139.4% | 7/10 | -24.34% / -19.26% | - | FAIL |
| Trend MA cross (50/yr run) | +46.6% | 8.4% | 36.9% | 0.44 | 7.6 | OK / OK | 40.4% | 5/10 | 37.65% / 37.3% | - | FAIL |
| Breakout >200MA (50/yr run) | +34.6% | 6.4% | 19.5% | 0.51 | 25.2 | over / OK | 35.9% | 5/10 | 38.2% / 33.46% | - | PASS |
| RSI mean-reversion (50/yr run) | +16.2% | 3.2% | 17.7% | 0.32 | 4.2 | OK / OK | 27.0% | 3/10 | 9.15% / 2.25% | - | PASS |
| BTC buy-and-hold (50/yr run) | +5.2% | 1.1% | 69.2% | 0.28 | 0.0 | OK / OK | 43.7% | 4/10 | - | - | FAIL |
| Breakout >200MA (ATR-scaled) (50/yr run) | +39.8% | 7.3% | 13.2% | 0.81 | 24.8 | OK / OK | 27.7% | 5/10 | - | - | PASS |
| SPY buy-and-hold | +71.3% | 12.0% | 24.5% | 0.74 | 0.2 | OK / OK | 0.3% | - | - | - | FAIL |

Coverage: {'stocks': 71, 'releases': 1719, 'with_text': 1320, 'raised': 167, 'beats_matched': 1299, 'beat_and_raised': 147}

## Verdict
- Casey's plan beats every old strategy on return and Sharpe (+110% vs SPY +71%), but at ~170 trades/yr with 10 slots it blows through both the 25 and 50/yr caps and its worst drop (23%) breaks the 20% shield. Holdout only +2%.
- Throttled to 4 slots / big beats: ~51 trades/yr (just over 50), worst drop 28%. Fails.
- **EPS beat + raised guidance** is the only new version that passes: +48%, 11.5% worst drop, Sharpe 0.90, 9.5 trades/yr (under even Casey's ~15/yr rule), small cost drag. But it lost in 5/10 windows (mostly small), lost 3.6% in the holdout, and only covers 71 big stocks with 147 signals in ~7 years. Promising, not proven.
- Not ready for real money. Next: add a market filter (SPY > 200-day) to cut 2022-style drawdowns, extend the guidance scan to all 500 names, and use point-in-time index membership.

## Data limitations
Survivorship bias (current members), yfinance EPS estimates (consensus as later recorded, may be revised; ~40 quarters max per stock), daily bars only (stop fills approximated at min(open, stop)), guidance flag is keyword-based on press releases only (misses guidance given only on calls), and the guidance subset was chosen by 2025 liquidity.
