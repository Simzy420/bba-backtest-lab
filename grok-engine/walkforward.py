#!/usr/bin/env python3
"""
Walk-forward harness v1 (2026-10-14). PAPER ONLY.
Train 2y / test 6mo / step 6mo. Params picked on TRAIN only (best Sharpe among Shield-passing configs),
OOS test results stitched as daily returns. Data: daily yfinance, same universe, as-of aligned to ^GSPC grid
(fixed_engine carry-forward). Costs: 4.5 bps fee + 4.5 bps slippage per side, funding per 8h on held notional.
Lab strategies (R4-C, R3) run through their own lab scripts; simple strategies use a vectorized sleeve engine:
equal-weight 1/6 sleeves of the 6 tradeables, 1x notional (no leverage beyond book sizing), long-only.
"""
import os, sys, json, math, pickle, importlib.util
import numpy as np, pandas as pd, yfinance as yf
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
CACHE = "/workspace/.bba_data_cache_max.pkl"
TICKERS = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD", "GOLD": "GC=F", "NVDA": "NVDA",
           "TSLA": "TSLA", "^GSPC": "^GSPC", "^VIX": "^VIX", "^TNX": "^TNX"}
TRADE = ["BTC", "ETH", "SOL", "GOLD", "NVDA", "TSLA"]
FUND = {"SOL": 0.0002}; FUND_DEF = 0.0001
SIDE_COST = (4.5 + 4.5) / 1e4
START = "2020-01-01"

def raw():
    if os.path.exists(CACHE): return pickle.load(open(CACHE, "rb"))
    out = {}
    for s, tk in TICKERS.items():
        df = yf.Ticker(tk).history(start="2019-01-01", auto_adjust=True).reset_index()
        df["date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.normalize().astype("datetime64[ns]")
        df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"})
        out[s] = df[["date", "open", "high", "low", "close"]].drop_duplicates("date").sort_values("date").reset_index(drop=True)
    pickle.dump(out, open(CACHE, "wb")); return out

def grid_data(start, end):
    R = raw(); g = R["^GSPC"]; g = g[(g.date >= start) & (g.date <= end)][["date"]].reset_index(drop=True)
    d = {}
    for s, df in R.items():
        a = pd.merge_asof(g, df, on="date", direction="backward")
        a["symbol"] = s; d[s] = a   # NaN before an asset's listing (e.g. SOL pre-2020-04) -> dropped below
    return d

# ---------- lab-script strategies ----------
def load_mod(script):
    spec = importlib.util.spec_from_file_location("m" + str(abs(hash(script))), script)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def lab_run(script, attrs, start, end, warm_days=110):
    m = load_mod(script)
    for k, v in attrs.items(): setattr(m, k, v)
    s0 = pd.Timestamp(start) - pd.Timedelta(days=warm_days)
    d = grid_data(s0, pd.Timestamp(end))
    d = {k: v.dropna(subset=["close"]).reset_index(drop=True) for k, v in d.items()}
    # assets not yet listed: give them an empty-safe frame by skipping; lab scripts expect all keys
    for k in list(d):
        if len(d[k]) < 60: d[k] = d["^GSPC"].assign(symbol=k).iloc[0:0]
    reg = m.build_regime_series(d)
    try:
        trades, eq, cash = m.run_backtest(d, reg)
    except Exception as e:
        return None
    if eq: eq[-1]["equity"] = round(cash, 2)
    e = pd.DataFrame(eq); e["date"] = pd.to_datetime(e["date"])
    e = e[e.date >= pd.Timestamp(start)]
    r = e.set_index("date")["equity"].pct_change().fillna(0)
    tr = [t for t in trades if pd.Timestamp(t["entry_date"]) >= pd.Timestamp(start)]
    gross = sum(t["gross_pnl"] for t in tr); cost = sum(t["fees"] + t["slippage"] + t["funding"] for t in tr)
    return {"ret": r, "n": len(tr), "gross": gross / m.START_CAPITAL, "cost": cost / m.START_CAPITAL}

# ---------- vectorized simple strategies ----------
def rsi(c, n=14):
    d = c.diff(); u = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean(); l = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + u / l)

