#!/usr/bin/env python3
"""Earnings robustness (2026-10-15). Plan = EPS beat + swing low (no guidance filter, no SPY filter), K=10 slots,
PAPER, 1x, long-only. Trade cap 100/yr (Casey-approved for commission-free stocks), max DD <= 20%.
Point-in-time S&P 500 membership (fja05680/sp500): a stock can only be ENTERED on days it was a member.
Fee models: 'current' = 9 bps/side (SIDE_COST); 'robinhood' = 0 commission + 5 bps slippage/side.
Tests: walk-forward 2022->today (2y train / 6m test / 6m step), unseen years (frozen 2022-24 pick on 2018-21 and
2025-26), Monte Carlo trade-order reshuffle x1000 (+ bootstrap), random-entry benchmark x200, nudges +-10/20%."""
import os, sys, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import walkforward as W, earnings_pit_data as PD, earnings_swinglow as E
W.TPY_CAP = 100.0; K = 10; STOP_BUF = 0.01
# base grid (K=10, all beats) + throttles so the 100/yr cap is reachable: fewer slots, min EPS surprise %
GRID = [{**p, "K": k, "min_sur": ms} for p in E.GRID for k in (10, 5) for ms in (0, 5, 10)]
FEES = {"current": 9 / 1e4, "robinhood": 5 / 1e4}
rng = np.random.default_rng(20261015)

def load():
    px = PD.prices(); eps = PD.earnings(); lv = px.columns.get_level_values(0)
    tk = [t for t in PD.universe() if t in lv and px[t]["Close"].notna().sum() > 50 and eps.get(t) is not None and len(eps[t]) > 0]
    F = {f: pd.DataFrame({t: px[t][f] for t in tk}) for f in ("Open", "High", "Low", "Close")}
    idx = F["Close"].index.tz_localize(None) if F["Close"].index.tz is not None else F["Close"].index
    for f in F: F[f].index = idx
    c = F["Close"]; ma20, ma50, ma200 = (c.rolling(n, min_periods=n).mean() for n in (20, 50, 200))
    beat = np.full(c.shape, np.nan); nbeats = 0
    for j, t in enumerate(tk):
        e = eps[t].dropna(subset=["Reported EPS", "EPS Estimate"])
        for ts, r in e[e["Reported EPS"] > e["EPS Estimate"]].iterrows():
            ts = pd.Timestamp(ts); d = ts.tz_localize(None).normalize() if ts.tzinfo else ts.normalize()
            k = idx.searchsorted(d) if (ts.hour < 12 and ts.tzinfo) else idx.searchsorted(d + pd.Timedelta(days=1))
            if k < len(idx): beat[k, j] = float(r.get("Surprise(%)", 1) or 1); nbeats += 1
    pit = PD.pit(); mem = np.zeros(c.shape, bool); pos = pit.date.searchsorted(idx, "right") - 1
    col = {t: j for j, t in enumerate(tk)}
    for i, p in enumerate(pos):
        if p < 0: continue
        for t in pit.set.iat[p]:
            if t in col: mem[i, col[t]] = True
    up = (c > ma200) & (ma50 > ma200); lo = F["Low"]
    touch = (lo <= ma20).shift(1).rolling(3).max().fillna(0).astype(bool)
    pivot = (lo.shift(1) < lo.shift(2)) & (lo.shift(1) < lo)
    swing = ((touch | pivot) & (c > c.shift(1)) & up).values & mem
    return dict(idx=idx, tk=tk, O=F["Open"].values, H=F["High"].values, L=lo.values, C=c.values, beat=beat,
                swing=swing, swlow=lo.rolling(3).min().values, mem=mem, nbeats=nbeats)

def run(D, p, start, end, log=False):
    """Same logic as earnings_swinglow.run, plus trade log (stock, entry bar, exit bar, net return)."""
    idx = D["idx"]; i0, i1 = idx.searchsorted(pd.Timestamp(start)), idx.searchsorted(pd.Timestamp(end), "right")
    O, L, C, B, S, SL = D["O"], D["L"], D["C"], D["beat"], D["swing"], D["swlow"]; sc = W.SIDE_COST
    N = int(p["N"]); n_s = C.shape[1]; K = int(p.get("K", 10)); ms = p.get("min_sur", 0)
    last_beat = np.full(n_s, -10**9); last_sur = np.zeros(n_s); used = np.zeros(n_s, bool)
    for i in range(max(0, i0 - N), i0):
        m = ~np.isnan(B[i]); last_beat[m] = i; last_sur[m] = B[i][m]; used[m] = False
    cash = 1.0; pos = {}; pend = []; rets = []; n = 0; gross = cost = 0.0; prev = 1.0; T = []
    for i in range(i0, i1):
        for j, stop in pend:
            if len(pos) >= K or j in pos or np.isnan(O[i, j]): continue
            alloc = min(cash, prev / K)
            if alloc <= 0: break
            sh = alloc * (1 - sc) / O[i, j]; cash -= alloc; cost += alloc * sc
            pos[j] = dict(sh=sh, px=O[i, j], stop=stop, hi=O[i, j], age=0, exit_open=False, i=i, a=alloc); n += 1
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
                v = q["sh"] * xp; cash += v * (1 - sc); cost += v * sc; gross += q["sh"] * (xp - q["px"])
                T.append((j, q["i"], i, v * (1 - sc) / q["a"] - 1)); del pos[j]
        m = ~np.isnan(B[i]); last_beat[m] = i; last_sur[m] = B[i][m]; used[m] = False
        act = (i - last_beat <= N) & (i - last_beat >= 1) & ~used & S[i]
        cands = sorted([j for j in np.where(act)[0] if j not in pos and last_sur[j] >= ms], key=lambda j: -last_sur[j])
        for j in cands[:K]: pend.append((j, SL[i, j] * (1 - STOP_BUF))); used[j] = True
        eq = cash + sum(q["sh"] * (C[i, j] if not np.isnan(C[i, j]) else q["px"]) for j, q in pos.items())
        rets.append(eq / prev - 1); prev = eq
    for j, q in pos.items():
        gross += q["sh"] * (C[i1 - 1, j] - q["px"]); T.append((j, q["i"], i1 - 1, C[i1 - 1, j] * q["sh"] * (1 - sc) / q["a"] - 1))
    return {"ret": pd.Series(rets, index=idx[i0:i1]), "n": n, "gross": gross, "cost": cost, "trades": T}

