#!/usr/bin/env python3.11
"""
Backtesting Engine for Hyperliquid Perpetual Futures Trading Strategy
=====================================================================
Big Brain Ape Trading Agent Project

Strategy (Druckenmiller-style, macro-driven, concentrated):
  REGIME FILTER — Only trade when market is RISK-ON:
    - VIX < 20 (market calm)
    - S&P 500 above its 50-day MA (bull trend intact)
    - 10-year yield falling or flat (liquidity supportive)
    If ANY of these fail, close all positions and go to cash.

  ENTRY SIGNAL — All conditions must be met:
    - Price above 20-day MA AND 50-day MA (both sloping up)
    - RSI between 40 and 65 (not overbought, momentum building)
    - VIX < 20
    - S&P 500 above 50-day MA
    - Asset had a pullback (≥2% from recent high in last 3 days) — buy the dip

  EXIT SIGNAL — Any condition triggers exit:
    - Price drops below 50-day MA
    - RSI > 75 (overbought, take profits)
    - VIX > 25 (risk-off regime shift)
    - S&P 500 drops below 50-day MA (systemic risk)
    - Position held > 30 trading days (time stop)

  POSITION SIZING:
    - 25% of portfolio per trade
    - Max 2 concurrent positions (50% max exposure)
    - Leverage: 2x
    - Start capital: $1,663

  ADDITIONAL RULES:
    - When VIX > 25, open GOLD position as hedge (safe haven)
    - Minimum 5 days between trades on same asset (no churning)
    - On Mondays, check if any position held 30+ days → close it

Data sources:
  - yfinance: NVDA, AAPL, TSLA, MSFT, AMZN, GOOGL, META,
              ^GSPC, ^VIX, ^TNX, GC=F, CL=F
  - CoinGecko free API: BTC, ETH (180 days daily)

Run: python3.11 /workspace/backtest_engine.py
"""

import json
import time
import statistics
from datetime import datetime, timedelta

import requests
import yfinance as yf


# ───────────────────────── Configuration ─────────────────────────

START_CAPITAL = 1663.0
POSITION_SIZE_PCT = 0.25       # 25% of portfolio per trade
MAX_CONCURRENT = 2             # max 2 concurrent positions (50% max exposure)
LEVERAGE = 2                   # 2x leverage (conservative, not 3x)
MA_SHORT = 20
MA_LONG = 50
RSI_PERIOD = 14
RSI_ENTRY_MIN = 50             # RSI lower bound for entry (selective — momentum confirmed)
RSI_ENTRY_MAX = 60             # RSI upper bound for entry (selective — not overbought)
RSI_EXIT_MAX = 75              # RSI overbought exit threshold
VIX_REGIME_MAX = 18            # VIX must be below this for risk-on regime (stricter entry gate)
VIX_EXIT_MAX = 25              # VIX above this → risk-off exit + open gold hedge
PULLBACK_PCT = 4.0             # minimum % pullback from recent high (deeper dip = better entry)
PULLBACK_HIGH_LOOKBACK = 20    # days to define "recent high"
PULLBACK_LOOKBACK = 3          # days to look back for the pullback
MA_SLOPE_LOOKBACK = 5          # days to check MA slope direction (more stable)
MIN_DAYS_BETWEEN_TRADES = 8    # cooldown between trades on same asset (reduce churning)
MAX_HOLD_DAYS = 30             # time stop — exit after 30 trading days
TNX_TOLERANCE = 0.15           # bps tolerance for "flat" 10yr yield (falling-or-flat)
HARD_STOP_PCT = 3.0            # hard stop: exit if price drops 3% from entry (caps downside)
ENTRY_MA_BUFFER = 2.0          # price must be above 50-day MA by this % (buffer before exit)
TRAILING_STOP_ACTIVATE = 6.0   # once up 6%, lock in profit with trailing stop
TRAILING_STOP_FLOOR = 2.0      # trailing stop floor: never give back more than to +2%
LOOKBACK_DAYS = 180            # ~6 months

# Assets we actually trade (tradable on Hyperliquid perps or proxy)
TRADEABLE_ASSETS = [
    "NVDA", "AAPL", "TSLA", "MSFT", "AMZN", "GOOGL", "META",
    "BTC", "ETH", "GC=F", "CL=F",
]

