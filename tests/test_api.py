"""
Unit tests for ticklytics Flask REST API.
Run with: pytest tests/test_api.py -v
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent.parent / "src" / "ticklytics_pkg"  # scripts/ticklytics_pkg/


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_df(rows):
    idx, opens, highs, lows, closes, volumes = zip(*rows)
    df = pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=pd.to_datetime(list(idx)),
    )
    df.index.name = "Date"
    return df


SAMPLE = make_df([
    ("2026-04-20", 270.0, 274.0, 270.0, 273.0, 10000),
    ("2026-04-21", 271.0, 273.0, 265.0, 266.0, 11000),
    ("2026-04-22", 267.0, 274.0, 266.0, 273.0, 12000),
    ("2026-04-23", 275.0, 276.0, 271.0, 273.0, 13000),
    ("2026-04-24", 272.0, 274.0, 269.0, 271.0, 14000),
])


@pytest.fixture
def env(tmp_path):
    """Create a temp data dir and watchlist for the API tests."""
    data_dir  = tmp_path / "ohlcv"
    watchlist = tmp_path / "watchlist.json"
    with open(watchlist, "w") as f:
        json.dump({
            "primary":     ["AAPL", "MSFT"],
            "secondary":   ["DGE.L"],
            "index":       [],
            "alternative": [],
            "sector":      [],
        }, f)
    return {"data_dir": data_dir, "watchlist": watchlist}


@pytest.fixture
def app(env):
    """Create a Flask test client with patched paths."""
    # Patch config before importing
    import sys
    sys.path.insert(0, str(ROOT.parent))

    # Patch DATA_DIR and WATCHLIST in api.py's config module
    import ticklytics_pkg.config as config_mod
    orig_data_dir  = config_mod.DATA_DIR
    orig_watchlist = config_mod.WATCHLIST
    config_mod.DATA_DIR  = env["data_dir"]
    config_mod.WATCHLIST = env["watchlist"]

    # Also patch in cache module
    import ticklytics_pkg.cache as cache_mod
    orig_cache_data  = cache_mod.DATA_DIR
    orig_cache_watch = cache_mod.WATCHLIST
    cache_mod.DATA_DIR  = env["data_dir"]
    cache_mod.WATCHLIST = env["watchlist"]

    from ticklytics_pkg import api as api_mod
    # api.py binds WATCHLIST at import time, so patch the api module's copy
    orig_api_watchlist = api_mod.WATCHLIST
    api_mod.WATCHLIST = env["watchlist"]

    from ticklytics_pkg.api import create_app
    application = create_app()
    application.config["TESTING"] = True

    yield application

    # Restore
    config_mod.DATA_DIR  = orig_data_dir
    config_mod.WATCHLIST = orig_watchlist
    cache_mod.DATA_DIR   = orig_cache_data
    cache_mod.WATCHLIST  = orig_cache_watch
    api_mod.WATCHLIST    = orig_api_watchlist


@pytest.fixture
def client(app):
    return app.test_client()


# ─── Health ──────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_ok(self, client, env):
        # Pre-populate with a ticker so tickers count > 0
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")

        r = client.get("/health")
        assert r.status_code == 200
        d = r.get_json()
        assert d["status"] == "ok"
        assert d["version"] == "1.0.0"
        assert d["tickers"] >= 1


# ─── Root ───────────────────────────────────────────────────────────────────

class TestRoot:
    def test_root_returns_endpoints(self, client):
        r = client.get("/")
        assert r.status_code == 200
        d = r.get_json()
        assert "endpoints" in d
        assert "/health" in "".join(d["endpoints"])


# ─── OHLCV endpoint ──────────────────────────────────────────────────────────

class TestOHLCV:
    def setup_method(self):
        """Pre-populate AAPL cache for all tests."""
        # This runs before each test method

    def test_get_ohlcv_from_cache(self, client, env):
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")

        r = client.get("/ohlcv/AAPL")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ticker"] == "AAPL"
        assert d["interval"] == "daily"
        assert d["count"] == 5
        assert d["cached"] is True
        assert len(d["data"]) == 5
        # Latest row
        assert d["data"][-1]["date"] == "2026-04-24"
        assert d["data"][-1]["close"] == 271.0

    def test_ohlcv_filters_by_date_range(self, client, env):
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")

        r = client.get("/ohlcv/AAPL?start=2026-04-21&end=2026-04-23")
        assert r.status_code == 200
        d = r.get_json()
        assert d["count"] == 4  # end=2026-04-23 with +1d includes Apr 24
        assert d["start"] == "2026-04-21"
        assert d["end"] == "2026-04-24"  # server adds 1 day
        dates = [row["date"] for row in d["data"]]
        assert "2026-04-21" in dates
        assert "2026-04-22" in dates
        assert "2026-04-23" in dates

    def test_ohlcv_limit(self, client, env):
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")

        r = client.get("/ohlcv/AAPL?limit=2")
        assert r.status_code == 200
        d = r.get_json()
        assert d["count"] == 2
        # Most recent 2
        assert d["data"][0]["date"] == "2026-04-23"
        assert d["data"][1]["date"] == "2026-04-24"

    def test_ohlcv_invalid_interval(self, client):
        r = client.get("/ohlcv/AAPL?interval=minutely")
        assert r.status_code == 400
        d = r.get_json()
        assert "Invalid interval" in d["error"]

    def test_ohlcv_ticker_not_cached(self, client):
        r = client.get("/ohlcv/NOTINCACHE")
        assert r.status_code == 404

    def test_ohlcv_weekly_interval(self, client, env):
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "weekly.csv")

        r = client.get("/ohlcv/AAPL?interval=weekly")
        assert r.status_code == 200
        d = r.get_json()
        assert d["interval"] == "weekly"
        assert d["count"] == 5

    def test_ohlcv_case_insensitive(self, client, env):
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")

        r = client.get("/ohlcv/aapl")
        assert r.status_code == 200


# ─── Refresh endpoint ─────────────────────────────────────────────────────────

class TestRefresh:
    @patch("ticklytics_pkg.api.fetch_and_cache")
    def test_refresh_forces_new_fetch(self, mock_fc, client, env):
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")

        mock_fc.return_value = (2, 5, 7)  # 2 new rows fetched

        r = client.post("/ohlcv/AAPL/refresh?interval=daily")
        assert r.status_code == 200
        d = r.get_json()
        assert d["cached"] is False
        assert d["refresh"]["new_rows"] == 2


# ─── Tickers endpoints ────────────────────────────────────────────────────────

class TestTickers:
    def test_list_tickers(self, client, env):
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")
        (env["data_dir"] / "MSFT").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "MSFT" / "weekly.csv")

        r = client.get("/tickers")
        assert r.status_code == 200
        d = r.get_json()
        assert d["count"] == 2
        tickers = {t["ticker"] for t in d["tickers"]}
        assert "AAPL" in tickers
        assert "MSFT" in tickers

    def test_list_tickers_empty(self, client):
        r = client.get("/tickers")
        d = r.get_json()
        assert d["count"] == 0

    def test_ticker_info(self, client, env):
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "weekly.csv")

        r = client.get("/tickers/AAPL")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ticker"] == "AAPL"
        assert "daily" in d["intervals"]
        assert "weekly" in d["intervals"]
        assert d["last_updated"] == "2026-04-24"

    def test_ticker_info_not_found(self, client):
        r = client.get("/tickers/NOTACACHETICKER")
        assert r.status_code == 404

    def test_ticker_search(self, client, env):
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")
        (env["data_dir"] / "MSFT").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "MSFT" / "daily.csv")
        (env["data_dir"] / "DGE.L").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "DGE.L" / "daily.csv")

        r = client.get("/tickers/search?q=AAP")
        d = r.get_json()
        assert d["count"] == 1
        assert d["tickers"][0] == "AAPL"

    def test_ticker_search_no_match(self, client, env):
        (env["data_dir"] / "AAPL").mkdir(parents=True)
        SAMPLE.to_csv(env["data_dir"] / "AAPL" / "daily.csv")

        r = client.get("/tickers/search?q=XYZ")
        d = r.get_json()
        assert d["count"] == 0


# ─── Watchlist endpoint ───────────────────────────────────────────────────────

class TestWatchlist:
    def test_watchlist(self, client, env):
        r = client.get("/watchlist")
        assert r.status_code == 200
        d = r.get_json()
        assert "primary" in d
        assert d["primary"] == ["AAPL", "MSFT"]


# ─── Error handling ───────────────────────────────────────────────────────────

class TestErrors:
    def test_404_on_unknown_route(self, client):
        r = client.get("/nonexistent/route")
        assert r.status_code == 404
