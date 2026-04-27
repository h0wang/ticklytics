"""
ticklytics — OHLCV market data cache and REST API.

Usage:
    python -m ticklytics update [tickers]    # Update OHLCV cache
    python -m ticklytics serve               # Start REST API on port 5050
"""
from .cache import (
    load_from_cache,
    save_to_cache,
    fetch_and_cache,
    load_watchlist,
    list_cached_tickers,
    get_ticker_intervals,
    get_ticker_last_updated,
)
from .api import create_app, serve
from .config import DATA_DIR, WATCHLIST, DEFAULT_PORT

__all__ = [
    # cache
    "load_from_cache",
    "save_to_cache",
    "fetch_and_cache",
    "load_watchlist",
    "list_cached_tickers",
    "get_ticker_intervals",
    "get_ticker_last_updated",
    # api
    "create_app",
    "serve",
    # config
    "DATA_DIR",
    "WATCHLIST",
    "DEFAULT_PORT",
]