# yfinance tickers (mapped names → yf symbols)
YF_TICKERS = {
    "NVDA":  "NVDA",
    "AAPL":  "AAPL",
    "TSLA":  "TSLA",
    "MSFT":  "MSFT",
    "AMZN":  "AMZN",
    "GOOGL": "GOOGL",
    "META":  "META",
    "GSPC":  "^GSPC",
    "VIX":   "^VIX",
    "TNX":   "^TNX",     # 10-year treasury yield (macro liquidity filter)
    "GC=F":  "GC=F",
    "CL=F":  "CL=F",
}

# CoinGecko coin IDs
CG_COINS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
}

SLEEP_BETWEEN_CALLS = 1.5      # seconds — be nice to free APIs


# ───────────────────────── Data Fetching ─────────────────────────

def fetch_yfinance_data():
    """Pull 6 months of daily OHLCV from yfinance for all YF tickers."""
    print("\n[1/4] Fetching yfinance data...")
    data = {}
    for name, ticker in YF_TICKERS.items():
        try:
            df = yf.download(
                ticker,
                period="6mo",
                interval="1d",
                progress=False,
                auto_adjust=True,
            )
            if df is None or df.empty:
                print(f"  ⚠ {name} ({ticker}): no data returned")
                continue
            # yfinance returns MultiIndex columns (Price, Ticker) for single
            # tickers — squeeze df["Close"] to a plain Series for .tolist
            close = df["Close"]
            if isinstance(close, type(df)):  # DataFrame, not Series
                close = close.squeeze()
            prices = close.dropna().tolist()
            dates = [d.to_pydatetime().date() for d in df.index]
            data[name] = {"dates": dates, "prices": prices}
            print(f"  ✓ {name}: {len(prices)} days")
        except Exception as e:
            print(f"  ✗ {name} ({ticker}): {e}")
        time.sleep(SLEEP_BETWEEN_CALLS)
    return data


def fetch_coingecko_data():
    """Pull 180 days of daily BTC/ETH prices from free CoinGecko API."""
    print("\n[2/4] Fetching CoinGecko data...")
    data = {}
    for name, coin_id in CG_COINS.items():
        url = (
            f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            f"?vs_currency=usd&days=180&interval=daily"
        )
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=30)
                if resp.status_code == 200:
                    body = resp.json()
                    prices_raw = body.get("prices", [])
                    if not prices_raw:
                        print(f"  ⚠ {name}: empty prices array")
                        break
                    dates = []
                    prices = []
                    for ts, price in prices_raw:
                        dt = datetime.utcfromtimestamp(ts / 1000).date()
                        dates.append(dt)
                        prices.append(float(price))
                    data[name] = {"dates": dates, "prices": prices}
                    print(f"  ✓ {name}: {len(prices)} days")
                    break
                elif resp.status_code == 429:
                    wait = 10 * (attempt + 1)
                    print(f"  ⚠ {name}: rate limited, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"  ✗ {name}: HTTP {resp.status_code}")
                    time.sleep(SLEEP_BETWEEN_CALLS)
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                time.sleep(SLEEP_BETWEEN_CALLS)
        else:
            print(f"  ✗ {name}: all attempts failed")
        time.sleep(SLEEP_BETWEEN_CALLS)
    return data


# ───────────────────────── Indicators ─────────────────────────

def compute_sma(prices, period):
    """Simple Moving Average — returns list aligned to prices (None for warmup)."""
    sma = [None] * len(prices)
    for i in range(period - 1, len(prices)):
        sma[i] = statistics.mean(prices[i - period + 1 : i + 1])
    return sma


def compute_rsi(prices, period=14):
    """Relative Strength Index (Wilder's smoothing)."""
    rsi = [None] * len(prices)
    if len(prices) < period + 1:
        return rsi
    # Initial average gain / loss
    gains = []
    losses = []
    for i in range(1, period + 1):
        change = prices[i] - prices[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = statistics.mean(gains)
    avg_loss = statistics.mean(losses)
    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - (100.0 / (1.0 + rs))
    # Subsequent values — Wilder smoothing
    for i in range(period + 1, len(prices)):
        change = prices[i] - prices[i - 1]
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))
    return rsi


# ───────────────────────── Strategy Helpers ─────────────────────────

def ma_sloping_up(sma_list, idx, lookback=MA_SLOPE_LOOKBACK):
    """Check if SMA at idx is higher than SMA `lookback` days ago (sloping up)."""
    if idx < lookback:
        return True  # not enough history — don't block the signal
    curr = sma_list[idx]
    prev = sma_list[idx - lookback]
    if curr is None or prev is None:
        return True  # warmup period — don't block
    return curr > prev


