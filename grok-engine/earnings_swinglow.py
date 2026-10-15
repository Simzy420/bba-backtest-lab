#!/usr/bin/env python3
"""Earnings beat + swing low (2026-10-15). PAPER ONLY, 1x, long-only, equal-weight, max K concurrent.
Universe: S&P 500 CURRENT members (survivorship bias). Signal: reported EPS > consensus EPS estimate
(yfinance get_earnings_dates) as stand-in for 'beat guidance'. Uptrend: close>MA200 and MA50>MA200.
Entry: within N trading days after the beat, a swing low = (low touched MA20 in last 3 bars OR 3-bar pivot low
at t-1) then close back up (close>prior close) -> buy next open. Exits: stop below swing low (intraday),
trailing stop on closes (exit next open), time stop. Cost: 9 bps per side (same SIDE_COST), no funding."""
import os, sys, json, math, pickle, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import walkforward as W, earnings_data as ED
K = 10; STOP_BUF = 0.01
GRID = [{"N": n, "trail": tr, "tstop": ts} for n in (20, 40, 60) for tr in (0.08, 0.12) for ts in (20, 40)]

def load(events_override=None):
    px = ED.prices(); eps = ED.earnings(); tk = [t for t in ED.members().yf if t in px.columns.get_level_values(0)]
    F = {f: pd.DataFrame({t: px[t][f] for t in tk}) for f in ("Open", "High", "Low", "Close")}
    idx = F["Close"].index.tz_localize(None) if F["Close"].index.tz is not None else F["Close"].index
    for f in F: F[f].index = idx
    c = F["Close"]; ma20, ma50, ma200 = (c.rolling(n, min_periods=n).mean() for n in (20, 50, 200))
    beat = pd.DataFrame(np.nan, index=idx, columns=tk)   # surprise% on signal day
    for j, t in enumerate(tk):
        e = events_override.get(t) if events_override is not None else eps.get(t)
        if e is None or len(e) == 0: continue
        e = e.dropna(subset=["Reported EPS", "EPS Estimate"]) if events_override is None else e
        for ts, r in e.iterrows():
            if events_override is None and not (r["Reported EPS"] > r["EPS Estimate"]): continue
            ts = pd.Timestamp(ts); d = ts.tz_localize(None).normalize() if ts.tzinfo else ts.normalize()
            # pre-market release -> tradable that day's close; after-hours -> next session
            k = idx.searchsorted(d) if (ts.hour < 12 and ts.tzinfo) else idx.searchsorted(d + pd.Timedelta(days=1))
            if k < len(idx): beat.iat[k, j] = float(r.get("Surprise(%)", 1) or 1)
    up = (c > ma200) & (ma50 > ma200)
    lo = F["Low"]
    touch = (lo <= ma20).shift(1).rolling(3).max().astype(bool)
    pivot = (lo.shift(1) < lo.shift(2)) & (lo.shift(1) < lo)
    swing = (touch | pivot) & (c > c.shift(1)) & up
    swlow = lo.rolling(3).min()
    return dict(idx=idx, tk=tk, O=F["Open"].values, H=F["High"].values, L=lo.values, C=c.values,
                beat=beat.values, swing=swing.values, swlow=swlow.values)

