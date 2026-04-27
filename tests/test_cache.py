"""
Unit tests for ticklytics.cache module.
Run with: pytest tests/test_cache.py -v
"""
import os
import sys
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent.parent / "src" / "ticklytics_pkg"  # scripts/ticklytics_pkg/


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_df(rows):
    """rows = [(date_str, open, high, low, close, volume), ...]"""
    idx, opens, highs, lows, closes, volumes = zip(*rows)
    df = pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=pd.to_datetime(list(idx)),
    )
    df.index.name = "Date"
    return df


SAMPLE = make_df([
    ("2026-01-02", 100.0, 105.0, 99.0, 104.0, 1000),
    ("2026-01-05", 101.0, 106.0, 100.0, 105.0, 1100),
    ("2026-01-06", 102.0, 107.0, 101.0, 106.0, 1200),
])

SAMPLE_2 = make_df([
    ("2026-01-07", 103.0, 108.0, 102.0, 107.0, 1300),
    ("2026-01-08", 104.0, 109.0, 103.0, 108.0, 1400),
])


def load_module(data_dir, watchlist_path):
    """Load ticklytics_pkg.cache with overridden DATA_DIR/WATCHLIST."""
    import sys
    from pathlib import Path
    # ROOT.parent = scripts/ which contains ticklytics_pkg/
    sys.path.insert(0, str(ROOT.parent))
    import ticklytics_pkg.config as config_mod
    import ticklytics_pkg.cache as cache_mod
    # Patch paths
    cache_mod.DATA_DIR  = data_dir
    cache_mod.WATCHLIST = watchlist_path
    config_mod.DATA_DIR  = data_dir
    config_mod.WATCHLIST = watchlist_path
    import ticklytics_pkg
    sys.modules["ticklytics_pkg"] = ticklytics_pkg
    sys.modules["ticklytics_pkg.cache"] = cache_mod
    return cache_mod


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def env(tmp_path):
    """Isolated temp DATA_DIR + WATCHLIST for one test."""
    data_dir  = tmp_path / "ohlcv"
    watchlist = tmp_path / "watchlist.json"
    with open(watchlist, "w") as f:
        json.dump({
            "primary":     ["AAPL", "MSFT"],
            "secondary":   ["DGE.L"],
            "index":       ["^SPX"],
            "alternative": ["BTC-USD"],
        }, f)
    return {"data_dir": data_dir, "watchlist": watchlist}


# ─── load_from_cache ─────────────────────────────────────────────────────────

class TestLoadFromCache:
    def test_miss_returns_none(self, env):
        m = load_module(env["data_dir"], env["watchlist"])
        assert m.load_from_cache("NOSUCH", "daily") is None

    def test_hit_returns_dataframe(self, env):
        m = load_module(env["data_dir"], env["watchlist"])
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")

        result = m.load_from_cache("AAPL", "daily")
        assert result is not None
        assert len(result) == 3
        assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]

    def test_wrong_timeframe_returns_none(self, env):
        m = load_module(env["data_dir"], env["watchlist"])
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")
        assert m.load_from_cache("AAPL", "weekly") is None

    def test_ticker_case_normalised(self, env):
        # load_from_cache normalizes ticker to uppercase in path
        m = load_module(env["data_dir"], env["watchlist"])
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")
        result = m.load_from_cache("AAPL", "daily")
        assert result is not None


# ─── save_to_cache ────────────────────────────────────────────────────────────

class TestSaveToCache:
    def test_saves_correct_columns(self, env):
        m = load_module(env["data_dir"], env["watchlist"])
        m.save_to_cache("MSFT", "daily", SAMPLE)
        path = env["data_dir"] / "MSFT" / "daily.csv"
        assert path.exists()
        df = m.load_from_cache("MSFT", "daily")
        assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]

    def test_saves_to_ticker_dir(self, env):
        m = load_module(env["data_dir"], env["watchlist"])
        m.save_to_cache("DGE.L", "weekly", SAMPLE)
        assert (env["data_dir"] / "DGE.L" / "weekly.csv").exists()

    def test_overwrites_existing(self, env):
        m = load_module(env["data_dir"], env["watchlist"])
        m.save_to_cache("AAPL", "daily", SAMPLE)
        m.save_to_cache("AAPL", "daily", SAMPLE_2)
        df = m.load_from_cache("AAPL", "daily")
        assert len(df) == 2


# ─── fetch_and_cache ──────────────────────────────────────────────────────────

