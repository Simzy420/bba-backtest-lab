#!/usr/bin/env python3
"""
Round 4 Test C — CHOP FILTER (isolated one-knob test)
================================================================================
Official engine fork of bba-engine/hl_backtest.py.

ONE KNOB ONLY: skip NEW entries / new probes when the bar is chop:
  1. ATR% is below its 20-bar median on that symbol, OR
  2. |EMA20 − EMA50| / close < 0.4% (0.004)

Definitions (daily engine — Boss text said “1h ATR%”; this engine is daily, so
daily ATR% is used):
  - ATR% = ATR(14) / close × 100   (percent units; 1.5 == 1.5%)
  - 20-bar median of ATR% on that symbol (rolling, includes current bar)
  - EMA20 / EMA50 on close (span EMAs, adjust=False)
  - gap = abs(EMA20 − EMA50) / close; chop if gap < 0.004

Applies only to NEW entries / new probes. Existing positions are not force-exited
for chop. BE stops, pyramid rules, regime, sizes, costs, universe, DD circuit
are unchanged.

Standing: paper only. No invented fills.

Run: python3 grok-engine/round4c_chop_filter.py
"""

import json
import time
import math
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests
import yfinance as yf


# ─────────────────────── Configuration ───────────────────────

START_CAPITAL = 1663.0
START_LEVERAGE_PROBE = 2
START_LEVERAGE_CONFIRM = 3
START_LEVERAGE_JUGULAR = 3
MAX_LEVERAGE = 3

MA_SHORT = 20
MA_LONG = 50
RSI_PERIOD = 14
RSI_ENTRY_MIN = 40
RSI_ENTRY_MAX = 65
RSI_EXIT_MAX = 75

VIX_RISK_ON = 20.0
VIX_RISK_OFF = 25.0
TNX_TOLERANCE_BPS = 15.0  # bps tolerance for "flat" 10yr yield

PULLBACK_PCT = 2.0            # min % drop from 5-day high to qualify as pullback
PULLBACK_HIGH_LOOKBACK = 5

MAX_CONCURRENT = 2
MAX_HOLD_DAYS = 30
MAX_POSITION_PCT = 0.50       # jugular phase cap

DD_DEFENSE_THRESHOLD = 0.20   # 20% drawdown from peak → go to cash

# Probe sizing
PROBE_MIN_PCT = 0.05
PROBE_MAX_PCT = 0.10
CONFIRM_ADD_PCT = 0.15        # add 15% on confirmation
JUGULAR_TARGET_PCT = 0.40     # target 40% (cap 50%)

# Hyperliquid costs
FEE_BPS = 4.5                 # per side (taker entry, maker exit avg)
SLIPPAGE_BPS = 4.5            # per side
TOTAL_ROUND_TRIP_BPS = (FEE_BPS + SLIPPAGE_BPS) * 2  # ~18 bps

FUNDING_RATES = {  # per 8h
    "BTC": 0.0001,
    "ETH": 0.0001,
    "SOL": 0.0002,
    "GOLD": 0.0001,
    "NVDA": 0.0001,
    "TSLA": 0.0001,
    "^GSPC": 0.0001,
}

# yfinance tickers (GOLD = GC=F)
YF_TICKERS = {
    "GOLD": "GC=F",
    "NVDA": "NVDA",
    "TSLA": "TSLA",
    "^GSPC": "^GSPC",
    "^VIX": "^VIX",
    "^TNX": "^TNX",  # 10yr yield
}

# CoinGecko coin ids
CG_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
}

# Round 4C chop-filter knobs (new-entry gate only)
ATR_PERIOD = 14
ATR_PCT_MEDIAN_BARS = 20
EMA_FAST_SPAN = 20
EMA_SLOW_SPAN = 50
CHOP_EMA_GAP_FRAC = 0.004  # 0.4% of close

_REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = str(_REPO_ROOT / "grok-results" / "round4_C_chop_filter_raw.json")
SUMMARY_JSON = str(_REPO_ROOT / "grok-results" / "round4_C_chop_filter.json")
R3_BASELINE_JSON = str(_REPO_ROOT / "bba-results" / "round3-hl-full-2026-09-16.json")


# ─────────────────────── Data Fetching ───────────────────────

