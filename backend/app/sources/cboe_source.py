"""CBOE delayed-quote data source adapter.

CBOE publishes official ~15-minute-delayed quotes for the indices it owns
(VIX, SPX, ...) via its public delayed-quotes feed. For index symbols like
``^VIX`` this is the authoritative upstream — far more reliable than scraping a
third party, and crucially it never substitutes a prior-day close for a live
value the way yfinance's ``.info`` does for indices.

Only index symbols in ``SYMBOL_MAP`` are served; everything else falls through to
the next source in the multi-source chain. No API key required.
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.request
from collections.abc import Iterable

import polars as pl

from ..logging_config import get_logger
from ..utils.market_hours import NY_TZ
from .base import BaseSource, DatasetRequest

logger = get_logger(__name__)

# Map our canonical symbols to CBOE delayed-quote tickers (indices are underscore-prefixed).
SYMBOL_MAP: dict[str, str] = {
    "^VIX": "_VIX",
}

_QUOTE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/quotes/{ticker}.json"
_TIMEOUT_SECONDS = 8
# CBOE's delayed feed is the authoritative intraday source for the indices it owns.
_PRICE_SESSION = "delayed"


def _fetch_quote(cboe_ticker: str) -> dict | None:
    url = _QUOTE_URL.format(ticker=cboe_ticker)
    req = urllib.request.Request(url, headers={"User-Agent": "portfolio-ai/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read())
    except Exception as exc:  # network/parse errors -> fall through to the next source
        logger.warning("cboe_quote_unavailable", ticker=cboe_ticker, error=str(exc))
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        logger.warning("cboe_quote_malformed", ticker=cboe_ticker)
        return None
    return data


def _quote_time_iso(raw: object) -> str | None:
    """Normalise CBOE ``last_trade_time`` to an aware US/Eastern ISO timestamp.

    CBOE serves ``last_trade_time`` as a naive wall-clock value in US/Eastern
    (e.g. ``2026-06-04T16:15:01`` for the 4:15pm ET VIX settle). Left naive it
    would be misread as UTC downstream, throwing the freshness age off by the
    Eastern offset; stamping the zone keeps the age math honest.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.strip())
    except ValueError:
        logger.warning("cboe_quote_time_unparseable", value=raw)
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=NY_TZ)
    return parsed.isoformat()


def _build_payload(symbol: str, data: dict) -> dict | None:
    price = data.get("current_price")
    if not isinstance(price, (int, float)) or price <= 0:
        logger.warning("cboe_quote_no_price", symbol=symbol)
        return None
    return {
        "symbol": symbol,
        "price": float(price),
        "price_session": _PRICE_SESSION,
        "quote_time": _quote_time_iso(data.get("last_trade_time")),
        "bid": data.get("bid"),
        "ask": data.get("ask"),
        "bid_size": data.get("bid_size"),
        "ask_size": data.get("ask_size"),
    }


class CboeSource(BaseSource):
    """CBOE official delayed-quote source for index symbols (VIX, ...)."""

    name = "cboe"
    priority = 0  # Tried before yfinance for the index symbols it owns
    supports_reference = True

    def is_enabled(self) -> bool:
        return True

    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        return None

    def fetch_reference_payload(
        self, symbols: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        records = []
        for symbol in symbols:
            cboe_ticker = SYMBOL_MAP.get(str(symbol).strip().upper())
            if cboe_ticker is None:
                continue  # not a CBOE index symbol -> let the next source handle it
            data = _fetch_quote(cboe_ticker)
            if data is None:
                continue
            payload = _build_payload(str(symbol).strip().upper(), data)
            if payload is None:
                continue
            records.append(
                {
                    "symbol": payload["symbol"],
                    "as_of_date": as_of,
                    "payload": json.dumps(payload),
                    "source": self.name,
                }
            )
        if not records:
            return None
        logger.info("cboe_reference_complete", num_symbols=len(records))
        return pl.DataFrame(records)

    def fetch_news_payload(
        self, symbols: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        return None
