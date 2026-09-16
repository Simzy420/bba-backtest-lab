# Researcher — Round 4 experiment matrix (official A–D)
**Baseline:** Official R3 `bba-results/round3-hl-full-2026-09-16.json`  
(+4.33% · MDD 12.65% · WR 33.3% · 15 trades · Sharpe 0.415 · costs $79.90 = 53.6% of gross · GOLD +$113.47)  
**Author:** Researcher (Grok) · **Boise / MT:** 2026-09-16 ~12:50 PM  
**Standing:** paper only · **one knob only** · no blending until Boss picks · no leverage/size-up · 15 trades/yr is a feature

**Shield veto (hard kill):** max DD **>20%** **OR** **>25 trades/year**.  
**BackTesting run order:** **A first**, then B/C/D as scheduled. Researcher preference if scarce cycles: **A → D → B → C**.

Older research tags (**S1 / F1 / C1 / R1 / G1**, Trader `R4-C-S1` etc.) are **secondary / mapped** below — do not substitute for official A–D.

Proxy sandbox (`bba-proxy-backtest`): **NOT live-agent alpha** — may replay for smoke only; success/kill criteria use **official R3 baseline**.

---

## Official isolated tests A–D

| ID | One knob | Concrete change vs R3 | Hypothesis (from official fills) | Success criteria | Kill criteria |
|----|----------|----------------------|----------------------------------|------------------|---------------|
| **A** ★ first | **BE-STOP DELAY** | No breakeven stop until **+1.5R *or* bar 8** (whichever later). Hard structural stops (MA50 / RISK_OFF / DD defense) unchanged. | Attacks book **BREAKEVEN_STOP 5× = −$183.16 net, 0% WR** (incl. GOLD −$25.62). Confirm currently sets `stop_price=avg_entry` immediately (`hl_backtest.py`). | Return **≥ R3 (+4.33%)**; WR **≥38%**; Sharpe **≥0.55**; MDD **≤16%**; n_trades **≤18**; cost/gross **≤45%** | MDD **>20%** **or** n_trades **>25** **or** return **<0** **or** (MDD >18% **and** WR gain <3pp) |
| **B** | **Entry tighten** | Require RSI recover/reject + price vs EMA20/50 alignment before new probe (and before confirm promote). | Cuts weak confirms that later die on BELOW_MA50 (3× −$149.85) and TRANSITION confirm bleed (TSLA −$33.79). | WR **≥40%**; n_trades **≤ R3**; return ≥ R3−1pp; MDD ≤ R3+2pp (≤14.65%) | WR flat/↓ **and** return < R3 **or** shield veto |
| **C** | **Chop filter** | Skip / half-size new risk if ATR% < 20-bar median **or** EMA20–EMA50 gap < 0.4%. | Lifts Sharpe from **0.415** by sitting out flat regimes without adding trade count. | Sharpe **≥0.60**; MDD ≤ R3; return ≥0; n_trades ≤18 | Sharpe < R3 **and** return < R3 **or** shield veto |
| **D** ★ second | **Funding / cost control** | Flatten if **adverse funding** persists **>48h** unless position **≥ +1R**. | Attacks funding **$58.82 ≈ 74% of $79.90 costs**; cost/gross was **53.6%**. Standing: do **not** add trades to claw fees. | cost/gross **≤35%**; return ≥ R3−1pp; MDD ≤18%; n_trades ≤18 | cost/gross still **>50%** **or** return <0 **or** shield veto |

### Metrics to log every run
`return_pct, max_drawdown_pct, sharpe_ratio, num_trades, win_rate_pct, total_costs, total_gross_pnl, cost_pct_of_gross, avg_hold_days, by_exit_reason, by_symbol`  
Tag: `R4-A` / `R4-B` / `R4-C` / `R4-D`. No composed stack until isolated winners reviewed.

### Shared reject / prefer
- **Reject:** DD >20% or >25 trades/yr (shield) · prefer also reject if cost/gross >45% after D.  
- **Prefer keep R3** unless WR ≥40% **and** Sharpe ≥0.6 **and** return ≥ R3 (Trader/Researcher shared bar).  
- **No size-up / no leverage increase** as a Round 4 knob.

---

## Map: older research hyps → official A–D (secondary)

| Older tag | Intent | Maps nearest to | Status |
|-----------|--------|-----------------|--------|
| **S1** / `R4-C-S1` | BE only after closed +1R (min hold H1) | **A** (A uses +1.5R \| bar 8 — stricter delay) | Research hyp; A is the official one-knob |
| **S2** | BE after closed +1.5R | **A** (almost identical threshold) | Fold into A |
| **F1** / `R4-C-F2` | Fewer / larger — max 1 probe/asset/5d; ≤12 RT/yr | *Not in A–D* — cost intent partially overlaps **D**; frequency cap is research-only until Boss adds | Secondary; do not run as primary R4 |
| **C1** / `R4-C-R2` | Stricter confirm (RISK-ON + ADX>25) | **B** (entry/confirm tighten family) | Secondary alias |
| **R1** | No TRANSITION jugular | Brief fidelity / low priority (official R3 had **0 jugular**; TRANSITION bleed was **confirm**) | Note only — not A–D |
| **R4** (chop z) | Chop \|z\|<0.15 ≥3d | **C** | Secondary alias |
| **G1** | GOLD RS bias | **Observation only** — GOLD dig shows book-maker (+$113.47); **not** an isolated R4 knob (curve-fit) | Defer after A–D |
| Trader composed “R4-A Quality first” | S1+R2+R1+R4+F1+F2 stack | **Forbidden until isolated A–D complete** | Wait for Boss |

---

## Suggested execution order

1. **BackTesting: R4-A** (BE delay) — largest measured failure $ (−$183.16 BE bucket).  
2. **R4-D** (funding flatten) — largest cost $ ($58.82 funding).  
3. **R4-B** then **R4-C**.  
4. GOLD RS / composed stacks: **only after** Boss picks a winner from isolated results.

Do **not** retune thresholds on the same 365d window used for R3 reporting without a holdout/walk-forward note.
