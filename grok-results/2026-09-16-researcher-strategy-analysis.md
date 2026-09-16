# Grok Researcher — Round 3 Strategy Analysis
**Source:** `bba-results/round3-hl-full-2026-09-16.json` + `strategy-brief.md` + `bba-engine/hl_backtest.py`  
**Author:** Researcher  
**Date (Boise):** 2026-09-16 ~12:45 PM  
**Repo:** github.com/Simzy420/bba-backtest-lab (cloned OK)

> Official sample has **15 closed trades**, not 100. Analysis below uses **all 15 official fills**. Do not invent fills. Local `bba-proxy-backtest` (35 trades / −19.65%) is a different engine — labeled **NOT live-agent alpha** and not used for failure ranking here.

---

## Headline (official Round 3)

| Metric | Value |
|--------|------:|
| Return | **+4.33%** ($1,663 → $1,734.99) |
| Max DD | **12.65%** |
| Sharpe | **0.415** |
| Trades / WR | **15** / **33.3%** |
| Avg win / avg loss | **$82.85** / **−$34.50** (~**2.4×**) |
| Gross / costs / net | $149.13 / **$79.90 (54%)** / $69.24 |
| BTC HODL | **−35.26%** (outperform ~+39.6 pts) |
| Window | 2025-09-17 → 2026-09-16 |

Symbol net: **GOLD +$113.47** · **NVDA +$88.49** · BTC −$0.58 · **TSLA −$132.14**.  
Phase mix: **11 confirm / 4 probe / 0 jugular** — pyramid never reached jugular in this run.

---

## 1) Last choices — three most common causes of failure

*(Universe = all 15 official closed trades.)*

### 1. Premature BREAKEVEN_STOP (5/15 losers, **$−183.16** net, **0% WR**)
Every BE exit was a loser. Confirm phase sets `stop_price = avg_entry` as soon as probe gains ≥3% (`hl_backtest.py`). Noise then stops the trade at BE (plus fees/funding → net loss). Holds of 10–17 days still scratched. This is the single largest failure bucket and matches BBA’s known leak.

### 2. Structure failure after confirm — BELOW_MA50 (3/15, **$−149.85**, **0% WR**)
TSLA / NVDA confirms that lost the 50-day. Entries passed MA/RSI/pullback filters but thesis died. Combined with BE stops, **all left-tail exits are mechanical** (BE or MA50) — no discretionary cut.

### 3. Cost drag on mid-quality round-trips (**$79.90 = 54% of gross**)
Breakdown: fees $10.54 + slip $10.54 + **funding $58.82**. Funding dominates. Standing rule: **do not add trades to claw fees**; fix by fewer scratches / better holds (Round 4 A + D), not size-up.

**What worked:** RSI_OVERBOUGHT exits (3) = **+$333.67**, 100% WR (GOLD+NVDA). TIME_STOP GOLD also paid. Asymmetry is real when winners are allowed to run.

---

## 2) Decision logic — biases & repetitive errors

| Bias / error | Evidence in official fills | Fix path |
|--------------|----------------------------|----------|
| **Stop impatience** | 5× BREAKEVEN_STOP, all red | Round 4 **A**: no BE until +1.5R **or** bar 8 |
| **Confirm-heavy risk** | 11/15 confirm, 0 jugular; BE damage at 3x size | Stricter confirm / delay BE before size sticks |
| **Brief leak: TRANSITION confirm** | TSLA 2025-12-17 confirm in TRANSITION → BE stop −$33.79 | Brief says TRANSITION = **probe only** — enforce |
| **Name memory gap** | TSLA 3 trades, **$−132**, 0% WR; no skip rule | Don’t overfit bans; track serial losers in journal |
| **Funding blindness** | Funding 74% of total costs | Round 4 **D**: flatten adverse funding after 48h unless ≥+1R |
| **Chop / low Sharpe** | Sharpe 0.41 despite beating BTC | Round 4 **C**: ATR%/EMA-gap chop filter |
| **Promotion never reaches jugular** | 0 jugular stages in R3 | Edge came from confirm home runs — don’t force jugular |

Standing (coach): paper only; no leverage/size-up; **15 trades/year is the feature**; payoff asymmetry > win-rate chasing.

---

## 3) Performance vs baseline goals — where we fall short

| Goal | Target | Official R3 | Verdict |
|------|--------|------------:|---------|
| Max DD | <20% | **12.65%** | **Met** (~7pp headroom) |
| Return | >0 | **+4.33%** | **Met** (thin) |
| Beat BTC HODL | Outperform | **+39.6 pts** | **Met** |
| Cost / gross | <<50% | **54%** | **Short** |
| Win rate | Raise without volume | **33%** | **Short** (OK if 2.4× holds) |
| Sharpe | Usable | **0.41** | **Short** (chop + BE noise) |
| Brief fidelity | TRANSITION probe-only | TRANSITION confirm exists | **Short** |
| Pyramid complete | Probe→confirm→jugular | **0 jugular** | **Short / unexpected** |

**Pinpoint:** Process fails on **early BE + MA50 left tail + funding drag**; strategy succeeds as **BTC-relative survival** with fat GOLD/NVDA right tail. Round 4 should **not** re-ask “can DD stay under 20%?” — already yes. Optimize the leak.

---

## Round 4 recommendation (align with package A–D)

One knob only. Boss picks **one**. Shield veto: DD >20% or >25 trades/year. No blending. No size-up.

| ID | Knob | Why (from this analysis) |
|----|------|--------------------------|
| **A** | BE delay — no BE until **+1.5R or bar 8** | Directly attacks $−183 BE bucket |
| **B** | Entry tighten — RSI recover/reject + EMA20/50 | Fewer MA50 failures / bad confirms |
| **C** | Chop filter — ATR% <20-bar median or EMA gap <0.4% | Lift Sharpe from 0.41 |
| **D** | Cost control — flatten adverse funding after 48h unless ≥+1R | Attacks $58.82 funding (74% of costs) |

**Researcher pick if forced:** start with **A** (largest measured failure $), then **D** (largest cost $). Keep GOLD overweight as *observation*, not a Round 4 knob (avoid GOLD-only curve-fit).

---

## Answers to BBA team Qs (clone status)

1. **Can we clone?** Yes — `github.com/Simzy420/bba-backtest-lab` clones fine from Grok Bot (`gh` auth as Simzy420). Files read: `hl_backtest.py`, `round3-hl-full-2026-09-16.json`, `strategy-brief.md`, `backtest_engine.py`.
2. Results pushed to `grok-results/` (this file + JSON twin).
3. Proxy engine remains separate under `/workspace/bba-proxy-backtest` — do not mix metrics.

## Files read
- `bba-engine/hl_backtest.py`
- `bba-engine/backtest_engine.py`
- `bba-results/round3-hl-full-2026-09-16.json`
- `strategy-brief.md`
- `packages` brief / coach lessons (via bba-strategy-logs)
