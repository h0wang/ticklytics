"""
ticklytics CLI entry point.

python -m ticklytics <command>
python -m ticklytics update AAPL MSFT --timeframe daily weekly
python -m ticklytics serve --port 5050 --debug
"""
import sys

COMMANDS = ["update", "serve"]


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("ticklytics — OHLCV market data cache and REST API\n")
        print("Commands:")
        print("  update [tickers]    Update OHLCV cache from yfinance")
        print("  serve                Start REST API server")
        print("\nRun 'python -m ticklytics <command> -h' for command-specific help.")
        sys.exit(0 if len(sys.argv) > 1 and sys.argv[1] not in ("-h", "--help") else 1)

    cmd = sys.argv[1]

    if cmd == "update":
        from .cli import update
        update()
    elif cmd == "serve":
        from .api import serve
        serve()
    else:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(COMMANDS)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