def M(r): return W.metrics(r["ret"], r["n"], r["gross"], r["cost"], max(len(r["ret"]), 1) / 252)
def pick(D, a, b):
    best, bs = None, -1e9
    for p in GRID:
        mt = M(run(D, p, a, b)); s = mt["sharpe"] - (100 if W.shield(mt) else 0)
        if s > bs: best, bs = p, s
    return best
def scale(p, f): return {**p, "N": max(2, int(round(p["N"] * f))), "trail": round(p["trail"] * f, 4), "tstop": max(2, int(round(p["tstop"] * f)))}
st = lambda l: (lambda x: x[~x.index.duplicated()])(pd.concat(l))
NUDGE = (0.8, 0.9, 1.1, 1.2)

def walkforward(D, last):
    oos, picks, n, g, c, T = [], [], 0, 0.0, 0.0, []; rob = {f: [] for f in NUDGE}
    for tr0, ts0, ts1 in W.windows(last):
        p = pick(D, tr0, ts0 - pd.Timedelta(days=1)); o = run(D, p, ts0, ts1 - pd.Timedelta(days=1))
        sp = spy_ret(ts0, ts1 - pd.Timedelta(days=1))
        picks.append({"test": f"{ts0.date()}..{ts1.date()}", "param": p, "oos_ret_pct": round(((1 + o["ret"]).prod() - 1) * 100, 2),
                      "spy_ret_pct": round(((1 + sp).prod() - 1) * 100, 2), "oos_trades": o["n"]}); print(picks[-1], flush=True)
        oos.append(o["ret"]); n += o["n"]; g += o["gross"]; c += o["cost"]; T += o["trades"]
        for f in rob: rob[f].append(run(D, scale(p, f), ts0, ts1 - pd.Timedelta(days=1))["ret"])
    R = st(oos); mt = W.metrics(R, n, g, c, len(R) / 252)
    mt["nudge"] = {f"x{f}": (lambda q: {"return_pct": round(((1 + q).prod() - 1) * 100, 2), "max_dd_pct": round((1 - (1 + q).cumprod() / (1 + q).cumprod().cummax()).max() * 100, 2)})(st(l)) for f, l in rob.items()}
    mt["losing_windows"] = f"{sum(x['oos_ret_pct'] < 0 for x in picks)}/{len(picks)}"
    mt["beat_spy_windows"] = f"{sum(x['oos_ret_pct'] > x['spy_ret_pct'] for x in picks)}/{len(picks)}"
    return mt, picks, T, R

_SPY = None
def spy_ret(a, b):
    global _SPY
    if _SPY is None:
        s = PD.prices()["SPY"]["Close"].dropna(); s.index = s.index.tz_localize(None) if s.index.tz else s.index; _SPY = s
    s = _SPY[(_SPY.index >= pd.Timestamp(a) - pd.Timedelta(days=7))]; r = s.pct_change(); r = r[(r.index >= pd.Timestamp(a)) & (r.index <= pd.Timestamp(b))].fillna(0)
    return r
def spy_m(a, b):
    r = spy_ret(a, b).copy(); r.iloc[0] -= 2 * W.SIDE_COST; return W.metrics(r, 1, 1.0, 0, len(r) / 252)

def seq_stats(rs, order, K=10):
    eq = np.cumprod(1 + rs[order] / K); dd = (1 - eq / np.maximum.accumulate(eq)).max() * 100
    return (eq[-1] - 1) * 100, dd

