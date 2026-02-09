"""YFinance raw data fetching operations.

Low-level fetching functions that interact with yfinance API.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import polars as pl
import yfinance as yf

from ..logging_config import get_logger
from .base import DatasetRequest, standardize_dates
from .yfinance_parsers import (
    build_reference_payload,
    parse_cash_flow_data,
    parse_insider_transactions,
    parse_institutional_holders,
    parse_news_item,
    parse_ohlcv_to_polars,
    parse_short_interest,
)

# Ensure HOME environment variable is set before importing yfinance
# This prevents yfinance from trying to create cache files in non-existent directories
if not os.environ.get("HOME"):
    os.environ["HOME"] = "/var/cache/portfolio-ai"

# Configure yfinance cache location to avoid SQLite readonly errors in worker processes
# The default location may have permission issues or concurrent access conflicts
_yf_cache_dir = Path(os.environ.get("HOME", "/tmp")) / ".cache" / "yfinance"
_yf_cache_dir.mkdir(parents=True, exist_ok=True)
yf.cache.set_cache_location(str(_yf_cache_dir))

logger = get_logger(__name__)

MARKET_SYMBOL = "^GSPC"


def fetch_day_bars(request: DatasetRequest) -> pl.DataFrame | None:
    """Fetch daily OHLCV bars from yfinance."""
    frames: list[pl.DataFrame] = []
    start_date, end_date = standardize_dates(request)

    logger.info(
        "yfinance_fetch_day_bars_start",
        num_symbols=len(list(request.symbols)),
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )

    for symbol in request.symbols:
        try:
            yf_obj = yf.Ticker(symbol)
            # NOTE: yfinance end parameter is EXCLUSIVE, so add 1 day to include end_date
            hist = yf_obj.history(
                start=start_date.isoformat(),
                end=(end_date + dt.timedelta(days=1)).isoformat(),
                auto_adjust=True,  # Adjust for splits/dividends
            )

            if hist.empty:
                logger.debug("yfinance_no_data", symbol=symbol)
                continue

            df = parse_ohlcv_to_polars(hist, symbol, request.ingest_run_id)
            frames.append(df)

            logger.debug("yfinance_fetch_success", symbol=symbol, rows=len(df))

        except Exception as e:
            logger.warning(
                "yfinance_fetch_error",
                symbol=symbol,
                error=str(e),
                error_type=type(e).__name__,
            )
            continue

    if not frames:
        logger.warning("yfinance_no_data_fetched")
        return None

    combined = pl.concat(frames, how="vertical_relaxed")

    logger.info(
        "yfinance_fetch_day_bars_complete",
        total_rows=len(combined),
        unique_symbols=combined["symbol"].n_unique(),
    )

    return combined


def fetch_reference_payload(symbols: Iterable[str], as_of: dt.date) -> pl.DataFrame | None:
    """Fetch company reference data from yfinance."""
    records = []
    symbol_list = list(symbols)

    logger.info(
        "yfinance_fetch_reference_start",
        num_symbols=len(symbol_list),
        as_of_date=as_of.isoformat(),
    )

    for symbol in symbol_list:
        try:
            yf_obj = yf.Ticker(symbol)
            info = yf_obj.info

            if not info:
                logger.debug("yfinance_no_reference_data", symbol=symbol)
                continue

            payload_dict = build_reference_payload(symbol, info)
            records.append(
                {
                    "symbol": symbol,
                    "as_of_date": as_of,
                    "payload": json.dumps(payload_dict),
                    "source": "yfinance",
                }
            )

            logger.debug("yfinance_reference_fetched", symbol=symbol)

        except Exception as e:
            logger.warning(
                "yfinance_reference_error",
                symbol=symbol,
                error=str(e),
                error_type=type(e).__name__,
            )
            continue

    if not records:
        logger.warning("yfinance_no_reference_data_fetched")
        return None

    logger.info("yfinance_reference_complete", num_symbols=len(records))
    return pl.DataFrame(records)


def fetch_news_payload(
    symbols: Iterable[str], start: dt.datetime, end: dt.datetime
) -> pl.DataFrame | None:
    """Fetch news articles using yfinance's symbol news feed."""
    records: list[dict[str, Any]] = []
    start_utc = start.astimezone(dt.UTC)
    end_utc = end.astimezone(dt.UTC)

    symbol_list = list(symbols) or ["__MARKET__"]

    for symbol in symbol_list:
        is_market = symbol in (None, "__MARKET__")
        target_symbol = MARKET_SYMBOL if is_market else symbol

        try:
            news_items = yf.Ticker(target_symbol).get_news()
        except Exception as exc:  # pragma: no cover - passthrough to fallback vendors
            logger.warning(
                "yfinance_news_error",
                symbol=target_symbol,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            continue

        if not news_items:
            logger.debug("yfinance_news_empty", symbol=target_symbol)
            continue

        for item in news_items:
            parsed = parse_news_item(item, symbol, is_market, start_utc, end_utc)
            if parsed:
                records.append(parsed)

        logger.debug(
            "yfinance_news_fetched",
            symbol=target_symbol,
            articles=len(news_items),
        )

    if not records:
        logger.info("yfinance_news_no_articles", symbols=symbol_list)
        return None

    return pl.DataFrame(records)


def fetch_cash_flow_data(symbol: str) -> dict[str, Any] | None:
    """Fetch cash flow statement data for a symbol."""
    try:
        yf_obj = yf.Ticker(symbol)
        cf = yf_obj.cashflow
        info = yf_obj.info
        return parse_cash_flow_data(cf, info, symbol)
    except Exception as e:
        logger.warning(f"Failed to fetch cash flow for {symbol}: {e}")
        return None


def fetch_insider_transactions(symbol: str) -> list[dict[str, Any]]:
    """Fetch insider transactions for a symbol."""
    try:
        yf_obj = yf.Ticker(symbol)
        insiders = yf_obj.insider_transactions
        transactions = parse_insider_transactions(insiders, symbol)
        logger.debug(f"Fetched {len(transactions)} insider transactions for {symbol}")
        return transactions
    except Exception as e:
        logger.warning(f"Failed to fetch insider transactions for {symbol}: {e}")
        return []


def fetch_institutional_holders(symbol: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch institutional holders for a symbol."""
    try:
        yf_obj = yf.Ticker(symbol)
        holders_df = yf_obj.institutional_holders
        info = yf_obj.info
        holders, summary = parse_institutional_holders(holders_df, info, symbol)
        logger.debug(f"Fetched {len(holders)} institutional holders for {symbol}")
        return holders, summary
    except Exception as e:
        logger.warning(f"Failed to fetch institutional holders for {symbol}: {e}")
        return [], {}


def fetch_short_interest(symbol: str) -> dict[str, Any] | None:
    """Fetch short interest data for a symbol."""
    try:
        yf_obj = yf.Ticker(symbol)
        info = yf_obj.info
        return parse_short_interest(info, symbol)
    except Exception as e:
        logger.warning(f"Failed to fetch short interest for {symbol}: {e}")
        return None


def fetch_all_fundamental_data(symbol: str) -> dict[str, Any]:
    """Fetch all fundamental data for a symbol in one call."""
    result = {
        "symbol": symbol,
        "cash_flow": fetch_cash_flow_data(symbol),
        "insider_transactions": fetch_insider_transactions(symbol),
        "short_interest": fetch_short_interest(symbol),
    }

    holders, summary = fetch_institutional_holders(symbol)
    result["institutional_holders"] = holders
    result["institutional_summary"] = summary

    return result


def fetch_sector_history(
    symbol: str,
    start_date: dt.date,
    end_date: dt.date,
) -> list[tuple[dt.date, float]]:
    """Fetch historical close prices for a sector ETF."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(
            start=start_date.isoformat(),
            end=(end_date + dt.timedelta(days=1)).isoformat(),
            auto_adjust=True,
        )

        if hist.empty:
            logger.debug("yfinance_sector_no_data", symbol=symbol)
            return []

        rows = [
            (row.Index.date(), float(row.Close))
            for row in hist.itertuples()
            if row.Index is not None and row.Close is not None
        ]

        logger.debug("yfinance_sector_fetched", symbol=symbol, rows=len(rows))
        return rows

    except Exception as e:
        logger.warning(
            "yfinance_sector_fetch_error",
            symbol=symbol,
            error=str(e),
        )
        return []
