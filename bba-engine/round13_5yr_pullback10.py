#!/usr/bin/env python3
"""
BBA Backtest — Round 10: 5-Year Live R4C Strategy (DD Defense Fixed)
=====================================================================
This is the EXACT strategy currently trading live on Hyperliquid.
R4C chop filter + regime + pyramiding + full costs.

FIX from R7: DD defense now resets after 10 days in cash (not waiting for RISK-OFF).
Also resets peak equity on reset to avoid ratchet effect.

Universe: BTC, ETH, SOL, GOLD, NVDA (no TSLA — R6 confirmed removal)
Period: 5 years (Oct 2021 - Oct 2026)
"""

import json
import math
import statistics
import random
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf

# ─────────────────────── Config (R4C EXACT) ───────────────────────

START_CAPITAL = 1663.0
LEVERAGE_PROBE = 2
LEVERAGE_CONFIRM = 3
LEVERAGE_JUGULAR = 3

MA_SHORT = 20
MA_LONG = 50
RSI_PERIOD = 14
RSI_ENTRY_MIN = 40
RSI_ENTRY_MAX = 65
RSI_EXIT_MAX = 75  # R4C baseline

VIX_RISK_ON = 20.0
VIX_RISK_OFF = 25.0
TNX_TOLERANCE_BPS = 15.0

PULLBACK_PCT = 10.0
PULLBACK_HIGH_LOOKBACK = 5

MAX_CONCURRENT = 2
MAX_HOLD_DAYS = 30
MAX_POSITION_PCT = 0.50

DD_DEFENSE_THRESHOLD = 0.20
DD_DEFENSE_RESET_DAYS = 10  # FIX: reset after 10 days, not waiting for RISK-OFF

PROBE_MAX_PCT = 0.10
CONFIRM_ADD_PCT = 0.15
JUGULAR_TARGET_PCT = 0.40

ATR_PERIOD = 14
ATR_MEDIAN_BARS = 20
EMA_GAP_MIN_PCT = 0.004

FEE_BPS = 4.5
SLIPPAGE_BPS = 4.5
FUNDING_RATES = {
    "BTC": 0.0001, "ETH": 0.0001, "SOL": 0.0002,
    "GOLD": 0.0001, "NVDA": 0.0001, "^GSPC": 0.0001,
}

YF_TICKERS = {
    "BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD",
    "GOLD": "GC=F", "NVDA": "NVDA",
    "^GSPC": "^GSPC", "^VIX": "^VIX", "^TNX": "^TNX",
}
TRADEABLE = ["BTC", "ETH", "SOL", "GOLD", "NVDA", "^GSPC"]

DATA_PERIOD = "5y"
OUTPUT_JSON = "/workspace/bba-backtest-lab/bba-results/round13-5yr-pullback10.json"
MONTE_CARLO_RUNS = 10000

# ─────────────────────── Data ───────────────────────

def fetch_yf(ticker, period):
    t = yf.Ticker(ticker)
    df = t.history(period=period, auto_adjust=True)
    if df.empty:
        raise RuntimeError(f"yfinance empty for {ticker}")
    df = df.reset_index()
    df["date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"})
    return df[["date", "open", "high", "low", "close"]].sort_values("date").reset_index(drop=True)

def load_all_data():
    all_data = {}
    for sym, tk in YF_TICKERS.items():
        print(f"  Fetching {sym} ({tk})...")
        all_data[sym] = fetch_yf(tk, DATA_PERIOD)
    return all_data

# ─────────────────────── Indicators ───────────────────────

def compute_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)

def compute_atr(df, period=14):
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

