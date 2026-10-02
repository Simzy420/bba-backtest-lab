#!/usr/bin/env python3
"""
BBA Backtest — Round 8: Support Bounce + Resistance Breakout + Momentum
=========================================================================
New strategy (not Druckenmiller macro). Pure price action:

ENTRY A — Support Bounce:
  - Price touches/bounces off 20-day swing low (within 1.5% of 20-day low)
  - Closes ABOVE that support level (bounce confirmed)
  - RSI between 35-55 (oversold to neutral — coming off a dip)
  - Price above 50-day MA (long-term trend still intact)
  → Buy the bounce

ENTRY B — Resistance Breakout:
  - Price closes ABOVE 20-day swing high (breakout)
  - Volume/momentum confirmation: RSI between 55-72 (strong but not overbought)
  - Price above 20-day AND 50-day MA (both sloping up)
  → Buy the breakout

EXIT:
  - Stop loss: 3% below entry (hard stop, no hoping)
  - RSI > 75 (overbought, take profits)
  - Price drops below 50-day MA
  - Time stop: 20 days
  - 20% portfolio DD → go to cash, BUT reset defensive mode after 5 days (bug fix)

UNIVERSE: BTC, ETH, SOL, NVDA, GOLD (crypto perps + select assets)
PERIOD: 5 years (Oct 2021 - Oct 2026)
COSTS: Full Hyperliquid fees + slippage + funding
"""

import json
import math
import statistics
import random
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf

# ─────────────────────── Config ───────────────────────

START_CAPITAL = 1663.0
LEVERAGE = 3  # single leverage for all entries

# Support/Bounce params
SWING_LOOKBACK = 20       # days to look back for swing high/low
SUPPORT_PROXIMITY_PCT = 1.5  # within 1.5% of 20-day low = "at support"
BOUNCE_CONFIRMATION = True   # must close above support

# Breakout params
BREAKOUT_LOOKBACK = 20    # 20-day high to break through

# Momentum params
RSI_PERIOD = 14
RSI_BOUNCE_MIN = 35       # support bounce: RSI 35-55 (coming off oversold)
RSI_BOUNCE_MAX = 55
RSI_BREAKOUT_MIN = 55     # breakout: RSI 55-72 (strong momentum)
RSI_BREAKOUT_MAX = 72
RSI_EXIT_MAX = 75         # take profits when overbought

# MAs
MA_SHORT = 20
MA_LONG = 50

# Risk management
STOP_LOSS_PCT = 3.0       # 3% hard stop below entry
MAX_HOLD_DAYS = 20        # shorter — momentum plays are faster
MAX_CONCURRENT = 3        # allow 3 concurrent (more trades expected)
MAX_POSITION_PCT = 0.30   # max 30% per position
MIN_POSITION_PCT = 0.05   # min 5% per position
DD_DEFENSE_THRESHOLD = 0.20
DD_DEFENSE_RESET_DAYS = 5 # bug fix: reset defensive mode after 5 days in cash

# Hyperliquid costs
FEE_BPS = 4.5
SLIPPAGE_BPS = 4.5
FUNDING_RATES = {
    "BTC": 0.0001, "ETH": 0.0001, "SOL": 0.0002,
    "GOLD": 0.0001, "NVDA": 0.0001,
}

YF_TICKERS = {
    "BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD",
    "GOLD": "GC=F", "NVDA": "NVDA",
}
TRADEABLE = ["BTC", "ETH", "SOL", "NVDA", "GOLD"]

DATA_PERIOD = "5y"
OUTPUT_JSON = "/workspace/bba-backtest-lab/bba-results/round8-support-breakout-momentum.json"
MONTE_CARLO_RUNS = 10000

# ─────────────────────── Data ───────────────────────