class TestFetchAndCache:
    @patch("ticklytics_pkg.cache.yf.Ticker")
    def test_first_fetch_creates_cache(self, mock_ticker, env):
        m = load_module(env["data_dir"], env["watchlist"])
        mock_instance = MagicMock()
        mock_instance.history.return_value = SAMPLE.copy()
        mock_ticker.return_value = mock_instance

        n_new, n_cached, n_total = m.fetch_and_cache("AAPL", "daily")

        assert n_new == 3 and n_cached == 0 and n_total == 3
        assert (env["data_dir"] / "AAPL" / "daily.csv").exists()

    @patch("ticklytics_pkg.cache.yf.Ticker")
    def test_append_fetch_merges(self, mock_ticker, env):
        m = load_module(env["data_dir"], env["watchlist"])
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")

        mock_instance = MagicMock()
        mock_instance.history.return_value = SAMPLE_2.copy()
        mock_ticker.return_value = mock_instance

        n_new, n_cached, n_total = m.fetch_and_cache("AAPL", "daily")

        assert n_new == 2 and n_cached == 3 and n_total == 5
        df = m.load_from_cache("AAPL", "daily")
        assert len(df) == 5
        assert df.index.max() == pd.Timestamp("2026-01-08")

    @patch("ticklytics_pkg.cache.yf.Ticker")
    def test_up_to_date_skips_fetch(self, mock_ticker, env):
        m = load_module(env["data_dir"], env["watchlist"])
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        today_df = SAMPLE.copy()
        today_df.index = pd.DatetimeIndex([datetime.now()] * 3)
        today_df.index.name = "Date"
        today_df.to_csv(env["data_dir"] / "AAPL" / "daily.csv")

        mock_instance = MagicMock()
        mock_ticker.return_value = mock_instance

        n_new, n_cached, n_total = m.fetch_and_cache("AAPL", "daily")

        assert n_new == 0 and n_cached == 3 and n_total == 3
        mock_instance.history.assert_not_called()

    @patch("ticklytics_pkg.cache.yf.Ticker")
    def test_empty_yfinance_returns_cache(self, mock_ticker, env):
        m = load_module(env["data_dir"], env["watchlist"])
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")

        mock_instance = MagicMock()
        mock_instance.history.return_value = pd.DataFrame()
        mock_ticker.return_value = mock_instance

        n_new, n_cached, n_total = m.fetch_and_cache("AAPL", "daily")

        assert n_new == 0 and n_cached == 3 and n_total == 3

    @patch("ticklytics_pkg.cache.yf.Ticker")
    def test_dedup_by_date(self, mock_ticker, env):
        m = load_module(env["data_dir"], env["watchlist"])
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")

        # yfinance returns only rows from last cached date + 1
        new_only = make_df([
            ("2026-01-07", 103.0, 108.0, 102.0, 107.0, 1300),
            ("2026-01-08", 104.0, 109.0, 103.0, 108.0, 1400),
        ])
        mock_instance = MagicMock()
        mock_instance.history.return_value = new_only
        mock_ticker.return_value = mock_instance

        n_new, n_cached, n_total = m.fetch_and_cache("AAPL", "daily")

        assert n_new == 2
        assert n_total == 5  # not 7 (dedup removed Jan 5, Jan 6 overlap)

    @patch("ticklytics_pkg.cache.yf.Ticker")
    def test_all_intervals(self, mock_ticker, env):
        m = load_module(env["data_dir"], env["watchlist"])
        for interval in ("daily", "weekly", "monthly"):
            mock_instance = MagicMock()
            mock_instance.history.return_value = SAMPLE.copy()
            mock_ticker.return_value = mock_instance
            n_new, n_cached, n_total = m.fetch_and_cache("AAPL", interval)
            assert n_new == 3
            assert (env["data_dir"] / "AAPL" / f"{interval}.csv").exists()


# ─── load_watchlist ─────────────────────────────────────────────────────────

class TestLoadWatchlist:
    def test_load_all_sections(self, env):
        m = load_module(env["data_dir"], env["watchlist"])
        result = m.load_watchlist()
        assert "AAPL" in result and "DGE.L" in result

    def test_load_primary_only(self, env):
        m = load_module(env["data_dir"], env["watchlist"])
        assert m.load_watchlist(section="primary") == ["AAPL", "MSFT"]

    def test_load_secondary_only(self, env):
        m = load_module(env["data_dir"], env["watchlist"])
        assert m.load_watchlist(section="secondary") == ["DGE.L"]

    def test_load_missing_section_empty(self, env):
        m = load_module(env["data_dir"], env["watchlist"])
        assert m.load_watchlist(section="nonexistent") == []


# ─── list_cached_tickers ─────────────────────────────────────────────────────

class TestListCachedTickers:
    def test_empty_returns_empty_list(self, env):
        m = load_module(env["data_dir"], env["watchlist"])
        assert m.list_cached_tickers() == []

    def test_returns_tickers_with_csv(self, env):
        m = load_module(env["data_dir"], env["watchlist"])
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")
        (env["data_dir"] / "DGE.L").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "DGE.L" / "daily.csv")
        result = m.list_cached_tickers()
        assert "AAPL" in result and "DGE.L" in result


# ─── get_ticker_intervals ─────────────────────────────────────────────────────

class TestGetTickerIntervals:
    def test_no_intervals(self, env):
        m = load_module(env["data_dir"], env["watchlist"])
        assert m.get_ticker_intervals("NOSUCH") == []

    def test_returns_cached_intervals(self, env):
        m = load_module(env["data_dir"], env["watchlist"])
        tk_dir = env["data_dir"] / "AAPL"
        tk_dir.mkdir(parents=True)
        SAMPLE.to_csv(tk_dir / "daily.csv")
        SAMPLE.to_csv(tk_dir / "weekly.csv")
        result = m.get_ticker_intervals("AAPL")
        assert "daily" in result and "weekly" in result
        assert len(result) == 2


# ─── get_ticker_last_updated ──────────────────────────────────────────────────

class TestGetTickerLastUpdated:
    def test_none_returns_none(self, env):
        m = load_module(env["data_dir"], env["watchlist"])
        assert m.get_ticker_last_updated("NOSUCH") is None

    def test_returns_last_date(self, env):
        m = load_module(env["data_dir"], env["watchlist"])
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")
        result = m.get_ticker_last_updated("AAPL")
        assert result == "2026-01-06"