def add_indicators(df):
    df = df.copy()
    df["ma20"] = df["close"].rolling(MA_SHORT).mean()
    df["ma50"] = df["close"].rolling(MA_LONG).mean()
    df["ema20"] = df["close"].ewm(span=MA_SHORT, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=MA_LONG, adjust=False).mean()
    df["rsi"] = compute_rsi(df["close"], RSI_PERIOD)
    df["ma20_slope_up"] = df["ma20"] > df["ma20"].shift(5)
    df["ma50_slope_up"] = df["ma50"] > df["ma50"].shift(5)
    df["high_5d"] = df["close"].rolling(PULLBACK_HIGH_LOOKBACK).max()
    df["pullback_pct"] = (df["high_5d"] - df["close"]) / df["high_5d"] * 100
    df["atr"] = compute_atr(df, ATR_PERIOD)
    df["atr_pct"] = df["atr"] / df["close"] * 100
    df["atr_median"] = df["atr_pct"].rolling(ATR_MEDIAN_BARS).median()
    df["ema_gap_pct"] = (df["ema20"] - df["ema50"]).abs() / df["close"]
    return df

# ─────────────────────── Regime ───────────────────────

def classify_regime(vix, spx_above_ma50, tnx_change_bps):
    risk_on = risk_off = 0
    if vix < VIX_RISK_ON: risk_on += 1
    elif vix > VIX_RISK_OFF: risk_off += 1
    if spx_above_ma50: risk_on += 1
    else: risk_off += 1
    if tnx_change_bps <= TNX_TOLERANCE_BPS: risk_on += 1
    else: risk_off += 1
    if risk_on >= 2 and risk_off == 0: return "RISK-ON"
    if risk_off >= 2: return "RISK-ON" if risk_on > risk_off else "RISK-OFF"
    return "TRANSITION"

def build_regime(all_data):
    spx = all_data["^GSPC"].copy()
    vix = all_data["^VIX"].copy()
    tnx = all_data["^TNX"].copy()
    regime = spx[["date", "close"]].rename(columns={"close": "spx"})
    regime = regime.merge(vix[["date", "close"]].rename(columns={"close": "vix"}), on="date", how="left")
    regime = regime.merge(tnx[["date", "close"]].rename(columns={"close": "tnx"}), on="date", how="left")
    regime = regime.sort_values("date").reset_index(drop=True)
    regime["spx_ma50"] = regime["spx"].rolling(MA_LONG).mean()
    regime["spx_above_ma50"] = regime["spx"] > regime["spx_ma50"]
    regime["tnx_chg_bps"] = (regime["tnx"] - regime["tnx"].shift(1)) * 100
    regime["vix"] = regime["vix"].ffill()
    regime["tnx"] = regime["tnx"].ffill()
    regime["tnx_chg_bps"] = regime["tnx_chg_bps"].fillna(0)
    regimes = []
    for _, row in regime.iterrows():
        if pd.isna(row["spx_above_ma50"]):
            regimes.append("TRANSITION")
        else:
            regimes.append(classify_regime(row["vix"], bool(row["spx_above_ma50"]), row["tnx_chg_bps"]))
    regime["regime"] = regimes
    return regime[["date", "vix", "spx", "spx_ma50", "spx_above_ma50", "tnx", "tnx_chg_bps", "regime"]]

# ─────────────────────── Chop Filter ───────────────────────

def is_choppy(row):
    if pd.isna(row.get("atr_pct")) or pd.isna(row.get("atr_median")):
        return False
    if row["atr_pct"] < row["atr_median"]:
        return True
    if pd.isna(row.get("ema_gap_pct")):
        return False
    if row["ema_gap_pct"] < EMA_GAP_MIN_PCT:
        return True
    return False

# ─────────────────────── Position ───────────────────────

class Position:
    def __init__(self, symbol, entry_date, entry_price, notional, leverage, phase, regime_at_entry):
        self.symbol = symbol
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.notional = notional
        self.leverage = leverage
        self.phase = phase
        self.regime_at_entry = regime_at_entry
        self.entries = [(entry_date, entry_price, notional, leverage, notional / leverage)]
        self.stop_price = None
        self.added = False

    def avg_entry(self):
        total = sum(n for _, _, n, _, _ in self.entries)
        weighted = sum(p * n for _, p, n, _, _ in self.entries)
        return weighted / total if total > 0 else self.entry_price

    def total_notional(self):
        return sum(n for _, _, n, _, _ in self.entries)

    def total_margin(self):
        return sum(m for _, _, _, _, m in self.entries)

