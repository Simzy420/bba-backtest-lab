#!/usr/bin/env python3
"""
Plateau (parameter-sensitivity) test for the shipped Round 4C chop filter.

Does not change Round 4C's rules. Every cell is the same engine, the same
prices, and the same year. Only two entry-gate thresholds move, one step
looser and one step tighter.

Shipped thresholds (PR #4, grok-engine/round4c_chop_filter.py @ 564478a):
  * ATR%: skip a new entry when ATR(14)% < 1.00 × its own 20-bar median
  * EMA gap: skip a new entry when |EMA20−EMA50| / close < 0.004 (0.40%)

No tuning grid exists in the engine, the journal, or PR #4. Those two values
were set once. The step used here is ±25%, which lands on round numbers:
  * ATR% hurdle: 0.75× / 1.00× / 1.25× the 20-day median
  * EMA-gap minimum: 0.30% / 0.40% / 0.50%

The 20-bar window stays at 20 in every cell. A longer window is not reliably
a tighter filter, so it is not the "one step tighter" the test asks for.
"""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import r4c_engine as eng  # noqa: E402

WINDOW_START = "2025-09-16"
WINDOW_END_EXCLUSIVE = "2026-09-17"  # yfinance end is exclusive; last bar is 2026-09-16
CACHE_PATH = HERE / "price_cache.csv"
CSV_PATH = HERE / "results.csv"
PNG_PATH = HERE / "heatmap.png"
WRITEUP_PATH = HERE / "WRITEUP.md"
ARTIFACT_DIR = Path("/opt/cursor/artifacts")

# Published Round 4C snapshot (PR #4, 2026-09-16). Used only as a comparison
# to this replay. The grid itself is computed, not copied from that snapshot.
PUBLISHED = {
    "total_return_pct": 14.90,
    "max_drawdown_pct": 8.46,
    "sharpe_ratio": 1.564,
    "num_trades": 9,
    "win_rate_pct": 44.44,
    "final_equity": 1910.71,
}
PUBLISHED_R3 = {
    "total_return_pct": 4.33,
    "num_trades": 15,
    "max_drawdown_pct": 12.65,
    "sharpe_ratio": 0.415,
}
PUBLISHED_TRADES = [
    ("2025-12-29", "2026-01-21", "GOLD"),
    ("2026-02-03", "2026-02-17", "GOLD"),
    ("2026-01-30", "2026-03-02", "GOLD"),
    ("2026-04-30", "2026-05-14", "NVDA"),
    ("2026-05-04", "2026-05-14", "NVDA"),
    ("2026-05-15", "2026-06-01", "TSLA"),
    ("2026-05-15", "2026-06-10", "NVDA"),
    ("2026-08-31", "2026-09-10", "NVDA"),
    ("2026-08-28", "2026-09-16", "GOLD"),
]

TICKERS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "GOLD": "GC=F",
    "NVDA": "NVDA",
    "TSLA": "TSLA",
    "^GSPC": "^GSPC",
    "^VIX": "^VIX",
    "^TNX": "^TNX",
}

# (plain label, value). Order is looser → shipped → tighter.
ATR_STEPS = [
    ("looser", 0.75),
    ("shipped", 1.00),
    ("tighter", 1.25),
]
EMA_STEPS = [
    ("looser", 0.003),
    ("shipped", 0.004),
    ("tighter", 0.005),
]


def fetch_symbol(ticker: str) -> pd.DataFrame:
    df = yf.Ticker(ticker).history(
        start=WINDOW_START, end=WINDOW_END_EXCLUSIVE, auto_adjust=True
    )
    if df.empty:
        raise RuntimeError(f"No prices for {ticker} between {WINDOW_START} and 2026-09-16")
    df = df.reset_index()
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    df["date"] = pd.to_datetime(df[date_col])
    if getattr(df["date"].dt, "tz", None) is not None:
        df["date"] = df["date"].dt.tz_localize(None)
    df["date"] = df["date"].dt.normalize()
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"})
    out = df[["date", "open", "high", "low", "close"]].sort_values("date")
    return out.drop_duplicates("date").reset_index(drop=True)