def fetch_coingecko_daily(coin_id: str, days: int = 365) -> pd.DataFrame:
    """Fetch daily OHLC from CoinGecko /coins/{id}/ohlc endpoint (free, no key)."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    params = {"vs_currency": "usd", "days": str(days)}
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, timeout=20)
            if r.status_code == 429:
                print(f"  [CoinGecko] 429 for {coin_id}, backoff {10+attempt*5}s")
                time.sleep(10 + attempt * 5)
                continue
            r.raise_for_status()
            data = r.json()
            # [[timestamp, open, high, low, close], ...]
            df = pd.DataFrame(data, columns=["date", "open", "high", "low", "close"])
            df["date"] = pd.to_datetime(df["date"], unit="ms", utc=True).dt.tz_localize(None)
            df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
            return df
        except Exception as e:
            print(f"  [CoinGecko] {coin_id} attempt {attempt+1} error: {e}")
            time.sleep(5 + attempt * 5)
    raise RuntimeError(f"Failed to fetch CoinGecko data for {coin_id}")


def fetch_yfinance_daily(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Fetch daily OHLC from yfinance. Returns df with date (tz-naive) + close."""
    t = yf.Ticker(ticker)
    df = t.history(period=period, auto_adjust=True)
    if df.empty:
        raise RuntimeError(f"yfinance returned empty for {ticker}")
    df = df.reset_index()
    df["date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None) if df["Date"].dt.tz is not None else pd.to_datetime(df["Date"])
    keep = ["date", "Open", "High", "Low", "Close", "Volume"]
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    df = df[["date", "open", "high", "low", "close"]].sort_values("date").reset_index(drop=True)
    return df


def load_all_data() -> dict:
    """Load all asset data + regime indicators. Returns dict symbol -> DataFrame(date,ohlc)."""
    all_data = {}
    # CoinGecko crypto with yfinance fallback
    yf_crypto_fallback = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD"}
    for sym, cid in CG_IDS.items():
        print(f"Fetching {sym} from CoinGecko ({cid})...")
        try:
            df = fetch_coingecko_daily(cid, days=365)
            df["symbol"] = sym
            all_data[sym] = df
        except RuntimeError as e:
            print(f"  CoinGecko failed for {sym}, falling back to yfinance ({yf_crypto_fallback[sym]})")
            df = fetch_yfinance_daily(yf_crypto_fallback[sym], period="1y")
            df["symbol"] = sym
            all_data[sym] = df
        time.sleep(2)  # rate limit
    # yfinance
    for sym, tk in YF_TICKERS.items():
        print(f"Fetching {sym} from yfinance ({tk})...")
        df = fetch_yfinance_daily(tk, period="1y")
        df["symbol"] = sym
        all_data[sym] = df
        time.sleep(0.5)
    return all_data


# ─────────────────────── Indicators ───────────────────────

def compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Wilder smoothing
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder ATR (same ewm alpha=1/period, adjust=False as RSI in this engine)."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ma20"] = df["close"].rolling(MA_SHORT).mean()
    df["ma50"] = df["close"].rolling(MA_LONG).mean()
    df["rsi"] = compute_rsi(df["close"], RSI_PERIOD)
    df["ma20_slope_up"] = df["ma20"] > df["ma20"].shift(5)
    df["ma50_slope_up"] = df["ma50"] > df["ma50"].shift(5)
    df["high_5d"] = df["close"].rolling(PULLBACK_HIGH_LOOKBACK).max()
    df["pullback_pct"] = (df["high_5d"] - df["close"]) / df["high_5d"] * 100
    # Round 4C chop indicators (daily). ATR% in percent units; EMA gap as fraction of close.
    df["atr"] = compute_atr(df, ATR_PERIOD)
    df["atr_pct"] = df["atr"] / df["close"] * 100
    df["atr_pct_median_20"] = df["atr_pct"].rolling(
        ATR_PCT_MEDIAN_BARS, min_periods=ATR_PCT_MEDIAN_BARS
    ).median()
    df["ema20"] = df["close"].ewm(span=EMA_FAST_SPAN, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=EMA_SLOW_SPAN, adjust=False).mean()
    df["ema_gap_frac"] = (df["ema20"] - df["ema50"]).abs() / df["close"]
    return df


# ─────────────────────── Regime Classification ───────────────────────

def classify_regime(vix: float, spx_above_ma50: bool, tnx_change_bps: float) -> str:
    """Return RISK-ON, RISK-OFF, or TRANSITION."""
    risk_on_score = 0
    risk_off_score = 0
    # VIX
    if vix < VIX_RISK_ON:
        risk_on_score += 1
    elif vix > VIX_RISK_OFF:
        risk_off_score += 1
    # S&P vs 50MA
    if spx_above_ma50:
        risk_on_score += 1
    else:
        risk_off_score += 1
    # 10Y yield (falling or flat = supportive)
    if tnx_change_bps <= TNX_TOLERANCE_BPS:
        risk_on_score += 1
    else:
        risk_off_score += 1
    # Decision
    if risk_on_score >= 2 and risk_off_score == 0:
        return "RISK-ON"
    if risk_off_score >= 2:
        return "RISK-ON" if risk_on_score > risk_off_score else "RISK-OFF"
    return "TRANSITION"


def build_regime_series(all_data: dict) -> pd.DataFrame:
    """Build daily regime classification aligned to a master calendar."""
    spx = all_data["^GSPC"].copy()
    vix = all_data["^VIX"].copy()
    tnx = all_data["^TNX"].copy()
    # Merge
    regime = spx[["date", "close"]].rename(columns={"close": "spx"})
    regime = regime.merge(vix[["date", "close"]].rename(columns={"close": "vix"}), on="date", how="left")
    regime = regime.merge(tnx[["date", "close"]].rename(columns={"close": "tnx"}), on="date", how="left")
    regime = regime.sort_values("date").reset_index(drop=True)
    regime["spx_ma50"] = regime["spx"].rolling(MA_LONG).mean()
    regime["spx_above_ma50"] = regime["spx"] > regime["spx_ma50"]
    regime["tnx_chg_bps"] = (regime["tnx"] - regime["tnx"].shift(1)) * 100  # yield points -> bps
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


# ─────────────────────── Position & Trade Logic ───────────────────────

class Position:
    def __init__(self, symbol, entry_date, entry_price, notional, leverage, phase, regime_at_entry, capital_at_entry):
        self.symbol = symbol
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.notional = notional            # initial position notional in USD (leveraged)
        self.leverage = leverage
        self.phase = phase                  # "probe" | "confirm" | "jugular"
        self.regime_at_entry = regime_at_entry
        self.capital_at_entry = capital_at_entry
        self.margin = notional / leverage   # initial capital locked
        self.cash_locked = notional / leverage  # track actual cash deposited (handles leverage changes)
        self.added = False                  # whether we've pyramided
        self.entries = [(entry_date, entry_price, notional, leverage, notional / leverage)]  # track all adds with per-entry leverage
        self.stop_price = None              # breakeven stop after confirmation
        self.funding_paid = 0.0

    def avg_entry_price(self):
        total_notional = sum(n for _, _, n, _, _ in self.entries)
        weighted = sum(p * n for _, p, n, _, _ in self.entries)
        return weighted / total_notional if total_notional > 0 else self.entry_price

    def total_notional(self):
        return sum(n for _, _, n, _, _ in self.entries)

    def total_margin(self):
        """Actual cash locked = sum of per-entry margin deposits."""
        return sum(m for _, _, _, _, m in self.entries)


