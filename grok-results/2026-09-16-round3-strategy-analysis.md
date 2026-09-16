# Grok Ops — Round 3 strategy analysis
**Source of truth:** `bba-results/round3-hl-full-2026-09-16.json` + `strategy-brief.md` + `bba-engine/hl_backtest.py`  
**Generated:** 2026-09-16 (America/Boise)  
**Label:** Official HL Druckenmiller proxy Round 3 — paper/education; not advice to buy.

> Note: An earlier Ops note based on `/workspace/bba-proxy-backtest/results/round3_365d` (−19.65%, 35 trades) was a **different engine**. This file supersedes that for team decisions. Official Round 3 = **+4.33% / 15 trades**.

---

## Headline (official)

| Metric | Value |
|--------|------:|
| Start / final equity | $1,663 → $1,734.99 |
| Total return | **+4.33%** |
| Max DD | **12.65%** |
| Sharpe | **0.41** |
| Trades | **15** |
| Win rate | **33.3%** |
| Avg win / avg loss | $82.85 / −$34.50 (~2.4×) |
| Profit factor | 1.20 |
| Gross PnL / costs / net | $149.13 / **$79.90 (54% of gross)** / $69.24 |
| BTC HODL same window | **−35.26%** (outperform ≈ +39.6 pts) |
| Window | 2025-09-17 → 2026-09-16 |

Regime days in sample: RISK-ON 153 · TRANSITION 83 · RISK-OFF 16.

---

## 1) Last choices — three most common failure causes
(15 closed trades = full Round 3 sample, not 100.)

### 1. Breakeven stops firing too early (5/15, **$−183 net**, **0% WR**)
Largest single failure bucket. Confirm-phase BE stops on TSLA/GOLD/NVDA flipped winners-in-progress (or scratch trades) into full losers. Matches strategy-brief intent (“move mental stop to breakeven” on confirm) but the **engine implementation is too eager** vs giving the trade room after +1R.

### 2. Trend-invalidation exits without a winner path (BELOW_MA50: 3/15, **$−150 net**, 0% WR)
Clean rule-following losses — price lost MA50 after entry. Not “bad luck”; the entry filter (MA/RSI/pullback) still lets trades that fail structure quickly. Combined with BE stops, **loser exits are mechanical and frequent**.

### 3. Cost drag from sparse but expensive round-trips (**$79.90 = 54% of gross**)
With only 15 trades, fees+slip+funding still ate more than half of gross. Funding on multi-week holds + two-sided costs means **edge must be larger per winner** or **fewer mid-quality confirms**. Not fixed by “trade more.”

**What worked:** RSI_OVERBOUGHT exits (3/15) = **$+334 net**, 100% WR — GOLD + NVDA home runs. TIME_STOP GOLD also paid. GOLD is the star book; TSLA is the hole (3 trades, $−132, 0% WR).

---

## 2) Decision logic — biases & repetitive errors

- **Confirm-heavy book:** 11 confirm vs 4 probe. Brief allows probes in TRANSITION; engine still spends most risk in confirm size (3x). When BE stops fire on confirms, damage is outsized.
- **Long-only in this sample:** no short contribution in the 15 — RISK-OFF mostly means flatten/avoid, so bear legs don’t monetize.
- **BE-stop bias:** “preserve capital” implemented as *tight BE* → converts path noise into realized losses (classic premature stop bias).
- **Name concentration:** NVDA 6 + GOLD 5 + TSLA 3 + BTC 1. Fine for Druck-style concentration, but **TSLA confirms repeatedly failed** — no “skip this name” memory.
- **TRANSITION entries still allowed at confirm** (e.g. TSLA TRANSITION confirm → BE stop). Brief says TRANSITION = probe-only / max 1 concurrent — **logic leak vs brief**.
- **Cannot replay:** LLM thesis, news, discretionary charts, 6Q audit — this is the HL quant proxy of the brief, not live BBA.

---

## 3) Vs baseline goals — where it falls short

| Goal | Result |
|------|--------|
| Beat BTC HODL on window | **Pass** (+4.33% vs −35.26%) |
| Keep max DD under ~20% | **Pass** (12.65%) |
| Positive expectancy / PF > 1 | **Pass thin** (PF 1.20) |
| Win rate sustainable | **Short** (33% — OK if winners stay 2.4×, but BE stops kill that) |
| Costs << gross | **Fail** (costs 54% of gross) |
| Sharpe “usable” | **Soft fail** (0.41 — chop + BE noise) |
| Brief fidelity (TRANSITION = probe only) | **Soft fail** (TRANSITION confirm exists) |

**Bottom line:** Official Round 3 *works* as a BTC-relative survival story with fat right-tail GOLD/NVDA exits. It fails as a *clean* process because **BE stops + MA50 cuts produce most of the left tail**, and **costs eat the middle**. Don’t retune five knobs.

---

## Round 4 — single knob (pre-declared)

### Change (one only)
**Delay / soften BREAKEVEN_STOP:** require price to hold ≥ +1R for N bars (propose **N=3 daily bars**) *or* trail BE only after RSI still ≥ entry RSI, before arming BE. Do **not** change MA50 exit, RSI target, size, or universe in Round 4.

### Falsifier (declare before run)
Round 4 **fails** if any of:
1. Max DD **> 20%**, or
2. Net return **≤ Round 3 (+4.33%)** *and* BE-stop count still ≥ 4 with mean BE loss still worse than −$30, or
3. Costs still **≥ 50% of gross** *and* trade count does not drop (i.e. we didn’t actually reduce noise exits).

### Success (any one is enough to keep the knob)
- BE-stop losses shrink by ≥ 40% in dollar sum vs Round 3’s $−183, **and**
- Net return ≥ Round 3, **and** max DD ≤ 15%.

### Explicitly not tuning yet
Win-rate targeting, “trade less” via higher RSI gates, bigger size to dilute costs, MA50 removal — park until Round 4 falsifier resolves.

---

## Files read
- `bba-engine/hl_backtest.py`
- `bba-results/round3-hl-full-2026-09-16.json`
- `strategy-brief.md`
- (contrast only) local proxy `bba-proxy-backtest` — discarded for decisions

## Next ask for team
Run Round 4 with the BE-delay knob only; drop JSON into `bba-results/` and ping Ops to write `grok-results/2026-09-XX-round4-*.md`.
