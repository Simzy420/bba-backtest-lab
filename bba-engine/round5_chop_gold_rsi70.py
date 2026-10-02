#!/usr/bin/env python3
"""
BBA Backtest — Round 5: Chop Filter + GOLD Overweight + RSI Exit 70
==================================================================
Baseline: Round 4C (chop filter, shipped 2026-09-16)
Changes from R4C:
  1. GOLD probe size: 15% instead of 10% (GOLD was best trade in R3/R4)
  2. RSI exit: 70 instead of 75 (take profits earlier, don't give back gains)
  3. Fresh data: latest 365 days (out-of-sample vs R3/R4 which ran Sep 2025-Sep 2026)

Chop filter (from R4C):
  - Skip NEW entries/probes when ATR%(14) < 20-bar median on that symbol
    OR |EMA20-EMA50|/close < 0.4%
  - Existing positions NOT force-exited for chop
  - Applies to new entries/new probes only

All other rules from R3 baseline: regime filter, pyramiding, costs, universe, DD defense.
"""

import json
import time
import math
import statistics
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests
import yfinance as yf

# ─────────────────────── Configuration ───────────────────────

START_CAPITAL = 1663.0
LEVERAGE_PROBE = 2
LEVERAGE_CONFIRM = 3
LEVERAGE_JUGULAR = 3
MAX_LEVERAGE = 3

MA_SHORT = 20
MA_LONG = 50
RSI_PERIOD = 14
RSI_ENTRY_MIN = 40
RSI_ENTRY_MAX = 65
RSI_EXIT_MAX = 70  # ← R5 CHANGE: was 75 in R3/R4

VIX_RISK_ON = 20.0
VIX_RISK_OFF = 25.0
TNX_TOLERANCE_BPS = 15.0

PULLBACK_PCT = 2.0
PULLBACK_HIGH_LOOKBACK = 5

MAX_CONCURRENT = 2
MAX_HOLD_DAYS = 30
MAX_POSITION_PCT = 0.50

DD_DEFENSE_THRESHOLD = 0.20

PROBE_MIN_PCT = 0.05
PROBE_MAX_PCT = 0.10
CONFIRM_ADD_PCT = 0.15
JUGULAR_TARGET_PCT = 0.40

# R5 CHANGE: GOLD gets 15% probe instead of 10%
GOLD_PROBE_PCT = 0.15

# Chop filter params (from R4C)
ATR_PERIOD = 14
ATR_MEDIAN_BARS = 20
EMA_GAP_MIN_PCT = 0.004  # 0.4%

# Hyperliquid costs
FEE_BPS = 4.5
SLIPPAGE_BPS = 4.5
FUNDING_RATES = {
    "BTC": 0.0001, "ETH": 0.0001, "SOL": 0.0002,
    "GOLD": 0.0001, "NVDA": 0.0001, "TSLA": 0.0001, "^GSPC": 0.0001,
}

YF_TICKERS = {
    "GOLD": "GC=F", "NVDA": "NVDA", "TSLA": "TSLA",
    "^GSPC": "^GSPC", "^VIX": "^VIX", "^TNX": "^TNX",
}
CG_IDS = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}

OUTPUT_JSON = "/workspace/bba-backtest-lab/bba-results/round5-chop-gold-rsi70.json"

# ─────────────────────── Data Fetching ───────────────────────

def fetch_coingecko_daily(coin_id, days=365):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    params = {"vs_currency": "usd", "days": str(days)}
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, timeout=20)
            if r.status_code == 429:
                time.sleep(10 + attempt * 5)
                continue
            r.raise_for_status()
            data = r.json()
            df = pd.DataFrame(data, columns=["date", "open", "high", "low", "close"])
            df["date"] = pd.to_datetime(df["date"], unit="ms", utc=True).dt.tz_localize(None)
            df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
            return df
        except Exception as e:
            print(f"  [CoinGecko] {coin_id} attempt {attempt+1} error: {e}")
            time.sleep(5 + attempt * 5)
    raise RuntimeError(f"CoinGecko failed for {coin_id}")

