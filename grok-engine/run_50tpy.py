#!/usr/bin/env python3
"""2026-10-15: walk-forward scoreboard re-run with trade cap 50/yr (vs 25). ONLY change: TPY_CAP.
Same 2y train / 6mo test / 6mo step, fees, funding, 1x, paper-only, Shield DD<=20%."""
import os, sys, json
os.environ["TPY_CAP"] = "50"
import pandas as pd, walkforward as W, breakout_sizing as B
assert W.TPY_CAP == 50
res, Wn = W.main()
for k, v in res.items():
    v["metrics"]["losing_windows"] = f"{sum(x['oos_ret_pct'] < 0 for x in v['windows'])}/{len(v['windows'])}"
res["Breakout >200MA (ATR-scaled)"] = B.evaluate("atr", Wn)
json.dump({"tpy_cap": 50, "windows": [[str(a.date()), str(b.date()), str(c.date())] for a, b, c in Wn], "results": res},
          open(sys.argv[1], "w"), indent=1, default=str)
for k, v in res.items(): print(k, v["metrics"])
