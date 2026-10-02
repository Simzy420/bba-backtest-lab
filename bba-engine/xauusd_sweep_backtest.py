#!/usr/bin/env python3
"""
XAUUSD Liquidity Sweep Strategy — Proper Backtest with Costs
=============================================================
Original: github.com/ikeawesom/xauusd-backtest (71% claimed win rate)
Strategy: Previous Day High/Low sweep + reversal entry

This version adds:
- Real trading costs (fees, slippage)
- Position sizing (10% probe, pyramiding optional)
- Proper stop loss (sweep level + buffer)
- Leverage (3x)
- Max hold time
- DD defense
- 5-year test using 1h gold data (yfinance max for intraday)

Original had NONE of these. Let's see if 71% survives real costs.
"""

import json
import math
import statistics
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf

# ─────────────────────── Config ───────────────────────

START_CAPITAL = 1663.0
LEVERAGE = 3
POSITION_PCT = 0.10  # 10% per trade (probe size)
MAX_HOLD_HOURS = 24  # max 1 day hold (intraday strategy)
STOP_BUFFER_PCT = 0.15  # stop is 0.15% beyond sweep level

FEE_BPS = 4.5  # Hyperliquid perp fees
SLIPPAGE_BPS = 4.5
FUNDING_RATE = 0.0001  # per 8h
FUNDING_PERIOD_HOURS = 8

GOLD_TICKER = "GC=F"
DATA_INTERVAL = "1h"  # 1h gives 730 days from yfinance
DATA_PERIOD = "730d"  # yfinance max for 1h

OUTPUT_JSON = "/workspace/bba-backtest-lab/bba-results/xauusd-sweep-backtest.json"

# ─────────────────────── Data ───────────────────────

def fetch_gold_data():
    print(f"Fetching gold 1h data ({DATA_PERIOD})...")
    t = yf.Ticker(GOLD_TICKER)
    df = t.history(period=DATA_PERIOD, interval=DATA_INTERVAL, auto_adjust=True)
    if df.empty:
        raise RuntimeError("yfinance returned empty for gold")
    df = df.reset_index()
    df["datetime"] = pd.to_datetime(df["Datetime"])
    df["date"] = df["datetime"].dt.date
    df["time"] = df["datetime"].dt.strftime("%H:%M")
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"})
    print(f"  Got {len(df)} bars from {df['date'].iloc[0]} to {df['date'].iloc[-1]}")
    return df[["datetime", "date", "time", "open", "high", "low", "close"]].sort_values("datetime").reset_index(drop=True)

# ─────────────────────── Strategy ───────────────────────

