# Daily paper backtest 2026-11-08 (R4-C + ATR 0.9/1.1)

Window 2025-11-08 to 2026-11-08, last market bar 2026-11-06, engine sha 252295b (PR #10 still open). Paper only.

| Row | Return | Max DD | Sharpe | Trades | Shield |
|---|---|---|---|---|---|
| R4-C ATR 0.9x | -11.16% | 16.67% | -1.150 | 13 | PASS |
| R4-C baseline (ATR 1.0x) | +8.18% | 9.67% | 0.852 | 10 | PASS |
| R4-C ATR 1.1x | +9.06% | 11.26% | 0.814 | 8 | PASS |

No meaningful change vs 2026-11-06 (no 2026-11-07 artifact; that run failed): ATR 0.9: dRet=+0.00pp dDD=+0.00pp dTrades=+0; ATR 1.0: dRet=+0.00pp dDD=+0.00pp dTrades=+0; ATR 1.1: dRet=+0.00pp dDD=+0.00pp dTrades=+0. Sharpe moved by ≤0.006 (window shift / weekend). No Shield flips. No group post.
