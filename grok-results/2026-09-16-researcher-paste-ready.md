# PASTE FOR BIG BRAIN APE — Researcher (official R3 GOLD + Round 4)
**From:** Researcher via Casey · 2026-09-16 PT  
**Source:** github.com/Simzy420/bba-backtest-lab `round3-hl-full-2026-09-16.json`

## Official R3 (authoritative)
+4.33% · MDD 12.65% · 15 trades · WR 33.3% · winners ~2.4× losers · Sharpe 0.415 · HL costs $79.90 (54% gross) · vs BTC HODL −35.26%

## GOLD dig (official fills)
- GOLD sleeve **$+113.47 net** (164% of book net) across **5** trades — largest symbol contributor.
- Winners: RISK-ON **confirm** exits RSI_OVERBOUGHT (+$69.95, 23d) and TIME_STOP (+$79.13, 31d).
- Losers: BREAKEVEN_STOP confirm −$25.62; late probe BACKTEST_END −$11.40; TRANSITION probe +$1.41 then RISK_OFF.
- Whole book: **0 jugular** stages (11 confirm / 4 probe). Edge = confirm home runs allowed to run — not jugular size.
- Single best trade in file is **NVDA +$139.39**; treat GOLD as star **sleeve**, don’t GOLD-only overfit.
- Local proxy jugular/RS story is **NOT live-agent alpha** — official path differs.

## Failure buckets (all 15)
1. Premature BREAKEVEN_STOP — 5 trades, $−183, 0% WR  
2. BELOW_MA50 after confirm — 3 trades, $−150, 0% WR  
3. Funding drag — $58.82 of $79.90 costs (74%)

## Round 4 — isolated one knob (Boss picks ONE)
**A** BE delay → +1.5R or bar 8 (later) ← **run first**  
**B** Entry tighten (RSI recover/reject + EMA20/50)  
**C** Chop filter (ATR% / EMA gap)  
**D** Flatten adverse funding after 48h unless ≥+1R; no extra names ← **second**  

Shield veto: DD >20% or >25 trades/year. Paper only. 15 trades/year is the feature. No blending. No size-up for fees.

Artifacts: `grok-results/2026-09-16-researcher-gold-dig.md` · `…-round4-matrix.md`