def calc_funding(symbol, notional, hold_days):
    return notional * FUNDING_RATES.get(symbol, 0.0001) * hold_days * 3

def trade_pnl(pos, exit_price, hold_days):
    avg = pos.avg_entry()
    total = pos.total_notional()
    gross = (exit_price - avg) / avg * total
    fees = total * (FEE_BPS / 10000) * 2
    slip = total * (SLIPPAGE_BPS / 10000) * 2
    funding = calc_funding(pos.symbol, total, hold_days)
    return gross - fees - slip - funding, gross, fees, slip, funding

def _tdict(pos, exit_date, exit_price, hold_days, net, gross, fees, slip, funding, reason):
    return {
        "entry_date": str(pos.entry_date.date()),
        "exit_date": str(exit_date.date()),
        "symbol": pos.symbol, "side": "LONG", "phase": pos.phase,
        "entry_price": round(pos.avg_entry(), 4),
        "exit_price": round(exit_price, 4),
        "notional": round(pos.total_notional(), 2),
        "leverage": pos.leverage, "hold_days": hold_days,
        "regime_at_entry": pos.regime_at_entry,
        "gross_pnl": round(gross, 2), "fees": round(fees, 2),
        "slippage": round(slip, 2), "funding": round(funding, 2),
        "net_pnl": round(net, 2),
        "return_pct": round(net / pos.total_margin() * 100, 2),
        "exit_reason": reason,
    }

# ─────────────────────── Engine ───────────────────────

