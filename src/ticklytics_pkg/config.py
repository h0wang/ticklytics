"""Configuration paths for ticklytics."""
from pathlib import Path

DATA_DIR   = Path("/home/clawpi/.openclaw/data/ohlcv")
WATCHLIST  = Path("/home/clawpi/.openclaw/data/watchlist/watchlist.json")
PORTFOLIOS = Path("/home/clawpi/.openclaw/data/portfolios")

# API defaults
DEFAULT_PORT = 5050
DEFAULT_HOST = "0.0.0.0"

# Cache freshness thresholds (days)
CACHE_FRESHNESS = {
    "daily":   1,
    "weekly":  7,
    "monthly": 30,
}

# Longest history to ever fetch from yfinance (years)
MAX_LOOKBACK = {
    "daily":   15,
    "weekly":  15,
    "monthly": 30,
}