def calc_funding_cost(symbol, notional, hold_days):
    """Funding cost over hold period. Funding charged per 8h, 3 periods/day."""
    rate_per_8h = FUNDING_RATES.get(symbol, 0.0001)
    periods = hold_days * 3  # 3 funding periods per day
    return notional * rate_per_8h * periods


def trade_pnl(pos, exit_price, hold_days):
    """Calculate net P&L for a closed position including costs."""
    avg_entry = pos.avg_entry_price()
    total_notional = pos.total_notional()
    # Gross P&L (long)
    gross = (exit_price - avg_entry) / avg_entry * total_notional
    # Fees: entry + exit (taker entry, maker exit, both 4.5 bps) on notional per side
    fees = total_notional * (FEE_BPS / 10000) * 2
    # Slippage: entry + exit
    slip = total_notional * (SLIPPAGE_BPS / 10000) * 2
    # Funding (long pays funding when positive; we approximate as always paying avg rate)
    funding = calc_funding_cost(pos.symbol, total_notional, hold_days)
    net = gross - fees - slip - funding
    return net, gross, fees, slip, funding


# ─────────────────────── Backtest Engine ───────────────────────

def run_backtest(all_data: dict, regime_df: pd.DataFrame):
    """Run the full strategy backtest. Returns trades list + equity curve."""
    # Prepare per-asset indicator dataframes
    asset_dfs = {}
    tradeable = ["BTC", "ETH", "SOL", "GOLD", "NVDA", "TSLA", "^GSPC"]
    for sym in tradeable:
        df = add_indicators(all_data[sym])
        df = df.merge(regime_df[["date", "regime"]], on="date", how="left")
        df["regime"] = df["regime"].ffill().fillna("TRANSITION")
        asset_dfs[sym] = df

    # Master date index (use S&P dates as calendar)
    dates = regime_df["date"].drop_duplicates().sort_values().reset_index(drop=True)
    # Need enough warmup for MAs
    dates = dates[dates >= dates.iloc[MA_LONG]] if len(dates) > MA_LONG else dates

    equity = START_CAPITAL
    peak_equity = START_CAPITAL
    cash = START_CAPITAL
    positions = []  # open positions
    closed_trades = []
    equity_curve = []
    defensive_mode = False
    last_trade_date = {}  # symbol -> last entry date (cooldown)
    chop_skips = []  # R4-C: candidate new entries blocked by chop filter

    for i, date in enumerate(dates):
        # Get regime for this date
        reg_row = regime_df[regime_df["date"] == date]
        if reg_row.empty:
            continue
        regime = reg_row.iloc[0]["regime"]

        # Daily MTM: update peak equity and check drawdown
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
            # approximate daily costs not deducted here (taken at close)
            unrealized += gross
            locked_margin += pos.total_margin()

        mtm_equity = cash + locked_margin + unrealized
        if mtm_equity > peak_equity:
            peak_equity = mtm_equity

        dd = (peak_equity - mtm_equity) / peak_equity if peak_equity > 0 else 0

        # 20% DD defense → go to cash
        if dd >= DD_DEFENSE_THRESHOLD and not defensive_mode:
            defensive_mode = True
            print(f"  [{date.date()}] DEFENSIVE MODE triggered (DD={dd*100:.1f}%) — closing all positions")
            for pos in list(positions):
                sym_df = asset_dfs[pos.symbol]
                row = sym_df[sym_df["date"] == date]
                if row.empty:
                    continue
                exit_price = row.iloc[0]["close"]
                hold_days = (date - pos.entry_date).days
                net, gross, fees, slip, funding = trade_pnl(pos, exit_price, hold_days)
                cash += pos.total_margin() + net
                closed_trades.append({
                    "entry_date": str(pos.entry_date.date()),
                    "exit_date": str(date.date()),
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
                    "exit_reason": "DEFENSIVE_DD",
                })
            positions = []

        # RISK-OFF regime → close all positions
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
                closed_trades.append({
                    "entry_date": str(pos.entry_date.date()),
                    "exit_date": str(date.date()),
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
                    "exit_reason": "RISK_OFF",
                })
            positions = []
            defensive_mode = False  # reset after going to cash

        # Exit checks for open positions (end of day)
        for pos in list(positions):
            sym_df = asset_dfs[pos.symbol]
            row = sym_df[sym_df["date"] == date]
            if row.empty:
                continue
            r = row.iloc[0]
            exit_price = None
            reason = None
            hold_days = (date - pos.entry_date).days

            # 1. Price below 50-day MA
            if not pd.isna(r["ma50"]) and r["close"] < r["ma50"]:
                exit_price = r["close"]
                reason = "BELOW_MA50"
            # 2. RSI > 75
            elif not pd.isna(r["rsi"]) and r["rsi"] > RSI_EXIT_MAX:
                exit_price = r["close"]
                reason = "RSI_OVERBOUGHT"
            # 3. Time stop 30 days
            elif hold_days >= MAX_HOLD_DAYS:
                exit_price = r["close"]
                reason = "TIME_STOP"
            # 4. Breakeven stop (after confirmation)
            elif pos.stop_price and r["close"] < pos.stop_price:
                exit_price = r["close"]
                reason = "BREAKEVEN_STOP"

            if exit_price is not None:
                net, gross, fees, slip, funding = trade_pnl(pos, exit_price, hold_days)
                cash += pos.total_margin() + net
                closed_trades.append({
                    "entry_date": str(pos.entry_date.date()),
                    "exit_date": str(date.date()),
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
                })
                positions.remove(pos)

        # Pyramiding: check confirmation/jugular adds for existing positions
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
                # Never add to losers
                if r["close"] <= avg_entry:
                    continue
                # Confirmation: up 3%+ from entry, RSI 55-70, still above MA20
                gain_pct = (r["close"] - avg_entry) / avg_entry * 100
                if (pos.phase == "probe" and gain_pct >= 3.0
                        and not pd.isna(r["rsi"]) and 55 <= r["rsi"] <= 70
                        and not pd.isna(r["ma20"]) and r["close"] > r["ma20"]):
                    # Add confirmation size
                    add_capital = min(cash * CONFIRM_ADD_PCT, cash * 0.20)
                    if add_capital > 10 and cash > add_capital:
                        add_notional = add_capital * START_LEVERAGE_CONFIRM
                        pos.entries.append((date, r["close"], add_notional, START_LEVERAGE_CONFIRM, add_capital))
                        pos.phase = "confirm"
                        pos.leverage = START_LEVERAGE_CONFIRM
                        pos.stop_price = avg_entry  # move stop to breakeven
                        cash -= add_capital
                        pos.added = True
                        print(f"  [{date.date()}] CONFIRM add {pos.symbol} @ {r['close']:.2f} (+{gain_pct:.1f}%)")
                # Jugular: up 8%+ from entry, momentum accelerating (RSI 60-72), MA50 up
                elif (pos.phase == "confirm" and gain_pct >= 8.0
                      and not pd.isna(r["rsi"]) and 60 <= r["rsi"] <= 72
                      and not pd.isna(r["ma50"]) and bool(r["ma50_slope_up"])):
                    current_pct = pos.total_margin() / (cash + pos.total_margin())
                    if current_pct < MAX_POSITION_PCT:
                        add_capital = min(cash * JUGULAR_TARGET_PCT, cash * 0.30, (cash + pos.total_margin()) * MAX_POSITION_PCT - pos.total_margin())
                        if add_capital > 10 and cash > add_capital:
                            add_notional = add_capital * START_LEVERAGE_JUGULAR
                            pos.entries.append((date, r["close"], add_notional, START_LEVERAGE_JUGULAR, add_capital))
                            pos.phase = "jugular"
                            pos.leverage = START_LEVERAGE_JUGULAR
                            pos.stop_price = avg_entry * 1.02  # trail up
                            cash -= add_capital
                            pos.added = True
                            print(f"  [{date.date()}] JUGULAR add {pos.symbol} @ {r['close']:.2f} (+{gain_pct:.1f}%)")

        # Entry scans (only if not defensive and regime allows)
        if not defensive_mode and regime in ("RISK-ON", "TRANSITION") and len(positions) < MAX_CONCURRENT:
            # Determine max capital pct per new trade based on regime
            if regime == "TRANSITION":
                max_cap_pct = 0.10  # probe only
            else:
                max_cap_pct = PROBE_MAX_PCT

            for sym in tradeable:
                if len(positions) >= MAX_CONCURRENT:
                    break
                if sym not in asset_dfs:
                    continue
                # Cooldown check
                if sym in last_trade_date:
                    days_since = (date - last_trade_date[sym]).days
                    if days_since < 3:
                        continue

                sym_df = asset_dfs[sym]
                row = sym_df[sym_df["date"] == date]
                if row.empty:
                    continue
                r = row.iloc[0]

                # Entry conditions (all must align)
                if pd.isna(r["ma20"]) or pd.isna(r["ma50"]) or pd.isna(r["rsi"]):
                    continue
                # Asset above 20 & 50 MA, both sloping up
                if not (r["close"] > r["ma20"] and r["close"] > r["ma50"]):
                    continue
                if not (bool(r["ma20_slope_up"]) and bool(r["ma50_slope_up"])):
                    continue
                # RSI 40-65
                if not (RSI_ENTRY_MIN <= r["rsi"] <= RSI_ENTRY_MAX):
                    continue
                # Pullback: price dropped 2%+ from 5-day high
                if pd.isna(r["pullback_pct"]) or r["pullback_pct"] < PULLBACK_PCT:
                    continue
                # 3:1 R/R is a risk management guideline (achieved via cut losers/ride winners),
                # not a hard entry gate. We compute it for logging but don't block entries.
                lookback = sym_df[sym_df["date"] <= date].tail(20)
                if len(lookback) < 10:
                    continue
                swing_low = lookback["low"].min()
                swing_high = lookback["high"].max()
                entry_px = r["close"]
                risk = entry_px - swing_low
                reward = swing_high - entry_px
                rr_ratio = reward / risk if risk > 0 else 0

                # Round 4C: chop filter — new entries / new probes only.
                # Skip if ATR% < 20-bar median OR EMA gap < 0.4%. Incomplete warmup → skip.
                atr_pct = r.get("atr_pct")
                atr_med = r.get("atr_pct_median_20")
                ema_gap = r.get("ema_gap_frac")
                if pd.isna(atr_pct) or pd.isna(atr_med) or pd.isna(ema_gap):
                    chop_skips.append({
                        "date": str(date.date()),
                        "symbol": sym,
                        "reason": "warmup",
                        "atr_pct": None if pd.isna(atr_pct) else round(float(atr_pct), 4),
                        "atr_pct_median_20": None if pd.isna(atr_med) else round(float(atr_med), 4),
                        "ema_gap_frac": None if pd.isna(ema_gap) else round(float(ema_gap), 6),
                    })
                    continue
                low_vol = float(atr_pct) < float(atr_med)
                tight_ema = float(ema_gap) < CHOP_EMA_GAP_FRAC
                if low_vol or tight_ema:
                    if low_vol and tight_ema:
                        reason = "both"
                    elif low_vol:
                        reason = "atr_below_median"
                    else:
                        reason = "ema_gap_lt_0.4pct"
                    chop_skips.append({
                        "date": str(date.date()),
                        "symbol": sym,
                        "reason": reason,
                        "atr_pct": round(float(atr_pct), 4),
                        "atr_pct_median_20": round(float(atr_med), 4),
                        "ema_gap_frac": round(float(ema_gap), 6),
                        "ema_gap_pct": round(float(ema_gap) * 100, 4),
                    })
                    print(
                        f"  [{date.date()}] SKIP CHOP {sym} ({reason}) "
                        f"ATR%={float(atr_pct):.3f}<med={float(atr_med):.3f}={low_vol} "
                        f"EMAgap={float(ema_gap)*100:.3f}%<{CHOP_EMA_GAP_FRAC*100:.1f}%={tight_ema}"
                    )
                    continue

                # Sizing
                trade_capital = min(cash * max_cap_pct, cash * 0.15)  # cap at 15% cash per probe to keep diversified
                if trade_capital < 10:
                    continue
                lev = START_LEVERAGE_PROBE
                notional = trade_capital * lev
                pos = Position(sym, date, entry_px, notional, lev, "probe", regime, cash + sum(p.total_margin() for p in positions))
                positions.append(pos)
                cash -= trade_capital
                last_trade_date[sym] = date
                print(f"  [{date.date()}] ENTRY {sym} @ {entry_px:.2f} (probe, cap=${trade_capital:.0f}, lev={lev}x, RSI={r['rsi']:.1f}, PB={r['pullback_pct']:.1f}%)")

        # Record equity curve (MTM)
        equity_curve.append({
            "date": str(date.date()),
            "equity": round(mtm_equity, 2),
            "cash": round(cash, 2),
            "positions_open": len(positions),
            "regime": regime,
            "drawdown_pct": round(dd * 100, 2),
        })

    # Close any remaining positions at last date
    last_date = dates.iloc[-1]
    for pos in list(positions):
        sym_df = asset_dfs[pos.symbol]
        row = sym_df[sym_df["date"] == last_date]
        if row.empty:
            # use last available
            row = sym_df.tail(1)
        exit_price = row.iloc[0]["close"]
        hold_days = (last_date - pos.entry_date).days
        net, gross, fees, slip, funding = trade_pnl(pos, exit_price, hold_days)
        cash += pos.total_margin() + net
        closed_trades.append({
            "entry_date": str(pos.entry_date.date()),
            "exit_date": str(last_date.date()),
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
            "exit_reason": "BACKTEST_END",
        })
    positions = []

    final_equity = cash
    return closed_trades, equity_curve, final_equity, chop_skips


