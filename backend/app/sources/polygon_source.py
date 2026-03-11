"""Polygon data source adapter using PolygonClient.

Adapted from market-sim for portfolio-ai.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable
from typing import Any

import polars as pl

from ..logging_config import get_logger
from .base import BaseSource, DatasetRequest
from .jsonpath_mapper import map_response_to_schema
from .polygon_client import get_client

logger = get_logger(__name__)

# Mapping config for grouped daily endpoint
_DAY_BAR_MAPPING: dict[str, Any] = {
    "field_mapping": {
        "T": "symbol",
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
        "vw": "vwap",
        "n": "trade_count",
    },
    "data_path": "results",
}


def _iterate_dates(start: dt.date | dt.datetime, end: dt.date | dt.datetime) -> list[str]:
    """Generate list of ISO date strings between start and end."""
    start_date = start.date() if isinstance(start, dt.datetime) else start
    end_date = end.date() if isinstance(end, dt.datetime) else end
    if end_date < start_date:
        return []
    days: list[str] = []
    current = start_date
    while current <= end_date:
        days.append(current.isoformat())
        current += dt.timedelta(days=1)
    return days


def _parse_published_utc(raw: Any) -> dt.datetime | None:
    """Parse a published_utc string to a UTC datetime."""
    if not isinstance(raw, str):
        return None
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _news_item_to_record(item: dict[str, Any], symbol: str) -> dict[str, Any]:
    """Convert a Polygon news API item to a flat record dict."""
    return {
        "symbol": symbol,
        "headline": item.get("title"),
        "url": item.get("article_url"),
        "summary": item.get("description"),
        "news_source_name": (item.get("publisher") or {}).get("name"),
        "author": item.get("author"),
        "image_url": item.get("image_url"),
        "published_at": _parse_published_utc(item.get("published_utc")),
        "raw_payload": json.dumps(item),
        "source": "polygon",
    }


def _bar_to_record(bar: dict[str, Any], symbol: str) -> dict[str, Any]:
    """Convert a Polygon aggregate bar to a flat record dict."""
    bar_time = dt.datetime.fromtimestamp(bar.get("t", 0) / 1000, tz=dt.UTC)
    return {
        "symbol": symbol,
        "timestamp": bar_time,
        "open": bar.get("o"),
        "high": bar.get("h"),
        "low": bar.get("l"),
        "close": bar.get("c"),
        "volume": bar.get("v"),
        "vwap": bar.get("vw"),
        "trade_count": bar.get("n"),
        "source": "polygon",
    }


def _trade_to_record(trade: dict[str, Any], symbol: str) -> dict[str, Any]:
    """Convert a Polygon trade to a flat record dict."""
    trade_time = dt.datetime.fromtimestamp(trade.get("sip_timestamp", 0) / 1e9, tz=dt.UTC)
    return {
        "symbol": symbol,
        "timestamp": trade_time,
        "price": trade.get("price"),
        "size": trade.get("size"),
        "exchange": trade.get("exchange"),
        "conditions": trade.get("conditions"),
        "source": "polygon",
    }


class PolygonSource(BaseSource):
    """Polygon data source with automatic rate limiting."""

    name = "polygon"
    priority = 10  # Medium priority - rate limited on free tier (5/min)
    supports_day = True
    supports_reference = True
    supports_news = True

    def __init__(self, include_otc: bool = True) -> None:
        """Initialize Polygon source.

        Args:
            include_otc: Whether to include OTC (over-the-counter) securities
        """
        self.include_otc = include_otc
        self.client = get_client()
        logger.info("polygon_source_initialized", include_otc=include_otc)

    def _fetch_day_bar_for_date(self, iso_date: str, ingest_run_id: str | None) -> pl.DataFrame | None:
        """Fetch and annotate a single date's grouped daily bars."""
        path = f"/v2/aggs/grouped/locale/us/market/stocks/{iso_date}"
        params = {
            "adjusted": "true",
            "include_otc": "true" if self.include_otc else "false",
        }
        response = self.client.get(path, params)
        df = map_response_to_schema(response, _DAY_BAR_MAPPING)
        if df is None or len(df) == 0:
            logger.debug("polygon_no_data_for_date", date=iso_date)
            return None
        df = df.with_columns(pl.lit(dt.date.fromisoformat(iso_date)).alias("date_utc"))
        df = df.with_columns(pl.lit("polygon").alias("source"))
        if ingest_run_id:
            df = df.with_columns(pl.lit(ingest_run_id).alias("ingest_run_id"))
        return df

    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        """Fetch daily OHLCV bars using Polygon grouped_daily endpoint."""
        dates = _iterate_dates(request.start, request.end)
        logger.info(
            "polygon_fetch_day_bars_start",
            num_dates=len(dates),
            num_symbols=len(list(request.symbols)),
        )
        frames: list[pl.DataFrame] = []
        for iso_date in dates:
            try:
                df = self._fetch_day_bar_for_date(iso_date, request.ingest_run_id)
                if df is not None:
                    frames.append(df)
            except Exception as e:
                logger.warning(
                    "polygon_fetch_date_error",
                    date=iso_date,
                    error=str(e),
                    error_type=type(e).__name__,
                )
        if not frames:
            logger.warning("polygon_no_data_fetched")
            return None
        df_all = pl.concat(frames, how="vertical_relaxed")
        if request.symbols:
            df_all = df_all.filter(pl.col("symbol").is_in(list(request.symbols)))
        logger.info(
            "polygon_fetch_day_bars_complete",
            total_rows=len(df_all),
            unique_symbols=df_all["symbol"].n_unique(),
        )
        return df_all

    def fetch_reference_payload(
        self, symbols: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        """Fetch company reference data (symbol details) from Polygon.

        Returns:
            DataFrame with columns: symbol, as_of_date, payload (JSON string), source
        """
        records = []
        for symbol in symbols:
            try:
                response = self.client.get_symbol_details(symbol)
                payload_dict = response.get("results", {})
                if not payload_dict:
                    logger.debug("polygon_no_reference_data", symbol=symbol)
                    continue
                records.append(
                    {
                        "symbol": symbol,
                        "as_of_date": as_of,
                        "payload": json.dumps(payload_dict),
                        "source": "polygon",
                    }
                )
                logger.debug("polygon_reference_fetched", symbol=symbol)
            except Exception as e:
                logger.warning(
                    "polygon_reference_error",
                    symbol=symbol,
                    error=str(e),
                    error_type=type(e).__name__,
                )
        if not records:
            logger.warning("polygon_no_reference_data_fetched")
            return None
        logger.info("polygon_reference_complete", num_symbols=len(records))
        return pl.DataFrame(records)

    def _fetch_news_for_symbol(
        self, symbol: str, start_iso: str, end_iso: str
    ) -> list[dict[str, Any]]:
        """Fetch news records for one symbol (or market-wide)."""
        is_market = symbol == "__MARKET__"
        params: dict[str, Any] = {
            "published_utc.gte": start_iso,
            "published_utc.lte": end_iso,
            "order": "desc",
            "sort": "published_utc",
            "limit": 50,
        }
        if not is_market:
            params["symbol"] = symbol
        response = self.client.get("/v2/reference/news", params)
        results = response.get("results", [])
        if not results:
            logger.debug("polygon_news_empty", symbol=symbol)
            return []
        records = [_news_item_to_record(item, symbol) for item in results]
        logger.debug("polygon_news_fetched", symbol=symbol, articles=len(results))
        return records

    def fetch_news_payload(
        self, symbols: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        """Fetch news articles from Polygon reference news endpoint."""
        start_iso = start.astimezone(dt.UTC).isoformat()
        end_iso = end.astimezone(dt.UTC).isoformat()
        symbol_list = list(symbols) or ["__MARKET__"]
        records: list[dict[str, Any]] = []
        for symbol in symbol_list:
            try:
                records.extend(self._fetch_news_for_symbol(symbol, start_iso, end_iso))
            except Exception as exc:
                logger.warning(
                    "polygon_news_error",
                    symbol=symbol,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
        if not records:
            logger.info("polygon_news_no_articles", symbols=symbol_list)
            return None
        logger.info(
            "polygon_news_complete",
            total_articles=len(records),
            symbols=len({r["symbol"] for r in records}),
        )
        return pl.DataFrame(records)

    def fetch_intraday_bars(
        self,
        symbol: str,
        date: dt.date,
        timespan: str = "minute",
        multiplier: int = 1,
    ) -> pl.DataFrame | None:
        """Fetch intraday bars for a symbol."""
        try:
            date_str = date.isoformat()
            path = f"/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{date_str}/{date_str}"
            response = self.client.get(path, {"adjusted": "true", "sort": "asc", "limit": 50000})
            results = response.get("results", [])
            if not results:
                logger.debug("polygon_no_intraday_data", symbol=symbol, date=date_str)
                return None
            df = pl.DataFrame([_bar_to_record(bar, symbol) for bar in results])
            logger.info(
                "polygon_intraday_fetched",
                symbol=symbol,
                date=date_str,
                bars=len(df),
                timespan=f"{multiplier}{timespan}",
            )
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch intraday for {symbol}: {e}")
            return None

    def fetch_trades(
        self,
        symbol: str,
        date: dt.date,
        limit: int = 50000,
    ) -> pl.DataFrame | None:
        """Fetch individual trades (tick data) for a symbol."""
        try:
            date_str = date.isoformat()
            params = {
                "timestamp.gte": f"{date_str}T00:00:00Z",
                "timestamp.lte": f"{date_str}T23:59:59Z",
                "limit": limit,
                "sort": "timestamp",
            }
            response = self.client.get(f"/v3/trades/{symbol}", params)
            results = response.get("results", [])
            if not results:
                logger.debug("polygon_no_trades", symbol=symbol, date=date_str)
                return None
            df = pl.DataFrame([_trade_to_record(t, symbol) for t in results])
            logger.info("polygon_trades_fetched", symbol=symbol, date=date_str, trades=len(df))
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch trades for {symbol}: {e}")
            return None

    def fetch_extended_hours(
        self,
        symbol: str,
        date: dt.date,
    ) -> dict[str, pl.DataFrame | None]:
        """Fetch pre-market and after-hours data."""
        full_day = self.fetch_intraday_bars(symbol, date, "minute", 1)
        if full_day is None:
            return {"premarket": None, "afterhours": None}
        premarket_end = dt.time(14, 30)   # 9:30 AM ET = 14:30 UTC
        afterhours_start = dt.time(21, 0)  # 4:00 PM ET = 21:00 UTC
        premarket = full_day.filter(pl.col("timestamp").dt.time() < premarket_end)
        afterhours = full_day.filter(pl.col("timestamp").dt.time() >= afterhours_start)
        logger.info(
            "polygon_extended_hours_fetched",
            symbol=symbol,
            date=str(date),
            premarket_bars=len(premarket),
            afterhours_bars=len(afterhours),
        )
        return {
            "premarket": premarket if len(premarket) > 0 else None,
            "afterhours": afterhours if len(afterhours) > 0 else None,
        }
