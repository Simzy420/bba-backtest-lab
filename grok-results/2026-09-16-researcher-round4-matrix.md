# Researcher — Round 4 isolated A–D matrix (official engine)
**Baseline:** Official R3 +4.33% / MDD 12.65% / 15 RT / WR 33.3% / Sharpe 0.415 / costs $79.90 (54% gross)  
**Standing:** paper only · no leverage/size-up · do not add trades for fees · **15 RT/yr is the feature**  
**Shield veto:** DD >20% OR >25 trades/year → kill. Boss picks **ONE** winner. **No blending.**  
**Runner:** BBA BackTesting bot starts with **A** on `bba-engine/hl_backtest.py`.

| ID | Knob | Change vs R3 | Why (official evidence) | Success | Kill |
|----|------|--------------|-------------------------|---------|------|
| **A** | BE-stop delay | No BE until **+1.5R OR bar 8** (whichever later); hard stop live pre-BE | 5× BREAKEVEN_STOP, **$−183.16**, 0% WR — largest failure bucket; GOLD confirm BE −$25.62 | WR ≥38%; return ≥ R3; MDD ≤16%; BE-exit count ↓ ≥50% | MDD >18% with WR gain <3pp **or** return drop >2pp **or** shield |
| **B** | Entry tighten | RSI recover/reject + EMA20/EMA50 rules | Structure failures BELOW_MA50 (3 trades, $−149.85, 0% WR); TSLA sleeve −$132 | WR ≥38%; n ≤15; return ≥0; MDD ≤18% | n <8 with return <0 **or** shield |
| **C** | Chop filter | No trade if ATR% < 20-bar median **or** EMA gap <0.4% | Sharpe 0.41 from chop / scratch noise | Sharpe ≥0.55; cost/gross ≤45%; MDD ≤ R3+2pp; return ≥ R3−1pp | return drop >2pp **or** shield |
| **D** | Cost control | Flatten adverse funding after **48h** unless ≥+1R; **no extra names** | Funding **$58.82** = 74% of $79.90 costs; long GOLD holds pay $6–9 funding | cost/gross ≤35%; n ≤15; return ≥0 | cost/gross >45% **or** >25 RT/yr **or** shield |

## Recommended order
1. **A** (BackTesting running) — highest pain / lowest overfit  
2. **D** — funding is majority of cost drag without adding volume  
3. **C** then **B** — only if A/D don’t clear Sharpe/WR enough  

Secondary research hyps (NOT official A–D; do not blend): fewer/larger soft cap, hard ban TRANSITION confirm/jugular, GOLD 60d RS filter.

## Log every run
return, MDD, WR, n_trades, cost% of gross, Sharpe, BE-exit count, funding $. Baseline = official R3. Label proxy runs **NOT live-agent alpha**.
