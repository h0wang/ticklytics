"""
OHLCV cache management — read/write CSV cache, fetch from yfinance.

All functions use paths from config.py.
"""
import os
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from .config import DATA_DIR, WATCHLIST, MAX_LOOKBACK


# ─── Public API ───────────────────────────────────────────────────────────────

def load_from_cache(ticker: str, interval: str) -> pd.DataFrame | None:
    """Load cached OHLCV data for a ticker/interval, or None if not cached."""
    path = DATA_DIR / ticker.upper() / f"{interval}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
    return df


def save_to_cache(ticker: str, interval: str, df: pd.DataFrame) -> None:
    """Save a DataFrame to the CSV cache. Creates ticker dir if needed."""
    ticker_dir = DATA_DIR / ticker.upper()
    ticker_dir.mkdir(parents=True, exist_ok=True)
    path = ticker_dir / f"{interval}.csv"
    df.to_csv(path)


def fetch_and_cache(
    ticker: str,
    interval: str,
    period: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> tuple[int, int, int]:
    """
    Fetch OHLCV data from yfinance and save to cache.

    Returns (n_fetched, n_was_cached, n_total):
        n_fetched:    rows fetched from yfinance this call
        n_was_cached: rows already in cache before this call
        n_total:      total rows in cache after this call

    Strategy:
        - If existing cache found: fetch from (last_date + 1) to today only
        - If no cache: full refresh with MAX_LOOKBACK years
        - Merge new data with existing cache, deduplicate by date
    """
    interval_map = {"daily": "1d", "weekly": "1wk", "monthly": "1mo"}
    yf_interval = interval_map.get(interval, "1d")
    max_years = MAX_LOOKBACK.get(interval, 15)

    existing = load_from_cache(ticker, interval)

    t = yf.Ticker(ticker)

    if existing is not None and not existing.empty:
        last_date = existing.index.max()
        start_dt = last_date + timedelta(days=1)
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str   = datetime.now().strftime("%Y-%m-%d")
        if start_str >= end_str:
            # Already up to date
            return 0, len(existing), len(existing)
        df = t.history(start=start_str, end=end_str, interval=yf_interval, auto_adjust=False)
    else:
        if start:
            df = t.history(start=start, end=end or datetime.now().strftime("%Y-%m-%d"),
                           interval=yf_interval, auto_adjust=False)
        else:
            df = t.history(period=period or f"{max_years}y",
                           interval=yf_interval, auto_adjust=False)

    if df.empty:
        return 0, len(existing) if existing is not None else 0, \
               len(existing) if existing is not None else 0

    # Normalise columns and timezone
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    df.columns = [c.lower() for c in df.columns]
    df.index = pd.DatetimeIndex(df.index).tz_localize(None)

    n_fetched = len(df)

    # Merge with existing cache
    if existing is not None and not existing.empty:
        combined = pd.concat([existing, df]).sort_index()
        combined = combined[~combined.index.duplicated(keep="last")]
    else:
        combined = df

    save_to_cache(ticker, interval, combined)

    n_was_cached = len(existing) if existing is not None else 0
    return n_fetched, n_was_cached, len(combined)


def load_watchlist(section: str | None = None) -> list[str]:
    """Load tickers from the watchlist JSON."""
    with open(WATCHLIST) as f:
        wl = json.load(f)
    if section:
        return wl.get(section, [])
    all_tickers = []
    for v in wl.values():
        all_tickers.extend(v)
    return all_tickers


def list_cached_tickers() -> list[str]:
    """Return all tickers that have at least one cached interval."""
    if not DATA_DIR.exists():
        return []
    return sorted([
        d.name for d in DATA_DIR.iterdir()
        if d.is_dir() and any(d.glob("*.csv"))
    ])


def get_ticker_intervals(ticker: str) -> list[str]:
    """Return which intervals are cached for a ticker."""
    ticker_dir = DATA_DIR / ticker.upper()
    if not ticker_dir.exists():
        return []
    return sorted(f.stem for f in ticker_dir.glob("*.csv"))


def get_ticker_last_updated(ticker: str) -> str | None:
    """Return the date of the most recent cached row, or None."""
    df = load_from_cache(ticker, "daily")
    if df is None or df.empty:
        return None
    return str(df.index.max().date())
