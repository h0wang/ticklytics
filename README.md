# ticklytics

OHLCV market data cache and REST API — fetch, store, and serve price data via a clean Flask interface.

## Install

```bash
pip install -e .
```

## CLI

```bash
# Update specific tickers
python -m ticklytics update AAPL MSFT

# Update from watchlist
python -m ticklytics update --watchlist primary

# Dry run
python -m ticklytics update AAPL --dry-run

# All three timeframes
python -m ticklytics update AAPL --all
```

## REST API

```bash
python -m ticklytics serve --port 5050
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service status |
| `GET` | `/ohlcv/<ticker>` | OHLCV data (daily by default) |
| `POST` | `/ohlcv/<ticker>/refresh` | Force-refresh from yfinance |
| `GET` | `/tickers` | All cached tickers |
| `GET` | `/tickers/<ticker>` | Info for one ticker |
| `GET` | `/tickers/search?q=` | Search tickers |
| `GET` | `/watchlist` | Watchlist sections |

### Query parameters

- `?interval=daily|weekly|monthly`
- `?start=YYYY-MM-DD&end=YYYY-MM-DD`
- `?limit=N` — most recent N rows
- `?refresh=true` — bypass cache and fetch live

## Cache

Data is stored in `~/.openclaw/data/ohlcv/<TICKER>/<interval>.csv`.
Cache-first: yfinance is only hit when local data is stale (>1 day for daily, >7 days for weekly/monthly).

## Tests

```bash
pytest tests/ -v
```