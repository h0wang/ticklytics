"""Data models / response schemas for ticklytics REST API."""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Literal


@dataclass
class OHLCVRow:
    """Single OHLCV candle row."""
    date:   str   # ISO date string YYYY-MM-DD
    open:   float
    high:   float
    low:    float
    close:  float
    volume: int


@dataclass
class OHLCVResponse:
    """Standard OHLCV API response."""
    ticker:    str
    interval:  str
    start:     str
    end:       str
    count:     int
    data:      list[OHLCVRow]
    cached:    bool       # whether served from cache (True) or fetched fresh
    fetched_at: str      # ISO timestamp


@dataclass
class TickerInfo:
    """Basic metadata for a ticker."""
    ticker:       str
    name:         str | None
    currency:     str | None
    exchange:     str | None
    intervals:    list[str]  # which timeframes are cached
    last_updated: str | None  # date of most recent cached row


@dataclass
class HealthResponse:
    """Health check response."""
    status:    str
    version:   str
    timestamp: str
    tickers:   int
    cache_dir: str


@dataclass
class ErrorResponse:
    """Standard error response."""
    error:   str
    detail:  str | None = None
    code:    int = 500


def format_ohlcv_response(ticker: str, interval: str, df, cached: bool) -> dict:
    """Build a OHLCVResponse dict from a pandas DataFrame."""
    rows = [
        OHLCVRow(
            date=  str(idx.date()),
            open=  float(r["Open"]),
            high=  float(r["High"]),
            low=   float(r["Low"]),
            close= float(r["Close"]),
            volume=int(r["Volume"]),
        )
        for idx, r in df.iterrows()
    ]
    if not df.empty:
        start = str(df.index.min().date())
        end   = str(df.index.max().date())
    else:
        start = end = ""

    return {
        "ticker":    ticker,
        "interval":  interval,
        "start":     start,
        "end":       end,
        "count":     len(rows),
        "data":      [asdict(r) for r in rows],
        "cached":    cached,
        "fetched_at": datetime.now().isoformat(),
    }


def format_ticker_info(ticker: str, intervals: list[str], last_updated: str | None) -> dict:
    return {
        "ticker":       ticker,
        "name":         None,
        "currency":     None,
        "exchange":     None,
        "intervals":    intervals,
        "last_updated": last_updated,
    }
