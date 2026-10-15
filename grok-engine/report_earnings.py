import json, sys
es = json.load(open(sys.argv[1])); sb = json.load(open("../grok-results/2026-10-15-50tpy.json"))["results"]
f = lambda x: "n/a" if x is None else x
def row(name, m, ho=None):
    nud = m.get("robust_ret_pct") or {}
    nd = f"{nud.get('x0.9','-')}% / {nud.get('x1.1','-')}%" if nud else "-"
    h = f"{ho['return_pct']:+.1f}% (DD {ho['max_dd_pct']:.1f}%)" if ho else "-"
    tpy = m["trades_per_yr"]
    return f"| {name} | {m['return_pct']:+.1f}% | {m['cagr_pct']:.1f}% | {m['max_dd_pct']:.1f}% | {m['sharpe']:.2f} | {tpy} | {'OK' if tpy<=25 else 'over'} / {'OK' if tpy<=50 else 'over'} | {f(m.get('cost_pct_of_gross'))}% | {m.get('losing_windows','-')} | {nd} | {h} | {'PASS' if m['max_dd_pct']<=20 else 'FAIL'} |"
L = ["| Strategy | Return | CAGR | Max DD | Sharpe | Trades/yr | 25/yr / 50/yr cap | Cost/gross | Losing windows | Nudge -10% / +10% | Holdout (last 6 mo) | DD shield |", "|" + "---|" * 12]
names = {"eps_beat": "**NEW** Earnings beat + swing low (10 slots, all beats)", "eps_beat_capped": "**NEW** Earnings beat + swing low, throttled (4 slots, surprise >=10%)",
         "eps_beat_subset100": "**NEW** EPS beat, throttled, guidance-subset stocks only", "guidance_raise": "**NEW** EPS beat + RAISED guidance (EDGAR), throttled"}
for k, nm in names.items():
    if k in es: L.append(row(nm, es[k]["metrics"], es[k]["holdout"]))
for k, v in sb.items():
    if k != "Donchian trend": L.append(row(k + " (50/yr run)", v["metrics"]))
L.append(row("SPY buy-and-hold", {**es["spy"], "losing_windows": "-"}))
print("\n".join(L))
if "guidance_raise" in es: print("\nCoverage:", es["guidance_raise"]["coverage"])