def run(D, p, start, end):
    idx = D["idx"]; i0, i1 = idx.searchsorted(pd.Timestamp(start)), idx.searchsorted(pd.Timestamp(end), "right")
    O, H, L, C, B, S, SL = D["O"], D["H"], D["L"], D["C"], D["beat"], D["swing"], D["swlow"]
    N = int(p["N"]); n_s = C.shape[1]; K = int(p.get("K", 10)); ms = p.get("min_sur", 0)
    # active beat window: last beat index within N bars (lookback can precede start)
    last_beat = np.full(n_s, -10**9); last_sur = np.zeros(n_s); used = np.zeros(n_s, bool)
    for i in range(max(0, i0 - N), i0):
        m = ~np.isnan(B[i]); last_beat[m] = i; last_sur[m] = B[i][m]; used[m] = False
    eq = 1.0; cash = 1.0; pos = {}; pend = []; rets = []; n = 0; gross = 0.0; cost = 0.0; prev = 1.0
    for i in range(i0, i1):
        # entries at open from yesterday's signals
        for j, stop in pend:
            if len(pos) >= K or j in pos or np.isnan(O[i, j]): continue
            alloc = min(cash, prev / K)
            if alloc <= 0: break
            sh = alloc * (1 - W.SIDE_COST) / O[i, j]; cash -= alloc; cost += alloc * W.SIDE_COST
            pos[j] = dict(sh=sh, px=O[i, j], stop=stop, hi=O[i, j], age=0, exit_open=False); n += 1
        pend = []
        for j in list(pos):
            q = pos[j]; xp = None
            if np.isnan(C[i, j]): continue
            if q["exit_open"]: xp = O[i, j]
            elif L[i, j] <= q["stop"]: xp = min(O[i, j], q["stop"])
            else:
                q["age"] += 1; q["hi"] = max(q["hi"], C[i, j])
                if q["age"] >= p["tstop"]: xp = C[i, j]
                elif C[i, j] < q["hi"] * (1 - p["trail"]): q["exit_open"] = True
            if xp is not None:
                v = q["sh"] * xp; cash += v * (1 - W.SIDE_COST); cost += v * W.SIDE_COST
                gross += q["sh"] * (xp - q["px"]); del pos[j]
        m = ~np.isnan(B[i]); last_beat[m] = i; last_sur[m] = B[i][m]; used[m] = False
        act = (i - last_beat <= N) & (i - last_beat >= 1) & ~used & S[i]
        cands = [j for j in np.where(act)[0] if j not in pos and last_sur[j] >= ms]
        cands.sort(key=lambda j: -last_sur[j])
        for j in cands[:K]:
            pend.append((j, SL[i, j] * (1 - STOP_BUF))); used[j] = True
        eq = cash + sum(q["sh"] * (C[i, j] if not np.isnan(C[i, j]) else q["px"]) for j, q in pos.items())
        rets.append(eq / prev - 1); prev = eq
    for j, q in pos.items(): gross += q["sh"] * (C[i1 - 1, j] - q["px"])
    return {"ret": pd.Series(rets, index=idx[i0:i1]), "n": n, "gross": gross, "cost": cost}

def scale(p, f):
    return {**p, "N": max(2, int(round(p["N"] * f))), "trail": round(p["trail"] * f, 4), "tstop": max(2, int(round(p["tstop"] * f)))}

def pick(D, a, b, GRID):
    best, bs = None, -1e9
    for p in GRID:
        r = run(D, p, a, b); mt = W.metrics(r["ret"], r["n"], r["gross"], r["cost"], len(r["ret"]) / 252)
        sc = mt["sharpe"] - (100 if W.shield(mt) else 0)
        if sc > bs: best, bs = p, sc
    return best

def evaluate(D, last, G=GRID):
    Wn = W.windows(last); oos, picks, n, g, c = [], [], 0, 0.0, 0.0; rob = {0.9: [], 1.1: []}
    for tr0, ts0, ts1 in Wn:
        p = pick(D, tr0, ts0 - pd.Timedelta(days=1), G); o = run(D, p, ts0, ts1 - pd.Timedelta(days=1))
        picks.append({"train": f"{tr0.date()}..{ts0.date()}", "test": f"{ts0.date()}..{ts1.date()}", "param": p,
                      "oos_ret_pct": round(((1 + o["ret"]).prod() - 1) * 100, 2), "oos_trades": o["n"]}); print(picks[-1], flush=True)
        oos.append(o["ret"]); n += o["n"]; g += o["gross"]; c += o["cost"]
        for f in rob: rob[f].append(run(D, scale(p, f), ts0, ts1 - pd.Timedelta(days=1))["ret"])
    st = lambda l: (lambda x: x[~x.index.duplicated()])(pd.concat(l))
    R = st(oos); mt = W.metrics(R, n, g, c, len(R) / 252)
    mt["robust_ret_pct"] = {f"x{f}": round(((1 + st(l)).prod() - 1) * 100, 2) for f, l in rob.items()}
    mt["robust_spread_pp"] = round(max(abs(v - mt["return_pct"]) for v in mt["robust_ret_pct"].values()), 2)
    mt["losing_windows"] = f"{sum(x['oos_ret_pct'] < 0 for x in picks)}/{len(picks)}"
    mt["shield_dd_ok"] = mt["max_dd_pct"] <= 20
    mt["within_25tpy"] = mt["trades_per_yr"] <= 25; mt["within_50tpy"] = mt["trades_per_yr"] <= 50
    h0, h1 = pd.Timestamp("2026-04-14"), last
    hp = pick(D, h0 - pd.DateOffset(years=2), pd.Timestamp("2026-04-13"), G); ho = run(D, hp, h0, h1)
    hm = W.metrics(ho["ret"], ho["n"], ho["gross"], ho["cost"], len(ho["ret"]) / 252); hm["param"] = hp
    return {"metrics": mt, "holdout": hm, "windows": picks,
            "oos_equity": {str(k.date()): round(v, 4) for k, v in (1 + R).cumprod().items()}}