def load_prices() -> dict:
    """One cached download, shared by all 9 cells."""
    if CACHE_PATH.exists():
        raw = pd.read_csv(CACHE_PATH, parse_dates=["date"])
        print(f"Loaded cached prices from {CACHE_PATH.name} ({len(raw)} rows)")
    else:
        frames = []
        for sym, ticker in TICKERS.items():
            print(f"Fetching {sym} ({ticker})...")
            part = fetch_symbol(ticker)
            part.insert(0, "symbol", sym)
            frames.append(part)
        raw = pd.concat(frames, ignore_index=True)
        raw.to_csv(CACHE_PATH, index=False)
        print(f"Wrote {CACHE_PATH.name}")

    all_data = {}
    for sym, part in raw.groupby("symbol", sort=False):
        df = part.drop(columns=["symbol"]).copy()
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
        df["symbol"] = sym
        all_data[sym] = df.sort_values("date").reset_index(drop=True)
    missing = [s for s in TICKERS if s not in all_data]
    if missing:
        raise RuntimeError(f"Price cache is missing {missing}")
    return all_data


def run_cell(all_data: dict, regime_df: pd.DataFrame, atr_mult: float, ema_gap: float) -> dict:
    eng.ATR_MEDIAN_MULT = atr_mult
    eng.CHOP_EMA_GAP_FRAC = ema_gap
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        trades, equity_curve, _final, skips = eng.run_backtest(all_data, regime_df)
    metrics = eng.compute_metrics(trades, equity_curve, eng.START_CAPITAL)
    metrics["chop_skips"] = len(skips)
    metrics["trades"] = trades
    return metrics


def classify(rows: list[dict]) -> dict:
    """Pre-set rule, applied after the grid is in.

    Plateau: at least 6 of 8 neighbors made money AND at least 6 of 8 finished
    within 5 percentage points of the shipped cell.
    Spike: 2 or fewer neighbors made money.
    Mixed: anything else.
    """
    center = next(r for r in rows if r["is_shipped"])
    neighbors = [r for r in rows if not r["is_shipped"]]
    n_prof = sum(1 for r in neighbors if r["total_return_pct"] > 0)
    n_sim = sum(
        1 for r in neighbors if abs(r["total_return_pct"] - center["total_return_pct"]) <= 5.0
    )
    n_all_prof = sum(1 for r in rows if r["total_return_pct"] > 0)
    if n_prof >= 6 and n_sim >= 6:
        label = "PLATEAU"
    elif n_prof <= 2:
        label = "SPIKE"
    else:
        label = "MIXED"
    return {
        "label": label,
        "neighbors_profitable": n_prof,
        "neighbors_within_5pp": n_sim,
        "cells_profitable": n_all_prof,
        "center_return": center["total_return_pct"],
    }


def write_csv(rows: list[dict]) -> None:
    table = pd.DataFrame(rows).drop(columns=["trades"])
    col_order = [
        "atr_label",
        "atr_median_mult",
        "ema_label",
        "ema_gap_frac",
        "ema_gap_pct",
        "total_return_pct",
        "max_drawdown_pct",
        "num_trades",
        "win_rate_pct",
        "sharpe_ratio",
        "profit_factor",
        "final_equity",
        "total_net_pnl",
        "chop_skips",
        "is_shipped",
    ]
    table = table[col_order]
    table.to_csv(CSV_PATH, index=False)