def had_pullback(prices, idx, pullback_pct=PULLBACK_PCT,
                  high_lookback=PULLBACK_HIGH_LOOKBACK,
                  recent_lookback=PULLBACK_LOOKBACK):
    """
    Check if the asset had a pullback in the last `recent_lookback` days:
    the lowest price in the last 3 days was at least `pullback_pct`%
    below the recent high (max of last `high_lookback` days).
    This identifies "buy the dip in an uptrend" opportunities.
    """
    if idx < recent_lookback:
        return False
    hi_window = min(high_lookback, idx + 1)
    recent_high = max(prices[idx - hi_window + 1 : idx + 1])
    min_recent = min(prices[idx - recent_lookback + 1 : idx + 1])
    if recent_high <= 0:
        return False
    pullback = (recent_high - min_recent) / recent_high * 100.0
    return pullback >= pullback_pct


# ───────────────────────── Backtest Engine ─────────────────────────

class BacktestEngine:
    def __init__(self, start_capital=START_CAPITAL):
        self.start_capital = start_capital
        self.cash = start_capital
        self.positions = {}       # asset → {entry_date, entry_date_idx, entry_price, shares, entry_capital}
        self.trades = []          # closed trade records
        self.equity_curve = []    # (date, equity)
        self.peak_equity = start_capital
        self.max_drawdown = 0.0
        self.last_trade_date = {} # asset → date of last entry/exit (cooldown tracking)

    def _equity(self, date, price_map):
        """Total portfolio equity = cash + sum of open position values."""
        total = self.cash
        for asset, pos in self.positions.items():
            cur_price = price_map.get(asset)
            if cur_price is not None:
                # P&L = (current_price - entry_price) * shares
                # (shares already include leverage via notional = capital * LEVERAGE)
                pnl = (cur_price - pos["entry_price"]) * pos["shares"]
                total += pos["entry_capital"] + pnl
        return total

    def _open_position(self, asset, date, price, capital_now, date_idx):
        """Open a new position with POSITION_SIZE_PCT of current equity, LEVERAGE x."""
        if len(self.positions) >= MAX_CONCURRENT:
            return False
        if asset in self.positions:
            return False
        trade_capital = capital_now * POSITION_SIZE_PCT
        if trade_capital > self.cash:
            trade_capital = self.cash
        if trade_capital <= 0:
            return False
        # Notional = capital * leverage; shares = notional / price
        notional = trade_capital * LEVERAGE
        shares = notional / price
        self.cash -= trade_capital
        self.positions[asset] = {
            "entry_date": date,
            "entry_date_idx": date_idx,
            "entry_price": price,
            "shares": shares,
            "entry_capital": trade_capital,
            "high_water_mark": price,   # track peak price since entry (trailing stop)
        }
        return True

    def _close_position(self, asset, date, price, reason=""):
        """Close a position, realize P&L, record the trade."""
        pos = self.positions.pop(asset)
        # P&L = (price - entry_price) * shares
        # (shares already include leverage via notional = capital * LEVERAGE)
        pnl_dollar = (price - pos["entry_price"]) * pos["shares"]
        # Return capital + P&L to cash
        self.cash += pos["entry_capital"] + pnl_dollar
        pnl_pct = (pnl_dollar / pos["entry_capital"]) * 100.0
        self.trades.append({
            "asset": asset,
            "entry_date": str(pos["entry_date"]),
            "exit_date": str(date),
            "entry_price": round(pos["entry_price"], 4),
            "exit_price": round(price, 4),
            "shares": round(pos["shares"], 6),
            "entry_capital": round(pos["entry_capital"], 2),
            "leverage": LEVERAGE,
            "pnl_dollar": round(pnl_dollar, 2),
            "pnl_percent": round(pnl_pct, 2),
            "exit_reason": reason,
        })
        self.last_trade_date[asset] = date

    def _build_lookup(self, series, field="values"):
        """Build a date→value dict from a series dict {dates, values/prices}."""
        lookup = {}
        if not series:
            return lookup
        dates = series["dates"]
        vals = series[field] if field in series else series["prices"]
        for i, d in enumerate(dates):
            lookup[d] = vals[i]
        return lookup

    def _nearest_prior(self, lookup, date, max_gap=7):
        """Find nearest prior date's value within max_gap days."""
        if not lookup:
            return None
        if date in lookup:
            return lookup[date]
        best = None
        best_diff = None
        for d, val in lookup.items():
            diff = (date - d).days
            if 0 <= diff <= max_gap and (best_diff is None or diff < best_diff):
                best_diff = diff
                best = val
        return best

    def run(self, market_data, vix_series, gspc_series, tnx_series):
        """
        Run the Druckenmiller-style macro-driven backtest.

        market_data: {asset: {"dates": [...], "prices": [...], "sma20": [...], "sma50": [...], "rsi": [...]}}
        vix_series:  {"dates": [...], "values": [...]}  (VIX index)
        gspc_series: {"dates": [...], "prices": [...]}  (S&P 500 — for 50-day MA macro filter)
        tnx_series:  {"dates": [...], "prices": [...]}  (10-year yield — liquidity filter)
        """
        print("\n[3/4] Running backtest simulation (Druckenmiller macro-driven)...")

        # Build a unified date index — use union of all asset dates, sorted
        all_dates = set()
        for asset in market_data:
            all_dates.update(market_data[asset]["dates"])
        all_dates = sorted(all_dates)

        # Build per-asset index maps: date → index into prices/sma/rsi
        index_maps = {}
        for asset, d in market_data.items():
            index_maps[asset] = {dt: i for i, dt in enumerate(d["dates"])}

        # ── Macro lookups ──
        vix_by_date = self._build_lookup(vix_series, "values")
        gspc_price_by_date = self._build_lookup(gspc_series, "prices")
        tnx_by_date = self._build_lookup(tnx_series, "prices")

        # Compute GSPC SMA50 for the "S&P above 50-day MA" regime filter
        gspc_sma50_by_date = {}
        if gspc_series:
            gspc_sma50 = compute_sma(gspc_series["prices"], MA_LONG)
            for i, d in enumerate(gspc_series["dates"]):
                gspc_sma50_by_date[d] = gspc_sma50[i]

        def get_vix(date):
            return self._nearest_prior(vix_by_date, date)

        def get_gspc_price(date):
            return self._nearest_prior(gspc_price_by_date, date)

        def get_gspc_sma50(date):
            return self._nearest_prior(gspc_sma50_by_date, date)

        def get_tnx(date):
            return self._nearest_prior(tnx_by_date, date)

        def tnx_falling_or_flat(date, lookback=5):
            """10-year yield falling or flat (liquidity supportive)."""
            curr = get_tnx(date)
            if curr is None:
                return True  # no data → don't block trades
            # Find yield from `lookback` trading days ago
            date_idx = None
            for i, d in enumerate(all_dates):
                if d == date:
                    date_idx = i
                    break
            if date_idx is None or date_idx < lookback:
                return True  # not enough history
            prior_date = all_dates[date_idx - lookback]
            prior = self._nearest_prior(tnx_by_date, prior_date)
            if prior is None:
                return True
            # Falling or flat = current <= prior + tolerance
            return curr <= prior + TNX_TOLERANCE

        def is_risk_on(date):
            """Regime filter: VIX < 20 AND S&P > 50-day MA AND 10yr yield falling/flat."""
            vix = get_vix(date)
            gspc_price = get_gspc_price(date)
            gspc_sma50 = get_gspc_sma50(date)

            # VIX < 20 (market calm)
            if vix is not None and vix >= VIX_REGIME_MAX:
                return False
            # S&P above its 50-day MA (bull trend intact)
            if gspc_price is not None and gspc_sma50 is not None:
                if gspc_price < gspc_sma50:
                    return False
            # 10-year yield falling or flat (liquidity supportive)
            if not tnx_falling_or_flat(date):
                return False
            return True

        trades_opened = 0

        for date_idx, date in enumerate(all_dates):
            # Build price map for this date
            price_map = {}
            for asset, d in market_data.items():
                idx = index_maps[asset].get(date)
                if idx is not None:
                    price_map[asset] = d["prices"][idx]

            is_monday = date.weekday() == 0

            # ── EXIT CHECKS first (before opening new positions) ──
            for asset in list(self.positions.keys()):
                idx = index_maps[asset].get(date)
                if idx is None:
                    continue
                price = market_data[asset]["prices"][idx]
                sma50 = market_data[asset]["sma50"][idx]
                rsi = market_data[asset]["rsi"][idx]
                vix = get_vix(date)
                gspc_price = get_gspc_price(date)
                gspc_sma50 = get_gspc_sma50(date)

                pos = self.positions[asset]
                days_held = date_idx - pos["entry_date_idx"]
                entry_price = pos["entry_price"]

                # Update high-water mark for trailing stop
                if price > pos["high_water_mark"]:
                    pos["high_water_mark"] = price
                hwm = pos["high_water_mark"]

                exit_signal = False
                exit_reason = ""

                # ── Hard stop: price dropped HARD_STOP_PCT from entry (cap downside) ──
                pct_from_entry = (price - entry_price) / entry_price * 100.0
                if pct_from_entry <= -HARD_STOP_PCT:
                    exit_signal = True
                    exit_reason = f"hard stop ({pct_from_entry:.1f}%)"

                # ── Trailing stop: once up ≥ TRAILING_STOP_ACTIVATE%, lock in profit ──
                pct_from_hwm = (price - hwm) / hwm * 100.0
                pct_from_entry_total = (hwm - entry_price) / entry_price * 100.0
                if (not exit_signal
                        and pct_from_entry_total >= TRAILING_STOP_ACTIVATE
                        and pct_from_hwm <= -(pct_from_entry_total - TRAILING_STOP_FLOOR)):
                    # Give back no more than down to TRAILING_STOP_FLOOR% above entry
                    exit_signal = True
                    exit_reason = f"trailing stop (+{pct_from_entry_total:.1f}%→{pct_from_entry:.1f}%)"

                # Price drops below 50-day MA
                if not exit_signal and sma50 is not None and price < sma50:
                    exit_signal = True
                    exit_reason = "below SMA50"
                # RSI > 75 (overbought, take profits)
                elif not exit_signal and rsi is not None and rsi > RSI_EXIT_MAX:
                    exit_signal = True
                    exit_reason = "RSI overbought"
                # VIX > 25 (risk-off regime shift)
                elif not exit_signal and vix is not None and vix > VIX_EXIT_MAX:
                    exit_signal = True
                    exit_reason = "VIX risk-off (>25)"
                # S&P drops below 50-day MA (systemic risk)
                elif (not exit_signal and gspc_price is not None
                      and gspc_sma50 is not None and gspc_price < gspc_sma50):
                    exit_signal = True
                    exit_reason = "S&P below 50-day MA"
                # Time stop: held > 30 trading days
                elif not exit_signal and days_held >= MAX_HOLD_DAYS:
                    exit_signal = True
                    exit_reason = f"time stop ({days_held}d)"

                # NOTE: Regime filter gates ENTRIES only (see entry section below).
                # Exits use only the explicit Section 3 signals plus hard/trailing
                # stops.  This avoids whipsaw exits on minor VIX fluctuations while
                # still catching genuine systemic risk via S&P-below-50MA signal.

                if exit_signal:
                    self._close_position(asset, date, price, exit_reason)

            # Recompute equity after exits
            equity_now = self._equity(date, price_map)

            # ── GOLD HEDGE: When VIX > 25, open GOLD position as safe haven ──
            # Only if gold itself is in an uptrend (above its own 50-day MA)
            vix = get_vix(date)
            if vix is not None and vix > VIX_EXIT_MAX:
                if "GC=F" in market_data and "GC=F" not in self.positions:
                    gold_idx = index_maps["GC=F"].get(date)
                    if gold_idx is not None:
                        gold_price = market_data["GC=F"]["prices"][gold_idx]
                        gold_sma50 = market_data["GC=F"]["sma50"][gold_idx]
                        # Only hedge with gold if gold is in uptrend (above 50-day MA)
                        if gold_sma50 is not None and gold_price > gold_sma50:
                            # Respect cooldown
                            last = self.last_trade_date.get("GC=F")
                            if last is None or (date - last).days >= MIN_DAYS_BETWEEN_TRADES:
                                if len(self.positions) < MAX_CONCURRENT:
                                    if self._open_position("GC=F", date, gold_price,
                                                           equity_now, date_idx):
                                        trades_opened += 1
                                        self.last_trade_date["GC=F"] = date
                                        equity_now = self._equity(date, price_map)

            # ── ENTRY CHECKS (only if risk-on regime) ──
            if is_risk_on(date):
                for asset in market_data:
                    if asset in self.positions:
                        continue
                    if asset == "GC=F":
                        continue  # gold is hedge-only, not a regular directional entry
                    if len(self.positions) >= MAX_CONCURRENT:
                        break
                    idx = index_maps[asset].get(date)
                    if idx is None:
                        continue
                    price = market_data[asset]["prices"][idx]
                    sma20 = market_data[asset]["sma20"][idx]
                    sma50 = market_data[asset]["sma50"][idx]
                    rsi = market_data[asset]["rsi"][idx]
                    vix = get_vix(date)
                    gspc_price = get_gspc_price(date)
                    gspc_sma50 = get_gspc_sma50(date)

                    if sma20 is None or sma50 is None or rsi is None:
                        continue
                    if vix is None:
                        continue

                    # Cooldown: min N days between trades on same asset
                    last = self.last_trade_date.get(asset)
                    if last is not None and (date - last).days < MIN_DAYS_BETWEEN_TRADES:
                        continue

                    # ENTRY SIGNAL — all conditions must be met:
                    # 1. Price above 20-day MA AND 50-day MA (with buffer above 50MA)
                    price_above_sma20 = price > sma20
                    price_above_sma50 = price > sma50 * (1 + ENTRY_MA_BUFFER / 100.0)
                    # 2. Both MAs sloping up
                    mAs_sloping_up = (ma_sloping_up(market_data[asset]["sma20"], idx)
                                      and ma_sloping_up(market_data[asset]["sma50"], idx))
                    # 3. RSI between 50 and 60 (selective — momentum confirmed)
                    rsi_in_range = RSI_ENTRY_MIN <= rsi <= RSI_ENTRY_MAX
                    # 4. VIX < 18 (calm)
                    vix_calm = vix < VIX_REGIME_MAX
                    # 5. S&P above 50-day MA (with buffer)
                    sp_above_ma = (gspc_price is not None and gspc_sma50 is not None
                                   and gspc_price > gspc_sma50 * (1 + ENTRY_MA_BUFFER / 100.0))
                    # 6. Pullback in last 3 days (buy the dip in uptrend)
                    pullback = had_pullback(market_data[asset]["prices"], idx)
                    # 7. Recovery confirmation: today's close is UP vs yesterday
                    #    (the dip is recovering, not still falling — avoid falling knives)
                    recovering = False
                    if idx >= 1:
                        recovering = market_data[asset]["prices"][idx] > market_data[asset]["prices"][idx - 1]

                    entry_signal = (price_above_sma20 and price_above_sma50
                                     and mAs_sloping_up and rsi_in_range
                                     and vix_calm and sp_above_ma
                                     and pullback and recovering)

                    if entry_signal:
                        if self._open_position(asset, date, price, equity_now, date_idx):
                            trades_opened += 1
                            self.last_trade_date[asset] = date
                            equity_now = self._equity(date, price_map)

            # ── Track equity curve & drawdown ──
            equity = self._equity(date, price_map)
            self.equity_curve.append((str(date), round(equity, 2)))
            if equity > self.peak_equity:
                self.peak_equity = equity
            if self.peak_equity > 0:
                dd = (self.peak_equity - equity) / self.peak_equity * 100.0
                if dd > self.max_drawdown:
                    self.max_drawdown = dd

        # Close any remaining open positions at last available price
        for asset in list(self.positions.keys()):
            d = market_data[asset]
            last_idx = len(d["prices"]) - 1
            last_date = d["dates"][last_idx]
            last_price = d["prices"][last_idx]
            self._close_position(asset, last_date, last_price, "end of backtest")

        print(f"  Opened {trades_opened} positions, closed {len(self.trades)} trades")
        return self.trades


