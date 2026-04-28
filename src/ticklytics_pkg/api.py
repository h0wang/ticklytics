"""
Flask REST API for ticklytics OHLCV data.

python -m ticklytics serve [--host HOST] [--port PORT] [--debug]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from flask import Blueprint, Flask, jsonify, request, send_from_directory

from .cache import (
    load_from_cache,
    fetch_and_cache,
    list_cached_tickers,
    get_ticker_intervals,
    get_ticker_last_updated,
    load_watchlist,
)
from .config import DATA_DIR, DEFAULT_HOST, DEFAULT_PORT, WATCHLIST
from .models import (
    format_ohlcv_response,
    format_ticker_info,
    HealthResponse,
    ErrorResponse,
)

VERSION = "1.0.0"

# ─── Reusable Blueprint ────────────────────────────────────────────────────────

def create_blueprint() -> Blueprint:
    """Create a Flask Blueprint with all ticklytics routes."""
    bp = Blueprint("ticklytics", __name__)

    @bp.route("/health")
    def health():
        return jsonify(HealthResponse(
            status="ok",
            version=VERSION,
            timestamp=datetime.now().isoformat(),
            tickers=len(list_cached_tickers()),
            cache_dir=str(DATA_DIR),
        ).__dict__)

    @bp.route("/ohlcv/<ticker>")
    def ohlcv(ticker: str):
        interval = request.args.get("interval", "daily")
        if interval not in ("daily", "weekly", "monthly"):
            return jsonify(ErrorResponse(
                error="Invalid interval",
                detail="Must be daily, weekly, or monthly",
                code=400,
            ).__dict__), 400

        start_str = request.args.get("start")
        end_str   = request.args.get("end")
        limit     = int(request.args.get("limit", 1000))
        refresh   = request.args.get("refresh", "0") == "1"
        ticker_upper = ticker.upper()

        df = load_from_cache(ticker_upper, interval)
        if df is None or df.empty:
            try:
                fetch_and_cache(ticker_upper, interval)
                df = load_from_cache(ticker_upper, interval)
            except Exception as e:
                return jsonify(ErrorResponse(
                    error="Ticker not found",
                    detail=str(e),
                    code=404,
                ).__dict__), 404

        if df is None or df.empty:
            return jsonify(ErrorResponse(
                error="No data for ticker",
                detail=f"No cached data found for {ticker_upper}",
                code=404,
            ).__dict__), 404

        if start_str:
            df = df[df.index >= pd.Timestamp(start_str)]
        if end_str:
            df = df[df.index <= pd.Timestamp(end_str) + pd.Timedelta(days=1)]
        if len(df) > limit:
            df = df.sort_index().tail(limit)

        return jsonify(format_ohlcv_response(ticker_upper, interval, df, cached=not refresh))

    @bp.route("/ohlcv/<ticker>/refresh", methods=["POST"])
    def ohlcv_refresh(ticker: str):
        interval = request.args.get("interval", "daily")
        if interval not in ("daily", "weekly", "monthly"):
            return jsonify(ErrorResponse(
                error="Invalid interval",
                detail="Must be daily, weekly, or monthly",
                code=400,
            ).__dict__), 400

        ticker_upper = ticker.upper()
        try:
            n_new, n_cached, n_total = fetch_and_cache(ticker_upper, interval)
            df = load_from_cache(ticker_upper, interval)
            return jsonify({
                **format_ohlcv_response(ticker_upper, interval, df, cached=False),
                "refresh": {
                    "new_rows": n_new,
                    "was_cached": n_cached,
                    "total": n_total,
                },
            })
        except Exception as e:
            return jsonify(ErrorResponse(
                error="Refresh failed",
                detail=str(e),
                code=500,
            ).__dict__), 500

    @bp.route("/tickers")
    def tickers():
        all_tickers = list_cached_tickers()
        result = []
        for tk in all_tickers:
            result.append(format_ticker_info(
                ticker=tk,
                intervals=get_ticker_intervals(tk),
                last_updated=get_ticker_last_updated(tk),
            ))
        return jsonify({"count": len(result), "tickers": result})

    @bp.route("/tickers/<ticker>")
    def ticker_info(ticker: str):
        ticker_upper = ticker.upper()
        intervals = get_ticker_intervals(ticker_upper)
        if not intervals:
            return jsonify(ErrorResponse(
                error="Ticker not found",
                detail=f"No cached data for {ticker_upper}",
                code=404,
            ).__dict__), 404
        return jsonify(format_ticker_info(
            ticker=ticker_upper,
            intervals=intervals,
            last_updated=get_ticker_last_updated(ticker_upper),
        ))

    @bp.route("/tickers/search")
    def ticker_search():
        q = (request.args.get("q") or "").upper()
        if not q:
            return jsonify({"count": 0, "tickers": []})
        matches = [tk for tk in list_cached_tickers() if tk.startswith(q)]
        return jsonify({"count": len(matches), "query": q, "tickers": matches})

    @bp.route("/watchlist")
    def watchlist():
        with open(WATCHLIST) as f:
            wl = json.load(f)
        return jsonify(wl)

    @bp.route("/")
    def root():
        return jsonify({
            "name": "ticklytics",
            "version": VERSION,
            "description": "OHLCV market data cache and REST API",
            "endpoints": [
                "GET  /health",
                "GET  /ohlcv/<ticker>?interval=&start=&end=&limit=&refresh=",
                "POST /ohlcv/<ticker>/refresh?interval=",
                "GET  /tickers",
                "GET  /tickers/<ticker>",
                "GET  /tickers/search?q=",
                "GET  /watchlist",
            ],
        })

    return bp


def create_app() -> Flask:
    """Create a standalone Flask app with ticklytics routes."""
    app = Flask(__name__)
    app.register_blueprint(create_blueprint())
    return app


def serve(argv: list[str] | None = None) -> None:
    """Start the Flask REST API server."""
    parser = argparse.ArgumentParser(prog="ticklytics serve")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind to")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes")
    args = parser.parse_args(argv if argv is not None else sys.argv[2:])

    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug, reload=args.reload)


if __name__ == "__main__":
    serve()