def fetch_yf(ticker, period):
    t = yf.Ticker(ticker)
    df = t.history(period=period, auto_adjust=True)
    if df.empty:
        raise RuntimeError(f"yfinance empty for {ticker}")
    df = df.reset_index()
    df["date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    return df[["date", "open", "high", "low", "close", "volume"]].sort_values("date").reset_index(drop=True)

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

def add_indicators(df):
    df = df.copy()
    df["ma20"] = df["close"].rolling(MA_SHORT).mean()
    df["ma50"] = df["close"].rolling(MA_LONG).mean()
    df["rsi"] = compute_rsi(df["close"], RSI_PERIOD)
    df["ma20_slope_up"] = df["ma20"] > df["ma20"].shift(3)
    df["ma50_slope_up"] = df["ma50"] > df["ma50"].shift(5)
    # Swing high/low (20-day)
    df["swing_high"] = df["close"].rolling(SWING_LOOKBACK).max()
    df["swing_low"] = df["close"].rolling(SWING_LOOKBACK).min()
    # Previous swing high/low (exclude today to detect breakout/bounce)
    df["prev_swing_high"] = df["close"].shift(1).rolling(SWING_LOOKBACK).max()
    df["prev_swing_low"] = df["close"].shift(1).rolling(SWING_LOOKBACK).min()
    # Distance from support (as %)
    df["dist_from_low_pct"] = (df["close"] - df["prev_swing_low"]) / df["prev_swing_low"] * 100
    # Volume momentum (5-day avg vs 20-day avg)
    df["vol_5d"] = df["volume"].rolling(5).mean() if "volume" in df.columns else 1
    df["vol_20d"] = df["volume"].rolling(20).mean() if "volume" in df.columns else 1
    df["vol_ratio"] = df["vol_5d"] / df["vol_20d"].replace(0, np.nan)
    df["vol_ratio"] = df["vol_ratio"].fillna(1.0)
    return df

# ─────────────────────── Position ───────────────────────

class Position:
    def __init__(self, symbol, entry_date, entry_price, notional, leverage, entry_type, regime_at_entry):
        self.symbol = symbol
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.notional = notional
        self.leverage = leverage
        self.entry_type = entry_type  # "SUPPORT_BOUNCE" or "RESISTANCE_BREAKOUT"
        self.regime_at_entry = regime_at_entry
        self.stop_price = entry_price * (1 - STOP_LOSS_PCT / 100)
        self.funding_paid = 0.0

def calc_funding(symbol, notional, hold_days):
    return notional * FUNDING_RATES.get(symbol, 0.0001) * hold_days * 3

def trade_pnl(pos, exit_price, hold_days):
    gross = (exit_price - pos.entry_price) / pos.entry_price * pos.notional
    fees = pos.notional * (FEE_BPS / 10000) * 2
    slip = pos.notional * (SLIPPAGE_BPS / 10000) * 2
    funding = calc_funding(pos.symbol, pos.notional, hold_days)
    net = gross - fees - slip - funding
    return net, gross, fees, slip, funding

def _tdict(pos, exit_date, exit_price, hold_days, net, gross, fees, slip, funding, reason):
    margin = pos.notional / pos.leverage
    return {
        "entry_date": str(pos.entry_date.date()),
        "exit_date": str(exit_date.date()),
        "symbol": pos.symbol,
        "side": "LONG",
        "entry_type": pos.entry_type,
        "entry_price": round(pos.entry_price, 4),
        "exit_price": round(exit_price, 4),
        "notional": round(pos.notional, 2),
        "leverage": pos.leverage,
        "hold_days": hold_days,
        "stop_price": round(pos.stop_price, 4),
        "gross_pnl": round(gross, 2),
        "fees": round(fees, 2),
        "slippage": round(slip, 2),
        "funding": round(funding, 2),
        "net_pnl": round(net, 2),
        "return_pct": round(net / margin * 100, 2),
        "exit_reason": reason,
    }

# ─────────────────────── Engine ───────────────────────

def run_backtest(all_data):
    asset_dfs = {}
    for sym in TRADEABLE:
        df = add_indicators(all_data[sym])
        asset_dfs[sym] = df

    # Master calendar from BTC (most data)
    dates = asset_dfs["BTC"]["date"].sort_values().reset_index(drop=True)
    if len(dates) > MA_LONG + SWING_LOOKBACK:
        dates = dates[dates >= dates.iloc[MA_LONG + SWING_LOOKBACK]]

    cash = START_CAPITAL
    peak_equity = START_CAPITAL
    positions = []
    closed_trades = []
    equity_curve = []
    defensive_mode = False
    defensive_start_date = None
    last_trade_date = {}

    for date in dates:
        # MTM
        unrealized = 0.0
        locked = 0.0
        for pos in positions:
            sym_df = asset_dfs.get(pos.symbol)
            if sym_df is None: continue
            row = sym_df[sym_df["date"] == date]
            if row.empty: continue
            cur = row.iloc[0]["close"]
            unrealized += (cur - pos.entry_price) / pos.entry_price * pos.notional
            locked += pos.notional / pos.leverage

        mtm = cash + locked + unrealized
        if mtm > peak_equity: peak_equity = mtm
        dd = (peak_equity - mtm) / peak_equity if peak_equity > 0 else 0

        # DD defense — close all and go to cash
        if dd >= DD_DEFENSE_THRESHOLD and not defensive_mode:
            defensive_mode = True
            defensive_start_date = date
            print(f"  [{date.date()}] DEFENSIVE MODE (DD={dd*100:.1f}%) — closing all")
            for pos in list(positions):
                sym_df = asset_dfs[pos.symbol]
                row = sym_df[sym_df["date"] == date]
                if row.empty: continue
                ep = row.iloc[0]["close"]
                h = (date - pos.entry_date).days
                net, g, f, s, fd = trade_pnl(pos, ep, h)
                cash += (pos.notional / pos.leverage) + net
                closed_trades.append(_tdict(pos, date, ep, h, net, g, f, s, fd, "DEFENSIVE_DD"))
            positions = []

        # DD defense reset: reset peak equity when coming out of defensive mode
        # This prevents the infinite re-trigger loop
        if defensive_mode and defensive_start_date:
            days_in_defense = (date - defensive_start_date).days
            if days_in_defense >= DD_DEFENSE_RESET_DAYS:
                defensive_mode = False
                defensive_start_date = None
                # Reset peak equity to current cash — this is the key fix
                # Without this, old peak makes DD always > 20%
                peak_equity = cash
                print(f"  [{date.date()}] DEFENSIVE MODE RESET — peak reset to ${peak_equity:.2f}, back to trading")

        # Exit checks for open positions
        for pos in list(positions):
            sym_df = asset_dfs[pos.symbol]
            row = sym_df[sym_df["date"] == date]
            if row.empty: continue
            r = row.iloc[0]
            ep = reason = None
            h = (date - pos.entry_date).days

            # 1. Hard stop loss (3%)
            if r["close"] <= pos.stop_price:
                ep, reason = r["close"], "STOP_LOSS"
            # 2. Below 50-day MA
            elif not pd.isna(r["ma50"]) and r["close"] < r["ma50"]:
                ep, reason = r["close"], "BELOW_MA50"
            # 3. RSI overbought
            elif not pd.isna(r["rsi"]) and r["rsi"] > RSI_EXIT_MAX:
                ep, reason = r["close"], "RSI_OVERBOUGHT"
            # 4. Time stop
            elif h >= MAX_HOLD_DAYS:
                ep, reason = r["close"], "TIME_STOP"

            if ep is not None:
                net, g, f, s, fd = trade_pnl(pos, ep, h)
                cash += (pos.notional / pos.leverage) + net
                closed_trades.append(_tdict(pos, date, ep, h, net, g, f, s, fd, reason))
                positions.remove(pos)

        # Entry scans
        if not defensive_mode and len(positions) < MAX_CONCURRENT:
            for sym in TRADEABLE:
                if len(positions) >= MAX_CONCURRENT: break
                if sym not in asset_dfs: continue
                if sym in last_trade_date and (date - last_trade_date[sym]).days < 2: continue

                sym_df = asset_dfs[sym]
                row = sym_df[sym_df["date"] == date]
                if row.empty: continue
                r = row.iloc[0]

                if pd.isna(r["ma20"]) or pd.isna(r["ma50"]) or pd.isna(r["rsi"]): continue
                if pd.isna(r["prev_swing_high"]) or pd.isna(r["prev_swing_low"]): continue

                entry_type = None

                # ENTRY A: Support Bounce
                # Price within 1.5% of 20-day low AND closes above it
                # RSI 35-55 (coming off oversold)
                # Price above 50-day MA (trend intact)
                dist_from_low = r["dist_from_low_pct"]
                if (dist_from_low <= SUPPORT_PROXIMITY_PCT and dist_from_low >= -0.5  # at or near support
                        and r["close"] > r["prev_swing_low"]  # bounced, closed above
                        and RSI_BOUNCE_MIN <= r["rsi"] <= RSI_BOUNCE_MAX
                        and r["close"] > r["ma50"]  # long-term trend intact
                        and r["vol_ratio"] > 0.8):  # some volume
                    entry_type = "SUPPORT_BOUNCE"

                # ENTRY B: Resistance Breakout
                # Price closes ABOVE 20-day high
                # RSI 55-72 (strong momentum, not overbought)
                # Both MAs sloping up
                elif (r["close"] > r["prev_swing_high"]  # broke above resistance
                        and RSI_BREAKOUT_MIN <= r["rsi"] <= RSI_BREAKOUT_MAX
                        and r["close"] > r["ma20"] and r["close"] > r["ma50"]  # above both MAs
                        and bool(r["ma20_slope_up"])  # short-term trend up
                        and r["vol_ratio"] > 1.0):  # volume confirming breakout
                    entry_type = "RESISTANCE_BREAKOUT"

                if entry_type is None: continue

                # Position sizing
                position_pct = min(MAX_POSITION_PCT, max(MIN_POSITION_PCT, 0.15))  # 15% default
                trade_cap = cash * position_pct
                if trade_cap < 10: continue

                notional = trade_cap * LEVERAGE
                pos = Position(sym, date, r["close"], notional, LEVERAGE, entry_type, "N/A")
                positions.append(pos)
                cash -= trade_cap
                last_trade_date[sym] = date
                print(f"  [{date.date()}] {entry_type} {sym} @ {r['close']:.2f} (${trade_cap:.0f}, lev={LEVERAGE}x, RSI={r['rsi']:.1f}, stop={pos.stop_price:.2f})")

        equity_curve.append({
            "date": str(date.date()), "equity": round(mtm, 2),
            "cash": round(cash, 2), "positions": len(positions),
            "drawdown_pct": round(dd * 100, 2),
            "defensive": defensive_mode,
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
        cash += (pos.notional / pos.leverage) + net
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
    # Entry type breakdown
    bounce_trades = [t for t in trades if t["entry_type"] == "SUPPORT_BOUNCE"]
    breakout_trades = [t for t in trades if t["entry_type"] == "RESISTANCE_BREAKOUT"]
    bounce_pnl = sum(t["net_pnl"] for t in bounce_trades)
    breakout_pnl = sum(t["net_pnl"] for t in breakout_trades)
    bounce_wins = len([t for t in bounce_trades if t["net_pnl"] > 0])
    breakout_wins = len([t for t in breakout_trades if t["net_pnl"] > 0])
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
        "support_bounce": {
            "trades": len(bounce_trades),
            "wins": bounce_wins,
            "win_rate": round(bounce_wins / len(bounce_trades) * 100, 2) if bounce_trades else 0,
            "net_pnl": round(bounce_pnl, 2),
        },
        "resistance_breakout": {
            "trades": len(breakout_trades),
            "wins": breakout_wins,
            "win_rate": round(breakout_wins / len(breakout_trades) * 100, 2) if breakout_trades else 0,
            "net_pnl": round(breakout_pnl, 2),
        },
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
    print("BBA ROUND 8 — Support Bounce + Resistance Breakout + Momentum (5-Year)")
    print("=" * 80)

    print("\nLoading 5 years of market data...")
    all_data = load_all_data()
    print(f"  {len(all_data)} assets loaded\n")

    print("Running 5-year backtest...")
    print("-" * 80)
    trades, equity_curve, final_equity = run_backtest(all_data)
    print("-" * 80)
    print(f"  {len(trades)} trades closed over 5 years.\n")

    metrics = compute_metrics(trades, equity_curve, START_CAPITAL)
    benchmark = btc_hodl(all_data, START_CAPITAL)

    print("=" * 80)
    print("ROUND 8 RESULTS — 5 YEAR")
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
    print(f"  Avg Hold Days:      {metrics.get('avg_hold_days', 0):.1f}")
    print(f"  Total Costs:        ${metrics.get('total_costs', 0):,.2f}")
    print(f"  Net P&L:            ${metrics.get('total_net_pnl', 0):,.2f}")

    sb = metrics.get("support_bounce", {})
    rb = metrics.get("resistance_breakout", {})
    print(f"\n  ENTRY TYPE BREAKDOWN:")
    print(f"    Support Bounce:    {sb.get('trades',0)} trades, {sb.get('wins',0)} wins ({sb.get('win_rate',0):.1f}% WR), P&L ${sb.get('net_pnl',0):.2f}")
    print(f"    Resistance Break:  {rb.get('trades',0)} trades, {rb.get('wins',0)} wins ({rb.get('win_rate',0):.1f}% WR), P&L ${rb.get('net_pnl',0):.2f}")

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
    print(f"{'#':>3} {'Entry':>12} {'Exit':>12} {'Symbol':>8} {'Type':>18} {'EntryPx':>10} {'ExitPx':>10} {'P&L':>10} {'Ret%':>7} {'Hold':>5} {'Exit':>14}")
    print("-" * 130)
    for i, t in enumerate(trades, 1):
        print(f"{i:>3} {t['entry_date']:>12} {t['exit_date']:>12} {t['symbol']:>8} {t['entry_type']:>18} "
              f"{t['entry_price']:>10.2f} {t['exit_price']:>10.2f} {t['net_pnl']:>+10.2f} "
              f"{t['return_pct']:>+7.2f} {t['hold_days']:>5} {t['exit_reason']:>14}")

    # Monte Carlo
    print(f"\n{'='*80}")
    print(f"MONTE CARLO SIMULATION ({MONTE_CARLO_RUNS:,} runs)")
    print("=" * 80)
    mc = monte_carlo(trades, START_CAPITAL, MONTE_CARLO_RUNS)
    print(f"  Survival Rate:     {mc.get('survival_rate_pct', 0):.2f}% ({mc.get('bust_count',0)} busts)")
    print(f"  Return — 5th pct:  {mc.get('return_p5', 0):.2f}%")
    print(f"  Return — Median:   {mc.get('return_median', 0):.2f}%")
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
        "test_id": "round8-support-breakout-momentum",
        "description": "Support bounce + resistance breakout + momentum, 5-year, crypto perps",
        "strategy": {
            "entry_a": "Support bounce: price within 1.5% of 20-day low, closes above, RSI 35-55, above 50MA",
            "entry_b": "Resistance breakout: closes above 20-day high, RSI 55-72, both MAs up, volume confirm",
            "exits": ["3% hard stop", "below 50MA", "RSI > 75", "20-day time stop", "20% DD defense (5-day reset)"],
        },
        "config": {
            "start_capital": START_CAPITAL,
            "leverage": LEVERAGE,
            "stop_loss_pct": STOP_LOSS_PCT,
            "max_hold_days": MAX_HOLD_DAYS,
            "max_concurrent": MAX_CONCURRENT,
            "swing_lookback": SWING_LOOKBACK,
            "support_proximity_pct": SUPPORT_PROXIMITY_PCT,
            "universe": TRADEABLE,
            "dd_defense_reset_days": DD_DEFENSE_RESET_DAYS,
        },
        "metrics": metrics,
        "benchmark_btc_hodl": benchmark,
        "monte_carlo": mc,
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