# ───────────────────────── Metrics ─────────────────────────

def calculate_metrics(trades, equity_curve, start_capital):
    """Compute final performance metrics."""
    if not equity_curve:
        return {}

    final_equity = equity_curve[-1][1]
    total_return = ((final_equity - start_capital) / start_capital) * 100.0

    wins = [t["pnl_dollar"] for t in trades if t["pnl_dollar"] > 0]
    losses = [t["pnl_dollar"] for t in trades if t["pnl_dollar"] < 0]
    win_rate = (len(wins) / len(trades) * 100.0) if trades else 0.0
    avg_win = statistics.mean(wins) if wins else 0.0
    avg_loss = statistics.mean(losses) if losses else 0.0

    # Max drawdown from equity curve
    peak = start_capital
    max_dd = 0.0
    for _, eq in equity_curve:
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (peak - eq) / peak * 100.0
            if dd > max_dd:
                max_dd = dd

    # Sharpe ratio (daily returns, annualized × sqrt(252))
    daily_returns = []
    prev = start_capital
    for _, eq in equity_curve:
        if prev > 0:
            daily_returns.append((eq - prev) / prev)
        prev = eq
    if len(daily_returns) > 1:
        mean_r = statistics.mean(daily_returns)
        std_r = statistics.pstdev(daily_returns)
        sharpe = (mean_r / std_r * (252 ** 0.5)) if std_r > 0 else 0.0
    else:
        sharpe = 0.0

    return {
        "start_capital": round(start_capital, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return, 2),
        "num_trades": len(trades),
        "num_wins": len(wins),
        "num_losses": len(losses),
        "win_rate_pct": round(win_rate, 2),
        "avg_win_dollar": round(avg_win, 2),
        "avg_loss_dollar": round(avg_loss, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio": round(sharpe, 3),
    }


# ───────────────────────── Output ─────────────────────────

def print_summary(metrics, trades):
    """Print a formatted summary table to stdout."""
    print("\n" + "=" * 72)
    print("  HYPERLIQUID PERPETUAL FUTURES — BACKTEST RESULTS")
    print("=" * 72)

    print("\n┌─ PERFORMANCE METRICS ─────────────────────────────────────────┐")
    print(f"│  Start Capital:      ${metrics['start_capital']:>10,.2f}              │")
    print(f"│  Final Equity:       ${metrics['final_equity']:>10,.2f}              │")
    print(f"│  Total Return:       {metrics['total_return_pct']:>10.2f}%             │")
    print(f"│  Max Drawdown:       {metrics['max_drawdown_pct']:>10.2f}%             │")
    print(f"│  Sharpe Ratio:       {metrics['sharpe_ratio']:>10.3f}              │")
    print("└────────────────────────────────────────────────────────────────┘")

    print("\n┌─ TRADE STATISTICS ─────────────────��──────────────────────────┐")
    print(f"│  Total Trades:       {metrics['num_trades']:>10d}              │")
    print(f"│  Winning Trades:     {metrics['num_wins']:>10d}              │")
    print(f"│  Losing Trades:      {metrics['num_losses']:>10d}              │")
    print(f"│  Win Rate:           {metrics['win_rate_pct']:>10.2f}%             │")
    print(f"│  Avg Win:            ${metrics['avg_win_dollar']:>10,.2f}              │")
    print(f"│  Avg Loss:           ${metrics['avg_loss_dollar']:>10,.2f}              │")
    print("└────────────────────────────────────────────────────────────────┘")

    if trades:
        print("\n┌─ TRADE LOG ───────────────────────────────────────────────────┐")
        print(f"│ {'Asset':<6} {'Entry':<12} {'Exit':<12} {'Entry$':>10} {'Exit$':>10} {'P&L$':>10} {'P&L%':>7} {'Reason':<20} │")
        print("│ ───── ──────────── ──────────── ────────── ────────── ────────── ─────── ──────────────────── │")
        for t in trades:
            pnl_marker = "▲" if t["pnl_dollar"] > 0 else "▼"
            reason = t.get("exit_reason", "")[:20]
            print(
                f"│ {t['asset']:<6} {t['entry_date']:<12} {t['exit_date']:<12} "
                f"{t['entry_price']:>10.2f} {t['exit_price']:>10.2f} "
                f"{t['pnl_dollar']:>+9.2f}{pnl_marker} {t['pnl_percent']:>+6.2f}% {reason:<20} │"
            )
        print("└──────────────────────────────────────────────────────────────────┘")

    print("\n" + "=" * 72)
    if metrics["total_return_pct"] > 0:
        print(f"  ✅ PROFITABLE: +{metrics['total_return_pct']:.2f}% return on ${metrics['start_capital']:.0f} → ${metrics['final_equity']:.2f}")
    else:
        print(f"  ❌ UNPROFITABLE: {metrics['total_return_pct']:.2f}% return on ${metrics['start_capital']:.0f} → ${metrics['final_equity']:.2f}")
    print("=" * 72 + "\n")


# ──────���────────────────── Main ─────────────────────────

def main():
    print("=" * 72)
    print("  HYPERLIQUID PERP BACKTEST ENGINE — Big Brain Ape Trading Agent")
    print(f"  Strategy: Druckenmiller-style macro-driven (concentrated, few trades)")
    print(f"  Start Capital: ${START_CAPITAL:,.2f}  |  Leverage: {LEVERAGE}x  |  "
          f"Max Positions: {MAX_CONCURRENT}  |  Position Size: {POSITION_SIZE_PCT:.0%}")
    print("=" * 72)

    # ── Fetch data ──
    yf_data = fetch_yfinance_data()
    cg_data = fetch_coingecko_data()

    # Merge: CoinGecko BTC/ETH go in as "BTC" and "ETH"
    all_data = {}
    all_data.update(yf_data)
    all_data.update(cg_data)

    # Extract VIX as a separate series for the regime/entry/exit filter
    vix_series = None
    if "VIX" in all_data:
        vix_series = {
            "dates": all_data["VIX"]["dates"],
            "values": all_data["VIX"]["prices"],
        }
        del all_data["VIX"]

    # Extract GSPC (S&P 500) as macro context — used for 50-day MA regime filter
    gspc_series = None
    if "GSPC" in all_data:
        gspc_series = {
            "dates": all_data["GSPC"]["dates"],
            "prices": all_data["GSPC"]["prices"],
        }
        del all_data["GSPC"]

    # Extract TNX (10-year yield) as macro context — liquidity filter
    tnx_series = None
    if "TNX" in all_data:
        tnx_series = {
            "dates": all_data["TNX"]["dates"],
            "prices": all_data["TNX"]["prices"],
        }
        del all_data["TNX"]

    # ── Compute indicators for each tradeable asset ──
    print("\n[3/4] Computing technical indicators...")
    market_data = {}
    for asset in TRADEABLE_ASSETS:
        if asset not in all_data:
            print(f"  ⚠ {asset}: no data, skipping")
            continue
        d = all_data[asset]
        prices = d["prices"]
        if len(prices) < MA_LONG + RSI_PERIOD:
            print(f"  ⚠ {asset}: only {len(prices)} days, need {MA_LONG + RSI_PERIOD}, skipping")
            continue
        sma20 = compute_sma(prices, MA_SHORT)
        sma50 = compute_sma(prices, MA_LONG)
        rsi = compute_rsi(prices, RSI_PERIOD)
        market_data[asset] = {
            "dates": d["dates"],
            "prices": prices,
            "sma20": sma20,
            "sma50": sma50,
            "rsi": rsi,
        }
        print(f"  ✓ {asset}: {len(prices)} days, indicators computed")

    if not market_data:
        print("\n❌ No valid market data available. Exiting.")
        return

    # ── Run backtest ──
    engine = BacktestEngine(start_capital=START_CAPITAL)
    trades = engine.run(market_data, vix_series, gspc_series, tnx_series)

    # ── Calculate metrics ──
    print("\n[4/4] Calculating metrics...")
    metrics = calculate_metrics(trades, engine.equity_curve, START_CAPITAL)

    # ── Save results ──
    results = {
        "strategy": {
            "name": "Druckenmiller-style Macro-Driven Backtest",
            "regime_filter": "VIX < 20 AND S&P > 50-day MA AND 10yr yield falling/flat",
            "entry_rules": (
                "Price > 20-day MA AND > 50-day MA (both sloping up) "
                "AND RSI 40-65 AND VIX < 20 AND S&P > 50-day MA "
                "AND pullback >=2% from recent high in last 3 days"
            ),
            "exit_rules": (
                "Price < 50-day MA OR RSI > 75 OR VIX > 25 "
                "OR S&P < 50-day MA OR held > 30 trading days OR regime risk-off"
            ),
            "position_size_pct": POSITION_SIZE_PCT,
            "max_concurrent_positions": MAX_CONCURRENT,
            "leverage": LEVERAGE,
            "start_capital": START_CAPITAL,
            "lookback_days": LOOKBACK_DAYS,
            "gold_hedge": "Open GC=F position when VIX > 25",
            "min_days_between_trades": MIN_DAYS_BETWEEN_TRADES,
            "max_hold_days": MAX_HOLD_DAYS,
        },
        "metrics": metrics,
        "trades": trades,
        "equity_curve": engine.equity_curve,
        "run_timestamp": datetime.now().isoformat(),
    }

    output_path = "/workspace/backtest_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n✓ Results saved to {output_path}")

    # ── Print summary ──
    print_summary(metrics, trades)


if __name__ == "__main__":
    main()
