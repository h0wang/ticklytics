# ticklytics

OHLCV market data cache and REST API — fetch, store, and serve price data via a clean Flask interface.

## Install

```bash
pip install -e .
```

## Standalone REST API

```bash
python -m ticklytics serve --port 5050
```

### Endpoints (standalone)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service status |
| `GET` | `/ohlcv/<ticker>` | OHLCV data (daily by default) |
| `POST` | `/ohlcv/<ticker>/refresh` | Force-refresh from yfinance |
| `GET` | `/tickers` | All cached tickers |
| `GET` | `/tickers/<ticker>` | Info for one ticker |
| `GET` | `/tickers/search?q=` | Search tickers |
| `GET` | `/watchlist` | Watchlist sections |

## Embed in any Flask app

ticklytics exposes a reusable Blueprint that can be mounted on any Flask app:

```python
from ticklytics_pkg.api import create_blueprint

app = Flask(__name__)
app.register_blueprint(create_blueprint(), url_prefix="/api/tick")
# → serves /api/tick/health, /api/tick/ohlcv/<ticker>, etc.
```

This is how romhongbus uses ticklytics — no separate service needed.

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

## Cache

Data is stored in `~/.openclaw/data/ohlcv/<TICKER>/<interval>.csv`.
Cache-first: yfinance is only hit when local data is stale (>1 day for daily, >7 days for weekly/monthly).

## Tests

```bash
pytest tests/ -v
```
