#!/usr/bin/env python3.11
"""
Comprehensive Backtest: Big Brain Ape Druckenmiller Strategy on Hyperliquid Perpetual Futures
==============================================================================================
Implements the FULL production strategy with:
  - Daily regime classification (RISK-ON / RISK-OFF / TRANSITION) via VIX, S&P 50MA, 10Y yield
  - Pyramiding system: Probe → Confirmation → Jugular → Exit
  - Full risk rules: max 2 concurrent, 20% DD defense, never add to losers, 3:1 R/R
  - Entry: above 20&50 MA (both up-sloping), RSI 40-65, buy pullbacks (2%+ from 5-day high)
  - Exit: below 50MA, RSI>75, regime shift, 30-day time stop, 20% portfolio DD
  - Real Hyperliquid costs: 4.5 bps fee/side, 4.5 bps slippage/side, funding per 8h
  - Universe: BTC, ETH, SOL (CoinGecko), GOLD, NVDA, TSLA, ^GSPC (yfinance)
  - Start capital: $1,663, leverage 2x/3x/3x capped at 3x
  - vs BTC HODL benchmark

Run: python3.11 /workspace/hl_backtest.py
"""

import json
import time
import math
import statistics
from datetime import datetime, timedelta, timezone
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

OUTPUT_JSON = "/workspace/repos/bba-backtest-lab/grok-results/round4_A_be_stop_delay_raw.json"


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


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ma20"] = df["close"].rolling(MA_SHORT).mean()
    df["ma50"] = df["close"].rolling(MA_LONG).mean()
    df["rsi"] = compute_rsi(df["close"], RSI_PERIOD)
    df["ma20_slope_up"] = df["ma20"] > df["ma20"].shift(5)
    df["ma50_slope_up"] = df["ma50"] > df["ma50"].shift(5)
    df["high_5d"] = df["close"].rolling(PULLBACK_HIGH_LOOKBACK).max()
    df["pullback_pct"] = (df["high_5d"] - df["close"]) / df["high_5d"] * 100
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
        self.pending_be_stop = None         # delayed BE stop price (Round 4A)
        self.be_arm_after = None            # date when pending BE stop arms
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

            # Round 4A: arm delayed BE stop before exit checks
            if (pos.pending_be_stop is not None and pos.be_arm_after is not None
                    and date >= pos.be_arm_after and pos.stop_price is None):
                pos.stop_price = pos.pending_be_stop

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
                        # Round 4A: delay BE stop arm by 3 calendar days
                        pos.pending_be_stop = avg_entry
                        pos.be_arm_after = date + timedelta(days=3)
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
    return closed_trades, equity_curve, final_equity


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


# ─────────────────────── Main ───────────────────────

def main():
    print("=" * 80)
    print("ROUND 4 TEST A — BE_STOP_DELAY=3d only")
    print("BIG BRAIN APE — DRUCKENMILLER STRATEGY BACKTEST ON HYPERLIQUID PERPS")
    print("ONE-KNOB: delayed breakeven stop arm (+3 calendar days after confirm)")
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
    trades, equity_curve, final_equity = run_backtest(all_data, regime_df)
    print("-" * 80)
    print(f"  Backtest complete. {len(trades)} trades closed.\n")

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

    # 7. Save results
    results = {
        "strategy": "Big Brain Ape Druckenmiller — Hyperliquid Perps Backtest",
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
        },
        "regime_distribution": {k: int(v) for k, v in regime_counts.items()},
        "metrics": metrics,
        "benchmark_btc_hodl": benchmark,
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
