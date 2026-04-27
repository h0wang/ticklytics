"""
Unit tests for ticklytics CLI commands.
Run with: pytest tests/test_cli.py -v
"""
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).parent.parent.parent / "src" / "ticklytics_pkg"  # scripts/ticklytics_pkg/


@pytest.fixture
def env(tmp_path):
    """Isolated temp DATA_DIR + WATCHLIST for CLI tests."""
    data_dir  = tmp_path / "ohlcv"
    watchlist = tmp_path / "watchlist.json"
    with open(watchlist, "w") as f:
        json.dump({
            "primary":     ["AAPL", "MSFT"],
            "secondary":   ["DGE.L"],
            "index":       ["^SPX"],
            "alternative": [],
            "sector":      [],
        }, f)
    return {"data_dir": data_dir, "watchlist": watchlist}


def cli_main(args: list[str], capsys=None, env=None):
    """Run ticklytics CLI with given args. Returns (exit_code, stdout, stderr)."""
    import sys
    from pathlib import Path

    # Add scripts/ to path so ticklytics_pkg imports work
    sys.path.insert(0, str(ROOT.parent))

    # Patch config before importing cli
    import ticklytics_pkg.config as config_mod
    import ticklytics_pkg.cache as cache_mod
    orig_data_dir  = getattr(config_mod, "DATA_DIR",  None)
    orig_watchlist = getattr(config_mod, "WATCHLIST", None)

    if env:
        config_mod.DATA_DIR  = env["data_dir"]
        config_mod.WATCHLIST = env["watchlist"]
        cache_mod.DATA_DIR   = env["data_dir"]
        cache_mod.WATCHLIST  = env["watchlist"]

    import ticklytics_pkg.__main__ as main_mod
    old_argv = sys.argv
    sys.argv = ["ticklytics"] + args
    exit_code = 0
    try:
        main_mod.main()
    except SystemExit as e:
        exit_code = e.code or 0
    finally:
        sys.argv = old_argv
        if orig_data_dir is not None:
            config_mod.DATA_DIR  = orig_data_dir
            config_mod.WATCHLIST = orig_watchlist
            cache_mod.DATA_DIR   = orig_data_dir
            cache_mod.WATCHLIST  = orig_watchlist

    if capsys:
        out, err = capsys.readouterr()
        return exit_code, out, err
    return exit_code, "", ""


class TestUpdateCLI:
    def test_update_help(self, capsys):
        exit_code, out, err = cli_main(["update", "--help"], capsys)
        assert exit_code == 0
        assert "ticklytics update" in out

    @patch("ticklytics_pkg.cache.yf.Ticker")
    def test_update_specific_tickers(self, mock_ticker, capsys, env):
        mock_instance = MagicMock()
        import pandas as pd
        mock_instance.history.return_value = pd.DataFrame({
            "Open": [270], "High": [275], "Low": [269], "Close": [273], "Volume": [10000]
        }, index=pd.to_datetime(["2026-04-24"]))
        mock_ticker.return_value = mock_instance

        exit_code, out, _ = cli_main(
            ["update", "AAPL", "--dry-run"],
            capsys,
            env
        )
        assert exit_code == 0
        assert "Dry run" in out
        assert "AAPL" in out

    def test_update_watchlist_secondary(self, capsys, env):
        exit_code, out, _ = cli_main(
            ["update", "--watchlist", "secondary", "--dry-run"],
            capsys,
            env
        )
        assert exit_code == 0
        assert "secondary" in out
        assert "DGE.L" in out

    def test_update_all_timeframes(self, capsys, env):
        exit_code, out, _ = cli_main(
            ["update", "AAPL", "--all", "--dry-run"],
            capsys,
            env
        )
        assert exit_code == 0
        assert "daily" in out and "weekly" in out and "monthly" in out


class TestServeCLI:
    def test_serve_help(self, capsys):
        exit_code, out, err = cli_main(["serve", "--help"], capsys)
        assert exit_code == 0
        assert "--port" in out

    def test_serve_unknown_flag(self, capsys):
        exit_code, out, err = cli_main(["serve", "--unknown-flag"], capsys)
        assert exit_code == 2  # argparse exits with 2 for invalid args


class TestMainRouter:
    def test_unknown_command(self, capsys):
        exit_code, out, err = cli_main(["foobar"], capsys)
        assert exit_code == 1
        assert "Unknown command" in out

    def test_no_args_shows_help(self, capsys):
        exit_code, out, err = cli_main([], capsys)
        assert exit_code == 1
        assert "ticklytics" in out
