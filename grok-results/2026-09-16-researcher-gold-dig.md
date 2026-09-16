# Researcher — Official R3 GOLD dig
**Source:** `bba-results/round3-hl-full-2026-09-16.json` (15 official fills — no invented fills)  
**Author:** Researcher · **Boise:** 2026-09-16 ~1:00 PM  
**Repo:** github.com/Simzy420/bba-backtest-lab  

## Headline
- Book: **+4.33%** · MDD **12.65%** · 15 trades · WR 33.3% · costs **$79.90 (54% gross)** · Sharpe 0.415
- Symbol net: GOLD **$+113.47** · NVDA **$+88.49** · TSLA **$-132.14** · BTC **$-0.58**
- GOLD = **164% of book net** ($113.47 / $69.24) — largest symbol contributor
- Note: single best trade in JSON is NVDA +$139.39 (RSI_OVERBOUGHT); GOLD best single is +$79.13. BBA “star” = **sleeve**, not one print.
- Phase mix whole book: **11 confirm / 4 probe / 0 jugular** — pyramid never reached jugular in R3

## Official GOLD trades (n=5)

| Entry | Exit | Phase | Regime@entry | Exit reason | Hold | Lev | Gross $ | Funding $ | Net $ | Ret% |
|-------|------|-------|--------------|-------------|-----:|----:|--------:|---------:|------:|-----:|
| 2025-12-29 | 2026-01-21 | confirm | RISK-ON | RSI_OVERBOUGHT | 23 | 3x | 77.82 | 6.24 | 69.95 | 20.40% |
| 2026-02-03 | 2026-02-17 | confirm | RISK-ON | BREAKEVEN_STOP | 14 | 3x | -21.02 | 3.22 | -25.62 | -8.62% |
| 2026-01-30 | 2026-03-02 | confirm | RISK-ON | TIME_STOP | 31 | 3x | 90.24 | 9.31 | 79.13 | 20.36% |
| 2026-03-03 | 2026-03-06 | probe | TRANSITION | RISK_OFF | 3 | 2x | 2.33 | 0.31 | 1.41 | 0.83% |
| 2026-08-28 | 2026-09-16 | probe | RISK-ON | BACKTEST_END | 19 | 2x | -9.25 | 1.64 | -11.40 | -7.93% |

### What made GOLD work
1. **Two RISK-ON confirms that were allowed to run** — RSI_OVERBOUGHT (+$69.95, 23d) and TIME_STOP (+$79.13, 31d). Right-tail exits, not scratches.
2. **Regime:** 4/5 entries RISK-ON; 1 TRANSITION probe exited RISK_OFF flat-ish (+$1.41). Supports metals as **RISK-ON RS / macro hedge**, not RISK-OFF-only.
3. **Sizing:** winners were **confirm @ 3x**, not probes. Probe losers (BACKTEST_END −$11.40) and BE scratch (−$25.62) show the same book-wide leak on GOLD sleeve.
4. **Costs on GOLD:** fees+slip ~$5.94 + funding **$20.72** — funding still bites on long holds, but winners cleared it.

### What did NOT work on GOLD
- BREAKEVEN_STOP confirm (2026-02-03 → 02-17): **−$25.62** — same early-BE leak as book (5 BE exits, $−183.16, 0% WR).
- Late RISK-ON probe left open at BACKTEST_END: **−$11.40**.

### Contrast vs local proxy (NOT live-agent alpha)
Proxy R3 GOLD was only net+ sleeve via **jugular** targets while BTC sold. Official R3 had **0 jugulars**; GOLD edge = **confirm home runs + time/RSI exits**. Do not import proxy jugular narrative as official truth.

### Round 4 implications for GOLD sleeve
- **A (BE delay)** should cut the −$25.62 GOLD BE scratch (and book’s −$183 BE bucket).
- **D (funding flatten)** matters on 23–31d GOLD holds (funding $6–9/trade).
- Keep GOLD RS bias as parallel research — **do not** GOLD-only curve-fit; NVDA also printed the largest single winner.
- Enforce brief: TRANSITION = probe only (book had a TRANSITION **confirm** on TSLA — fidelity gap).