def signals(kind, p, c):
    if kind == "trend_ma":
        return (c.rolling(p["fast"]).mean() > c.rolling(p["slow"]).mean()).astype(float)
    if kind == "donchian":
        hi = c.rolling(p["n"]).max().shift(1); lo = c.rolling(max(2, p["n"] // 2)).min().shift(1)
        pos = pd.Series(np.nan, index=c.index); pos[c > hi] = 1; pos[c < lo] = 0
        return pos.ffill().fillna(0)
    if kind == "breakout_vol":   # close > N-day high AND above 200MA; exit below 20MA
        hi = c.rolling(p["n"]).max().shift(1); ma = c.rolling(200).mean(); ex = c.rolling(20).mean()
        pos = pd.Series(np.nan, index=c.index); pos[(c > hi) & (c > ma)] = 1; pos[c < ex] = 0
        return pos.ffill().fillna(0)
    if kind == "rsi_mr":         # buy RSI<lo above 200MA, exit RSI>hi or after 10 bars
        r = rsi(c); ma = c.rolling(200).mean()
        pos = pd.Series(np.nan, index=c.index); pos[(r < p["lo"]) & (c > ma)] = 1; pos[r > p["hi"]] = 0
        pos = pos.ffill().fillna(0)
        return pos
    if kind == "btc_hodl":
        return pd.Series(1.0, index=c.index)
    raise ValueError(kind)

def vec_run(kind, p, start, end, warm_days=420):
    d = grid_data(pd.Timestamp(start) - pd.Timedelta(days=warm_days), pd.Timestamp(end))
    syms = ["BTC"] if kind == "btc_hodl" else TRADE
    rets, n, gross, cost = [], 0, 0.0, 0.0
    w = 1.0 / len(syms)
    for s in syms:
        df = d[s].set_index("date"); c = df["close"]
        if c.notna().sum() < 50: continue
        pos = signals(kind, p, c).where(c.notna(), 0).shift(1).fillna(0)   # trade next bar
        ar = c.pct_change().fillna(0)
        days = pd.Series(df.index, index=df.index).diff().dt.days.fillna(1)
        fund = pos * (FUND.get(s, FUND_DEF) * 3) * days
        turn = pos.diff().abs().fillna(pos.abs())
        if kind == "btc_hodl": turn = pd.Series(0.0, index=c.index); 
        cst = turn * SIDE_COST + fund
        g = pos * ar
        m = df.index >= pd.Timestamp(start)
        if kind == "btc_hodl": cst = cst.copy(); first = np.argmax(m); cst.iloc[first] += 2 * SIDE_COST
        rets.append(((g - cst) * w)[m]); gross += (g * w)[m].sum(); cost += (cst * w)[m].sum()
        n += int((pos.diff() > 0)[m].sum())
    r = pd.concat(rets, axis=1).sum(axis=1)
    return {"ret": r, "n": n, "gross": gross, "cost": cost}

# ---------- metrics ----------
def metrics(r, n, gross, cost, years):
    eq = (1 + r).cumprod(); dd = (1 - eq / eq.cummax()).max() * 100
    sh = r.mean() / r.std() * math.sqrt(252) if r.std() > 0 else 0.0
    return {"return_pct": round((eq.iloc[-1] - 1) * 100, 2), "max_dd_pct": round(dd, 2), "sharpe": round(sh, 3),
            "trades": n, "trades_per_yr": round(n / years, 1),
            "cost_pct_of_gross": round(cost / gross * 100, 1) if gross > 0 else None,
            "cagr_pct": round((eq.iloc[-1] ** (1 / years) - 1) * 100, 2)}

def shield(mt): return mt["max_dd_pct"] > 20 or mt["trades_per_yr"] > 25

LAB_R4C = os.path.join(HERE, "r4c_chop_filter_engine.py")
LAB_R3 = os.path.join(HERE, "..", "bba-engine", "hl_backtest.py")
STRATS = {
    "R4-C Druckenmiller": ("lab", LAB_R4C, "ATR_MULT", [0.9, 1.0, 1.1]),
    "R3 Druckenmiller":   ("lab", LAB_R3, "PULLBACK_PCT", [1.5, 2.0, 2.5]),
    "Trend MA cross":     ("vec", "trend_ma", None, [{"fast": 20, "slow": 100}, {"fast": 50, "slow": 200}, {"fast": 30, "slow": 150}]),
    "Donchian trend":     ("vec", "donchian", None, [{"n": 20}, {"n": 55}, {"n": 100}]),
    "Breakout >200MA":    ("vec", "breakout_vol", None, [{"n": 20}, {"n": 40}, {"n": 60}]),
    "RSI mean-reversion": ("vec", "rsi_mr", None, [{"lo": 25, "hi": 55}, {"lo": 30, "hi": 55}, {"lo": 35, "hi": 60}]),
    "BTC buy-and-hold":   ("vec", "btc_hodl", None, [{}]),
}

def run_one(spec, p, s, e):
    kind, a, knob, _ = spec
    if kind == "lab": return lab_run(a, {knob: p}, s, e)
    return vec_run(a, p, s, e)

def scale(p, f):
    if isinstance(p, (int, float)): return round(p * f, 3)
    return {k: max(2, int(round(v * f))) for k, v in p.items()}

def windows(last):
    out, t = [], pd.Timestamp("2022-01-01")
    while t < last:
        out.append((t - pd.DateOffset(years=2), t, min(t + pd.DateOffset(months=6), last))); t += pd.DateOffset(months=6)
    return out

def main(only=None):
    last = raw()["^GSPC"].date.max()
    W = windows(last); res = {}
    for name, spec in STRATS.items():
        if only and name not in only: continue
        print("==", name, flush=True)
        oos, picks, n, g, c = [], [], 0, 0.0, 0.0
        rob = {0.9: [], 1.1: []}
        for tr0, ts0, ts1 in W:
            best, bsh = None, -1e9
            for p in spec[3]:
                r = run_one(spec, p, tr0, ts0 - pd.Timedelta(days=1))
                if r is None: continue
                yrs = len(r["ret"]) / 252; mt = metrics(r["ret"], r["n"], r["gross"], r["cost"], yrs)
                sc = mt["sharpe"] - (100 if shield(mt) else 0)
                if sc > bsh: best, bsh = p, sc
            o = run_one(spec, best, ts0, ts1)
            picks.append({"train": f"{tr0.date()}..{ts0.date()}", "test": f"{ts0.date()}..{ts1.date()}", "param": best,
                          "oos_ret_pct": round(((1 + o["ret"]).prod() - 1) * 100, 2), "oos_trades": o["n"]})
            print(" ", picks[-1], flush=True)
            oos.append(o["ret"]); n += o["n"]; g += o["gross"]; c += o["cost"]
            if spec[2] is not None or spec[1] != "btc_hodl":
                for f in rob:
                    rr = run_one(spec, scale(best, f), ts0, ts1); rob[f].append(rr["ret"] if rr else o["ret"] * 0)
        R = pd.concat(oos); R = R[~R.index.duplicated()]
        yrs = len(R) / 252
        mt = metrics(R, n, g, c, yrs)
        rb = {}
        for f, lst in rob.items():
            if lst:
                x = pd.concat(lst); x = x[~x.index.duplicated()]; rb[f"x{f}"] = round(((1 + x).prod() - 1) * 100, 2)
        mt["robust_ret_pct"] = rb
        mt["robust_spread_pp"] = round(max(abs(v - mt["return_pct"]) for v in rb.values()), 2) if rb else 0
        mt["shield_veto"] = shield(mt)
        res[name] = {"metrics": mt, "windows": picks, "oos_equity": {str(k.date()): round(v, 4) for k, v in (1 + R).cumprod().items()}}
    return res, W

if __name__ == "__main__":
    only = [x for x in sys.argv[1].split(",") if x] or None if len(sys.argv) > 1 else None
    res, W = main(only)
    out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/wf.json"
    json.dump({"windows": [[str(a.date()), str(b.date()), str(c.date())] for a, b, c in W], "results": res}, open(out, "w"), indent=1, default=str)
    for k, v in res.items(): print(k, v["metrics"])