def run_backtest(all_data, regime_df):
    asset_dfs = {}
    for sym in TRADEABLE:
        df = add_indicators(all_data[sym])
        df = df.merge(regime_df[["date", "regime"]], on="date", how="left")
        df["regime"] = df["regime"].ffill().fillna("TRANSITION")
        asset_dfs[sym] = df

    dates = regime_df["date"].drop_duplicates().sort_values().reset_index(drop=True)
    if len(dates) > MA_LONG:
        dates = dates[dates >= dates.iloc[MA_LONG]]

    cash = START_CAPITAL
    peak_equity = START_CAPITAL
    positions = []
    closed_trades = []
    equity_curve = []
    defensive_mode = False
    defensive_start_date = None
    last_trade_date = {}

    for date in dates:
        reg_row = regime_df[regime_df["date"] == date]
        if reg_row.empty: continue
        regime = reg_row.iloc[0]["regime"]

        # MTM
        unrealized = 0.0
        locked = 0.0
        for pos in positions:
            sym_df = asset_dfs.get(pos.symbol)
            if sym_df is None: continue
            row = sym_df[sym_df["date"] == date]
            if row.empty: continue
            cur = row.iloc[0]["close"]
            unrealized += (cur - pos.avg_entry()) / pos.avg_entry() * pos.total_notional()
            locked += pos.total_margin()

        mtm = cash + locked + unrealized
        if not defensive_mode and mtm > peak_equity:
            peak_equity = mtm
        dd = (peak_equity - mtm) / peak_equity if peak_equity > 0 else 0

        # DD defense — go to cash
        if dd >= DD_DEFENSE_THRESHOLD and not defensive_mode:
            defensive_mode = True
            defensive_start_date = date
            print(f"  [{date.date()}] DEFENSIVE (DD={dd*100:.1f}%) — going to cash")
            for pos in list(positions):
                sym_df = asset_dfs[pos.symbol]
                row = sym_df[sym_df["date"] == date]
                if row.empty: continue
                ep = row.iloc[0]["close"]
                h = (date - pos.entry_date).days
                net, g, f, s, fd = trade_pnl(pos, ep, h)
                cash += pos.total_margin() + net
                closed_trades.append(_tdict(pos, date, ep, h, net, g, f, s, fd, "DEFENSIVE_DD"))
            positions = []

        # DD defense reset — FIX: reset after 10 days, not waiting for RISK-OFF
        if defensive_mode and defensive_start_date:
            days_in_defense = (date - defensive_start_date).days
            if days_in_defense >= DD_DEFENSE_RESET_DAYS:
                defensive_mode = False
                defensive_start_date = None
                peak_equity = cash  # reset peak to avoid ratchet
                print(f"  [{date.date()}] DEFENSIVE RESET — peak=${peak_equity:.2f}, back to trading")

        # RISK-OFF — close all
        if regime == "RISK-OFF" and positions:
            for pos in list(positions):
                sym_df = asset_dfs[pos.symbol]
                row = sym_df[sym_df["date"] == date]
                if row.empty: continue
                ep = row.iloc[0]["close"]
                h = (date - pos.entry_date).days
                net, g, f, s, fd = trade_pnl(pos, ep, h)
                cash += pos.total_margin() + net
                closed_trades.append(_tdict(pos, date, ep, h, net, g, f, s, fd, "RISK_OFF"))
            positions = []
            defensive_mode = False
            defensive_start_date = None
            peak_equity = cash

        # Exits
        for pos in list(positions):
            sym_df = asset_dfs[pos.symbol]
            row = sym_df[sym_df["date"] == date]
            if row.empty: continue
            r = row.iloc[0]
            ep = reason = None
            h = (date - pos.entry_date).days

            if not pd.isna(r["ma50"]) and r["close"] < r["ma50"]:
                ep, reason = r["close"], "BELOW_MA50"
            elif not pd.isna(r["rsi"]) and r["rsi"] > RSI_EXIT_MAX:
                ep, reason = r["close"], "RSI_OVERBOUGHT"
            elif h >= MAX_HOLD_DAYS:
                ep, reason = r["close"], "TIME_STOP"
            elif pos.stop_price and r["close"] < pos.stop_price:
                ep, reason = r["close"], "BREAKEVEN_STOP"

            if ep is not None:
                net, g, f, s, fd = trade_pnl(pos, ep, h)
                cash += pos.total_margin() + net
                closed_trades.append(_tdict(pos, date, ep, h, net, g, f, s, fd, reason))
                positions.remove(pos)

        # Pyramiding
        if regime in ("RISK-ON", "TRANSITION") and not defensive_mode:
            for pos in positions:
                if pos.added or pos.symbol not in asset_dfs: continue
                sym_df = asset_dfs[pos.symbol]
                row = sym_df[sym_df["date"] == date]
                if row.empty: continue
                r = row.iloc[0]
                avg = pos.avg_entry()
                if r["close"] <= avg: continue
                gain = (r["close"] - avg) / avg * 100

                if (pos.phase == "probe" and gain >= 3.0
                        and not pd.isna(r["rsi"]) and 55 <= r["rsi"] <= 70
                        and not pd.isna(r["ma20"]) and r["close"] > r["ma20"]):
                    add_cap = min(cash * CONFIRM_ADD_PCT, cash * 0.20)
                    if add_cap > 10 and cash > add_cap:
                        pos.entries.append((date, r["close"], add_cap * LEVERAGE_CONFIRM, LEVERAGE_CONFIRM, add_cap))
                        pos.phase = "confirm"
                        pos.leverage = LEVERAGE_CONFIRM
                        pos.stop_price = avg
                        cash -= add_cap
                        pos.added = True
                        print(f"  [{date.date()}] CONFIRM {pos.symbol} @ {r['close']:.2f} (+{gain:.1f}%)")

                elif (pos.phase == "confirm" and gain >= 8.0
                      and not pd.isna(r["rsi"]) and 60 <= r["rsi"] <= 72
                      and not pd.isna(r["ma50_slope_up"]) and bool(r["ma50_slope_up"])):
                    cur_pct = pos.total_margin() / (cash + pos.total_margin())
                    if cur_pct < MAX_POSITION_PCT:
                        add_cap = min(cash * JUGULAR_TARGET_PCT, cash * 0.30, (cash + pos.total_margin()) * MAX_POSITION_PCT - pos.total_margin())
                        if add_cap > 10 and cash > add_cap:
                            pos.entries.append((date, r["close"], add_cap * LEVERAGE_JUGULAR, LEVERAGE_JUGULAR, add_cap))
                            pos.phase = "jugular"
                            pos.leverage = LEVERAGE_JUGULAR
                            pos.stop_price = avg * 1.02
                            cash -= add_cap
                            pos.added = True
                            print(f"  [{date.date()}] JUGULAR {pos.symbol} @ {r['close']:.2f} (+{gain:.1f}%)")

        # Entries
        if not defensive_mode and regime in ("RISK-ON", "TRANSITION") and len(positions) < MAX_CONCURRENT:
            max_cap_pct = 0.10 if regime == "TRANSITION" else PROBE_MAX_PCT
            for sym in TRADEABLE:
                if len(positions) >= MAX_CONCURRENT: break
                if sym not in asset_dfs: continue
                if sym in last_trade_date and (date - last_trade_date[sym]).days < 3: continue
                sym_df = asset_dfs[sym]
                row = sym_df[sym_df["date"] == date]
                if row.empty: continue
                r = row.iloc[0]
                if pd.isna(r["ma20"]) or pd.isna(r["ma50"]) or pd.isna(r["rsi"]): continue
                if not (r["close"] > r["ma20"] and r["close"] > r["ma50"]): continue
                if not (bool(r["ma20_slope_up"]) and bool(r["ma50_slope_up"])): continue
                if not (RSI_ENTRY_MIN <= r["rsi"] <= RSI_ENTRY_MAX): continue
                if pd.isna(r["pullback_pct"]) or r["pullback_pct"] < PULLBACK_PCT: continue
                if is_choppy(r): continue
                trade_cap = min(cash * max_cap_pct, cash * 0.20)
                if trade_cap < 10: continue
                lev = LEVERAGE_PROBE
                pos = Position(sym, date, r["close"], trade_cap * lev, lev, "probe", regime)
                positions.append(pos)
                cash -= trade_cap
                last_trade_date[sym] = date
                print(f"  [{date.date()}] ENTRY {sym} @ {r['close']:.2f} (probe ${trade_cap:.0f}, RSI={r['rsi']:.1f})")

        equity_curve.append({
            "date": str(date.date()), "equity": round(mtm, 2),
            "cash": round(cash, 2), "positions": len(positions),
            "regime": regime, "drawdown_pct": round(dd * 100, 2),
        })

    # Close remaining
    last_date = dates.iloc[-1]
    for pos in list(positions):
        sym_df = asset_dfs[pos.symbol]
        row = sym_df[sym_df["date"] == last_date]
        if row.empty: row = sym_df.tail(1)
        ep = row.iloc[0]["close"]
        h = (last_date - pos.entry_date).days
        net, g, f, s, fd = trade_pnl(pos, ep, h)
        cash += pos.total_margin() + net
        closed_trades.append(_tdict(pos, last_date, ep, h, net, g, f, s, fd, "BACKTEST_END"))
    positions = []
    return closed_trades, equity_curve, cash