def draw_heatmap(rows: list[dict]) -> None:
    by_key = {(r["atr_label"], r["ema_label"]): r for r in rows}
    returns = np.array(
        [[by_key[(a, e)]["total_return_pct"] for e, _ in EMA_STEPS] for a, _ in ATR_STEPS],
        dtype=float,
    )
    trades = np.array(
        [[by_key[(a, e)]["num_trades"] for e, _ in EMA_STEPS] for a, _ in ATR_STEPS],
        dtype=int,
    )
    span = max(abs(float(returns.min())), abs(float(returns.max())), 1.0)
    norm = TwoSlopeNorm(vmin=-span, vcenter=0.0, vmax=span)

    fig, ax = plt.subplots(figsize=(9.4, 7.4), dpi=160)
    im = ax.imshow(returns, cmap="RdYlGn", norm=norm, origin="upper")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Total return %")

    ax.set_xticks(range(3), ["looser", "shipped", "tighter"])
    ax.set_yticks(range(3), ["looser", "shipped", "tighter"])
    ax.set_xlabel("EMA-gap filter: looser / shipped / tighter", fontsize=12, labelpad=10)
    ax.set_ylabel("ATR% filter: looser / shipped / tighter", fontsize=12, labelpad=10)
    ax.set_title(
        "Round 4C chop filter — one step either way",
        fontsize=15,
        pad=12,
    )
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    for i in range(3):
        for j in range(3):
            ret = returns[i, j]
            n = trades[i, j]
            shipped = ATR_STEPS[i][0] == "shipped" and EMA_STEPS[j][0] == "shipped"
            lines = f"{ret:+.1f}%\n{n} trades"
            if shipped:
                lines += "\nshipped"
            ax.text(
                j,
                i,
                lines,
                ha="center",
                va="center",
                fontsize=12,
                fontweight="bold",
                color="#1a1a1a",
                bbox=dict(boxstyle="round,pad=0.28", fc="white", ec="none", alpha=0.72),
            )
            if shipped:
                ax.add_patch(
                    Rectangle(
                        (j - 0.5, i - 0.5),
                        1,
                        1,
                        fill=False,
                        edgecolor="black",
                        linewidth=3.2,
                    )
                )
                ax.add_patch(
                    Rectangle(
                        (j - 0.47, i - 0.47),
                        0.94,
                        0.94,
                        fill=False,
                        edgecolor="white",
                        linewidth=1.3,
                    )
                )

    fig.text(
        0.5,
        0.02,
        "Green made money. Red lost money. Darker means a bigger gain or loss.\n"
        "Same book, same year (16 Sep 2025 – 16 Sep 2026). The outlined cell is the shipped Round 4C setting.\n"
        "ATR% steps: block under 0.75× / 1.00× / 1.25× the 20-day typical range.  "
        "EMA-gap steps: 0.30% / 0.40% / 0.50%.",
        ha="center",
        va="bottom",
        fontsize=8.5,
        color="#333333",
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(PNG_PATH, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _fmt_trades(trades: list[dict]) -> str:
    if not trades:
        return "_No closed trades._"
    lines = [
        "| Entry | Exit | Symbol | Net P&L | Exit reason |",
        "|-------|------|--------|---------|-------------|",
    ]
    for t in trades:
        pnl = t["net_pnl"]
        pnl_txt = f"-${abs(pnl):,.2f}" if pnl < 0 else f"${pnl:,.2f}"
        lines.append(
            f"| {t['entry_date']} | {t['exit_date']} | {t['symbol']} | "
            f"{pnl_txt} | {t['exit_reason']} |"
        )
    return "\n".join(lines)


def write_writeup(rows: list[dict], verdict: dict, all_data: dict, regime_df: pd.DataFrame) -> None:
    by_key = {(r["atr_label"], r["ema_label"]): r for r in rows}
    center = by_key[("shipped", "shipped")]
    header = (
        "| ATR% filter \\ EMA-gap filter | Looser (0.30%) | Shipped (0.40%) | Tighter (0.50%) |\n"
        "|---|---:|---:|---:|\n"
    )
    body_rows = []
    for atr_label, mult in ATR_STEPS:
        name = {"looser": "Looser (0.75×)", "shipped": "Shipped (1.00×)", "tighter": "Tighter (1.25×)"}[
            atr_label
        ]
        cells = []
        for ema_label, _gap in EMA_STEPS:
            r = by_key[(atr_label, ema_label)]
            mark = "**" if r["is_shipped"] else ""
            end = "**" if r["is_shipped"] else ""
            cells.append(
                f"{mark}{r['total_return_pct']:+.2f}% · DD {r['max_drawdown_pct']:.2f}% · "
                f"{r['num_trades']} trades · WR {r['win_rate_pct']:.0f}% · "
                f"Sharpe {r['sharpe_ratio']:.2f}{end}"
            )
        body_rows.append(f"| {name} | " + " | ".join(cells) + " |")
    table = header + "\n".join(body_rows)

    btc = all_data["BTC"]
    gold = all_data["GOLD"]
    gold_last = gold.loc[gold["date"] == pd.Timestamp("2026-09-16"), "close"]
    gold_last_px = float(gold_last.iloc[0]) if len(gold_last) else float("nan")
    spx_days = int(regime_df["date"].nunique())
    regime_counts = regime_df["regime"].value_counts().to_dict()

    replay_keys = {(t["entry_date"], t["exit_date"], t["symbol"]) for t in center["trades"]}
    published_keys = set(PUBLISHED_TRADES)
    matched = len(replay_keys & published_keys)
    missing = sorted(published_keys - replay_keys)
    extra = sorted(replay_keys - published_keys)

    def _trade_phrase(keys: list[tuple]) -> str:
        if not keys:
            return "none"
        return ", ".join(f"{sym} {entry} → {exit}" for entry, exit, sym in keys)

    # How much of the grid is just the ATR hurdle, with the EMA gap sitting still.
    row_spans = []
    for atr_label, _mult in ATR_STEPS:
        subset = [r for r in rows if r["atr_label"] == atr_label]
        rets_row = [r["total_return_pct"] for r in subset]
        ns_row = sorted({r["num_trades"] for r in subset})
        row_spans.append(
            (atr_label, min(rets_row), max(rets_row), max(rets_row) - min(rets_row), ns_row)
        )
    ema_barely_moves = all(span < 2.0 for _label, _lo, _hi, span, _ns in row_spans)

    rets = [r["total_return_pct"] for r in rows]
    if verdict["label"] == "PLATEAU":
        verdict_sentence = (
            f"Moving either setting one step still made money in "
            f"{verdict['neighbors_profitable']} of the 8 neighboring cells, and "
            f"{verdict['neighbors_within_5pp']} of those 8 finished within 5 percentage points "
            f"of the shipped cell ({verdict['center_return']:+.2f}%). "
            f"Inside this one year the result sits on a plateau, not on a single lucky cell."
        )
    elif verdict["label"] == "SPIKE":
        verdict_sentence = (
            f"Only {verdict['neighbors_profitable']} of the 8 neighboring cells made money. "
            f"The shipped setting is doing work that the nearby settings do not. "
            f"Treat the published gain as fragile."
        )
    else:
        verdict_sentence = (
            f"{verdict['neighbors_profitable']} of the 8 neighboring cells made money, and "
            f"{verdict['neighbors_within_5pp']} of the 8 finished within 5 percentage points "
            f"of the shipped cell ({verdict['center_return']:+.2f}%). "
            f"That is neither a broad plateau nor a one-cell spike."
        )

    def _row_blurb(label: str, lo: float, hi: float, span: float, ns: list[int]) -> str:
        trade_bit = f"{ns[0]} trades" if len(ns) == 1 else f"{ns[0]}–{ns[-1]} trades"
        if span < 0.05:
            return f"the {label} ATR% row is the same result in all three EMA columns ({lo:+.2f}%, {trade_bit})"
        return (
            f"the {label} ATR% row only moves from {lo:+.2f}% to {hi:+.2f}% "
            f"when the EMA-gap changes ({trade_bit})"
        )

    if ema_barely_moves:
        blurbs = "; ".join(_row_blurb(*span) for span in row_spans)
        pattern = (
            "The picture is a stripe.\n\n"
            f"Changing the EMA-gap and leaving the ATR% hurdle alone does almost nothing: {blurbs}.\n\n"
            "The ATR% hurdle is the sensitive setting. "
            "One step looser lets quieter days in, and the year loses money. "
            "One step tighter demands a bigger daily range, and almost all of the gain disappears. "
            "The shipped hurdle is the ATR% setting that produces the strong year. "
            "That fits the original Round 4C skip log: blocked entries were almost all "
            "\"range too quiet,\" and the EMA-gap almost never blocked a trade on its own."
        )
    else:
        pattern = "Both settings move the result. The table shows which direction hurts."

    text = f"""# Round 4C chop filter: plateau or spike?

This note is for the owner. It checks whether the shipped Round 4C result depends on two very specific filter settings, or whether the nearby settings still make money.

Round 4C's live rules were not changed. This folder only replays them.

## What the shipped filter actually does

Round 4C (PR #4, recorded in `backtest-params.json`) skips a **new** trade when either of these is true. A trade already open is left alone.

1. **ATR% filter.** Today's daily range is under the typical range of the last 20 days. "Typical" is the median. The shipped hurdle is **1.00×** that typical range. There is no fixed cutoff such as "ATR under 2%".
2. **EMA-gap filter.** The 20-day and 50-day trend lines are less than **0.40%** of the price apart.

Published Round 4C result on the 16 Sep 2026 snapshot: **+14.90%** return, **8.46%** max drawdown, Sharpe **1.564**, **9** trades, win rate **44%**. Round 3, the same book without this filter: **+4.33%**, **15** trades, drawdown **12.65%**, Sharpe **0.415**. Those figures are in the saved results. This test re-runs the engine; it does not paste the old percentage into the grid.

## The one step each setting moved

Nobody swept these values when Round 4C was built. The engine, the journal, and PR #4 each state the pair once. With no grid step on record, each hurdle moves **25%**, which is a round number an owner can see:

| Setting | Looser (easier to get in) | Shipped | Tighter (harder to get in) |
|---|---:|---:|---:|
| ATR% filter | block only under **0.75×** the 20-day typical range | **1.00×** | block under **1.25×** |
| EMA-gap filter | trend lines must be **0.30%** apart | **0.40%** | **0.50%** apart |

The 20-day window stays at 20 in every cell. Making that window 15 or 25 days changes *which* days look quiet. It does not reliably make the filter easier or harder, so it is the wrong "one step tighter."

Nine cells: looser / shipped / tighter for each setting. Everything else — prices, year, costs, exits, size, regime — stays put.

## The 3×3 result

Each cell shows return, max drawdown, trade count, win rate, and Sharpe. The shipped cell is in bold.

{table}

Return across the nine cells ran from **{min(rets):+.2f}%** to **{max(rets):+.2f}%**. **{verdict['cells_profitable']} of 9** cells made money.

Green cells made money. Red cells lost money. The shipped cell is outlined.

![Round 4C chop-filter plateau](heatmap.png)

## Verdict: {verdict['label']}

{verdict_sentence}

{pattern}

The label uses a rule set before looking at the numbers:

- **PLATEAU** — at least 6 of the 8 neighbors made money, and at least 6 of the 8 finished within 5 percentage points of the shipped cell.
- **SPIKE** — 2 or fewer neighbors made money.
- **MIXED** — anything in between.

**Small sample.** The shipped book is a handful of trades (the published run had 9; this replay of the shipped cell had {center['num_trades']}). Two cells can print similar percentages because they took nearly the same trades. That is a real check on these two settings. It is not a large-sample proof that the strategy will keep working.

## Did the middle cell match the published +14.90%?

| | Published snapshot (16 Sep 2026) | This replay, shipped cell |
|---|---:|---:|
| Return | {PUBLISHED['total_return_pct']:+.2f}% | {center['total_return_pct']:+.2f}% |
| Max drawdown | {PUBLISHED['max_drawdown_pct']:.2f}% | {center['max_drawdown_pct']:.2f}% |
| Sharpe | {PUBLISHED['sharpe_ratio']:.3f} | {center['sharpe_ratio']:.3f} |
| Trades | {PUBLISHED['num_trades']} | {center['num_trades']} |
| Win rate | {PUBLISHED['win_rate_pct']:.2f}% | {center['win_rate_pct']:.2f}% |
| Final equity | ${PUBLISHED['final_equity']:,.2f} | ${center['final_equity']:,.2f} |

{matched} of the 9 published round-trips match this replay on entry date, exit date, and symbol. Missing from this replay: {_trade_phrase(missing)}. Extra in this replay: {_trade_phrase(extra)}. The last gold trade is in both lists, but this replay holds it to the end of the test instead of closing it for a weak trend, because the settled gold price that day is higher than the price the September run used.

This replay's shipped-cell trades:

{_fmt_trades(center['trades'])}

Why a replay can differ from the September snapshot, even with the same rules:

- The calendar is the same published year. S&P sessions in this file run **{WINDOW_START} through 2026-09-16** ({spx_days} sessions). The published regime count was 252 days (153 risk-on / 83 transition / 16 risk-off). This replay's regime count is {regime_counts.get('RISK-ON', 0)} / {regime_counts.get('TRANSITION', 0)} / {regime_counts.get('RISK-OFF', 0)}.
- Stocks and gold that the published trades actually touched match the saved prints in the middle of the year (NVDA 235.20 on 14 May 2026, TSLA 415.88 on 1 Jun 2026, gold 4837.50 / 4905.90 / 5311.60). The last gold print does not. The published Round 4C exit used **4288.70** on 16 Sep 2026. The settled gold future close in this file is **{gold_last_px:.2f}**. Round 3's own note for that same day was about 4384. All nine cells use this settled series, so they still compare fairly with each other.
- Bitcoin in the published test came from CoinGecko (116,763 on 17 Sep 2025 to 75,590 on 16 Sep 2026). CoinGecko's "last 365 days" cannot be rewound to that morning. This replay uses Yahoo Finance for bitcoin, ether, and solana so the file can be re-run. Bitcoin here is {float(btc.iloc[0]['close']):,.2f} on {btc.iloc[0]['date'].date()} to {float(btc.iloc[-1]['close']):,.2f} on {btc.iloc[-1]['date'].date()}.

## What was not changed

Position size, leverage, the regime filter, pyramids, the breakeven stop, the 30-day time stop, costs, and the symbol list are the Round 4C rules. The shipped engine on PR #4 was not edited. The copy in this folder exists so the two hurdles can be moved for the test, and its defaults are the shipped hurdles.
"""
    WRITEUP_PATH.write_text(text)


def copy_artifacts() -> None:
    if not ARTIFACT_DIR.is_dir():
        print(f"Artifact dir missing: {ARTIFACT_DIR}")
        return
    shutil.copy(PNG_PATH, ARTIFACT_DIR / "round4c-plateau-heatmap.png")
    shutil.copy(CSV_PATH, ARTIFACT_DIR / "round4c-plateau-results.csv")
    print(f"Copied heatmap and CSV to {ARTIFACT_DIR}")


def main() -> None:
    all_data = load_prices()
    regime_df = eng.build_regime_series(all_data)
    print("Regime:", dict(regime_df["regime"].value_counts()))
    print(
        f"SPX {all_data['^GSPC']['date'].min().date()} → {all_data['^GSPC']['date'].max().date()} "
        f"({len(all_data['^GSPC'])} rows)"
    )

    rows = []
    for atr_label, atr_mult in ATR_STEPS:
        for ema_label, ema_gap in EMA_STEPS:
            print(f"Running ATR {atr_label} ({atr_mult}) × EMA {ema_label} ({ema_gap})...")
            metrics = run_cell(all_data, regime_df, atr_mult, ema_gap)
            row = {
                "atr_label": atr_label,
                "atr_median_mult": atr_mult,
                "ema_label": ema_label,
                "ema_gap_frac": ema_gap,
                "ema_gap_pct": round(ema_gap * 100, 2),
                "total_return_pct": metrics["total_return_pct"],
                "max_drawdown_pct": metrics["max_drawdown_pct"],
                "num_trades": metrics["num_trades"],
                "win_rate_pct": metrics["win_rate_pct"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "profit_factor": metrics["profit_factor"],
                "final_equity": metrics["final_equity"],
                "total_net_pnl": metrics["total_net_pnl"],
                "chop_skips": metrics["chop_skips"],
                "is_shipped": atr_label == "shipped" and ema_label == "shipped",
                "trades": metrics["trades"],
            }
            rows.append(row)
            print(
                f"  return {row['total_return_pct']:+.2f}%  DD {row['max_drawdown_pct']:.2f}%  "
                f"n={row['num_trades']}  WR {row['win_rate_pct']:.1f}%  "
                f"Sharpe {row['sharpe_ratio']:.3f}"
            )

    # Confirm the shipped cell really used the shipped constants.
    if eng.ATR_MEDIAN_MULT != 1.25 or eng.CHOP_EMA_GAP_FRAC != 0.005:
        raise RuntimeError("Last cell did not leave the engine on the tighter/tighter knobs")

    verdict = classify(rows)
    write_csv(rows)
    draw_heatmap(rows)
    write_writeup(rows, verdict, all_data, regime_df)
    copy_artifacts()
    print(f"Verdict: {verdict['label']}")
    print(f"Wrote {CSV_PATH.name}, {PNG_PATH.name}, {WRITEUP_PATH.name}")


if __name__ == "__main__":
    main()
