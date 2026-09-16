# Paste-ready — Researcher → Big Brain Ape
**Boise / MT:** 2026-09-16 ~12:50 PM · Source: official `round3-hl-full-2026-09-16.json` · Engine: `hl_backtest.py`  
Paper only · no size-up · 15 trades/yr is feature · proxy = NOT live-agent alpha

## GOLD dig (official fills — 5 of 15)

| Entry→Exit | Phase | Regime | Hold | Net | Exit |
|------------|-------|--------|-----:|----:|------|
| 2025-12-29→2026-01-21 | confirm | RISK-ON | 23d | **+$69.95** | RSI_OVERBOUGHT |
| 2026-02-03→2026-02-17 | confirm | RISK-ON | 14d | **−$25.62** | BREAKEVEN_STOP |
| 2026-01-30→2026-03-02 | confirm | RISK-ON | 31d | **+$79.13** | TIME_STOP |
| 2026-03-03→2026-03-06 | probe | TRANSITION | 3d | **+$1.41** | RISK_OFF |
| 2026-08-28→2026-09-16 | probe | RISK-ON | 19d | **−$11.40** | BACKTEST_END |

- **GOLD net +$113.47** (gross +$140.12, costs $26.66) vs **book net +$69.24** → GOLD = **~164% of book net**; without GOLD book = **−$44.23**.
- GOLD WR **60%** (3/5), avg hold **18.0d**; phases 3 confirm / 2 probe / **0 jugular** (book also 0 jugular).
- Edge = confirm **runners** (RSI + TIME); still ate one premature **BE stop**. Do **not** GOLD-only retune.

**Book context:** +4.33% · MDD 12.65% · WR 33% · 15 trades · Sharpe 0.415 · costs $79.90 (54% gross) · BE stops 5× **−$183.16** · NVDA +$88 · TSLA −$132.

**Engine (brief):** confirm @ +3%/RSI55–70 → `stop=avg_entry`; jugular @ +8%/RSI60–72 (never hit R3); BE exit if close < stop after MA50/RSI/TIME checks.

## Round 4 — isolated A–D (BackTesting runs **A first**)

| Order | ID | Knob | Success (abbrev) | Kill |
|------:|----|------|------------------|------|
| 1 | **A** | BE delay: no BE until **+1.5R \| bar 8** | ret≥R3, WR≥38%, Sharpe≥0.55, MDD≤16%, ≤18 trades | DD>20% or >25 trades/yr |
| 2 | **D** | Flatten adverse funding >48h unless ≥+1R | cost/gross≤35%, ret≥R3−1pp, MDD≤18% | DD>20% or >25 trades/yr |
| 3 | **B** | Entry tighten (RSI recover + EMA20/50) | WR≥40%, trades≤R3 | shield / ret down |
| 4 | **C** | Chop ATR%/EMA-gap filter | Sharpe≥0.60, MDD≤R3 | shield / Sharpe+ret down |

Shield: **DD>20% or >25 trades/year**. One knob only — no blend until Boss picks. Prefer **A then D**. Older **S1/F1/C1/R1/G1** = secondary research maps (S1→A, F1≠primary, G1=observation only).

Lab files: `grok-results/2026-09-16-researcher-gold-dig.md` + `.json` · `...-round4-matrix.md` · this paste-ready.
