#!/usr/bin/env python3
"""Fetch S&P 500 current members, daily OHLC (yfinance, auto-adjusted) and EPS earnings history
(yfinance get_earnings_dates: reported EPS vs consensus estimate). Cached to /workspace/.earn_cache."""
import os, io, pickle, time, requests, pandas as pd, yfinance as yf
C = "/workspace/.earn_cache"
def members():
    f = f"{C}/sp500.csv"
    if os.path.exists(f): return pd.read_csv(f)
    h = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", headers={"User-Agent": "Mozilla/5.0"}).text
    df = pd.read_html(io.StringIO(h))[0][["Symbol", "Security", "GICS Sector"]]
    df["yf"] = df.Symbol.str.replace(".", "-", regex=False); df.to_csv(f, index=False); return df
def prices():
    f = f"{C}/px.pkl"
    if os.path.exists(f): return pickle.load(open(f, "rb"))
    tk = list(members().yf) + ["SPY"]
    px = yf.download(tk, start="2019-01-01", auto_adjust=True, group_by="ticker", threads=True, progress=False)
    pickle.dump(px, open(f, "wb")); return px
def earnings():
    f = f"{C}/eps.pkl"; out = pickle.load(open(f, "rb")) if os.path.exists(f) else {}
    for i, t in enumerate(members().yf):
        if t in out: continue
        for k in range(3):
            try: out[t] = yf.Ticker(t).get_earnings_dates(limit=40); break
            except Exception as e: print(t, e); time.sleep(3 * (k + 1))
        if i % 25 == 0: pickle.dump(out, open(f, "wb")); print(i, flush=True)
        time.sleep(0.3)
    pickle.dump(out, open(f, "wb")); return out
if __name__ == "__main__":
    print(len(members())); px = prices(); print(px.shape); e = earnings(); print(len(e), sum(v is not None and len(v) > 0 for v in e.values()))
