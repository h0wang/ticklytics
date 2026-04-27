"""
CLI commands for ticklytics.

python -m ticklytics update [tickers] [options]
"""
import argparse
import sys
import os

from .cache import fetch_and_cache, load_watchlist
from .config import DATA_DIR


def update(argv: list[str] | None = None) -> None:
    """Update OHLCV cache for specified tickers."""
    parser = argparse.ArgumentParser(
        prog="ticklytics update",
        description="Update OHLCV cache from yfinance.",
    )
    parser.add_argument(
        "tickers",
        nargs="*",
        help="Specific tickers. If omitted, uses --watchlist.",
    )
    parser.add_argument(
        "--watchlist", "-w",
        dest="watchlist_section",
        metavar="SECTION",
        help="Use watchlist section: primary (default), secondary, all, index, alternative, sector",
    )
    parser.add_argument(
        "--timeframe", "-t",
        nargs="+",
        choices=["daily", "weekly", "monthly"],
        default=["daily"],
        dest="timeframes",
        help="Timeframe(s) to update.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Update all three timeframes.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without fetching.",
    )
    parser.add_argument(
        "--since",
        dest="since_days",
        type=int,
        metavar="N",
        help="Force refresh if cache is older than N days (for a specific ticker).",
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[2:])

    # Resolve tickers
    if args.tickers:
        tickers = args.tickers
    elif args.watchlist_section:
        section_map = {
            "primary": "primary", "secondary": "secondary",
            "all": None, "index": "index",
            "alternative": "alternative", "sector": "sector",
        }
        section = section_map.get(args.watchlist_section, "primary")
        tickers = load_watchlist(section=section)
        if not tickers:
            print(f"No tickers found for watchlist section '{args.watchlist_section}'.")
            sys.exit(1)
        print(f"Watchlist [{args.watchlist_section}]: {len(tickers)} tickers")
    else:
        tickers = load_watchlist(section="primary")
        print(f"Default (primary watchlist): {len(tickers)} tickers")

    timeframes = args.timeframes
    if args.all:
        timeframes = ["daily", "weekly", "monthly"]

    if args.dry_run:
        print(f"\nDry run — would update {len(tickers)} tickers for {timeframes}:")
        for tk in tickers:
            print(f"  {tk}")
        return

    print(f"\nUpdating {len(tickers)} tickers × {timeframes}...")
    print()

    total_fetched = 0
    errors = []

    for ticker in tickers:
        for tf in timeframes:
            try:
                n_new, n_cached, n_total = fetch_and_cache(ticker, tf)
                total_fetched += n_new
                status = f"+{n_new} new" if n_new > 0 else "up to date"
                print(f"  {ticker} [{tf}]: {status} ({n_cached} cached → {n_total} total)")
            except Exception as e:
                errors.append((ticker, tf, str(e)))
                print(f"  {ticker} [{tf}]: ERROR — {e}")

    print(f"\nDone. {total_fetched} new rows fetched.", end="")
    if errors:
        print(f" {len(errors)} failures: {[(e[0], e[1]) for e in errors]}")
    else:
        print()
