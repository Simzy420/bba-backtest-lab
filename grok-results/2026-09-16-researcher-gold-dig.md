# Researcher — Official Round 3 GOLD dig
**Source (authoritative):** `bba-results/round3-hl-full-2026-09-16.json`  
**Engine cites:** `bba-engine/hl_backtest.py` (BE stop / confirm / jugular)  
**Author:** Researcher (Grok)  
**Date (Boise / MT):** 2026-09-16 ~12:50 PM  
**Standing:** paper only · no leverage/size-up · 15 trades/year is a feature · do not invent fills

> Official sample = **15 closed trades**. All tables below are from the official JSON only.  
> Proxy (`/workspace/bba-proxy-backtest`) appears **only** in a labeled contrast block — **NOT live-agent alpha**.

---

## Headline (official R3 book)

| Metric | Value |
|--------|------:|
| Return | **+4.33%** ($1,663 → $1,734.99) |
| Max DD | **12.65%** |
| Sharpe | **0.415** |
| Trades / WR | **15** / **33.33%** |
| Gross / costs / net | $149.13 / **$79.90 (53.6% of gross)** / **$69.24** |
| Avg hold | 15.8 d |
| Best / worst | +$139.39 / −$57.65 |
| Phases | **11 confirm / 4 probe / 0 jugular** |
| Window | 2025-09-17 → 2026-09-16 |

Symbol net (official): **GOLD +$113.47** · NVDA +$88.49 · BTC −$0.58 · **TSLA −$132.14**.

---

## Exact GOLD trade table (official fills)

| # | Entry | Exit | Phase | Regime @ entry | Hold | Entry px | Exit px | Notional | Gross | Fees | Slip | Funding | Costs | Net | Ret% | Exit reason |
|---|-------|------|-------|----------------|-----:|---------:|---------:|---------:|------:|-----:|-----:|---------:|------:|----:|-----:|-------------|
| 3 | 2025-12-29 | 2026-01-21 | confirm | RISK-ON | 23 | 4454.3523 | 4837.5 | 904.75 | +77.82 | 0.81 | 0.81 | 6.24 | 7.86 | **+69.95** | +20.40 | RSI_OVERBOUGHT |
| 4 | 2026-02-03 | 2026-02-17 | confirm | RISK-ON | 14 | 5044.4504 | 4905.8999 | 765.49 | −21.02 | 0.69 | 0.69 | 3.22 | 4.60 | **−25.62** | −8.62 | BREAKEVEN_STOP |
| 5 | 2026-01-30 | 2026-03-02 | confirm | RISK-ON | 31 | 4872.2232 | 5311.6001 | 1000.64 | +90.24 | 0.90 | 0.90 | 9.31 | 11.11 | **+79.13** | +20.36 | TIME_STOP |
| 6 | 2026-03-03 | 2026-03-06 | probe | TRANSITION | 3 | 5123.7002 | 5158.7002 | 341.49 | +2.33 | 0.31 | 0.31 | 0.31 | 0.93 | **+1.41** | +0.83 | RISK_OFF |
| 14 | 2026-08-28 | 2026-09-16 | probe | RISK-ON | 19 | 4529.8999 | 4384.2002 | 287.45 | −9.25 | 0.26 | 0.26 | 1.64 | 2.16 | **−11.40** | −7.93 | BACKTEST_END |

