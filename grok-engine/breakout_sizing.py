#!/usr/bin/env python3
"""Breakout >200MA position-size test (2026-10-14). PAPER ONLY, long-only, 1x max.
ONE change vs walkforward.py: sleeve exposure multiplied by size factor f (0.5..1.0), or
ATR-vol-scaled: exposure = min(1, 2.5% / ATR14%) per asset. Signals/params/costs unchanged."""
import sys, json, math, numpy as np, pandas as pd
import walkforward as W

def atr_pct(df, n=14):
    h, l, c = df["high"], df["low"], df["close"]; pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean() / c

def run(p, start, end, size, warm_days=420):
    d = W.grid_data(pd.Timestamp(start) - pd.Timedelta(days=warm_days), pd.Timestamp(end))
    rets, n, gross, cost = [], 0, 0.0, 0.0; w = 1 / len(W.TRADE)
    for s in W.TRADE:
        df = d[s].set_index("date"); c = df["close"]
        if c.notna().sum() < 50: continue
        sig = W.signals("breakout_vol", p, c).where(c.notna(), 0)
        if size == "atr":
            k = (0.025 / atr_pct(df)).clip(upper=1.0).fillna(0)
            # size fixed at entry, held through trade
            ent = (sig.diff() > 0) | ((sig > 0) & (sig.shift(1).fillna(0) == 0))
            k = k.where(ent).ffill().fillna(0)
            pos = (sig * k)
        else: pos = sig * size
        pos = pos.shift(1).fillna(0)
        ar = c.pct_change().fillna(0)
        days = pd.Series(df.index, index=df.index).diff().dt.days.fillna(1)
        fund = pos * (W.FUND.get(s, W.FUND_DEF) * 3) * days
        turn = pos.diff().abs().fillna(pos.abs())
        cst = turn * W.SIDE_COST + fund; g = pos * ar
        m = df.index >= pd.Timestamp(start)
        rets.append(((g - cst) * w)[m]); gross += (g * w)[m].sum(); cost += (cst * w)[m].sum()
        n += int(((pos > 0) & (pos.shift(1).fillna(0) == 0))[m].sum())
    return {"ret": pd.concat(rets, axis=1).sum(axis=1), "n": n, "gross": gross, "cost": cost}

GRID = [{"n": 20}, {"n": 40}, {"n": 60}]
def pick(size, a, b):
    best, bs = None, -1e9
    for p in GRID:
        r = run(p, a, b, size); mt = W.metrics(r["ret"], r["n"], r["gross"], r["cost"], len(r["ret"]) / 252)
        sc = mt["sharpe"] - (100 if W.shield(mt) else 0)
        if sc > bs: best, bs = p, sc
    return best

def stitch(lst):
    x = pd.concat(lst); return x[~x.index.duplicated()]

def evaluate(size, Wn):
    oos, rob, picks, n, g, c, losers = [], {0.9: [], 1.1: []}, [], 0, 0, 0, 0
    for tr0, ts0, ts1 in Wn:
        p = pick(size, tr0, ts0 - pd.Timedelta(days=1)); o = run(p, ts0, ts1, size)
        rr = ((1 + o["ret"]).prod() - 1) * 100; losers += rr < 0
        picks.append({"test": f"{ts0.date()}..{ts1.date()}", "param": p, "oos_ret_pct": round(rr, 2), "trades": o["n"]})
        oos.append(o["ret"]); n += o["n"]; g += o["gross"]; c += o["cost"]
        for f in rob: rob[f].append(run(W.scale(p, f), ts0, ts1, size)["ret"])
    R = stitch(oos); mt = W.metrics(R, n, g, c, len(R) / 252)
    mt["nudge_ret_pct"] = {f"x{f}": round(((1 + stitch(l)).prod() - 1) * 100, 2) for f, l in rob.items()}
    mt["losing_windows"] = f"{losers}/{len(Wn)}"
    # true holdout
    h0, h1 = pd.Timestamp("2026-04-14"), pd.Timestamp("2026-10-13")
    hp = pick(size, h0 - pd.DateOffset(years=2), pd.Timestamp("2026-04-13"))
    ho = run(hp, h0, h1, size); hm = W.metrics(ho["ret"], ho["n"], ho["gross"], ho["cost"], len(ho["ret"]) / 252)
    hm["param"] = hp
    mt["shield_veto"] = W.shield(mt) or W.shield(hm) if False else W.shield(mt)
    return {"metrics": mt, "holdout": hm, "holdout_shield_veto": W.shield({**hm, "trades_per_yr": hm["trades"] * 2}),
            "windows": picks}

if __name__ == "__main__":
    last = W.raw()["^GSPC"].date.max(); Wn = W.windows(last)
    out = {}
    for sz in [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, "atr"]:
        k = f"size_{sz}" if sz != "atr" else "size_atr_2.5pct"
        out[k] = evaluate(sz, Wn); print(k, out[k]["metrics"], out[k]["holdout"], flush=True)
    json.dump({"data_last": str(last.date()), "windows": [[str(a.date()), str(b.date()), str(c.date())] for a, b, c in Wn],
               "results": out}, open(sys.argv[1], "w"), indent=1, default=str)