# ─────────────────────── Monte Carlo ───────────────────────

def monte_carlo(trades, start_capital, runs=10000):
    pnls = [t["net_pnl"] for t in trades]
    n = len(pnls)
    if n == 0: return {}
    bust_count = 0
    final_equities = []
    max_dds = []
    returns_list = []
    for _ in range(runs):
        shuffled = pnls.copy()
        random.shuffle(shuffled)
        equity = start_capital
        peak = start_capital
        bust = False
        max_dd = 0.0
        for pnl in shuffled:
            equity += pnl
            if equity <= 0:
                bust = True
                break
            if equity > peak: peak = equity
            dd = (peak - equity) / peak
            if dd > max_dd: max_dd = dd
        if bust:
            bust_count += 1
        else:
            final_equities.append(equity)
            max_dds.append(max_dd * 100)
            returns_list.append((equity - start_capital) / start_capital * 100)
    survival = (runs - bust_count) / runs * 100
    return {
        "runs": runs,
        "bust_count": bust_count,
        "survival_rate_pct": round(survival, 2),
        "return_p5": round(np.percentile(returns_list, 5), 2) if returns_list else 0,
        "return_p25": round(np.percentile(returns_list, 25), 2) if returns_list else 0,
        "return_median": round(np.percentile(returns_list, 50), 2) if returns_list else 0,
        "return_p75": round(np.percentile(returns_list, 75), 2) if returns_list else 0,
        "return_p95": round(np.percentile(returns_list, 95), 2) if returns_list else 0,
        "median_dd_pct": round(np.percentile(max_dds, 50), 2) if max_dds else 0,
        "p95_dd_pct": round(np.percentile(max_dds, 95), 2) if max_dds else 0,
        "worst_dd_pct": round(max(max_dds), 2) if max_dds else 0,
    }