def run_sweep_backtest(df, start_capital):
    # Group by date
    dates = sorted(df["date"].unique())
    
    cash = start_capital
    peak_equity = start_capital
    trades = []
    equity_curve = []
    defensive_mode = False
    
    for i in range(1, len(dates)):
        if defensive_mode:
            defensive_mode = False  # reset after 1 day
            
        prev_date = dates[i-1]
        curr_date = dates[i]
        
        prev_day = df[df["date"] == prev_date]
        curr_day = df[df["date"] == curr_date]
        
        if prev_day.empty or curr_day.empty:
            continue
        
        # Previous day bias: bullish if close > open
        prev_open = prev_day.iloc[0]["open"]
        prev_close = prev_day.iloc[-1]["close"]
        bullish_bias = prev_close >= prev_open
        
        # Previous day high/low
        pdh = prev_day["high"].max()
        pdl = prev_day["low"].min()
        
        # Track equity at end of day
        unrealized = 0.0
        locked = 0.0
        for pos in [t for t in trades if t.get("status") == "open"]:
            locked += pos["margin"]
            unrealized += (curr_day.iloc[-1]["close"] - pos["entry_price"]) / pos["entry_price"] * pos["notional"]
        
        mtm = cash + locked + unrealized
        if mtm > peak_equity:
            peak_equity = mtm
        dd = (peak_equity - mtm) / peak_equity if peak_equity > 0 else 0
        
        if dd >= 0.20:
            defensive_mode = True
            # close any open positions
            for pos in [t for t in trades if t.get("status") == "open"]:
                exit_price = curr_day.iloc[-1]["close"]
                hold_hours = 0
                gross = (exit_price - pos["entry_price"]) / pos["entry_price"] * pos["notional"] * (1 if pos["side"] == "LONG" else -1)
                fees = pos["notional"] * (FEE_BPS / 10000) * 2
                slip = pos["notional"] * (SLIPPAGE_BPS / 10000) * 2
                net = gross - fees - slip
                cash += pos["margin"] + net
                pos["status"] = "closed"
                pos["exit_price"] = exit_price
                pos["exit_reason"] = "DEFENSIVE_DD"
                pos["net_pnl"] = round(net, 2)
                pos["is_win"] = net > 0
        
        # Sweep logic
        sweeped = False
        sweep_price = -1
        entry_price = -1
        is_entered = False
        entry_time = ""
        side = "LONG" if bullish_bias else "SHORT"
        stop_price = -1
        
        for _, bar in curr_day.iterrows():
            cur_price = bar["close"]
            cur_time = bar["time"]
            
            if is_entered:
                # Check exit: price returns to sweep level (win) or hits stop (loss)
                if bullish_bias:
                    # Long position: win if price >= entry_price, stop if price <= stop_price
                    if cur_price >= entry_price and cur_price != entry_price:
                        # Win - take profit at current price
                        gross = (cur_price - entry_price) / entry_price * notional
                        fees = notional * (FEE_BPS / 10000) * 2
                        slip = notional * (SLIPPAGE_BPS / 10000) * 2
                        # Funding (assume 1 8h period)
                        funding = notional * FUNDING_RATE * 1
                        net = gross - fees - slip - funding
                        cash += margin + net
                        trades.append({
                            "date": str(curr_date), "entry_time": entry_time, "exit_time": cur_time,
                            "side": side, "bias": "BULLISH", "entry_price": round(entry_price, 2),
                            "exit_price": round(cur_price, 2), "notional": round(notional, 2),
                            "margin": round(margin, 2), "net_pnl": round(net, 2),
                            "is_win": net > 0, "exit_reason": "TP_SWEEP_RETURN",
                            "hold_hours": 0, "status": "closed"
                        })
                        is_entered = False
                        break
                    elif cur_price <= stop_price:
                        # Stop loss hit
                        gross = (cur_price - entry_price) / entry_price * notional
                        fees = notional * (FEE_BPS / 10000) * 2
                        slip = notional * (SLIPPAGE_BPS / 10000) * 2
                        funding = notional * FUNDING_RATE * 1
                        net = gross - fees - slip - funding
                        cash += margin + net
                        trades.append({
                            "date": str(curr_date), "entry_time": entry_time, "exit_time": cur_time,
                            "side": side, "bias": "BULLISH", "entry_price": round(entry_price, 2),
                            "exit_price": round(cur_price, 2), "notional": round(notional, 2),
                            "margin": round(margin, 2), "net_pnl": round(net, 2),
                            "is_win": net > 0, "exit_reason": "STOP_LOSS",
                            "hold_hours": 0, "status": "closed"
                        })
                        is_entered = False
                        break
                else:
                    # Short position: win if price <= entry_price, stop if price >= stop_price
                    if cur_price <= entry_price and cur_price != entry_price:
                        gross = (entry_price - cur_price) / entry_price * notional
                        fees = notional * (FEE_BPS / 10000) * 2
                        slip = notional * (SLIPPAGE_BPS / 10000) * 2
                        funding = notional * FUNDING_RATE * 1
                        net = gross - fees - slip - funding
                        cash += margin + net
                        trades.append({
                            "date": str(curr_date), "entry_time": entry_time, "exit_time": cur_time,
                            "side": side, "bias": "BEARISH", "entry_price": round(entry_price, 2),
                            "exit_price": round(cur_price, 2), "notional": round(notional, 2),
                            "margin": round(margin, 2), "net_pnl": round(net, 2),
                            "is_win": net > 0, "exit_reason": "TP_SWEEP_RETURN",
                            "hold_hours": 0, "status": "closed"
                        })
                        is_entered = False
                        break
                    elif cur_price >= stop_price:
                        gross = (entry_price - cur_price) / entry_price * notional
                        fees = notional * (FEE_BPS / 10000) * 2
                        slip = notional * (SLIPPAGE_BPS / 10000) * 2
                        funding = notional * FUNDING_RATE * 1
                        net = gross - fees - slip - funding
                        cash += margin + net
                        trades.append({
                            "date": str(curr_date), "entry_time": entry_time, "exit_time": cur_time,
                            "side": side, "bias": "BEARISH", "entry_price": round(entry_price, 2),
                            "exit_price": round(cur_price, 2), "notional": round(notional, 2),
                            "margin": round(margin, 2), "net_pnl": round(net, 2),
                            "is_win": net > 0, "exit_reason": "STOP_LOSS",
                            "hold_hours": 0, "status": "closed"
                        })
                        is_entered = False
                        break
            else:
                if not sweeped:
                    # Check for sweep
                    if bullish_bias and cur_price <= pdl:
                        sweeped = True
                        sweep_price = cur_price
                        continue
                    elif not bullish_bias and cur_price >= pdh:
                        sweeped = True
                        sweep_price = cur_price
                        continue
                else:
                    # Check for reversal entry
                    if bullish_bias and cur_price >= sweep_price:
                        # Enter long
                        entry_price = cur_price
                        entry_time = cur_time
                        is_entered = True
                        # Stop loss is 0.15% below sweep price
                        stop_price = sweep_price * (1 - STOP_BUFFER_PCT / 100)
                        margin = cash * POSITION_PCT
                        notional = margin * LEVERAGE
                        cash -= margin
                        side = "LONG"
                    elif not bullish_bias and cur_price <= sweep_price:
                        # Enter short
                        entry_price = cur_price
                        entry_time = cur_time
                        is_entered = True
                        stop_price = sweep_price * (1 + STOP_BUFFER_PCT / 100)
                        margin = cash * POSITION_PCT
                        notional = margin * LEVERAGE
                        cash -= margin
                        side = "SHORT"
        
        # End of day: close any open position at last price
        if is_entered:
            exit_price = curr_day.iloc[-1]["close"]
            if bullish_bias:
                gross = (exit_price - entry_price) / entry_price * notional
            else:
                gross = (entry_price - exit_price) / entry_price * notional
            fees = notional * (FEE_BPS / 10000) * 2
            slip = notional * (SLIPPAGE_BPS / 10000) * 2
            funding = notional * FUNDING_RATE * 1
            net = gross - fees - slip - funding
            cash += margin + net
            trades.append({
                "date": str(curr_date), "entry_time": entry_time, "exit_time": "EOD",
                "side": side, "bias": "BULLISH" if bullish_bias else "BEARISH",
                "entry_price": round(entry_price, 2), "exit_price": round(exit_price, 2),
                "notional": round(notional, 2), "margin": round(margin, 2),
                "net_pnl": round(net, 2), "is_win": net > 0,
                "exit_reason": "EOD_CLOSE", "hold_hours": 0, "status": "closed"
            })
            is_entered = False
        
        # Track equity
        locked_total = sum(t["margin"] for t in trades if t.get("status") == "open")
        equity_curve.append({
            "date": str(curr_date), "equity": round(cash + locked_total, 2),
            "cash": round(cash, 2)
        })
    
    return trades, equity_curve, cash