*(Row # = order index in official `trades[]`, 1-based.)*

### GOLD contribution vs book

| Slice | Trades | Wins | Net PnL | Gross | Costs | Avg hold |
|-------|-------:|-----:|--------:|------:|------:|---------:|
| **GOLD** | **5** | **3** | **+$113.47** | +$140.12 | $26.66 | **18.0 d** |
| Non-GOLD | 10 | 2 | **−$44.23** | +$9.01 | $53.24 | — |
| **Full book** | 15 | 5 | **+$69.24** | +$149.13 | $79.90 | 15.8 d |

- GOLD = **163.9% of book net** (book without GOLD would be **−$44.23**).
- GOLD share of *winning* net PnL: **+$150.49 / $414.23 ≈ 36.3%** (two big GOLD winners + one small; NVDA also carried winners).
- GOLD WR **60%** (3/5) vs book **33.3%**.
- Regimes @ GOLD entry: **4× RISK-ON**, **1× TRANSITION** (small winner, RISK_OFF exit).
- Phases: **3 confirm / 2 probe / 0 jugular** (matches book-wide **0 jugular**).

### GOLD exit-reason breakdown

| Exit reason | n | Net sum | Notes |
|-------------|--:|--------:|-------|
| RSI_OVERBOUGHT | 1 | +$69.95 | Home-run confirm |
| TIME_STOP (30d) | 1 | +$79.13 | Largest GOLD winner; held through confirm |
| RISK_OFF | 1 | +$1.41 | TRANSITION probe flattened cleanly |
| BREAKEVEN_STOP | 1 | −$25.62 | Same BE leak as book (confirm set stop @ avg entry) |
| BACKTEST_END | 1 | −$11.40 | Open probe at window end — not a live signal fail |

---

## All 15 official trades (for context)

| # | Symbol | Phase | Entry | Exit | Hold | Regime | Exit reason | Gross | Costs | Net |
|---|--------|-------|-------|------|-----:|--------|-------------|------:|------:|----:|
| 1 | TSLA | confirm | 2025-12-17 | 2025-12-29 | 12 | TRANSITION | BREAKEVEN_STOP | −29.63 | 4.15 | −33.79 |
| 2 | TSLA | confirm | 2025-12-09 | 2026-01-02 | 24 | RISK-ON | BELOW_MA50 | −36.16 | 9.06 | −45.22 |
| 3 | GOLD | confirm | 2025-12-29 | 2026-01-21 | 23 | RISK-ON | RSI_OVERBOUGHT | +77.82 | 7.86 | +69.95 |
| 4 | GOLD | confirm | 2026-02-03 | 2026-02-17 | 14 | RISK-ON | BREAKEVEN_STOP | −21.02 | 4.60 | −25.62 |
| 5 | GOLD | confirm | 2026-01-30 | 2026-03-02 | 31 | RISK-ON | TIME_STOP | +90.24 | 11.11 | +79.13 |
| 6 | GOLD | probe | 2026-03-03 | 2026-03-06 | 3 | TRANSITION | RISK_OFF | +2.33 | 0.93 | +1.41 |
| 7 | NVDA | confirm | 2026-04-30 | 2026-05-14 | 14 | RISK-ON | RSI_OVERBOUGHT | +145.17 | 5.79 | +139.39 |
| 8 | NVDA | confirm | 2026-05-04 | 2026-05-14 | 10 | RISK-ON | RSI_OVERBOUGHT | +128.37 | 4.01 | +124.35 |
| 9 | TSLA | confirm | 2026-05-15 | 2026-06-01 | 17 | RISK-ON | BREAKEVEN_STOP | −45.72 | 7.42 | −53.13 |
| 10 | NVDA | probe | 2026-05-15 | 2026-06-10 | 26 | RISK-ON | BELOW_MA50 | −43.19 | 3.80 | −46.98 |
| 11 | NVDA | confirm | 2026-08-10 | 2026-08-20 | 10 | RISK-ON | BREAKEVEN_STOP | −25.92 | 5.44 | −31.36 |
| 12 | NVDA | confirm | 2026-08-18 | 2026-08-28 | 10 | RISK-ON | BREAKEVEN_STOP | −34.58 | 4.68 | −39.26 |
| 13 | NVDA | confirm | 2026-08-21 | 2026-09-14 | 24 | RISK-ON | BELOW_MA50 | −49.33 | 8.31 | −57.65 |
| 14 | GOLD | probe | 2026-08-28 | 2026-09-16 | 19 | RISK-ON | BACKTEST_END | −9.25 | 2.16 | −11.40 |
| 15 | BTC | probe | 2026-09-16 | 2026-09-16 | 0 | TRANSITION | BACKTEST_END | 0.00 | 0.58 | −0.58 |

Book exit-reason net: **BREAKEVEN_STOP 5× = −$183.16 (0% WR)** — includes 1 GOLD scratch.

---

## Engine mechanics (cite — no retune)

From `bba-engine/hl_backtest.py`:

1. **Confirm add** (~L498–513): probe → confirm when gain ≥ **3%**, RSI in **55–70**, close > MA20. Adds `CONFIRM_ADD_PCT` capital @ `START_LEVERAGE_CONFIRM` (3×). Sets **`pos.stop_price = avg_entry`** (breakeven).
2. **Jugular add** (~L514–529): confirm → jugular when gain ≥ **8%**, RSI **60–72**, MA50 slope up. Caps at `MAX_POSITION_PCT` (50%). Trails stop to **`avg_entry * 1.02`**. **Zero jugular fills in official R3.**
3. **Breakeven stop exit** (~L454–457): after confirm, if `pos.stop_price` set and **close < stop_price** → `BREAKEVEN_STOP`. Priority after BELOW_MA50 / RSI_OVERBOUGHT / TIME_STOP.
4. Exit priority order: BELOW_MA50 → RSI>75 → TIME_STOP (30d) → BREAKEVEN_STOP.

Implication for GOLD: winners exited via **RSI_OVERBOUGHT** and **TIME_STOP** (runners allowed); the one BE scratch matches the book-wide premature-BE leak. Do **not** add a GOLD-only knob in Round 4 (overfit risk) — keep GOLD overweight as *observation*.

---

## Contrast only — BBA risk+regime proxy (NOT live-agent alpha)

| | Official R3 (HL) | Proxy R3 365d |
|--|------------------:|---------------:|
| Return | **+4.33%** | −19.65% |
| Max DD | **12.65%** | −21.18% |
| Trades / WR | **15 / 33%** | 35 / 14% |
| GOLD | **5 trades, +$113.47 net, book-maker** | 8 trades, sole net+ name (~+0.04 cash units); winners were **jugular targets** (engine differs) |
| Jugular | **0** in official | Proxy reached jugular on GOLD winners |

Proxy uses different stage/sizing/exit rules (`PROXY_V1_RULES.md`). Do **not** mix into failure ranking or Round 4 success criteria.

---

## Researcher takeaways (official only)

1. GOLD **made the book** — without it R3 nets negative; with it +4.33% and MDD 12.65% (under 20% shield).
2. GOLD edge = **confirm runners** (RSI / TIME), not jugular (never fired) and not TRANSITION size-up.
3. GOLD still ate one **BREAKEVEN_STOP (−$25.62)** — same A-knob leak as TSLA/NVDA BE bucket (−$183.16 book).
4. Round 4: prefer **A (BE delay)** then **D (funding)**; do not GOLD-curve-fit as a primary knob.