# ─────────────────────── Metrics ───────────────────────

def compute_metrics(trades, equity_curve, start_capital):
    eq = pd.DataFrame(equity_curve)
    if eq.empty: return {}
    final = eq["equity"].iloc[-1]
    total_ret = (final - start_capital) / start_capital * 100
    eq["peak"] = eq["equity"].cummax()
    eq["dd"] = (eq["peak"] - eq["equity"]) / eq["peak"]
    max_dd = eq["dd"].max() * 100
    eq["ret"] = eq["equity"].pct_change().fillna(0)
    sharpe = eq["ret"].mean() / eq["ret"].std() * math.sqrt(252) if eq["ret"].std() > 0 else 0.0
    pnls = [t["net_pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    win_rate = len(wins) / len(pnls) * 100 if pnls else 0
    avg_win = statistics.mean(wins) if wins else 0
    avg_loss = statistics.mean(losses) if losses else 0
    pf = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else (float('inf') if wins else 0)
    if len(eq) > 1:
        years = len(eq) / 252
        annualized = ((final / start_capital) ** (1 / years) - 1) * 100 if years > 0 else total_ret
    else:
        annualized = total_ret
    return {
        "start_capital": start_capital,
        "final_equity": round(final, 2),
        "total_return_pct": round(total_ret, 2),
        "annualized_return_pct": round(annualized, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio": round(sharpe, 3),
        "num_trades": len(trades),
        "win_rate_pct": round(win_rate, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(pf, 3) if pf != float('inf') else 999.0,
        "best_trade": round(max(pnls), 2) if pnls else 0,
        "worst_trade": round(min(pnls), 2) if pnls else 0,
        "avg_hold_days": round(statistics.mean([t["hold_days"] for t in trades]), 1) if trades else 0,
        "total_costs": round(sum(t["fees"] + t["slippage"] + t["funding"] for t in trades), 2),
        "total_gross_pnl": round(sum(t["gross_pnl"] for t in trades), 2),
        "total_net_pnl": round(sum(pnls), 2),
    }

def btc_hodl(all_data, start_capital):
    btc = all_data["BTC"].sort_values("date").reset_index(drop=True)
    if btc.empty: return {}
    entry = btc.iloc[0]["close"]
    exit_ = btc.iloc[-1]["close"]
    btc["peak"] = btc["close"].cummax()
    btc["dd"] = (btc["peak"] - btc["close"]) / btc["peak"]
    return {
        "btc_entry_price": round(entry, 2),
        "btc_exit_price": round(exit_, 2),
        "final_equity": round(start_capital * (exit_ / entry), 2),
        "total_return_pct": round((exit_ / entry - 1) * 100, 2),
        "max_drawdown_pct": round(btc["dd"].max() * 100, 2),
        "start_date": str(btc.iloc[0]["date"].date()),
        "end_date": str(btc.iloc[-1]["date"].date()),
    }

# ─────────────────────── Main ───────────────────────

def main():
    print("=" * 80)
    print("BBA ROUND 13 — 5-YEAR LIVE R4C STRATEGY — PULLBACK 10%")
    print("=" * 80)

    print("\nLoading 5 years of market data...")
    all_data = load_all_data()
    print(f"  {len(all_data)} assets loaded\n")

    print("Building regime classification...")
    regime_df = build_regime(all_data)
    regime_counts = regime_df["regime"].value_counts()
    print(f"  Regime distribution: {dict(regime_counts)}\n")

    print("Running 5-year backtest...")
    print("-" * 80)
    trades, equity_curve, final_equity = run_backtest(all_data, regime_df)
    print("-" * 80)
    print(f"  {len(trades)} trades closed over 5 years.\n")

    metrics = compute_metrics(trades, equity_curve, START_CAPITAL)
    benchmark = btc_hodl(all_data, START_CAPITAL)

    print("=" * 80)
    print("ROUND 13 RESULTS — LIVE R4C STRATEGY, 5 YEAR")
    print("=" * 80)
    print(f"  Period:             {benchmark.get('start_date','')} → {benchmark.get('end_date','')}")
    print(f"  Start Capital:      ${START_CAPITAL:,.2f}")
    print(f"  Final Equity:       ${metrics.get('final_equity', 0):,.2f}")
    print(f"  Total Return:       {metrics.get('total_return_pct', 0):.2f}%")
    print(f"  Annualized Return:  {metrics.get('annualized_return_pct', 0):.2f}%")
    print(f"  Max Drawdown:       {metrics.get('max_drawdown_pct', 0):.2f}%")
    print(f"  Sharpe Ratio:       {metrics.get('sharpe_ratio', 0):.3f}")
    print(f"  Num Trades:         {metrics.get('num_trades', 0)}")
    print(f"  Win Rate:           {metrics.get('win_rate_pct', 0):.2f}%")
    print(f"  Avg Win:            ${metrics.get('avg_win', 0):,.2f}")
    print(f"  Avg Loss:           ${metrics.get('avg_loss', 0):,.2f}")
    print(f"  Profit Factor:      {metrics.get('profit_factor', 0):.3f}")
    print(f"  Best Trade:         ${metrics.get('best_trade', 0):,.2f}")
    print(f"  Worst Trade:        ${metrics.get('worst_trade', 0):,.2f}")
    print(f"  Avg Hold Days:      ${metrics.get('avg_hold_days', 0):.1f}")
    print(f"  Total Costs:        ${metrics.get('total_costs', 0):,.2f}")
    print(f"  Gross P&L:          ${metrics.get('total_gross_pnl', 0):,.2f}")
    print(f"  Net P&L:            ${metrics.get('total_net_pnl', 0):,.2f}")

    print(f"\n  BTC HODL 5yr:       {benchmark.get('total_return_pct', 0):.2f}%")
    diff = metrics.get('total_return_pct', 0) - benchmark.get('total_return_pct', 0)
    print(f"  vs BTC HODL:        {diff:+.2f}%")

    # Per-year breakdown
    print(f"\n{'='*80}")
    print("PER-YEAR BREAKDOWN")
    print("=" * 80)
    eq = pd.DataFrame(equity_curve)
    if not eq.empty:
        eq["date"] = pd.to_datetime(eq["date"])
        eq["year"] = eq["date"].dt.year
        for year, year_eq in eq.groupby("year"):
            year_start = year_eq.iloc[0]["equity"]
            year_end = year_eq.iloc[-1]["equity"]
            year_ret = (year_end - year_start) / year_start * 100 if year_start > 0 else 0
            year_peak = year_eq["equity"].cummax()
            year_dd = ((year_peak - year_eq["equity"]) / year_peak).max() * 100
            year_trades = [t for t in trades if t["entry_date"][:4] == str(year)]
            print(f"  {year}: return={year_ret:+.2f}%, max_dd={year_dd:.2f}%, trades={len(year_trades)}")

    # Trades
    print(f"\n{'='*80}")
    print("ALL TRADES")
    print("=" * 80)
    print(f"{'#':>3} {'Entry':>12} {'Exit':>12} {'Symbol':>8} {'Phase':>8} {'EntryPx':>10} {'ExitPx':>10} {'P&L':>10} {'Ret%':>7} {'Hold':>5} {'Regime':>10} {'Exit':>16}")
    print("-" * 130)
    for i, t in enumerate(trades, 1):
        print(f"{i:>3} {t['entry_date']:>12} {t['exit_date']:>12} {t['symbol']:>8} {t['phase']:>8} "
              f"{t['entry_price']:>10.2f} {t['exit_price']:>10.2f} {t['net_pnl']:>+10.2f} "
              f"{t['return_pct']:>+7.2f} {t['hold_days']:>5} {t['regime_at_entry']:>10} {t['exit_reason']:>16}")

    # Monte Carlo
    print(f"\n{'='*80}")
    print(f"MONTE CARLO SIMULATION ({MONTE_CARLO_RUNS:,} runs)")
    print("=" * 80)
    mc = monte_carlo(trades, START_CAPITAL, MONTE_CARLO_RUNS)
    print(f"  Survival Rate:     {mc.get('survival_rate_pct', 0):.2f}% ({mc.get('bust_count',0)} busts)")
    print(f"  Return — 5th pct:  {mc.get('return_p5', 0):.2f}%")
    print(f"  Return — 25th pct: {mc.get('return_p25', 0):.2f}%")
    print(f"  Return — Median:   {mc.get('return_median', 0):.2f}%")
    print(f"  Return — 75th pct: {mc.get('return_p75', 0):.2f}%")
    print(f"  Return — 95th pct: {mc.get('return_p95', 0):.2f}%")
    print(f"  Max DD — Median:   {mc.get('median_dd_pct', 0):.2f}%")
    print(f"  Max DD — 95th pct: {mc.get('p95_dd_pct', 0):.2f}%")
    print(f"  Max DD — Worst:    {mc.get('worst_dd_pct', 0):.2f}%")

    # Shield
    dd = metrics.get("max_drawdown_pct", 0)
    nt = metrics.get("num_trades", 0)
    veto = dd > 30 or nt > 250
    print(f"\n  Shield: DD={dd:.2f}% trades={nt} → {'VETO' if veto else 'PASS'}")

    # Save
    results = {
        "test_id": "round13-5yr-pullback10",
        "description": "Live R4C strategy (chop filter + regime + pyramiding) over 5 years with DD defense fix",
        "fix_from_r7": "DD defense now resets after 10 days in cash instead of waiting for RISK-OFF. Peak equity reset on recovery to avoid ratchet.",
        "config": {
            "start_capital": START_CAPITAL,
            "rsi_exit_max": RSI_EXIT_MAX,
            "max_hold_days": MAX_HOLD_DAYS,
            "be_stop": "entry (R4C baseline)",
            "universe": TRADEABLE,
            "dd_defense_reset_days": DD_DEFENSE_RESET_DAYS,
            "chop_filter": {"atr_period": ATR_PERIOD, "atr_median_bars": ATR_MEDIAN_BARS, "ema_gap_min_pct": EMA_GAP_MIN_PCT},
        },
        "regime_distribution": {k: int(v) for k, v in regime_counts.items()},
        "metrics": metrics,
        "benchmark_btc_hodl": benchmark,
        "monte_carlo": mc,
        "shield": {"dd_limit_pct": 30, "trades_limit": 250, "veto": veto, "dd": dd, "trades": nt},
        "trades": trades,
        "equity_curve": equity_curve,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {OUTPUT_JSON}")
    print("=" * 80)

if __name__ == "__main__":
    main()
