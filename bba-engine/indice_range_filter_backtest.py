#!/usr/bin/env python3
"""
Indice Range Filter Strategy — Proper Backtest with Real Costs
================================================================
Original: github.com/junaid-mahmood/Indice-Trading-Strategy
Claimed: 69.81% win rate, 12.55% profit, 4.87% DD on S&P 500 (2020-2024)

Strategy:
- EMA 200 for trend direction
- Range filter: EMA of abs(price changes) × 3.5 multiplier, period 20
- Long: price > filter, price rising, filter direction up, close > EMA200
- Short: price < filter, price falling, filter direction down, close < EMA200
- 1% stop loss, 1% take profit
- 0.075% commission

This version tests on S&P 500 and Nasdaq with real perp costs for comparison.
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
LEVERAGE = 3
POSITION_PCT = 0.10

EMA_LENGTH = 200
RNG_PERIOD = 20
RNG_MULTIPLIER = 3.5

STOP_LOSS_PCT = 1.0  # 1% stop
TAKE_PROFIT_PCT = 1.0  # 1% take profit

# Use the original's commission for fair comparison
COMMISSION_PCT = 0.075  # 0.075% per trade (matching original)
# Also test with Hyperliquid perp costs
FEE_BPS = 4.5
SLIPPAGE_BPS = 4.5
FUNDING_RATE = 0.0001  # per 8h
FUNDING_PERIODS_PER_DAY = 3

OUTPUT_JSON = "/workspace/bba-backtest-lab/bba-results/indice-range-filter-backtest.json"

# Test on multiple assets
TEST_ASSETS = {
    "^GSPC": ("^GSPC", "S&P 500", "2020-01-01"),
    "^NDX": ("^NDX", "Nasdaq 100", "2020-01-01"),
    "GC=F": ("GC=F", "Gold", "2020-01-01"),
}

# ─────────────────────── Data ───────────────────────

def fetch_data(ticker, start_date):
    print(f"  Fetching {ticker}...")
    t = yf.Ticker(ticker)
    df = t.history(period="5y", auto_adjust=True)
    if df.empty:
        raise RuntimeError(f"yfinance empty for {ticker}")
    df = df.reset_index()
    df["date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"})
    return df[["date", "open", "high", "low", "close"]].sort_values("date").reset_index(drop=True)

# ─────────────────────── Indicators ───────────────────────

def add_indicators(df):
    df = df.copy()
    df["ema200"] = df["close"].ewm(span=EMA_LENGTH, adjust=False).mean()
    
    # Range filter
    df["abs_change"] = (df["close"] - df["close"].shift(1)).abs()
    df["avrng"] = df["abs_change"].ewm(span=RNG_PERIOD, adjust=False).mean()
    wper = RNG_PERIOD * 2 - 1
    df["ac"] = df["avrng"].ewm(span=wper, adjust=False).mean() * RNG_MULTIPLIER
    
    # Range filter calculation (stateful)
    rfilt = [df["close"].iloc[0]]
    for i in range(1, len(df)):
        x = df["close"].iloc[i]
        r = df["ac"].iloc[i]
        prev = rfilt[-1]
        if x - r > prev:
            rfilt.append(x - r)
        elif x + r < prev:
            rfilt.append(x + r)
        else:
            rfilt.append(prev)
    
    df["rfilt"] = rfilt
    df["h_band"] = df["rfilt"] + df["ac"]
    df["l_band"] = df["rfilt"] - df["ac"]
    
    # Direction
    df["fdir"] = 0.0
    for i in range(1, len(df)):
        if df["rfilt"].iloc[i] > df["rfilt"].iloc[i-1]:
            df.loc[df.index[i], "fdir"] = 1.0
        elif df["rfilt"].iloc[i] < df["rfilt"].iloc[i-1]:
            df.loc[df.index[i], "fdir"] = -1.0
        else:
            df.loc[df.index[i], "fdir"] = df["fdir"].iloc[i-1]
    
    df["upward"] = (df["fdir"] == 1).astype(int)
    df["downward"] = (df["fdir"] == -1).astype(int)
    
    # Entry conditions
    df["long_cond"] = (
        (df["close"] > df["rfilt"]) & 
        (df["close"] > df["close"].shift(1)) & 
        (df["upward"] > 0)
    ) | (
        (df["close"] > df["rfilt"]) & 
        (df["close"] < df["close"].shift(1)) & 
        (df["upward"] > 0)
    )
    
    df["short_cond"] = (
        (df["close"] < df["rfilt"]) & 
        (df["close"] < df["close"].shift(1)) & 
        (df["downward"] > 0)
    ) | (
        (df["close"] < df["rfilt"]) & 
        (df["close"] > df["close"].shift(1)) & 
        (df["downward"] > 0)
    )
    
    # State machine for entries (only enter when direction flips)
    cond_ini = [0]
    for i in range(1, len(df)):
        if df["long_cond"].iloc[i]:
            cond_ini.append(1)
        elif df["short_cond"].iloc[i]:
            cond_ini.append(-1)
        else:
            cond_ini.append(cond_ini[-1])
    df["cond_ini"] = cond_ini
    
    df["long_signal"] = df["long_cond"] & (df["cond_ini"].shift(1) == -1)
    df["short_signal"] = df["short_cond"] & (df["cond_ini"].shift(1) == 1)
    
    # Trend filter
    df["long_allowed"] = df["close"] > df["ema200"]
    df["short_allowed"] = df["close"] < df["ema200"]
    
    return df

# ─────────────────────── Backtest ───────────────────────

def run_backtest(df, start_capital, use_hl_costs=True):
    cash = start_capital
    trades = []
    position = None  # {"side": "LONG"/"SHORT", "entry_price", "entry_date", "notional", "margin", "stop", "tp"}
    
    for i in range(EMA_LENGTH, len(df)):
        row = df.iloc[i]
        
        # Check exits first
        if position:
            entry = position
            hold_days = (row["date"] - entry["entry_date"]).days
            
            if entry["side"] == "LONG":
                if row["low"] <= entry["stop"]:
                    exit_price = entry["stop"]
                    reason = "STOP_LOSS"
                elif row["high"] >= entry["tp"]:
                    exit_price = entry["tp"]
                    reason = "TAKE_PROFIT"
                else:
                    continue
                
                gross = (exit_price - entry["entry_price"]) / entry["entry_price"] * entry["notional"]
            else:
                if row["high"] >= entry["stop"]:
                    exit_price = entry["stop"]
                    reason = "STOP_LOSS"
                elif row["low"] <= entry["tp"]:
                    exit_price = entry["tp"]
                    reason = "TAKE_PROFIT"
                else:
                    continue
                
                gross = (entry["entry_price"] - exit_price) / entry["entry_price"] * entry["notional"]
            
            if use_hl_costs:
                fees = entry["notional"] * (FEE_BPS / 10000) * 2
                slip = entry["notional"] * (SLIPPAGE_BPS / 10000) * 2
                funding = entry["notional"] * FUNDING_RATE * FUNDING_PERIODS_PER_DAY * max(hold_days, 1)
            else:
                fees = entry["notional"] * (COMMISSION_PCT / 100) * 2
                slip = 0
                funding = 0
            
            net = gross - fees - slip - funding
            cash += entry["margin"] + net
            
            trades.append({
                "entry_date": str(entry["entry_date"].date()),
                "exit_date": str(row["date"].date()),
                "side": entry["side"],
                "entry_price": round(entry["entry_price"], 2),
                "exit_price": round(exit_price, 2),
                "notional": round(entry["notional"], 2),
                "margin": round(entry["margin"], 2),
                "hold_days": hold_days,
                "gross_pnl": round(gross, 2),
                "fees": round(fees + slip + funding, 2),
                "net_pnl": round(net, 2),
                "is_win": net > 0,
                "exit_reason": reason,
            })
            position = None
        
        # Check entries
        if position is None:
            margin = cash * POSITION_PCT
            notional = margin * LEVERAGE
            
            if row["long_signal"] and row["long_allowed"]:
                position = {
                    "side": "LONG",
                    "entry_price": row["close"],
                    "entry_date": row["date"],
                    "notional": notional,
                    "margin": margin,
                    "stop": row["close"] * (1 - STOP_LOSS_PCT / 100),
                    "tp": row["close"] * (1 + TAKE_PROFIT_PCT / 100),
                }
                cash -= margin
            
            elif row["short_signal"] and row["short_allowed"]:
                position = {
                    "side": "SHORT",
                    "entry_price": row["close"],
                    "entry_date": row["date"],
                    "notional": notional,
                    "margin": margin,
                    "stop": row["close"] * (1 + STOP_LOSS_PCT / 100),
                    "tp": row["close"] * (1 - TAKE_PROFIT_PCT / 100),
                }
                cash -= margin
    
    # Close remaining position
    if position:
        row = df.iloc[-1]
        if position["side"] == "LONG":
            gross = (row["close"] - position["entry_price"]) / position["entry_price"] * position["notional"]
        else:
            gross = (position["entry_price"] - row["close"]) / position["entry_price"] * position["notional"]
        hold_days = (row["date"] - position["entry_date"]).days
        if use_hl_costs:
            fees = position["notional"] * (FEE_BPS / 10000) * 2
            slip = position["notional"] * (SLIPPAGE_BPS / 10000) * 2
            funding = position["notional"] * FUNDING_RATE * FUNDING_PERIODS_PER_DAY * max(hold_days, 1)
        else:
            fees = position["notional"] * (COMMISSION_PCT / 100) * 2
            slip = 0
            funding = 0
        net = gross - fees - slip - funding
        cash += position["margin"] + net
        trades.append({
            "entry_date": str(position["entry_date"].date()),
            "exit_date": str(row["date"].date()),
            "side": position["side"],
            "entry_price": round(position["entry_price"], 2),
            "exit_price": round(row["close"], 2),
            "notional": round(position["notional"], 2),
            "margin": round(position["margin"], 2),
            "hold_days": hold_days,
            "gross_pnl": round(gross, 2),
            "fees": round(fees + slip + funding, 2),
            "net_pnl": round(net, 2),
            "is_win": net > 0,
            "exit_reason": "BACKTEST_END",
        })
    
    return trades, cash

# ─────────────────────── Metrics ───────────────────────

def compute_metrics(trades, start_capital):
    if not trades:
        return {"error": "No trades"}
    pnls = [t["net_pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    total_net = sum(pnls)
    final_equity = start_capital + total_net
    win_rate = len(wins) / len(trades) * 100
    avg_win = statistics.mean(wins) if wins else 0
    avg_loss = statistics.mean(losses) if losses else 0
    pf = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else 999
    equity = start_capital
    peak = start_capital
    max_dd = 0
    for pnl in pnls:
        equity += pnl
        if equity > peak: peak = equity
        dd = (peak - equity) / peak if peak > 0 else 0
        if dd > max_dd: max_dd = dd
    total_costs = sum(t["fees"] for t in trades)
    longs = [t for t in trades if t["side"] == "LONG"]
    shorts = [t for t in trades if t["side"] == "SHORT"]
    long_wins = sum(1 for t in longs if t["is_win"])
    short_wins = sum(1 for t in shorts if t["is_win"])
    return {
        "final_equity": round(final_equity, 2),
        "total_return_pct": round((final_equity - start_capital) / start_capital * 100, 2),
        "num_trades": len(trades),
        "win_rate_pct": round(win_rate, 2),
        "wins": len(wins), "losses": len(losses),
        "avg_win": round(avg_win, 2), "avg_loss": round(avg_loss, 2),
        "profit_factor": round(pf, 3),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "best_trade": round(max(pnls), 2), "worst_trade": round(min(pnls), 2),
        "total_costs": round(total_costs, 2),
        "total_net_pnl": round(total_net, 2),
        "long_trades": len(longs), "long_win_rate": round(long_wins/len(longs)*100, 2) if longs else 0,
        "short_trades": len(shorts), "short_win_rate": round(short_wins/len(shorts)*100, 2) if shorts else 0,
        "avg_hold_days": round(statistics.mean([t["hold_days"] for t in trades]), 1),
    }

# ─────────────────────── Monte Carlo ───────────────────────

def monte_carlo(trades, start_capital, runs=10000):
    pnls = [t["net_pnl"] for t in trades]
    if not pnls: return {}
    bust_count = 0
    final_equities = []
    max_dds = []
    for _ in range(runs):
        shuffled = pnls.copy()
        random.shuffle(shuffled)
        equity = start_capital
        peak = start_capital
        bust = False
        max_dd = 0
        for pnl in shuffled:
            equity += pnl
            if equity <= 0:
                bust = True
                break
            if equity > peak: peak = equity
            dd = (peak - equity) / peak
            if dd > max_dd: max_dd = dd
        if bust: bust_count += 1
        else:
            final_equities.append(equity)
            max_dds.append(max_dd * 100)
    survival = (runs - bust_count) / runs * 100
    returns = [(e - start_capital) / start_capital * 100 for e in final_equities]
    return {
        "runs": runs, "survival_rate_pct": round(survival, 2), "bust_count": bust_count,
        "return_median": round(np.median(returns), 2) if returns else 0,
        "median_dd": round(np.median(max_dds), 2) if max_dds else 0,
        "p95_dd": round(np.percentile(max_dds, 95), 2) if max_dds else 0,
    }

# ─────────────────────── Main ───────────────────────

def main():
    print("=" * 80)
    print("INDICE RANGE FILTER STRATEGY — BACKTEST WITH REAL COSTS")
    print("Original: github.com/junaid-mahmood/Indice-Trading-Strategy")
    print("Claimed: 69.81% WR, 12.55% profit, 4.87% DD on S&P 500 (2020-2024)")
    print("=" * 80)
    
    all_results = {}
    
    for ticker_key, (yf_ticker, name, start) in TEST_ASSETS.items():
        print(f"\n{'='*80}")
        print(f"Testing on: {name} ({yf_ticker})")
        print(f"{'='*80}")
        
        try:
            df = fetch_data(yf_ticker, start)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue
        
        df = add_indicators(df)
        
        # Test with original costs (0.075% commission, no slippage/funding)
        print(f"\n  --- Original costs (0.075% commission only) ---")
        trades_orig, cash_orig = run_backtest(df, START_CAPITAL, use_hl_costs=False)
        metrics_orig = compute_metrics(trades_orig, START_CAPITAL)
        
        print(f"  Trades: {metrics_orig['num_trades']}")
        print(f"  Win Rate: {metrics_orig['win_rate_pct']}%")
        print(f"  Return: {metrics_orig['total_return_pct']}%")
        print(f"  Max DD: {metrics_orig['max_drawdown_pct']}%")
        print(f"  Profit Factor: {metrics_orig['profit_factor']}")
        print(f"  Avg Win: ${metrics_orig['avg_win']}, Avg Loss: ${metrics_orig['avg_loss']}")
        print(f"  Longs: {metrics_orig['long_trades']} ({metrics_orig['long_win_rate']}% WR)")
        print(f"  Shorts: {metrics_orig['short_trades']} ({metrics_orig['short_win_rate']}% WR)")
        print(f"  Avg Hold: {metrics_orig['avg_hold_days']} days")
        
        # Test with Hyperliquid perp costs
        print(f"\n  --- Hyperliquid perp costs (4.5bps + 4.5bps slip + funding) ---")
        trades_hl, cash_hl = run_backtest(df, START_CAPITAL, use_hl_costs=True)
        metrics_hl = compute_metrics(trades_hl, START_CAPITAL)
        
        print(f"  Trades: {metrics_hl['num_trades']}")
        print(f"  Win Rate: {metrics_hl['win_rate_pct']}%")
        print(f"  Return: {metrics_hl['total_return_pct']}%")
        print(f"  Max DD: {metrics_hl['max_drawdown_pct']}%")
        print(f"  Profit Factor: {metrics_hl['profit_factor']}")
        print(f"  Costs: ${metrics_hl['total_costs']}")
        print(f"  Net P&L: ${metrics_hl['total_net_pnl']}")
        
        # Monte Carlo
        mc = monte_carlo(trades_hl, START_CAPITAL)
        print(f"\n  Monte Carlo: {mc['survival_rate_pct']}% survival, median DD {mc['median_dd']}%")
        
        all_results[name] = {
            "original_costs": metrics_orig,
            "hl_costs": metrics_hl,
            "monte_carlo": mc,
        }
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY: CLAIMED vs REALITY")
    print("=" * 80)
    print(f"{'Asset':<15} {'Claimed WR':>12} {'Orig WR':>10} {'HL WR':>10} {'Claimed Ret':>12} {'Orig Ret':>10} {'HL Ret':>10}")
    print("-" * 80)
    
    claimed_wr = 69.81
    claimed_ret = 12.55
    claimed_dd = 4.87
    
    for name, res in all_results.items():
        orig = res["original_costs"]
        hl = res["hl_costs"]
        print(f"{name:<15} {claimed_wr:>12}% {orig['win_rate_pct']:>9.2f}% {hl['win_rate_pct']:>9.2f}% {claimed_ret:>11.2f}% {orig['total_return_pct']:>9.2f}% {hl['total_return_pct']:>9.2f}%")
    
    # Save
    results = {
        "test_id": "indice-range-filter-backtest",
        "original_source": "github.com/junaid-mahmood/Indice-Trading-Strategy",
        "original_claimed_win_rate": 69.81,
        "original_claimed_return": 12.55,
        "original_claimed_dd": 4.87,
        "results": all_results,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved to {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