def monte_carlo(T, n=1000):
    rs = np.array([t[3] for t in sorted(T, key=lambda t: t[2])]); base = seq_stats(rs, np.arange(len(rs)))
    sh = np.array([seq_stats(rs, rng.permutation(len(rs))) for _ in range(n)])
    bs = np.array([seq_stats(rs, rng.integers(0, len(rs), len(rs))) for _ in range(n)])
    pc = lambda a: {f"p{q}": round(float(np.percentile(a, q)), 2) for q in (5, 50, 95)}
    return {"n_trades": len(rs), "model": "each trade = 1/10 of equity, compounded in sequence",
            "actual_order": {"return_pct": round(base[0], 2), "max_dd_pct": round(base[1], 2)},
            "shuffle_return_pct": pc(sh[:, 0]), "shuffle_max_dd_pct": pc(sh[:, 1]),
            "bootstrap_return_pct": pc(bs[:, 0]), "bootstrap_max_dd_pct": pc(bs[:, 1]),
            "bootstrap_prob_loss_pct": round(float((bs[:, 0] < 0).mean() * 100), 1),
            "shuffle_prob_dd_over_20_pct": round(float((sh[:, 1] > 20).mean() * 100), 1)}

def random_entry(D, T, i_lo, i_hi, n=200):
    O, C, mem = D["O"], D["C"], D["mem"]; sc = W.SIDE_COST
    rs = np.array([t[3] for t in T]); plan_mean = rs.mean(); plan_tot = seq_stats(np.array([t[3] for t in sorted(T, key=lambda t: t[2])]), np.arange(len(T)))[0]
    elig = {}
    for j, a, b, _ in T:
        h = b - a
        if (j, h) not in elig:
            ok = np.where(mem[i_lo:i_hi - h, j] & ~np.isnan(O[i_lo:i_hi - h, j]) & ~np.isnan(C[i_lo + h:i_hi, j]))[0] + i_lo
            elig[(j, h)] = ok
    means, tots = [], []
    for _ in range(n):
        tr = []
        for j, a, b, _r in T:
            ok = elig[(j, b - a)]
            if len(ok) == 0: continue
            e = ok[rng.integers(len(ok))]; tr.append((e + b - a, (C[e + b - a, j] * (1 - sc)) / (O[e, j] / (1 - sc)) - 1))
        tr.sort(); r = np.array([x[1] for x in tr]); means.append(r.mean()); tots.append(seq_stats(r, np.arange(len(r)))[0])
    means, tots = np.array(means), np.array(tots)
    return {"runs": n, "plan_avg_trade_pct": round(plan_mean * 100, 3), "random_avg_trade_pct_p50": round(float(np.median(means)) * 100, 3),
            "random_avg_trade_pct_p95": round(float(np.percentile(means, 95)) * 100, 3),
            "plan_beats_pct_of_random": round(float((plan_mean > means).mean() * 100), 1),
            "plan_total_pct_seqmodel": round(plan_tot, 2), "random_total_pct_p50": round(float(np.median(tots)), 2),
            "random_total_pct_p95": round(float(np.percentile(tots, 95)), 2), "beats_95pct": bool((plan_mean > means).mean() >= 0.95)}

def frozen(D, p, a, b):
    r = run(D, p, a, b); mt = M(r); mt["spy"] = spy_m(a, b); mt["first_bar"] = str(D["idx"][D["idx"].searchsorted(pd.Timestamp(a))].date()); return mt

if __name__ == "__main__":
    D = load(); last = pd.Timestamp(D["idx"].max()); idx = D["idx"]
    out = {"last": str(last.date()), "universe_pit_tickers": len(PD.universe()), "tradable_tickers_with_px_eps": len(D["tk"]),
           "eps_beats": D["nbeats"], "trade_cap": 100, "max_dd_limit": 20, "K": K, "grid": GRID, "fees": FEES, "results": {}}
    for fk, fv in FEES.items():
        W.SIDE_COST = fv; R = {}; print("=== fees", fk, flush=True)
        mt, picks, T, Rr = walkforward(D, last); mt["spy"] = spy_m("2022-01-01", last)
        R["walkforward"] = {"metrics": mt, "windows": picks, "oos_equity": {str(k.date()): round(v, 4) for k, v in (1 + Rr).cumprod().iloc[::5].items()}}
        R["monte_carlo"] = monte_carlo(T)
        R["random_entry"] = random_entry(D, T, idx.searchsorted(pd.Timestamp("2022-01-01")), len(idx))
        fp = pick(D, "2022-01-01", "2024-12-31"); R["frozen_param_2022_2024"] = fp
        R["in_sample_2022_2024"] = frozen(D, fp, "2022-01-01", "2024-12-31")
        R["unseen_2018_2021"] = frozen(D, fp, "2018-01-01", "2021-12-31")
        R["unseen_2025_2026"] = frozen(D, fp, "2025-01-01", last)
        R["unseen_nudge"] = {f"x{f}": {k: (lambda m: {"return_pct": m["return_pct"], "max_dd_pct": m["max_dd_pct"]})(M(run(D, scale(fp, f), a, b)))
                             for k, (a, b) in {"2018_2021": ("2018-01-01", "2021-12-31"), "2025_2026": ("2025-01-01", last)}.items()} for f in NUDGE}
        out["results"][fk] = R; print(json.dumps({k: v for k, v in R.items() if k != "walkforward"}, default=str)[:3000], flush=True)
    json.dump(out, open(sys.argv[1], "w"), indent=1, default=str)
