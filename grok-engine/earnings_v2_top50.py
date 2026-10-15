#!/usr/bin/env python3
"""v2 (2026-10-15): earnings beat + swing low on the 50 most-traded S&P 500 names (2025 median dollar volume
among the 71 cached guidance names -> HINDSIGHT BIAS). Single new change tested: market filter = no new entries
when SPY close < SPY 200-day MA. Each version run with and without it. Reuses /workspace/.earn_cache."""
import os, sys, json, pickle, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import walkforward as W, earnings_data as ED, earnings_swinglow as E

def top50():
    gd = pickle.load(open("/workspace/.earn_cache/guid.pkl", "rb")); px = ED.prices()
    names = [t for t in gd if gd[t] is not None and len(gd[t]) and t in px.columns.get_level_values(0)]
    dv = {t: float((px[t]["Close"] * px[t]["Volume"]).loc["2025"].median()) for t in names}
    return sorted(names, key=lambda t: -dv[t])[:50]

def restrict(D, keep, spy_filter):
    j = [D["tk"].index(t) for t in keep if t in D["tk"]]
    D2 = {k: (v[:, j] if isinstance(v, np.ndarray) and v.ndim == 2 else v) for k, v in D.items()}
    D2["tk"] = [D["tk"][i] for i in j]
    if spy_filter:
        s = ED.prices()["SPY"]["Close"]; s.index = s.index.tz_localize(None) if s.index.tz else s.index
        ok = (s > s.rolling(200, min_periods=200).mean()).reindex(D["idx"]).fillna(False).values
        D2["swing"] = D2["swing"] & ok[:, None]   # signal day gate -> no new entries next open
    return D2

if __name__ == "__main__":
    T = top50(); print(len(T), T, flush=True)
    ev, cov = E.guidance_events(); ev = {t: ev[t] for t in T if t in ev}
    eps = ED.earnings()
    beat = {t: (lambda e: e[e["Reported EPS"] > e["EPS Estimate"]])(eps[t].dropna(subset=["Reported EPS", "EPS Estimate"])) for t in T if eps.get(t) is not None}
    DB, DG = E.load(beat), E.load(ev); last = pd.Timestamp(DB["idx"].max())
    out = {"universe": T, "last": str(last.date()), "tpy_cap_used_in_pick": W.TPY_CAP, "spy": E.spy(last),
           "beat_raised_events": int(sum(len(v) for v in ev.values()))}
    for name, D, G in (("eps_beat", DB, E.GRID), ("eps_beat_raised", DG, E.GRID_CAPPED)):
        for f in (False, True):
            k = name + ("_spyfilter" if f else ""); print("==", k, flush=True)
            out[k] = E.evaluate(restrict(D, T, f), last, G)
    json.dump(out, open(sys.argv[1], "w"), indent=1, default=str)
