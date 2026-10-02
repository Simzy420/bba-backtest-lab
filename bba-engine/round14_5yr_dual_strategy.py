#!/usr/bin/env python3
"""
BBA Backtest — Round 14: Dual Strategy (Bull + Bear)
====================================================
Two separate strategies that activate based on market regime.

BULL STRATEGY (S&P above 200MA):
- 5% pullback entry (R12 winner)
- Long only
- Above MA20 + MA50, both sloping up
- RSI 40-65, pullback from 5-day high
- Pyramiding: probe 10% → confirm → jugular
- Exits: below MA50, RSI >75, 30-day time stop
- 3x leverage, max 2 concurrent

BEAR STRATEGY (S&P below 200MA):
- Short only — sell rallies in downtrends
- Below MA20 + MA50, both sloping down
- RSI 35-55 (not oversold), rally toward MA20
- No pyramiding — single entry, smaller size
- 5% probe, 2x leverage, max 1 concurrent
- Exits: above MA20 (stop), RSI < 30 (cover), 15-day time stop
- Faster in/out — don't hold shorts long

DD Defense: 20% → go to cash, reset after 10 days
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

# ─────────────────────── Config ───────────────────────

START_CAPITAL = 1663.0

# Bull strategy params
BULL_LEVERAGE_PROBE = 2
BULL_LEVERAGE_CONFIRM = 3
BULL_LEVERAGE_JUGULAR = 3
BULL_PULLBACK_PCT = 5.0  # R12 winner
BULL_RSI_ENTRY_MIN = 40
BULL_RSI_ENTRY_MAX = 65
BULL_RSI_EXIT_MAX = 75
BULL_MAX_HOLD = 30
BULL_PROBE_PCT = 0.10
BULL_CONFIRM_ADD_PCT = 0.15
BULL_JUGULAR_TARGET_PCT = 0.40
BULL_MAX_CONCURRENT = 2
BULL_MAX_POSITION_PCT = 0.50

# Bear strategy params
BEAR_LEVERAGE = 2
BEAR_RSI_ENTRY_MIN = 35
BEAR_RSI_ENTRY_MAX = 55
BEAR_RSI_EXIT_MIN = 30  # cover when oversold
BEAR_MAX_HOLD = 15
BEAR_PROBE_PCT = 0.05  # half bull size
BEAR_MAX_CONCURRENT = 1
BEAR_RALLY_PCT = 2.0  # must rally 2% from recent low to enter short

# Shared
MA_SHORT = 20
MA_LONG = 50
MA_TREND = 200  # regime switch
RSI_PERIOD = 14

VIX_RISK_ON = 20.0
VIX_RISK_OFF = 25.0
TNX_TOLERANCE_BPS = 15.0

DD_DEFENSE_THRESHOLD = 0.20
DD_DEFENSE_RESET_DAYS = 10

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
OUTPUT_JSON = "/workspace/bba-backtest-lab/bba-results/round14-5yr-dual-strategy.json"
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
    df["ma200"] = df["close"].rolling(MA_TREND).mean()
    df["ema20"] = df["close"].ewm(span=MA_SHORT, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=MA_LONG, adjust=False).mean()
    df["rsi"] = compute_rsi(df["close"], RSI_PERIOD)
    df["ma20_slope_up"] = df["ma20"] > df["ma20"].shift(5)
    df["ma50_slope_up"] = df["ma50"] > df["ma50"].shift(5)
    df["ma20_slope_down"] = df["ma20"] < df["ma20"].shift(5)
    df["ma50_slope_down"] = df["ma50"] < df["ma50"].shift(5)
    df["high_5d"] = df["close"].rolling(5).max()
    df["low_5d"] = df["close"].rolling(5).min()
    df["pullback_pct"] = (df["high_5d"] - df["close"]) / df["high_5d"] * 100
    df["rally_pct"] = (df["close"] - df["low_5d"]) / df["low_5d"] * 100
    df["atr"] = compute_atr(df, ATR_PERIOD)
    df["atr_pct"] = df["atr"] / df["close"] * 100
    df["atr_median"] = df["atr_pct"].rolling(ATR_MEDIAN_BARS).median()
    df["ema_gap_pct"] = (df["ema20"] - df["ema50"]).abs() / df["close"]
    return df

# ─────────────────────── Regime ────────────���──────────

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
    def __init__(self, symbol, entry_date, entry_price, notional, leverage, phase, regime_at_entry, strategy):
        self.symbol = symbol
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.notional = notional
        self.leverage = leverage
        self.phase = phase
        self.regime_at_entry = regime_at_entry
        self.strategy = strategy  # "bull" or "bear"
        self.side = "LONG" if strategy == "bull" else "SHORT"
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
    if pos.side == "LONG":
        gross = (exit_price - avg) / avg * total
    else:
        gross = (avg - exit_price) / avg * total
    fees = total * (FEE_BPS / 10000) * 2
    slip = total * (SLIPPAGE_BPS / 10000) * 2
    funding = calc_funding(pos.symbol, total, hold_days)
    return gross - fees - slip - funding, gross, fees, slip, funding

def _tdict(pos, exit_date, exit_price, hold_days, net, gross, fees, slip, funding, reason):
    return {
        "entry_date": str(pos.entry_date.date()),
        "exit_date": str(exit_date.date()),
        "symbol": pos.symbol, "side": pos.side, "phase": pos.phase,
        "strategy": pos.strategy,
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

    # S&P 200MA for bull/bear switch
    spx_df = asset_dfs["^GSPC"]

    dates = regime_df["date"].drop_duplicates().sort_values().reset_index(drop=True)
    if len(dates) > MA_TREND:
        dates = dates[dates >= dates.iloc[MA_TREND]]

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

        # Determine bull vs bear market using S&P 200MA
        spx_row = spx_df[spx_df["date"] == date]
        if spx_row.empty or pd.isna(spx_row.iloc[0]["ma200"]):
            is_bull_market = True  # default to bull
        else:
            is_bull_market = spx_row.iloc[0]["close"] > spx_row.iloc[0]["ma200"]

        # MTM
        unrealized = 0.0
        locked = 0.0
        for pos in positions:
            sym_df = asset_dfs.get(pos.symbol)
            if sym_df is None: continue
            row = sym_df[sym_df["date"] == date]
            if row.empty: continue
            cur = row.iloc[0]["close"]
            if pos.side == "LONG":
                unrealized += (cur - pos.avg_entry()) / pos.avg_entry() * pos.total_notional()
            else:
                unrealized += (pos.avg_entry() - cur) / pos.avg_entry() * pos.total_notional()
            locked += pos.total_margin()

        mtm = cash + locked + unrealized
        if not defensive_mode and mtm > peak_equity:
            peak_equity = mtm
        dd = (peak_equity - mtm) / peak_equity if peak_equity > 0 else 0

        # DD defense
        if dd >= DD_DEFENSE_THRESHOLD and not defensive_mode:
            defensive_mode = True
            defensive_start_date = date
            mkt = "BEAR" if not is_bull_market else "BULL"
            print(f"  [{date.date()}] DEFENSIVE (DD={dd*100:.1f}%) [{mkt} market] — going to cash")
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

        # DD defense reset
        if defensive_mode and defensive_start_date:
            if (date - defensive_start_date).days >= DD_DEFENSE_RESET_DAYS:
                defensive_mode = False
                defensive_start_date = None
                peak_equity = cash
                mkt = "BEAR" if not is_bull_market else "BULL"
                print(f"  [{date.date()}] DEFENSIVE RESET [{mkt} market] — peak=${peak_equity:.2f}")

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

        # Close positions from wrong market (bull position in bear market and vice versa)
        for pos in list(positions):
            if pos.strategy == "bull" and not is_bull_market:
                sym_df = asset_dfs[pos.symbol]
                row = sym_df[sym_df["date"] == date]
                if row.empty: continue
                ep = row.iloc[0]["close"]
                h = (date - pos.entry_date).days
                net, g, f, s, fd = trade_pnl(pos, ep, h)
                cash += pos.total_margin() + net
                closed_trades.append(_tdict(pos, date, ep, h, net, g, f, s, fd, "REGIME_SHIFT_BEAR"))
                positions.remove(pos)
            elif pos.strategy == "bear" and is_bull_market:
                sym_df = asset_dfs[pos.symbol]
                row = sym_df[sym_df["date"] == date]
                if row.empty: continue
                ep = row.iloc[0]["close"]
                h = (date - pos.entry_date).days
                net, g, f, s, fd = trade_pnl(pos, ep, h)
                cash += pos.total_margin() + net
                closed_trades.append(_tdict(pos, date, ep, h, net, g, f, s, fd, "REGIME_SHIFT_BULL"))
                positions.remove(pos)

        # Exits
        for pos in list(positions):
            sym_df = asset_dfs[pos.symbol]
            row = sym_df[sym_df["date"] == date]
            if row.empty: continue
            r = row.iloc[0]
            ep = reason = None
            h = (date - pos.entry_date).days

            if pos.strategy == "bull":
                # Bull exits
                if not pd.isna(r["ma50"]) and r["close"] < r["ma50"]:
                    ep, reason = r["close"], "BELOW_MA50"
                elif not pd.isna(r["rsi"]) and r["rsi"] > BULL_RSI_EXIT_MAX:
                    ep, reason = r["close"], "RSI_OVERBOUGHT"
                elif h >= BULL_MAX_HOLD:
                    ep, reason = r["close"], "TIME_STOP"
                elif pos.stop_price and r["close"] < pos.stop_price:
                    ep, reason = r["close"], "BREAKEVEN_STOP"
            else:
                # Bear exits (short)
                if not pd.isna(r["ma20"]) and r["close"] > r["ma20"]:
                    ep, reason = r["close"], "ABOVE_MA20"
                elif not pd.isna(r["rsi"]) and r["rsi"] < BEAR_RSI_EXIT_MIN:
                    ep, reason = r["close"], "RSI_OVERSOLD"
                elif h >= BEAR_MAX_HOLD:
                    ep, reason = r["close"], "TIME_STOP"
                elif pos.stop_price and r["close"] > pos.stop_price:
                    ep, reason = r["close"], "STOP_LOSS"

            if ep is not None:
                net, g, f, s, fd = trade_pnl(pos, ep, h)
                cash += pos.total_margin() + net
                closed_trades.append(_tdict(pos, date, ep, h, net, g, f, s, fd, reason))
                positions.remove(pos)

        # Pyramiding (bull only)
        if is_bull_market and regime in ("RISK-ON", "TRANSITION") and not defensive_mode:
            for pos in positions:
                if pos.strategy != "bull" or pos.added or pos.symbol not in asset_dfs: continue
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
                    add_cap = min(cash * BULL_CONFIRM_ADD_PCT, cash * 0.20)
                    if add_cap > 10 and cash > add_cap:
                        pos.entries.append((date, r["close"], add_cap * BULL_LEVERAGE_CONFIRM, BULL_LEVERAGE_CONFIRM, add_cap))
                        pos.phase = "confirm"
                        pos.leverage = BULL_LEVERAGE_CONFIRM
                        pos.stop_price = avg
                        cash -= add_cap
                        pos.added = True
                        print(f"  [{date.date()}] BULL CONFIRM {pos.symbol} @ {r['close']:.2f} (+{gain:.1f}%)")

                elif (pos.phase == "confirm" and gain >= 8.0
                      and not pd.isna(r["rsi"]) and 60 <= r["rsi"] <= 72
                      and not pd.isna(r["ma50_slope_up"]) and bool(r["ma50_slope_up"])):
                    cur_pct = pos.total_margin() / (cash + pos.total_margin())
                    if cur_pct < BULL_MAX_POSITION_PCT:
                        add_cap = min(cash * BULL_JUGULAR_TARGET_PCT, cash * 0.30, (cash + pos.total_margin()) * BULL_MAX_POSITION_PCT - pos.total_margin())
                        if add_cap > 10 and cash > add_cap:
                            pos.entries.append((date, r["close"], add_cap * BULL_LEVERAGE_JUGULAR, BULL_LEVERAGE_JUGULAR, add_cap))
                            pos.phase = "jugular"
                            pos.leverage = BULL_LEVERAGE_JUGULAR
                            pos.stop_price = avg * 1.02
                            cash -= add_cap
                            pos.added = True
                            print(f"  [{date.date()}] BULL JUGULAR {pos.symbol} @ {r['close']:.2f} (+{gain:.1f}%)")

        # ── BULL ENTRIES ──
        if is_bull_market and not defensive_mode and regime in ("RISK-ON", "TRANSITION"):
            bull_positions = [p for p in positions if p.strategy == "bull"]
            if len(bull_positions) < BULL_MAX_CONCURRENT:
                max_cap_pct = 0.10 if regime == "TRANSITION" else BULL_PROBE_PCT
                for sym in TRADEABLE:
                    if len([p for p in positions if p.strategy == "bull"]) >= BULL_MAX_CONCURRENT: break
                    if sym not in asset_dfs: continue
                    if sym in last_trade_date and (date - last_trade_date[sym]).days < 3: continue
                    sym_df = asset_dfs[sym]
                    row = sym_df[sym_df["date"] == date]
                    if row.empty: continue
                    r = row.iloc[0]
                    if pd.isna(r["ma20"]) or pd.isna(r["ma50"]) or pd.isna(r["rsi"]): continue
                    if not (r["close"] > r["ma20"] and r["close"] > r["ma50"]): continue
                    if not (bool(r["ma20_slope_up"]) and bool(r["ma50_slope_up"])): continue
                    if not (BULL_RSI_ENTRY_MIN <= r["rsi"] <= BULL_RSI_ENTRY_MAX): continue
                    if pd.isna(r["pullback_pct"]) or r["pullback_pct"] < BULL_PULLBACK_PCT: continue
                    if is_choppy(r): continue
                    trade_cap = min(cash * max_cap_pct, cash * 0.20)
                    if trade_cap < 10: continue
                    lev = BULL_LEVERAGE_PROBE
                    pos = Position(sym, date, r["close"], trade_cap * lev, lev, "probe", regime, "bull")
                    positions.append(pos)
                    cash -= trade_cap
                    last_trade_date[sym] = date
                    print(f"  [{date.date()}] 🐂 BULL ENTRY {sym} @ {r['close']:.2f} (${trade_cap:.0f}, RSI={r['rsi']:.1f})")

        # ── BEAR ENTRIES ──
        if not is_bull_market and not defensive_mode:
            bear_positions = [p for p in positions if p.strategy == "bear"]
            if len(bear_positions) < BEAR_MAX_CONCURRENT:
                for sym in TRADEABLE:
                    if len([p for p in positions if p.strategy == "bear"]) >= BEAR_MAX_CONCURRENT: break
                    if sym not in asset_dfs: continue
                    if sym in last_trade_date and (date - last_trade_date[sym]).days < 3: continue
                    sym_df = asset_dfs[sym]
                    row = sym_df[sym_df["date"] == date]
                    if row.empty: continue
                    r = row.iloc[0]
                    if pd.isna(r["ma20"]) or pd.isna(r["ma50"]) or pd.isna(r["rsi"]): continue
                    # Short conditions: below MA20 and MA50, both sloping down
                    if not (r["close"] < r["ma20"] and r["close"] < r["ma50"]): continue
                    if not (bool(r["ma20_slope_down"]) and bool(r["ma50_slope_down"])): continue
                    # RSI in range (not oversold, selling rallies)
                    if not (BEAR_RSI_ENTRY_MIN <= r["rsi"] <= BEAR_RSI_ENTRY_MAX): continue
                    # Must have rallied from recent low (selling the rally, not chasing)
                    if pd.isna(r["rally_pct"]) or r["rally_pct"] < BEAR_RALLY_PCT: continue
                    if is_choppy(r): continue
                    trade_cap = min(cash * BEAR_PROBE_PCT, cash * 0.10)
                    if trade_cap < 10: continue
                    lev = BEAR_LEVERAGE
                    pos = Position(sym, date, r["close"], trade_cap * lev, lev, "probe", regime, "bear")
                    # Stop is 5% above entry
                    pos.stop_price = r["close"] * 1.05
                    positions.append(pos)
                    cash -= trade_cap
                    last_trade_date[sym] = date
                    print(f"  [{date.date()}] 🐻 BEAR SHORT {sym} @ {r['close']:.2f} (${trade_cap:.0f}, RSI={r['rsi']:.1f})")

        equity_curve.append({
            "date": str(date.date()), "equity": round(mtm, 2),
            "cash": round(cash, 2), "positions": len(positions),
            "regime": regime, "market": "BULL" if is_bull_market else "BEAR",
            "drawdown_pct": round(dd * 100, 2),
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
        "runs": runs, "bust_count": bust_count,
        "survival_rate_pct": round(survival, 2),
        "return_p5": round(np.percentile(returns_list, 5), 2) if returns_list else 0,
        "return_median": round(np.percentile(returns_list, 50), 2) if returns_list else 0,
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
    years = len(eq) / 252
    annualized = ((final / start_capital) ** (1 / years) - 1) * 100 if years > 0 else total_ret

    # Split by strategy
    bull_trades = [t for t in trades if t["strategy"] == "bull"]
    bear_trades = [t for t in trades if t["strategy"] == "bear"]
    bull_pnls = [t["net_pnl"] for t in bull_trades]
    bear_pnls = [t["net_pnl"] for t in bear_trades]
    bull_wins = sum(1 for p in bull_pnls if p > 0)
    bear_wins = sum(1 for p in bear_pnls if p > 0)

    return {
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
        "total_costs": round(sum(t["fees"] + t["slippage"] + t["funding"] for t in trades), 2),
        "total_net_pnl": round(sum(pnls), 2),
        # Bull stats
        "bull_trades": len(bull_trades),
        "bull_win_rate": round(bull_wins / len(bull_trades) * 100, 2) if bull_trades else 0,
        "bull_net_pnl": round(sum(bull_pnls), 2),
        # Bear stats
        "bear_trades": len(bear_trades),
        "bear_win_rate": round(bear_wins / len(bear_trades) * 100, 2) if bear_trades else 0,
        "bear_net_pnl": round(sum(bear_pnls), 2),
    }

def btc_hodl(all_data, start_capital):
    btc = all_data["BTC"].sort_values("date").reset_index(drop=True)
    entry = btc.iloc[0]["close"]
    exit_ = btc.iloc[-1]["close"]
    btc["peak"] = btc["close"].cummax()
    btc["dd"] = (btc["peak"] - btc["close"]) / btc["peak"]
    return {
        "total_return_pct": round((exit_ / entry - 1) * 100, 2),
        "max_drawdown_pct": round(btc["dd"].max() * 100, 2),
    }

# ─────────────────────── Main ───────────────────────

def main():
    print("=" * 80)
    print("BBA ROUND 14 — DUAL STRATEGY (BULL + BEAR), 5 YEAR")
    print("=" * 80)

    print("\nLoading 5 years of market data...")
    all_data = load_all_data()
    print(f"  {len(all_data)} assets loaded\n")

    print("Building regime classification...")
    regime_df = build_regime(all_data)
    print(f"  Regime: {dict(regime_df['regime'].value_counts())}\n")

    print("Running dual strategy backtest...")
    print("-" * 80)
    trades, equity_curve, final_equity = run_backtest(all_data, regime_df)
    print("-" * 80)
    print(f"  {len(trades)} trades closed.\n")

    metrics = compute_metrics(trades, equity_curve, START_CAPITAL)
    benchmark = btc_hodl(all_data, START_CAPITAL)

    print("=" * 80)
    print("ROUND 14 RESULTS — DUAL STRATEGY, 5 YEAR")
    print("=" * 80)
    print(f"  Total Return:       {metrics['total_return_pct']:.2f}%")
    print(f"  Annualized:         {metrics['annualized_return_pct']:.2f}%")
    print(f"  Max Drawdown:       {metrics['max_drawdown_pct']:.2f}%")
    print(f"  Sharpe:             {metrics['sharpe_ratio']:.3f}")
    print(f"  Trades:             {metrics['num_trades']}")
    print(f"  Win Rate:           {metrics['win_rate_pct']:.2f}%")
    print(f"  Profit Factor:      {metrics['profit_factor']:.3f}")
    print(f"  Net P&L:            ${metrics['total_net_pnl']:,.2f}")
    print(f"\n  🐂 BULL: {metrics['bull_trades']} trades, {metrics['bull_win_rate']}% WR, ${metrics['bull_net_pnl']:,.2f} P&L")
    print(f"  🐻 BEAR: {metrics['bear_trades']} trades, {metrics['bear_win_rate']}% WR, ${metrics['bear_net_pnl']:,.2f} P&L")
    print(f"\n  BTC HODL:           {benchmark['total_return_pct']:.2f}%")
    print(f"  vs BTC:             {metrics['total_return_pct'] - benchmark['total_return_pct']:+.2f}%")

    # Per-year
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
            bull_t = sum(1 for t in year_trades if t["strategy"] == "bull")
            bear_t = sum(1 for t in year_trades if t["strategy"] == "bear")
            mkt = year_eq.iloc[-1]["market"]
            print(f"  {year}: {year_ret:+.2f}%, DD={year_dd:.2f}%, trades={len(year_trades)} (🐂{bull_t}/🐻{bear_t})")

    # Trades
    print(f"\n{'='*80}")
    print("ALL TRADES")
    print("=" * 80)
    print(f"{'#':>3} {'Entry':>12} {'Exit':>12} {'Symbol':>8} {'Strat':>5} {'Side':>5} {'EntryPx':>10} {'ExitPx':>10} {'P&L':>10} {'Ret%':>7} {'Hold':>5} {'Exit':>16}")
    print("-" * 120)
    for i, t in enumerate(trades, 1):
        icon = "🐂" if t["strategy"] == "bull" else "🐻"
        print(f"{i:>3} {t['entry_date']:>12} {t['exit_date']:>12} {t['symbol']:>8} {icon:>3} {t['side']:>5} "
              f"{t['entry_price']:>10.2f} {t['exit_price']:>10.2f} {t['net_pnl']:>+10.2f} "
              f"{t['return_pct']:>+7.2f} {t['hold_days']:>5} {t['exit_reason']:>16}")

    # Monte Carlo
    print(f"\n{'='*80}")
    print(f"MONTE CARLO ({MONTE_CARLO_RUNS:,} runs)")
    print("=" * 80)
    mc = monte_carlo(trades, START_CAPITAL, MONTE_CARLO_RUNS)
    print(f"  Survival:    {mc.get('survival_rate_pct', 0):.2f}%")
    print(f"  Return p5:   {mc.get('return_p5', 0):.2f}%")
    print(f"  Return med:  {mc.get('return_median', 0):.2f}%")
    print(f"  Return p95:  {mc.get('return_p95', 0):.2f}%")
    print(f"  DD median:   {mc.get('median_dd_pct', 0):.2f}%")
    print(f"  DD p95:      {mc.get('p95_dd_pct', 0):.2f}%")

    # Comparison
    print(f"\n{'='*80}")
    print("COMPARISON: ALL ROUNDS")
    print("=" * 80)
    print(f"  R10 (2% pullback, single):  +27.99%, DD 25.63%, Sharpe 0.358")
    print(f"  R12 (5% pullback, single):  +35.52%, DD 25.14%, Sharpe 0.431")
    print(f"  R14 (dual bull+bear):       {metrics['total_return_pct']:+.2f}%, DD {metrics['max_drawdown_pct']:.2f}%, Sharpe {metrics['sharpe_ratio']:.3f}")

    # Save
    results = {
        "test_id": "round14-5yr-dual-strategy",
        "metrics": metrics,
        "benchmark": benchmark,
        "monte_carlo": mc,
        "trades": trades,
        "equity_curve": equity_curve,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved to {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
