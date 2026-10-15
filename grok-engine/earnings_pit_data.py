#!/usr/bin/env python3
"""Point-in-time S&P 500 data (2026-10-15). Membership: fja05680/sp500 'Historical Components & Changes (Updated)'.
Union of all members since 2016 -> yfinance prices from 2016 (for MA200 warmup before 2018) + EPS history.
Delisted/renamed tickers yfinance can't serve are dropped and counted (residual survivorship)."""
import os, pickle, time, pandas as pd, yfinance as yf
C = "/workspace/.earn_cache"
def pit():
    d = pd.read_csv(f"{C}/pit.csv"); d["date"] = pd.to_datetime(d.date); d = d[d.date >= "2015-06-01"].reset_index(drop=True)
    d["set"] = [set(x.replace(".", "-") for x in s.split(",")) for s in d.tickers]; return d[["date", "set"]]
def universe(): s = set(); [s.update(x) for x in pit().set]; return sorted(s)
def prices():
    f = f"{C}/px_pit.pkl"
    if os.path.exists(f): return pickle.load(open(f, "rb"))
    px = yf.download(universe() + ["SPY"], start="2016-01-01", auto_adjust=True, group_by="ticker", threads=True, progress=False)
    pickle.dump(px, open(f, "wb")); return px
def earnings():
    f = f"{C}/eps.pkl"; out = pickle.load(open(f, "rb")); px = prices()
    have = [t for t in universe() if t in px.columns.get_level_values(0) and px[t]["Close"].notna().sum() > 50]
    for i, t in enumerate(have):
        if t in out: continue
        for k in range(2):
            try: out[t] = yf.Ticker(t).get_earnings_dates(limit=48); break
            except Exception as e: print(t, e); out[t] = None; time.sleep(2)
        if i % 25 == 0: pickle.dump(out, open(f, "wb"))
        time.sleep(0.3)
    pickle.dump(out, open(f, "wb")); return out
if __name__ == "__main__":
    u = universe(); px = prices(); e = earnings()
    ok = [t for t in u if t in px.columns.get_level_values(0) and px[t]["Close"].notna().sum() > 50]
    print("universe", len(u), "with prices", len(ok), "with eps", sum(e.get(t) is not None and len(e[t]) > 0 for t in ok))