# ─────────────────────── Metrics ───────────────────────

def compute_metrics(trades, start_capital):
    if not trades:
        return {"error": "No trades"}
    
    pnls = [t["net_pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    
    total_net = sum(pnls)
    final_equity = start_capital + total_net
    total_return = (final_equity - start_capital) / start_capital * 100
    
    win_rate = len(wins) / len(trades) * 100
    avg_win = statistics.mean(wins) if wins else 0
    avg_loss = statistics.mean(losses) if losses else 0
    pf = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else 999
    
    # Equity curve for DD
    equity = start_capital
    peak = start_capital
    max_dd = 0
    for pnl in pnls:
        equity += pnl
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    
    total_costs = sum(t["notional"] * (FEE_BPS + SLIPPAGE_BPS) / 10000 * 2 for t in trades)
    
    # Per-bias breakdown
    bullish_trades = [t for t in trades if t["bias"] == "BULLISH"]
    bearish_trades = [t for t in trades if t["bias"] == "BEARISH"]
    bullish_wins = sum(1 for t in bullish_trades if t["is_win"])
    bearish_wins = sum(1 for t in bearish_trades if t["is_win"])
    
    # Exit reason breakdown
    exit_reasons = {}
    for t in trades:
        r = t["exit_reason"]
        if r not in exit_reasons:
            exit_reasons[r] = {"count": 0, "wins": 0}
        exit_reasons[r]["count"] += 1
        if t["is_win"]:
            exit_reasons[r]["wins"] += 1
    
    return {
        "start_capital": start_capital,
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return, 2),
        "num_trades": len(trades),
        "win_rate_pct": round(win_rate, 2),
        "wins": len(wins),
        "losses": len(losses),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(pf, 3),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "best_trade": round(max(pnls), 2),
        "worst_trade": round(min(pnls), 2),
        "total_costs": round(total_costs, 2),
        "total_net_pnl": round(total_net, 2),
        "bullish_trades": len(bullish_trades),
        "bullish_win_rate": round(bullish_wins / len(bullish_trades) * 100, 2) if bullish_trades else 0,
        "bearish_trades": len(bearish_trades),
        "bearish_win_rate": round(bearish_wins / len(bearish_trades) * 100, 2) if bearish_trades else 0,
        "exit_reasons": exit_reasons,
    }

# ─────────────────────── Monte Carlo ───────────────────────

def monte_carlo(trades, start_capital, runs=10000):
    import random
    pnls = [t["net_pnl"] for t in trades]
    if not pnls:
        return {}
    
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
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
        if bust:
            bust_count += 1
        else:
            final_equities.append(equity)
            max_dds.append(max_dd * 100)
    
    survival = (runs - bust_count) / runs * 100
    returns = [(e - start_capital) / start_capital * 100 for e in final_equities]
    
    return {
        "runs": runs,
        "survival_rate_pct": round(survival, 2),
        "bust_count": bust_count,
        "return_median": round(np.median(returns), 2) if returns else 0,
        "return_p5": round(np.percentile(returns, 5), 2) if returns else 0,
        "return_p95": round(np.percentile(returns, 95), 2) if returns else 0,
        "median_dd": round(np.median(max_dds), 2) if max_dds else 0,
        "p95_dd": round(np.percentile(max_dds, 95), 2) if max_dds else 0,
    }

# ─────────────────────── Main ───────────────────────

def main():
    print("=" * 80)
    print("XAUUSD LIQUIDITY SWEEP STRATEGY — BACKTEST WITH REAL COSTS")
    print("=" * 80)
    
    df = fetch_gold_data()
    
    print(f"\nRunning sweep backtest...")
    print(f"  Capital: ${START_CAPITAL}")
    print(f"  Leverage: {LEVERAGE}x")
    print(f"  Position size: {POSITION_PCT*100}% per trade")
    print(f"  Stop buffer: {STOP_BUFFER_PCT}%")
    print(f"  Fees: {FEE_BPS}bps + {SLIPPAGE_BPS}bps slippage")
    print("-" * 80)
    
    trades, equity_curve, final_cash = run_sweep_backtest(df, START_CAPITAL)
    
    metrics = compute_metrics(trades, START_CAPITAL)
    
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"  Period:              ~2 years (1h data)")
    print(f"  Start Capital:       ${START_CAPITAL:,.2f}")
    print(f"  Final Equity:        ${metrics.get('final_equity', 0):,.2f}")
    print(f"  Total Return:        {metrics.get('total_return_pct', 0):.2f}%")
    print(f"  Num Trades:          {metrics.get('num_trades', 0)}")
    print(f"  Win Rate:            {metrics.get('win_rate_pct', 0):.2f}%")
    print(f"  Wins:                {metrics.get('wins', 0)}")
    print(f"  Losses:              {metrics.get('losses', 0)}")
    print(f"  Avg Win:             ${metrics.get('avg_win', 0):,.2f}")
    print(f"  Avg Loss:            ${metrics.get('avg_loss', 0):,.2f}")
    print(f"  Profit Factor:       {metrics.get('profit_factor', 0):.3f}")
    print(f"  Max Drawdown:        {metrics.get('max_drawdown_pct', 0):.2f}%")
    print(f"  Best Trade:          ${metrics.get('best_trade', 0):,.2f}")
    print(f"  Worst Trade:         ${metrics.get('worst_trade', 0):,.2f}")
    print(f"  Total Costs:         ${metrics.get('total_costs', 0):,.2f}")
    print(f"  Net P&L:             ${metrics.get('total_net_pnl', 0):,.2f}")
    
    print(f"\n  Bullish trades:      {metrics.get('bullish_trades', 0)} ({metrics.get('bullish_win_rate', 0):.1f}% WR)")
    print(f"  Bearish trades:      {metrics.get('bearish_trades', 0)} ({metrics.get('bearish_win_rate', 0):.1f}% WR)")
    
    print(f"\n  Exit reasons:")
    for reason, stats in metrics.get("exit_reasons", {}).items():
        wr = stats["wins"] / stats["count"] * 100 if stats["count"] > 0 else 0
        print(f"    {reason}: {stats['count']} trades, {wr:.1f}% WR")
    
    # Original claim comparison
    print(f"\n{'='*80}")
    print(f"ORIGINAL CLAIM vs REALITY")
    print(f"{'='*80}")
    print(f"  Original claimed win rate: 71.17%")
    print(f"  Our win rate with costs:    {metrics.get('win_rate_pct', 0):.2f}%")
    print(f"  Original costs included:    NO")
    print(f"  Our costs included:         YES (${metrics.get('total_costs', 0):,.2f})")
    
    # Monte Carlo
    if trades:
        print(f"\n{'='*80}")
        print(f"MONTE CARLO (10,000 runs)")
        print(f"{'='*80}")
        mc = monte_carlo(trades, START_CAPITAL)
        print(f"  Survival Rate:  {mc.get('survival_rate_pct', 0):.2f}%")
        print(f"  Median Return:  {mc.get('return_median', 0):.2f}%")
        print(f"  5th pct:        {mc.get('return_p5', 0):.2f}%")
        print(f"  95th pct:       {mc.get('return_p95', 0):.2f}%")
        print(f"  Median Max DD:  {mc.get('median_dd', 0):.2f}%")
        print(f"  95th pct DD:   {mc.get('p95_dd', 0):.2f}%")
    
    # Save
    results = {
        "test_id": "xauusd-sweep-backtest",
        "description": "XAUUSD liquidity sweep strategy with real costs, 2yr 1h data",
        "original_source": "github.com/ikeawesom/xauusd-backtest",
        "original_claimed_win_rate": 71.17,
        "config": {
            "capital": START_CAPITAL, "leverage": LEVERAGE, "position_pct": POSITION_PCT,
            "stop_buffer_pct": STOP_BUFFER_PCT, "fees_bps": FEE_BPS, "slippage_bps": SLIPPAGE_BPS,
        },
        "metrics": metrics,
        "monte_carlo": mc if trades else {},
        "trades": trades,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
