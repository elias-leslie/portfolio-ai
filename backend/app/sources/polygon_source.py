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

    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        """Fetch daily OHLCV bars using Polygon grouped_daily endpoint.

        Strategy: Fetch all symbols for each date, then filter to requested symbols.
        This is more efficient than per-symbol requests for multiple symbols.
        """
        frames: list[pl.DataFrame] = []
        dates = _iterate_dates(request.start, request.end)

        logger.info(
            "polygon_fetch_day_bars_start",
            num_dates=len(dates),
            num_symbols=len(list(request.symbols)),
        )

        for iso_date in dates:
            try:
                # Use grouped_daily endpoint: get all symbols for a date
                # Polygon API path: /v2/aggs/grouped/locale/us/market/stocks/{date}
                path = f"/v2/aggs/grouped/locale/us/market/stocks/{iso_date}"
                params = {
                    "adjusted": "true",
                    "include_otc": "true" if self.include_otc else "false",
                }

                response = self.client.get(path, params)

                # Map response to schema
                mapping_config = {
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

                df = map_response_to_schema(response, mapping_config)
                if df is None or len(df) == 0:
                    logger.debug("polygon_no_data_for_date", date=iso_date)
                    continue

                # Add date column
                df = df.with_columns(pl.lit(dt.date.fromisoformat(iso_date)).alias("date_utc"))

                # Add source and ingest_run_id
                df = df.with_columns(pl.lit("polygon").alias("source"))
                if request.ingest_run_id:
                    df = df.with_columns(pl.lit(request.ingest_run_id).alias("ingest_run_id"))

                frames.append(df)

            except Exception as e:
                logger.warning(
                    "polygon_fetch_date_error",
                    date=iso_date,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                continue

        if not frames:
            logger.warning("polygon_no_data_fetched")
            return None

        # Combine all dates
        df_all = pl.concat(frames, how="vertical_relaxed")

        # Filter to requested symbols
        if request.symbols:
            symbol_list = list(request.symbols)
            df_all = df_all.filter(pl.col("symbol").is_in(symbol_list))

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
                # Use symbol details endpoint
                response = self.client.get_symbol_details(symbol)

                # Extract the results payload
                payload_dict = response.get("results", {})
                if not payload_dict:
                    logger.debug("polygon_no_reference_data", symbol=symbol)
                    continue

                # Convert to JSON string for storage
                payload_json = json.dumps(payload_dict)

                records.append(
                    {
                        "symbol": symbol,
                        "as_of_date": as_of,
                        "payload": payload_json,
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
                continue

        if not records:
            logger.warning("polygon_no_reference_data_fetched")
            return None

        logger.info(
            "polygon_reference_complete",
            num_symbols=len(records),
        )

        return pl.DataFrame(records)

    def fetch_news_payload(
        self, symbols: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        """Fetch news articles from Polygon reference news endpoint."""
        records: list[dict[str, Any]] = []
        start_iso = start.astimezone(dt.UTC).isoformat()
        end_iso = end.astimezone(dt.UTC).isoformat()

        symbol_list = list(symbols) or ["__MARKET__"]

        for symbol in symbol_list:
            is_market_request = symbol in (None, "__MARKET__")
            try:
                params = {
                    "published_utc.gte": start_iso,
                    "published_utc.lte": end_iso,
                    "order": "desc",
                    "sort": "published_utc",
                    "limit": 50,
                }
                if not is_market_request:
                    params["symbol"] = symbol

                response = self.client.get("/v2/reference/news", params)
                results = response.get("results", [])
                if not results:
                    logger.debug(
                        "polygon_news_empty",
                        symbol="__MARKET__" if is_market_request else symbol,
                    )
                    continue

                for item in results:
                    published_raw = item.get("published_utc")
                    try:
                        published_dt = (
                            dt.datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                            if isinstance(published_raw, str)
                            else None
                        )
                    except Exception:
                        published_dt = None

                    records.append(
                        {
                            "symbol": symbol if not is_market_request else "__MARKET__",
                            "headline": item.get("title"),
                            "url": item.get("article_url"),
                            "summary": item.get("description"),
                            "news_source_name": (item.get("publisher") or {}).get("name"),
                            "author": item.get("author"),
                            "image_url": item.get("image_url"),
                            "published_at": published_dt,
                            "raw_payload": json.dumps(item),
                            "source": "polygon",
                        }
                    )

                logger.debug(
                    "polygon_news_fetched",
                    symbol="__MARKET__" if is_market_request else symbol,
                    articles=len(results),
                )

            except Exception as exc:
                logger.warning(
                    "polygon_news_error",
                    symbol="__MARKET__" if is_market_request else symbol,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                continue

        if not records:
            logger.info("polygon_news_no_articles", symbols=list(symbols))
            return None

        logger.info(
            "polygon_news_complete",
            total_articles=len(records),
            symbols=len({record["symbol"] for record in records}),
        )

        return pl.DataFrame(records)


    # ============================================
    # GAP-001: Intraday Data
    # ============================================
    def fetch_intraday_bars(
        self,
        symbol: str,
        date: dt.date,
        timespan: str = "minute",
        multiplier: int = 1,
    ) -> pl.DataFrame | None:
        """Fetch intraday bars for a symbol.

        Args:
            symbol: Stock symbol
            date: Date to fetch
            timespan: Bar size ('minute', 'hour')
            multiplier: Multiplier for timespan (e.g., 5 for 5-minute bars)

        Returns:
            DataFrame with intraday OHLCV data
        """
        try:
            date_str = date.isoformat()
            path = f"/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{date_str}/{date_str}"
            params = {"adjusted": "true", "sort": "asc", "limit": 50000}

            response = self.client.get(path, params)
            results = response.get("results", [])

            if not results:
                logger.debug("polygon_no_intraday_data", symbol=symbol, date=date_str)
                return None

            records = []
            for bar in results:
                timestamp_ms = bar.get("t", 0)
                bar_time = dt.datetime.fromtimestamp(timestamp_ms / 1000, tz=dt.UTC)
                records.append({
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
                })

            df = pl.DataFrame(records)
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

    # ============================================
    # GAP-030: Tick Data (via trades endpoint)
    # ============================================
    def fetch_trades(
        self,
        symbol: str,
        date: dt.date,
        limit: int = 50000,
    ) -> pl.DataFrame | None:
        """Fetch individual trades (tick data) for a symbol.

        Args:
            symbol: Stock symbol
            date: Date to fetch
            limit: Max trades to return

        Returns:
            DataFrame with trade data
        """
        try:
            date_str = date.isoformat()
            path = f"/v3/trades/{symbol}"
            params = {
                "timestamp.gte": f"{date_str}T00:00:00Z",
                "timestamp.lte": f"{date_str}T23:59:59Z",
                "limit": limit,
                "sort": "timestamp",
            }

            response = self.client.get(path, params)
            results = response.get("results", [])

            if not results:
                logger.debug("polygon_no_trades", symbol=symbol, date=date_str)
                return None

            records = []
            for trade in results:
                timestamp_ns = trade.get("sip_timestamp", 0)
                trade_time = dt.datetime.fromtimestamp(timestamp_ns / 1e9, tz=dt.UTC)
                records.append({
                    "symbol": symbol,
                    "timestamp": trade_time,
                    "price": trade.get("price"),
                    "size": trade.get("size"),
                    "exchange": trade.get("exchange"),
                    "conditions": trade.get("conditions"),
                    "source": "polygon",
                })

            df = pl.DataFrame(records)
            logger.info(
                "polygon_trades_fetched",
                symbol=symbol,
                date=date_str,
                trades=len(df),
            )
            return df

        except Exception as e:
            logger.warning(f"Failed to fetch trades for {symbol}: {e}")
            return None

    # ============================================
    # GAP-038: Pre-market and After-hours Data
    # ============================================
    def fetch_extended_hours(
        self,
        symbol: str,
        date: dt.date,
    ) -> dict[str, pl.DataFrame | None]:
        """Fetch pre-market and after-hours data.

        Pre-market: 04:00 - 09:30 ET
        After-hours: 16:00 - 20:00 ET

        Args:
            symbol: Stock symbol
            date: Date to fetch

        Returns:
            Dict with 'premarket' and 'afterhours' DataFrames
        """
        # Fetch full day of minute bars
        full_day = self.fetch_intraday_bars(symbol, date, "minute", 1)

        if full_day is None:
            return {"premarket": None, "afterhours": None}

        # Define market hours in UTC (ET + 5 during EST, +4 during EDT)
        # For simplicity, use approximate UTC times
        premarket_end = dt.time(14, 30)  # 9:30 AM ET = 14:30 UTC
        afterhours_start = dt.time(21, 0)  # 4:00 PM ET = 21:00 UTC

        # Filter for pre-market
        premarket = full_day.filter(
            pl.col("timestamp").dt.time() < premarket_end
        )

        # Filter for after-hours
        afterhours = full_day.filter(
            pl.col("timestamp").dt.time() >= afterhours_start
        )

        logger.info(
            "polygon_extended_hours_fetched",
            symbol=symbol,
            date=str(date),
            premarket_bars=len(premarket) if premarket is not None else 0,
            afterhours_bars=len(afterhours) if afterhours is not None else 0,
        )

        return {
            "premarket": premarket if len(premarket) > 0 else None,
            "afterhours": afterhours if len(afterhours) > 0 else None,
        }


def _iterate_dates(start: dt.date | dt.datetime, end: dt.date | dt.datetime) -> list[str]:
    """Generate list of ISO date strings between start and end.

    Args:
        start: Start date
        end: End date

    Returns:
        List of ISO date strings (e.g., ["2024-01-01", "2024-01-02", ...])
    """
    # Convert to date objects (helper function, simple inline conversion is fine)
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