def fetch_yfinance_daily(ticker, period="1y"):
    t = yf.Ticker(ticker)
    df = t.history(period=period, auto_adjust=True)
    if df.empty:
        raise RuntimeError(f"yfinance empty for {ticker}")
    df = df.reset_index()
    df["date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None) if df["Date"].dt.tz is not None else pd.to_datetime(df["Date"])
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"})
    df = df[["date", "open", "high", "low", "close"]].sort_values("date").reset_index(drop=True)
    return df

def load_all_data():
    all_data = {}
    yf_crypto_fallback = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD"}
    for sym, cid in CG_IDS.items():
        print(f"Fetching {sym} (CoinGecko)...")
        try:
            df = fetch_coingecko_daily(cid, 365)
            df["symbol"] = sym
            all_data[sym] = df
        except RuntimeError:
            print(f"  CoinGecko failed, yfinance fallback for {sym}")
            df = fetch_yfinance_daily(yf_crypto_fallback[sym], "1y")
            df["symbol"] = sym
            all_data[sym] = df
        time.sleep(2)
    for sym, tk in YF_TICKERS.items():
        print(f"Fetching {sym} (yfinance {tk})...")
        df = fetch_yfinance_daily(tk, "1y")
        df["symbol"] = sym
        all_data[sym] = df
        time.sleep(0.5)
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
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
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
    # Chop filter indicators
    df["atr"] = compute_atr(df, ATR_PERIOD)
    df["atr_pct"] = df["atr"] / df["close"] * 100
    df["atr_median"] = df["atr_pct"].rolling(ATR_MEDIAN_BARS).median()
    df["ema_gap_pct"] = (df["ema20"] - df["ema50"]).abs() / df["close"]
    return df

# ─────────────────────── Regime Classification ───────────────────────

def classify_regime(vix, spx_above_ma50, tnx_change_bps):
    risk_on = 0
    risk_off = 0
    if vix < VIX_RISK_ON:
        risk_on += 1
    elif vix > VIX_RISK_OFF:
        risk_off += 1
    if spx_above_ma50:
        risk_on += 1
    else:
        risk_off += 1
    if tnx_change_bps <= TNX_TOLERANCE_BPS:
        risk_on += 1
    else:
        risk_off += 1
    if risk_on >= 2 and risk_off == 0:
        return "RISK-ON"
    if risk_off >= 2:
        return "RISK-ON" if risk_on > risk_off else "RISK-OFF"
    return "TRANSITION"

def build_regime_series(all_data):
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
            continue
        regimes.append(classify_regime(row["vix"], bool(row["spx_above_ma50"]), row["tnx_chg_bps"]))
    regime["regime"] = regimes
    return regime[["date", "vix", "spx", "spx_ma50", "spx_above_ma50", "tnx", "tnx_chg_bps", "regime"]]

# ─────────────────────── Chop Filter ───────────────────────

def is_choppy(row):
    """Return True if this bar is 'choppy' — new entries should be skipped."""
    if pd.isna(row.get("atr_pct")) or pd.isna(row.get("atr_median")):
        return False  # not enough data — allow
    if row["atr_pct"] < row["atr_median"]:
        return True
    if pd.isna(row.get("ema_gap_pct")):
        return False
    if row["ema_gap_pct"] < EMA_GAP_MIN_PCT:
        return True
    return False

# ─────────────────────── Position & Trade Logic ───────────────────────

class Position:
    def __init__(self, symbol, entry_date, entry_price, notional, leverage, phase, regime_at_entry, capital_at_entry):
        self.symbol = symbol
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.notional = notional
        self.leverage = leverage
        self.phase = phase
        self.regime_at_entry = regime_at_entry
        self.capital_at_entry = capital_at_entry
        self.entries = [(entry_date, entry_price, notional, leverage, notional / leverage)]
        self.stop_price = None
        self.funding_paid = 0.0
        self.added = False

    def avg_entry_price(self):
        total_notional = sum(n for _, _, n, _, _ in self.entries)
        weighted = sum(p * n for _, p, n, _, _ in self.entries)
        return weighted / total_notional if total_notional > 0 else self.entry_price

    def total_notional(self):
        return sum(n for _, _, n, _, _ in self.entries)

    def total_margin(self):
        return sum(m for _, _, _, _, m in self.entries)

def calc_funding_cost(symbol, notional, hold_days):
    rate = FUNDING_RATES.get(symbol, 0.0001)
    return notional * rate * hold_days * 3

def trade_pnl(pos, exit_price, hold_days):
    avg_entry = pos.avg_entry_price()
    total_notional = pos.total_notional()
    gross = (exit_price - avg_entry) / avg_entry * total_notional
    fees = total_notional * (FEE_BPS / 10000) * 2
    slip = total_notional * (SLIPPAGE_BPS / 10000) * 2
    funding = calc_funding_cost(pos.symbol, total_notional, hold_days)
    net = gross - fees - slip - funding
    return net, gross, fees, slip, funding

# ─────────────────────── Backtest Engine ───────────────────────

def run_backtest(all_data, regime_df):
    asset_dfs = {}
    tradeable = ["BTC", "ETH", "SOL", "GOLD", "NVDA", "TSLA", "^GSPC"]
    for sym in tradeable:
        df = add_indicators(all_data[sym])
        df = df.merge(regime_df[["date", "regime"]], on="date", how="left")
        df["regime"] = df["regime"].ffill().fillna("TRANSITION")
        asset_dfs[sym] = df

    dates = regime_df["date"].drop_duplicates().sort_values().reset_index(drop=True)
    dates = dates[dates >= dates.iloc[MA_LONG]] if len(dates) > MA_LONG else dates

    equity = START_CAPITAL
    peak_equity = START_CAPITAL
    cash = START_CAPITAL
    positions = []
    closed_trades = []
    equity_curve = []
    defensive_mode = False
    last_trade_date = {}

    for i, date in enumerate(dates):
        reg_row = regime_df[regime_df["date"] == date]
        if reg_row.empty:
            continue
        regime = reg_row.iloc[0]["regime"]

        # MTM
        unrealized = 0.0
        locked_margin = 0.0
        for pos in positions:
            sym_df = asset_dfs.get(pos.symbol)
            if sym_df is None:
                continue
            row = sym_df[sym_df["date"] == date]
            if row.empty:
                continue
            cur_price = row.iloc[0]["close"]
            avg_entry = pos.avg_entry_price()
            total_notional = pos.total_notional()
            gross = (cur_price - avg_entry) / avg_entry * total_notional
            unrealized += gross
            locked_margin += pos.total_margin()

        mtm_equity = cash + locked_margin + unrealized
        if mtm_equity > peak_equity:
            peak_equity = mtm_equity
        dd = (peak_equity - mtm_equity) / peak_equity if peak_equity > 0 else 0

        # DD defense
        if dd >= DD_DEFENSE_THRESHOLD and not defensive_mode:
            defensive_mode = True
            print(f"  [{date.date()}] DEFENSIVE MODE (DD={dd*100:.1f}%)")
            for pos in list(positions):
                sym_df = asset_dfs[pos.symbol]
                row = sym_df[sym_df["date"] == date]
                if row.empty:
                    continue
                exit_price = row.iloc[0]["close"]
                hold_days = (date - pos.entry_date).days
                net, gross, fees, slip, funding = trade_pnl(pos, exit_price, hold_days)
                cash += pos.total_margin() + net
                closed_trades.append(_trade_dict(pos, date, exit_price, hold_days, net, gross, fees, slip, funding, "DEFENSIVE_DD"))
            positions = []

        # RISK-OFF → close all
        if regime == "RISK-OFF" and positions:
            for pos in list(positions):
                sym_df = asset_dfs[pos.symbol]
                row = sym_df[sym_df["date"] == date]
                if row.empty:
                    continue
                exit_price = row.iloc[0]["close"]
                hold_days = (date - pos.entry_date).days
                net, gross, fees, slip, funding = trade_pnl(pos, exit_price, hold_days)
                cash += pos.total_margin() + net
                closed_trades.append(_trade_dict(pos, date, exit_price, hold_days, net, gross, fees, slip, funding, "RISK_OFF"))
            positions = []
            defensive_mode = False

        # Exit checks
        for pos in list(positions):
            sym_df = asset_dfs[pos.symbol]
            row = sym_df[sym_df["date"] == date]
            if row.empty:
                continue
            r = row.iloc[0]
            exit_price = None
            reason = None
            hold_days = (date - pos.entry_date).days

            if not pd.isna(r["ma50"]) and r["close"] < r["ma50"]:
                exit_price = r["close"]
                reason = "BELOW_MA50"
            elif not pd.isna(r["rsi"]) and r["rsi"] > RSI_EXIT_MAX:  # R5: 70 not 75
                exit_price = r["close"]
                reason = "RSI_OVERBOUGHT"
            elif hold_days >= MAX_HOLD_DAYS:
                exit_price = r["close"]
                reason = "TIME_STOP"
            elif pos.stop_price and r["close"] < pos.stop_price:
                exit_price = r["close"]
                reason = "BREAKEVEN_STOP"

            if exit_price is not None:
                net, gross, fees, slip, funding = trade_pnl(pos, exit_price, hold_days)
                cash += pos.total_margin() + net
                closed_trades.append(_trade_dict(pos, date, exit_price, hold_days, net, gross, fees, slip, funding, reason))
                positions.remove(pos)

        # Pyramiding
        if regime in ("RISK-ON", "TRANSITION") and not defensive_mode:
            for pos in positions:
                if pos.added or pos.symbol not in asset_dfs:
                    continue
                sym_df = asset_dfs[pos.symbol]
                row = sym_df[sym_df["date"] == date]
                if row.empty:
                    continue
                r = row.iloc[0]
                avg_entry = pos.avg_entry_price()
                if r["close"] <= avg_entry:
                    continue
                gain_pct = (r["close"] - avg_entry) / avg_entry * 100
                if (pos.phase == "probe" and gain_pct >= 3.0
                        and not pd.isna(r["rsi"]) and 55 <= r["rsi"] <= 70
                        and not pd.isna(r["ma20"]) and r["close"] > r["ma20"]):
                    add_capital = min(cash * CONFIRM_ADD_PCT, cash * 0.20)
                    if add_capital > 10 and cash > add_capital:
                        add_notional = add_capital * LEVERAGE_CONFIRM
                        pos.entries.append((date, r["close"], add_notional, LEVERAGE_CONFIRM, add_capital))
                        pos.phase = "confirm"
                        pos.leverage = LEVERAGE_CONFIRM
                        pos.stop_price = avg_entry
                        cash -= add_capital
                        pos.added = True
                        print(f"  [{date.date()}] CONFIRM {pos.symbol} @ {r['close']:.2f} (+{gain_pct:.1f}%)")
                elif (pos.phase == "confirm" and gain_pct >= 8.0
                      and not pd.isna(r["rsi"]) and 60 <= r["rsi"] <= 72
                      and not pd.isna(r["ma50_slope_up"]) and bool(r["ma50_slope_up"])):
                    current_pct = pos.total_margin() / (cash + pos.total_margin())
                    if current_pct < MAX_POSITION_PCT:
                        add_capital = min(cash * JUGULAR_TARGET_PCT, cash * 0.30, (cash + pos.total_margin()) * MAX_POSITION_PCT - pos.total_margin())
                        if add_capital > 10 and cash > add_capital:
                            add_notional = add_capital * LEVERAGE_JUGULAR
                            pos.entries.append((date, r["close"], add_notional, LEVERAGE_JUGULAR, add_capital))
                            pos.phase = "jugular"
                            pos.leverage = LEVERAGE_JUGULAR
                            pos.stop_price = avg_entry * 1.02
                            cash -= add_capital
                            pos.added = True
                            print(f"  [{date.date()}] JUGULAR {pos.symbol} @ {r['close']:.2f} (+{gain_pct:.1f}%)")

        # Entry scans
        if not defensive_mode and regime in ("RISK-ON", "TRANSITION") and len(positions) < MAX_CONCURRENT:
            if regime == "TRANSITION":
                max_cap_pct = 0.10
            else:
                max_cap_pct = PROBE_MAX_PCT

            for sym in tradeable:
                if len(positions) >= MAX_CONCURRENT:
                    break
                if sym not in asset_dfs:
                    continue
                if sym in last_trade_date:
                    if (date - last_trade_date[sym]).days < 3:
                        continue

                sym_df = asset_dfs[sym]
                row = sym_df[sym_df["date"] == date]
                if row.empty:
                    continue
                r = row.iloc[0]

                if pd.isna(r["ma20"]) or pd.isna(r["ma50"]) or pd.isna(r["rsi"]):
                    continue
                if not (r["close"] > r["ma20"] and r["close"] > r["ma50"]):
                    continue
                if not (bool(r["ma20_slope_up"]) and bool(r["ma50_slope_up"])):
                    continue
                if not (RSI_ENTRY_MIN <= r["rsi"] <= RSI_ENTRY_MAX):
                    continue
                if pd.isna(r["pullback_pct"]) or r["pullback_pct"] < PULLBACK_PCT:
                    continue

                # R5: Chop filter — skip new entries in choppy markets
                if is_choppy(r):
                    continue

                # R5: GOLD gets bigger probe size
                if sym == "GOLD":
                    probe_pct = GOLD_PROBE_PCT
                else:
                    probe_pct = max_cap_pct

                trade_capital = min(cash * probe_pct, cash * 0.20)
                if trade_capital < 10:
                    continue
                lev = LEVERAGE_PROBE
                notional = trade_capital * lev
                pos = Position(sym, date, r["close"], notional, lev, "probe", regime,
                               cash + sum(p.total_margin() for p in positions))
                positions.append(pos)
                cash -= trade_capital
                last_trade_date[sym] = date
                print(f"  [{date.date()}] ENTRY {sym} @ {r['close']:.2f} (probe ${trade_capital:.0f}, lev={lev}x, RSI={r['rsi']:.1f})")

        equity_curve.append({
            "date": str(date.date()),
            "equity": round(mtm_equity, 2),
            "cash": round(cash, 2),
            "positions_open": len(positions),
            "regime": regime,
            "drawdown_pct": round(dd * 100, 2),
        })

    # Close remaining
    last_date = dates.iloc[-1]
    for pos in list(positions):
        sym_df = asset_dfs[pos.symbol]
        row = sym_df[sym_df["date"] == last_date]
        if row.empty:
            row = sym_df.tail(1)
        exit_price = row.iloc[0]["close"]
        hold_days = (last_date - pos.entry_date).days
        net, gross, fees, slip, funding = trade_pnl(pos, exit_price, hold_days)
        cash += pos.total_margin() + net
        closed_trades.append(_trade_dict(pos, last_date, exit_price, hold_days, net, gross, fees, slip, funding, "BACKTEST_END"))
    positions = []

    return closed_trades, equity_curve, cash

def _trade_dict(pos, exit_date, exit_price, hold_days, net, gross, fees, slip, funding, reason):
    return {
        "entry_date": str(pos.entry_date.date()),
        "exit_date": str(exit_date.date()),
        "symbol": pos.symbol,
        "side": "LONG",
        "phase": pos.phase,
        "entry_price": round(pos.avg_entry_price(), 4),
        "exit_price": round(exit_price, 4),
        "notional": round(pos.total_notional(), 2),
        "leverage": pos.leverage,
        "hold_days": hold_days,
        "regime_at_entry": pos.regime_at_entry,
        "gross_pnl": round(gross, 2),
        "fees": round(fees, 2),
        "slippage": round(slip, 2),
        "funding": round(funding, 2),
        "net_pnl": round(net, 2),
        "return_pct": round(net / pos.total_margin() * 100, 2),
        "exit_reason": reason,
    }

# ─────────────────────── Metrics ───────────────────────

def compute_metrics(trades, equity_curve, start_capital):
    eq = pd.DataFrame(equity_curve)
    if eq.empty:
        return {}
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
    profit_factor = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else (float('inf') if wins else 0)
    return {
        "start_capital": start_capital,
        "final_equity": round(final, 2),
        "total_return_pct": round(total_ret, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio": round(sharpe, 3),
        "num_trades": len(trades),
        "win_rate_pct": round(win_rate, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 3) if profit_factor != float('inf') else 999.0,
        "best_trade": round(max(pnls), 2) if pnls else 0,
        "worst_trade": round(min(pnls), 2) if pnls else 0,
        "avg_hold_days": round(statistics.mean([t["hold_days"] for t in trades]), 1) if trades else 0,
        "total_costs": round(sum(t["fees"] + t["slippage"] + t["funding"] for t in trades), 2),
        "total_gross_pnl": round(sum(t["gross_pnl"] for t in trades), 2),
        "total_net_pnl": round(sum(pnls), 2),
    }

def btc_hodl_benchmark(all_data, start_capital):
    btc = all_data["BTC"].sort_values("date").reset_index(drop=True)
    if btc.empty:
        return {}
    entry = btc.iloc[0]["close"]
    exit_ = btc.iloc[-1]["close"]
    final = start_capital * (exit_ / entry)
    ret = (exit_ / entry - 1) * 100
    btc["peak"] = btc["close"].cummax()
    btc["dd"] = (btc["peak"] - btc["close"]) / btc["peak"]
    return {
        "btc_entry_price": round(entry, 2),
        "btc_exit_price": round(exit_, 2),
        "final_equity": round(final, 2),
        "total_return_pct": round(ret, 2),
        "max_drawdown_pct": round(btc["dd"].max() * 100, 2),
        "start_date": str(btc.iloc[0]["date"].date()),
        "end_date": str(btc.iloc[-1]["date"].date()),
    }

# ─────────────────────── Main ───────────────────────

def main():
    print("=" * 80)
    print("BBA ROUND 5 — Chop Filter + GOLD Overweight + RSI Exit 70")
    print("=" * 80)

    print("\nLoading market data (latest 365 days)...")
    all_data = load_all_data()
    print(f"  Loaded {len(all_data)} assets\n")

    print("Building regime classification...")
    regime_df = build_regime_series(all_data)
    regime_counts = regime_df["regime"].value_counts()
    print(f"  Regime distribution: {dict(regime_counts)}\n")

    print("Running backtest...")
    print("-" * 80)
    trades, equity_curve, final_equity = run_backtest(all_data, regime_df)
    print("-" * 80)
    print(f"  {len(trades)} trades closed.\n")

    metrics = compute_metrics(trades, equity_curve, START_CAPITAL)
    benchmark = btc_hodl_benchmark(all_data, START_CAPITAL)

    # Summary
    print("=" * 80)
    print("ROUND 5 RESULTS")
    print("=" * 80)
    print(f"  Start Capital:     ${START_CAPITAL:,.2f}")
    print(f"  Final Equity:      ${metrics.get('final_equity', 0):,.2f}")
    print(f"  Total Return:      {metrics.get('total_return_pct', 0):.2f}%")
    print(f"  Max Drawdown:      {metrics.get('max_drawdown_pct', 0):.2f}%")
    print(f"  Sharpe Ratio:      {metrics.get('sharpe_ratio', 0):.3f}")
    print(f"  Num Trades:        {metrics.get('num_trades', 0)}")
    print(f"  Win Rate:          {metrics.get('win_rate_pct', 0):.2f}%")
    print(f"  Avg Win:           ${metrics.get('avg_win', 0):,.2f}")
    print(f"  Avg Loss:          ${metrics.get('avg_loss', 0):,.2f}")
    print(f"  Profit Factor:     {metrics.get('profit_factor', 0):.3f}")
    print(f"  Best Trade:        ${metrics.get('best_trade', 0):,.2f}")
    print(f"  Worst Trade:       ${metrics.get('worst_trade', 0):,.2f}")
    print(f"  Avg Hold Days:     {metrics.get('avg_hold_days', 0):.1f}")
    print(f"  Total Costs:       ${metrics.get('total_costs', 0):,.2f}")
    print(f"  Gross P&L:         ${metrics.get('total_gross_pnl', 0):,.2f}")
    print(f"  Net P&L:           ${metrics.get('total_net_pnl', 0):,.2f}")

    print(f"\n  BTC HODL:          {benchmark.get('total_return_pct', 0):.2f}%")
    diff = metrics.get('total_return_pct', 0) - benchmark.get('total_return_pct', 0)
    print(f"  vs BTC HODL:       {diff:+.2f}% ({'OUTPERFORMED' if diff > 0 else 'UNDERPERFORMED'})")

    # vs R4C baseline comparison
    r4c = {"total_return_pct": 14.9, "max_drawdown_pct": 8.46, "sharpe_ratio": 1.564, "num_trades": 9, "win_rate_pct": 44.44, "profit_factor": 2.247, "total_costs": 55.53, "total_net_pnl": 244.76}
    print(f"\n  vs R4C baseline:")
    for k in ["total_return_pct", "max_drawdown_pct", "sharpe_ratio", "num_trades", "win_rate_pct", "profit_factor"]:
        v5 = metrics.get(k, 0)
        v4c = r4c[k]
        delta = v5 - v4c
        print(f"    {k:25s} R5={v5:>8.2f}  R4C={v4c:>8.2f}  Δ={delta:+8.2f}")

    # Print trades
    print(f"\n{'='*80}")
    print("ALL TRADES")
    print("=" * 80)
    print(f"{'#':>3} {'Entry':>12} {'Exit':>12} {'Symbol':>8} {'EntryPx':>10} {'ExitPx':>10} {'P&L':>10} {'Ret%':>7} {'Hold':>5} {'Regime':>10} {'Exit':>16}")
    print("-" * 120)
    for i, t in enumerate(trades, 1):
        print(f"{i:>3} {t['entry_date']:>12} {t['exit_date']:>12} {t['symbol']:>8} "
              f"{t['entry_price']:>10.2f} {t['exit_price']:>10.2f} {t['net_pnl']:>+10.2f} "
              f"{t['return_pct']:>+7.2f} {t['hold_days']:>5} {t['regime_at_entry']:>10} {t['exit_reason']:>16}")

    # Shield check
    dd = metrics.get("max_drawdown_pct", 0)
    nt = metrics.get("num_trades", 0)
    veto = False
    veto_reason = ""
    if dd > 20:
        veto = True
        veto_reason = f"DD {dd}% > 20%"
    if nt > 25:
        veto = True
        veto_reason = f"trades {nt} > 25"
    print(f"\n  Shield: DD={dd:.2f}% trades={nt} → {'VETO ('+veto_reason+')' if veto else 'PASS'}")

    # Save
    results = {
        "test_id": "round5-chop-gold-rsi70",
        "description": "R4C chop filter + GOLD 15% probe + RSI exit 70, fresh 365-day data",
        "baseline": "round4-C-chop-filter",
        "changes_from_baseline": [
            "GOLD probe size 10% → 15%",
            "RSI exit threshold 75 → 70",
            "Fresh data: latest 365 days (out-of-sample vs R3/R4 Sep 2025-Sep 2026)"
        ],
        "config": {
            "start_capital": START_CAPITAL,
            "rsi_exit_max": RSI_EXIT_MAX,
            "gold_probe_pct": GOLD_PROBE_PCT,
            "chop_filter": {"atr_period": ATR_PERIOD, "atr_median_bars": ATR_MEDIAN_BARS, "ema_gap_min_pct": EMA_GAP_MIN_PCT},
            "fee_bps_per_side": FEE_BPS,
            "slippage_bps_per_side": SLIPPAGE_BPS,
            "funding_rates": FUNDING_RATES,
        },
        "regime_distribution": {k: int(v) for k, v in regime_counts.items()},
        "metrics": metrics,
        "benchmark_btc_hodl": benchmark,
        "shield": {"dd_limit_pct": 20, "trades_limit": 25, "veto": veto, "veto_reason": veto_reason, "dd": dd, "trades": nt},
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