def spy(last):
    px = ED.prices()["SPY"]["Close"].dropna(); px.index = px.index.tz_localize(None) if px.index.tz else px.index
    r = px[px.index >= "2022-01-01"].pct_change().fillna(0); r.iloc[0] -= 2 * W.SIDE_COST
    return W.metrics(r, 1, float((1 + r).prod() - 1), 2 * W.SIDE_COST, len(r) / 252)

GRID_CAPPED = [{**p, "K": 4, "min_sur": 10} for p in GRID]

def guidance_events():
    import guidance_edgar as GE
    gd = pickle.load(open(GE.C, "rb")); eps = ED.earnings(); ev = {}; cov = {"stocks": 0, "releases": 0, "with_text": 0, "raised": 0, "beats_matched": 0, "beat_and_raised": 0}
    for t, df in gd.items():
        if df is None or len(df) == 0: continue
        cov["stocks"] += 1; cov["releases"] += len(df); cov["with_text"] += int(df.has_text.sum())
        fl = [GE.flags(z) for z in df.text]; df = df.assign(raised=[a for a, b in fl], filed=pd.to_datetime(df.filed)); cov["raised"] += int(df.raised.sum())
        e = eps.get(t)
        if e is None: continue
        e = e.dropna(subset=["Reported EPS", "EPS Estimate"]); e = e[e["Reported EPS"] > e["EPS Estimate"]]; keep = []
        for ts, r in e.iterrows():
            d = pd.Timestamp(ts).tz_localize(None).normalize(); m = df[(df.filed >= d - pd.Timedelta(days=2)) & (df.filed <= d + pd.Timedelta(days=3))]
            if len(m) == 0 or d < pd.Timestamp("2019-07-01"): continue
            cov["beats_matched"] += 1
            if m.raised.any(): keep.append(ts); cov["beat_and_raised"] += 1
        ev[t] = e.loc[keep]
    return ev, cov

if __name__ == "__main__":
    D = load(); last = pd.Timestamp(D["idx"].max())
    out = {"spy": spy(last), "last": str(last.date()), "tpy_cap_used_in_pick": W.TPY_CAP}
    out["eps_beat"] = evaluate(D, last)
    out["eps_beat_capped"] = evaluate(D, last, GRID_CAPPED)
    if os.environ.get("GUID"):
        ev, cov = guidance_events(); DG = load(ev); out["guidance_raise"] = evaluate(DG, last, GRID_CAPPED); out["guidance_raise"]["coverage"] = cov
        # same 100-stock subset, EPS beat only, for apples-to-apples
        sub = {t: ED.earnings()[t] for t in ev}; DS = load({t: (lambda e: e[e["Reported EPS"] > e["EPS Estimate"]])(sub[t].dropna(subset=["Reported EPS", "EPS Estimate"])) for t in sub})
        out["eps_beat_subset100"] = evaluate(DS, last, GRID_CAPPED)
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/es.json", "w"), indent=1, default=str)
    for k, v in out.items():
        if isinstance(v, dict) and "metrics" in v: print(k, v["metrics"], v["holdout"])