# ─────────────────────── Metrics & Benchmark ───────────────────────

def compute_metrics(trades, equity_curve, start_capital):
    eq = pd.DataFrame(equity_curve)
    if eq.empty:
        return {}
    final = eq["equity"].iloc[-1]
    total_ret = (final - start_capital) / start_capital * 100

    # Drawdown
    eq["peak"] = eq["equity"].cummax()
    eq["dd"] = (eq["peak"] - eq["equity"]) / eq["peak"]
    max_dd = eq["dd"].max() * 100

    # Daily returns for Sharpe
    eq["ret"] = eq["equity"].pct_change().fillna(0)
    if eq["ret"].std() > 0:
        sharpe = eq["ret"].mean() / eq["ret"].std() * math.sqrt(252)
    else:
        sharpe = 0.0

    # Trade stats
    pnls = [t["net_pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    win_rate = len(wins) / len(pnls) * 100 if pnls else 0
    avg_win = statistics.mean(wins) if wins else 0
    avg_loss = statistics.mean(losses) if losses else 0
    profit_factor = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else (float('inf') if wins else 0)
    best = max(pnls) if pnls else 0
    worst = min(pnls) if pnls else 0
    avg_hold = statistics.mean([t["hold_days"] for t in trades]) if trades else 0
    total_fees = sum(t["fees"] + t["slippage"] + t["funding"] for t in trades)
    total_gross = sum(t["gross_pnl"] for t in trades)

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
        "best_trade": round(best, 2),
        "worst_trade": round(worst, 2),
        "avg_hold_days": round(avg_hold, 1),
        "total_costs": round(total_fees, 2),
        "total_gross_pnl": round(total_gross, 2),
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
    # Max DD for HODL
    btc["peak"] = btc["close"].cummax()
    btc["dd"] = (btc["peak"] - btc["close"]) / btc["peak"]
    max_dd = btc["dd"].max() * 100
    return {
        "start_capital": start_capital,
        "btc_entry_price": round(entry, 2),
        "btc_exit_price": round(exit_, 2),
        "final_equity": round(final, 2),
        "total_return_pct": round(ret, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "start_date": str(btc.iloc[0]["date"].date()),
        "end_date": str(btc.iloc[-1]["date"].date()),
    }


# ─────────────────────── Round 4C summary artifacts ───────────────────────

def _cost_to_gross_pct(metrics: dict) -> Optional[float]:
    gross = metrics.get("total_gross_pnl") or 0
    costs = metrics.get("total_costs") or 0
    if gross == 0:
        return None
    return round(costs / abs(gross) * 100, 2)


def write_round4c_summary(metrics, trades, benchmark, regime_counts, chop_skips):
    """Write grok-results/round4_C_chop_filter.json in the prior R4 schema."""
    with open(R3_BASELINE_JSON) as f:
        r3 = json.load(f)
    r3m = r3["metrics"]

    gross = metrics.get("total_gross_pnl") or 0
    cost_pct = _cost_to_gross_pct(metrics)
    r3_cost_pct = _cost_to_gross_pct(r3m)

    start = benchmark.get("start_date")
    end = benchmark.get("end_date")
    window_years = None
    if start and end:
        d0 = datetime.fromisoformat(start)
        d1 = datetime.fromisoformat(end)
        window_years = round((d1 - d0).days / 365.25, 4)
    n_trades = metrics.get("num_trades", 0)
    trades_per_year = round(n_trades / window_years, 2) if window_years else n_trades

    dd = metrics.get("max_drawdown_pct", 0)
    ret = metrics.get("total_return_pct", 0)
    r3_ret = r3m.get("total_return_pct", 0)
    r3_dd = r3m.get("max_drawdown_pct", 0)
    sharpe = metrics.get("sharpe_ratio", 0)

    shield_dd = bool(dd > 20)
    shield_n = bool(n_trades > 25)
    shield_n_yr = bool(trades_per_year > 25) if window_years else False
    shield_veto = bool(shield_dd or shield_n)
    pass_vs = bool(ret >= r3_ret)

    if pass_vs:
        pass_reason = f"return {ret}% >= R3 {r3_ret}%"
    else:
        pass_reason = (
            f"return {ret}% vs R3 {r3_ret}%, DD {dd}% vs {r3_dd}%, "
            f"Sharpe {sharpe} vs {r3m.get('sharpe_ratio')}"
        )

    skip_reasons = dict(Counter(s["reason"] for s in chop_skips))
    exit_reasons = dict(Counter(t["exit_reason"] for t in trades))
    phase_counts = dict(Counter(t["phase"] for t in trades))
    regime_at_entry = dict(Counter(t["regime_at_entry"] for t in trades))

    hyp = {
        "sharpe_ge_0.55": bool(sharpe >= 0.55),
        "cost_pct_down": (
            None if cost_pct is None or r3_cost_pct is None else bool(cost_pct < r3_cost_pct)
        ),
        "mdd_le_r3_plus_2pp": bool(dd <= r3_dd + 2.0),
        "note": (
            "Success hypothesis: Sharpe ≥0.55, cost%↓ vs R3, MDD ≤ R3+2pp. "
            "Reported honestly even if not met. Boss gate pass_vs_round3 is return ≥ R3."
        ),
    }

    def _delta(key, ndigits=None):
        a = metrics.get(key)
        b = r3m.get(key)
        if a is None or b is None:
            return None
        d = a - b
        if ndigits is not None:
            return round(d, ndigits)
        return d

    summary = {
        "test_id": "round4_C_chop_filter",
        "knob": "CHOP_FILTER",
        "knob_detail": {
            "description": (
                "Skip NEW entries/new probes when EITHER daily ATR% is below its 20-bar "
                "median on that symbol OR |EMA20−EMA50|/close < 0.4%. Existing positions "
                "are not force-exited for chop. BE stops, pyramids, regime, sizes, costs, "
                "universe, DD circuit unchanged."
            ),
            "atr_pct_definition": "ATR(14 Wilder) / close × 100 (percent units)",
            "atr_median_bars": ATR_PCT_MEDIAN_BARS,
            "ema_gap_definition": "abs(EMA20-EMA50)/close ; skip if < 0.004 (0.4%)",
            "ema_span": [EMA_FAST_SPAN, EMA_SLOW_SPAN],
            "timeframe": "daily (official hl_backtest.py; not 1h)",
            "applies_to": "new_entries_new_probes_only",
            "engine_file": "grok-engine/round4c_chop_filter.py",
            "base_engine": "bba-engine/hl_backtest.py",
        },
        "round3_baseline": {
            "source": "bba-results/round3-hl-full-2026-09-16.json",
            "metrics": r3m,
            "cost_to_gross_pct": r3_cost_pct,
        },
        "new_metrics": {
            **metrics,
            "cost_to_gross_pct": cost_pct,
        },
        "trades": trades,
        "chop_skips": chop_skips,
        "chop_skip_counts": skip_reasons,
        "exit_reason_counts": exit_reasons,
        "phase_counts": phase_counts,
        "regime_at_entry_counts": regime_at_entry,
        "shield_veto": shield_veto,
        "shield_rules": {
            "max_dd_gt_20": shield_dd,
            "num_trades_gt_25": shield_n,
            "trades_per_year_gt_25": shield_n_yr,
            "max_drawdown_pct": dd,
            "num_trades": n_trades,
            "trades_per_year": trades_per_year,
            "window_years": window_years,
        },
        "comparison_deltas": {
            "total_return_pct": _delta("total_return_pct", 2),
            "max_drawdown_pct": _delta("max_drawdown_pct", 2),
            "sharpe_ratio": _delta("sharpe_ratio", 3),
            "num_trades": _delta("num_trades"),
            "win_rate_pct": _delta("win_rate_pct", 2),
            "profit_factor": _delta("profit_factor", 3),
            "final_equity": _delta("final_equity", 2),
            "total_net_pnl": _delta("total_net_pnl", 2),
            "avg_hold_days": _delta("avg_hold_days", 1),
            "total_costs": _delta("total_costs", 2),
        },
        "pass_vs_round3": pass_vs,
        "pass_vs_round3_reason": pass_reason,
        "shield_pass": (not shield_veto),
        "success_hypothesis": hyp,
        "regime_distribution": {k: int(v) for k, v in regime_counts.items()},
        "benchmark_btc_hodl": benchmark,
        "raw_engine_output": "grok-results/round4_C_chop_filter_raw.json",
        "window": {
            "start_date": start,
            "end_date": end,
            "note": "Same live 1y fetch window as Round 3 (CoinGecko days=365 / yfinance period=1y)",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    Path(SUMMARY_JSON).parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_JSON, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    return summary


def write_round4c_markdown(summary: dict):
    r3m = summary["round3_baseline"]["metrics"]
    m = summary["new_metrics"]
    d = summary["comparison_deltas"]
    hyp = summary["success_hypothesis"]
    shield = summary["shield_rules"]
    vs = "PASS" if summary["pass_vs_round3"] else "FAIL"
    sh = "PASS" if summary["shield_pass"] else "VETO"

    def fmt_delta(v, money=False, pct=False):
        if v is None:
            return "n/a"
        sign = "+" if v > 0 else ""
        if money:
            return f"{sign}{v:.2f}"
        if pct:
            return f"{sign}{v:.2f}"
        return f"{sign}{v}"

    lines = [
        "# Round 4 Test C — CHOP FILTER",
        "",
        "**Date:** 2026-09-16  ",
        "**Test ID:** `round4_C_chop_filter`  ",
        "**Knob:** Skip new entries/new probes when daily ATR% < 20-bar median **OR** |EMA20−EMA50|/close < 0.4%. Existing exits unchanged. One knob only.",
        "",
        "## Verdict",
        "",
        f"**{vs} vs Round 3; SHIELD {sh}**",
        "",
        "| Gate | Result |",
        "|------|--------|",
        f"| vs Round 3 improvement | **{vs}** — {summary['pass_vs_round3_reason']} |",
        (
            f"| Shield (DD≤20% and ≤25 trades) | **{sh}** — DD {shield['max_drawdown_pct']}%, "
            f"trades {shield['num_trades']} ({shield['trades_per_year']}/yr) "
            f"→ `shield_veto={str(summary['shield_veto']).lower()}` |"
        ),
        "",
        "## Metrics: Round 3 vs Round 4C",
        "",
        "| Metric | Round 3 | Round 4C | Delta |",
        "|--------|---------|----------|-------|",
        f"| Final equity | ${r3m['final_equity']:,.2f} | ${m['final_equity']:,.2f} | {fmt_delta(d['final_equity'], money=True)} |",
        f"| Total return % | {r3m['total_return_pct']} | {m['total_return_pct']} | {fmt_delta(d['total_return_pct'], pct=True)} |",
        f"| Max DD % | {r3m['max_drawdown_pct']} | {m['max_drawdown_pct']} | {fmt_delta(d['max_drawdown_pct'], pct=True)} |",
        f"| Sharpe | {r3m['sharpe_ratio']} | {m['sharpe_ratio']} | {fmt_delta(d['sharpe_ratio'])} |",
        f"| Num trades | {r3m['num_trades']} | {m['num_trades']} | {fmt_delta(d['num_trades'])} |",
        f"| Win rate % | {r3m['win_rate_pct']} | {m['win_rate_pct']} | {fmt_delta(d['win_rate_pct'], pct=True)} |",
        f"| Profit factor | {r3m['profit_factor']} | {m['profit_factor']} | {fmt_delta(d['profit_factor'])} |",
        f"| Total costs | ${r3m['total_costs']:,.2f} | ${m['total_costs']:,.2f} | {fmt_delta(d['total_costs'], money=True)} |",
        f"| Cost / gross % | {summary['round3_baseline'].get('cost_to_gross_pct')} | {m.get('cost_to_gross_pct')} |  |",
        f"| Net P&L | ${r3m['total_net_pnl']:,.2f} | ${m['total_net_pnl']:,.2f} | {fmt_delta(d['total_net_pnl'], money=True)} |",
        f"| Avg hold days | {r3m['avg_hold_days']} | {m['avg_hold_days']} | {fmt_delta(d['avg_hold_days'])} |",
        "",
        "## Success hypothesis (honest)",
        "",
        "| Criterion | Result |",
        "|-----------|--------|",
        f"| Sharpe ≥ 0.55 | **{'MET' if hyp['sharpe_ge_0.55'] else 'NOT MET'}** ({m['sharpe_ratio']}) |",
        f"| cost% ↓ vs R3 | **{'MET' if hyp['cost_pct_down'] else 'NOT MET'}** ({m.get('cost_to_gross_pct')}% vs {summary['round3_baseline'].get('cost_to_gross_pct')}%) |",
        f"| MDD ≤ R3 + 2pp | **{'MET' if hyp['mdd_le_r3_plus_2pp'] else 'NOT MET'}** ({m['max_drawdown_pct']}% vs {r3m['max_drawdown_pct']}% + 2pp) |",
        "",
        "## Chop skips (candidate new entries blocked)",
        "",
        f"- Count: **{len(summary.get('chop_skips', []))}**",
        f"- Reasons: `{json.dumps(summary.get('chop_skip_counts', {}))}`",
        "",
        "## Notes",
        "",
        "- Standing: paper only; isolated one-knob test; no blending.",
        "- Engine output only — no invented fills. Raw: `grok-results/round4_C_chop_filter_raw.json`.",
        "- ATR% = ATR(14 Wilder) / close × 100 (percent). EMA gap = abs(EMA20−EMA50)/close. Daily bars.",
        "- Chop filter applies only after R3 entry conditions would have fired; does not flatten existing positions.",
        "- Do NOT ship R4-A, R4-D, or R4-R1. This is isolated C only.",
        "",
        "## Files",
        "",
        "- Engine: `grok-engine/round4c_chop_filter.py`",
        "- Summary: `grok-results/round4_C_chop_filter.json`",
        "- Raw: `grok-results/round4_C_chop_filter_raw.json`",
        "",
    ]
    md_path = _REPO_ROOT / "grok-results" / "2026-09-16-round4c-chop-filter.md"
    md_path.write_text("\n".join(lines))
    return str(md_path)


# ─────────────────────── Main ───────────────────────

def main():
    print("=" * 80)
    print("ROUND 4 TEST C — CHOP FILTER")
    print("BIG BRAIN APE — DRUCKENMILLER STRATEGY BACKTEST ON HYPERLIQUID PERPS")
    print("ONE-KNOB: skip new entries if ATR% < 20-bar median OR EMA gap < 0.4%")
    print("=" * 80)
    print()

    # 1. Load data
    print("Loading market data...")
    all_data = load_all_data()
    print(f"  Loaded {len(all_data)} assets\n")

    # 2. Build regime
    print("Building regime classification...")
    regime_df = build_regime_series(all_data)
    regime_counts = regime_df["regime"].value_counts()
    print(f"  Regime distribution: {dict(regime_counts)}\n")

    # 3. Run backtest
    print("Running backtest...")
    print("-" * 80)
    trades, equity_curve, final_equity, chop_skips = run_backtest(all_data, regime_df)
    print("-" * 80)
    print(f"  Backtest complete. {len(trades)} trades closed. {len(chop_skips)} chop skips.\n")

    # 4. Metrics
    metrics = compute_metrics(trades, equity_curve, START_CAPITAL)
    benchmark = btc_hodl_benchmark(all_data, START_CAPITAL)

    # 5. Print summary
    print("=" * 80)
    print("STRATEGY RESULTS")
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
    print(f"  Total Gross P&L:   ${metrics.get('total_gross_pnl', 0):,.2f}")
    print(f"  Total Net P&L:     ${metrics.get('total_net_pnl', 0):,.2f}")

    print()
    print("=" * 80)
    print("BTC HODL BENCHMARK")
    print("=" * 80)
    print(f"  Start:             ${benchmark.get('start_capital', 0):,.2f} @ ${benchmark.get('btc_entry_price', 0):,.2f}")
    print(f"  Final:             ${benchmark.get('final_equity', 0):,.2f} @ ${benchmark.get('btc_exit_price', 0):,.2f}")
    print(f"  Total Return:      {benchmark.get('total_return_pct', 0):.2f}%")
    print(f"  Max Drawdown:      {benchmark.get('max_drawdown_pct', 0):.2f}%")
    print(f"  Period:            {benchmark.get('start_date', '')} → {benchmark.get('end_date', '')}")

    print()
    strat_ret = metrics.get('total_return_pct', 0)
    hodl_ret = benchmark.get('total_return_pct', 0)
    diff = strat_ret - hodl_ret
    print(f"  Strategy vs HODL:  {diff:+.2f}% ({'OUTPERFORMED' if diff > 0 else 'UNDERPERFORMED'})")

    # 6. Print every trade
    print()
    print("=" * 80)
    print("ALL TRADES")
    print("=" * 80)
    print(f"{'#':>3} {'Entry':>12} {'Exit':>12} {'Symbol':>8} {'Side':>5} {'EntryPx':>10} {'ExitPx':>10} {'P&L':>10} {'Ret%':>7} {'Hold':>5} {'Regime':>10} {'Exit Reason':>16}")
    print("-" * 120)
    for i, t in enumerate(trades, 1):
        print(f"{i:>3} {t['entry_date']:>12} {t['exit_date']:>12} {t['symbol']:>8} {t['side']:>5} "
              f"{t['entry_price']:>10.2f} {t['exit_price']:>10.2f} {t['net_pnl']:>+10.2f} {t['return_pct']:>+7.2f} "
              f"{t['hold_days']:>5} {t['regime_at_entry']:>10} {t['exit_reason']:>16}")

    print()
    print("=" * 80)
    print("CHOP SKIPS (would-have-entered under R3 rules)")
    print("=" * 80)
    print(f"  n={len(chop_skips)}  reasons={dict(Counter(s['reason'] for s in chop_skips))}")
    for s in chop_skips:
        print(f"  {s['date']} {s['symbol']:>6} {s['reason']:<22} ATR%={s.get('atr_pct')} med={s.get('atr_pct_median_20')} gap={s.get('ema_gap_frac')}")

    # 7. Save raw + summary
    Path(OUTPUT_JSON).parent.mkdir(parents=True, exist_ok=True)
    results = {
        "strategy": "Big Brain Ape Druckenmiller — Hyperliquid Perps Backtest (Round 4C CHOP FILTER)",
        "test_id": "round4_C_chop_filter",
        "knob": "CHOP_FILTER",
        "config": {
            "start_capital": START_CAPITAL,
            "max_leverage": MAX_LEVERAGE,
            "max_concurrent": MAX_CONCURRENT,
            "max_position_pct": MAX_POSITION_PCT,
            "dd_defense_threshold": DD_DEFENSE_THRESHOLD,
            "fee_bps_per_side": FEE_BPS,
            "slippage_bps_per_side": SLIPPAGE_BPS,
            "funding_rates_per_8h": FUNDING_RATES,
            "ma_short": MA_SHORT,
            "ma_long": MA_LONG,
            "rsi_period": RSI_PERIOD,
            "rsi_entry_range": [RSI_ENTRY_MIN, RSI_ENTRY_MAX],
            "rsi_exit_max": RSI_EXIT_MAX,
            "pullback_pct": PULLBACK_PCT,
            "max_hold_days": MAX_HOLD_DAYS,
            "chop_atr_period": ATR_PERIOD,
            "chop_atr_pct_median_bars": ATR_PCT_MEDIAN_BARS,
            "chop_ema_gap_frac": CHOP_EMA_GAP_FRAC,
            "chop_atr_pct_units": "percent (ATR/close*100)",
        },
        "regime_distribution": {k: int(v) for k, v in regime_counts.items()},
        "metrics": metrics,
        "benchmark_btc_hodl": benchmark,
        "trades": trades,
        "chop_skips": chop_skips,
        "equity_curve": equity_curve,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nRaw results saved to {OUTPUT_JSON}")

    summary = write_round4c_summary(metrics, trades, benchmark, regime_counts, chop_skips)
    md_path = write_round4c_markdown(summary)
    print(f"Summary saved to {SUMMARY_JSON}")
    print(f"Writeup saved to {md_path}")
    print(f"  pass_vs_round3={summary['pass_vs_round3']}  shield_veto={summary['shield_veto']}")
    print("=" * 80)


if __name__ == "__main__":
    main()
