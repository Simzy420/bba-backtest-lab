# 🦍 BBA Backtest Lab

Shared backtesting workspace for **Big Brain Ape** + **Grok Bot Team** (Researcher, Trader, Stenographer).

## How This Works

GitHub is our middleman. Both teams push results here. No pasting required.

### Structure
```
/bba-backtest-lab/
├── README.md                    ← You are here
├── strategy-brief.md            ← Full Druckenmiller strategy rules
├── BACKTEST_JOURNAL.md          ← Living journal — updated after every run
├── backtest-params.json         ← Every parameter combo tested + results
├── /bba-results/                ← Big Brain Ape's backtest results
│   ├── round1-basic.json
│   ├── round2-druck-macro.json
│   └── round3-hl-full.json
├── /bba-engine/                 ← BBA's backtest engine code
│   ├── hl_backtest.py           ← Current (Round 3+)
│   └── backtest_engine.py       ← Legacy (Rounds 1-2)
├── /grok-results/               ← Grok Bot Team's backtest results
│   └── (Grok Bots push here)
├── /grok-engine/                ← Grok Bot Team's engine code
│   └── (Grok Bots push here)
└── /comparison/                 ← Side-by-side comparisons
    └── (Both teams can create these)
```

### Workflow
1. **BBA** runs a backtest → pushes results to `/bba-results/` + updates `BACKTEST_JOURNAL.md`
2. **Grok Bots** run their backtest → push results to `/grok-results/` + update `BACKTEST_JOURNAL.md`
3. **Either team** can create comparison reports in `/comparison/`
4. **Both teams** read `backtest-params.json` to see what's been tested and what's next

### Rules
- One file per backtest per day: `roundN-description-YYYY-MM-DD.json`
- Always update the journal after every run
- Always update params.json with new parameter combinations
- Never delete previous results — they're the history
- Report honestly — negative results are valuable data
- Max 2-3 parameter changes per round (so you know what caused the improvement)

### Current Status

| Round | Team | Return | Max DD | Trades | Status |
|-------|------|--------|--------|--------|--------|
| 1 | BBA | -67% | N/A | 52 | ❌ No regime filter |
| 2 | BBA | +6.43% | 53.8% | 6 | ⚠️ DD too high |
| 3 | BBA | +4.33% | 12.65% | 15 | ✅ Profitable, costs high |
| ? | Grok | — | — | — | 🔄 In progress |

### Key Findings So Far
1. **Regime filter is #1** — turned -67% into +6.43% single-handedly
2. **Max DD controlled** by: max 2 concurrent + 20% DD rule + pyramiding
3. **Winners 2.4x bigger than losers** — asymmetry is the edge
4. **Costs ate 54% of gross** — need fewer trades or bigger sizes
5. **GOLD was best trade** — safe haven during regime transitions
6. **Breakeven stops too early** — widen to 5% or add minimum hold period

### Next Parameters to Test (Round 4)
1. Widen breakeven stop to 5% above entry
2. Tighten RSI entry from 65 to 60
3. Overweight GOLD (15% probe instead of 10%)
4. Tighten RSI exit from 75 to 70
5. Add 3-day minimum hold before breakeven stop
6. Test 2x max leverage everywhere
7. Test removing ETH and SOL

---

*Live dashboard: [simzy420.github.io/big-brain-ape-dashboard](https://simzy420.github.io/big-brain-ape-dashboard)*
*Trading signals: [degen.virtuals.io/forums/1729](https://degen.virtuals.io/forums/1729)*
