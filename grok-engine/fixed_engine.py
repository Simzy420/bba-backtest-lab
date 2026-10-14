#!/usr/bin/env python3
"""
Shared fixed-engine harness (2026-10-14, phase 1 of walk-forward rebuild). PAPER ONLY.

Wraps any lab round script (same run_backtest/compute_metrics API as bba-engine/hl_backtest.py)
and applies the Round 15 accounting fixes WITHOUT editing the knob logic:

  1. Price carry-forward: every asset is daily (yfinance, incl. BTC-USD/ETH-USD/SOL-USD instead of
     CoinGecko's 4-day 365d candles) and as-of aligned to the regime (^GSPC) date grid, so an exact-date
     lookup never misses. This removes (a) phantom MTM drawdown when a held asset had no row and
     (b) the forced-close bug where DD-defense / RISK-OFF `continue`d on a missing row and then
     `positions = []` deleted the position without returning its margin.
  2. Forced-close safety: falls out of (1) — no empty rows on grid dates.
  3. End-of-window: final equity point = realized cash after BACKTEST_END closes (exit fees,
     slippage and funding included), so final equity - start == sum(trade net P&L).

Usage: python3 fixed_engine.py <script.py> <end_date YYYY-MM-DD> <out.json> [ENV=VAL ...]
"""
import sys, os, json, importlib.util, pickle
from datetime import timedelta
import pandas as pd
import yfinance as yf

CACHE = "/workspace/.bba_data_cache_3y.pkl"
TICKERS = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD", "GOLD": "GC=F", "NVDA": "NVDA",
           "TSLA": "TSLA", "^GSPC": "^GSPC", "^VIX": "^VIX", "^TNX": "^TNX"}

def fetch_all():
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE, "rb"))
    out = {}
    for sym, tk in TICKERS.items():
        df = yf.Ticker(tk).history(period="3y", auto_adjust=True).reset_index()
        df["date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.normalize().astype("datetime64[ns]")
        df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"})
        out[sym] = df[["date", "open", "high", "low", "close"]].drop_duplicates("date").sort_values("date").reset_index(drop=True)
    pickle.dump(out, open(CACHE, "wb"))
    return out

def window_data(end_date, days=365):
    end = pd.Timestamp(end_date); start = end - timedelta(days=days)
    raw = fetch_all()
    grid = raw["^GSPC"]
    grid = grid[(grid.date >= start) & (grid.date <= end)][["date"]].reset_index(drop=True)
    data = {}
    for sym, df in raw.items():
        a = pd.merge_asof(grid, df, on="date", direction="backward").dropna(subset=["close"]).reset_index(drop=True)
        a["symbol"] = sym
        data[sym] = a
    return data

def run(script, end_date, env=None):
    for k, v in (env or {}).items(): os.environ[k] = v
    spec = importlib.util.spec_from_file_location("roundmod_" + str(abs(hash((script, str(env))))), script)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    all_data = window_data(end_date)
    regime_df = mod.build_regime_series(all_data)
    trades, eq, final_cash = mod.run_backtest(all_data, regime_df)
    if eq:  # fix 3
        eq[-1]["equity"] = round(final_cash, 2); eq[-1]["positions_open"] = 0
    m = mod.compute_metrics(trades, eq, mod.START_CAPITAL)
    gross = m.get("total_gross_pnl") or 0
    m["cost_pct_of_gross"] = round(m["total_costs"] / gross * 100, 1) if gross > 0 else None
    m["reconcile_gap"] = round(m["final_equity"] - mod.START_CAPITAL - m["total_net_pnl"], 2)
    veto = m["max_drawdown_pct"] > 20 or m["num_trades"] > 25
    return {"script": script, "end_date": end_date, "env": env or {}, "metrics": m,
            "shield": {"veto": veto, "dd": m["max_drawdown_pct"], "trades": m["num_trades"]},
            "trades": trades, "first_date": str(regime_df.date.iloc[0].date()), "last_date": str(regime_df.date.iloc[-1].date())}

if __name__ == "__main__":
    script, end, out = sys.argv[1:4]
    env = dict(a.split("=", 1) for a in sys.argv[4:])
    r = run(script, end, env)
    json.dump(r, open(out, "w"), indent=2, default=str)
    print(json.dumps({k: r["metrics"][k] for k in ["total_return_pct", "max_drawdown_pct", "sharpe_ratio", "num_trades", "win_rate_pct", "cost_pct_of_gross", "reconcile_gap"]}), r["shield"])
