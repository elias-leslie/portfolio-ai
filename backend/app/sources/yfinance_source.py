"""YFinance data source adapter.

Implements BaseSource interface for yfinance library with support for
daily OHLCV data and company reference information.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
from collections.abc import Iterable
from typing import Any

import polars as pl

# Ensure HOME environment variable is set before importing yfinance
# This prevents yfinance from trying to create cache files in non-existent directories
if not os.environ.get("HOME"):
    os.environ["HOME"] = "/var/cache/portfolio-ai"

import yfinance as yf  # yfinance doesn't ship type stubs

from ..logging_config import get_logger
from .base import BaseSource, DatasetRequest, standardize_dates

logger = get_logger(__name__)


class YFinanceSource(BaseSource):
    """YFinance data source adapter.

    Free tier with no API key required.
    Note: yfinance has quirks - delays of 0.5-2s between requests recommended.
    """

    name = "yfinance"
    priority = 1  # Highest priority (free, no rate limits for basic usage)
    supports_day = True
    supports_reference = True
    supports_news = True

    MARKET_SYMBOL = "^GSPC"

    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        """Fetch daily OHLCV bars from yfinance.

        Args:
            request: DatasetRequest with symbols, start, end dates

        Returns:
            Polars DataFrame with OHLCV data, or None if fetch fails
        """
        frames: list[pl.DataFrame] = []

        # Convert dates to date objects
        start_date, end_date = standardize_dates(request)

        logger.info(
            "yfinance_fetch_day_bars_start",
            num_symbols=len(list(request.symbols)),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        for symbol in request.symbols:
            try:
                # Fetch historical data
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

                # Convert pandas DataFrame to Polars
                # Reset index to get Date as a column
                hist = hist.reset_index()

                # Map column names to our schema
                df = pl.from_pandas(hist).select(
                    [
                        pl.col("Date").cast(pl.Date).alias("date"),
                        pl.lit(symbol).alias("symbol"),
                        pl.col("Open").alias("open"),
                        pl.col("High").alias("high"),
                        pl.col("Low").alias("low"),
                        pl.col("Close").alias("close"),
                        pl.col("Volume").cast(pl.Int64).alias("volume"),
                        pl.lit(None)
                        .cast(pl.Float64)
                        .alias("vwap"),  # yfinance doesn't provide VWAP
                        pl.lit("yfinance").alias("source"),
                    ]
                )

                # Add ingest_run_id if provided
                if request.ingest_run_id:
                    df = df.with_columns(pl.lit(request.ingest_run_id).alias("ingest_run_id"))

                frames.append(df)

                logger.debug(
                    "yfinance_fetch_success",
                    symbol=symbol,
                    rows=len(df),
                )

            except Exception as e:
                logger.warning(
                    "yfinance_fetch_error",
                    symbol=symbol,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # Continue to next symbol
                continue

        if not frames:
            logger.warning("yfinance_no_data_fetched")
            return None

        # Combine all symbols
        combined = pl.concat(frames, how="vertical_relaxed")

        logger.info(
            "yfinance_fetch_day_bars_complete",
            total_rows=len(combined),
            unique_symbols=combined["symbol"].n_unique(),
        )

        return combined

    def _extract_price_from_info(self, info: dict[str, Any]) -> float | None:
        """Extract price from yfinance info dict (tries multiple fields)."""
        return (
            info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        )

    def _calculate_volatility_from_52w_range(self, info: dict[str, Any]) -> float | None:
        """Calculate approximate annualized volatility from 52-week range."""
        high_52 = info.get("fiftyTwoWeekHigh")
        low_52 = info.get("fiftyTwoWeekLow")
        if (
            high_52
            and low_52
            and isinstance(high_52, (int, float))
            and isinstance(low_52, (int, float))
            and high_52 > 0
        ):
            return float((high_52 - low_52) / high_52)
        return None

    def _build_reference_payload(self, symbol: str, info: dict[str, Any]) -> dict[str, Any]:
        """Build reference payload from yfinance info dict."""
        price = self._extract_price_from_info(info)
        beta = info.get("beta")
        volatility = self._calculate_volatility_from_52w_range(info)

        return {
            "symbol": symbol,
            "price": price,
            "beta": beta,
            "volatility": volatility,
            "longName": info.get("longName"),
            "shortName": info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "marketCap": info.get("marketCap"),
            "currency": info.get("currency"),
            "exchange": info.get("exchange"),
            "country": info.get("country"),
            "website": info.get("website"),
            "description": info.get("longBusinessSummary"),
            # Core valuation ratios (7 target metrics)
            "trailingPE": info.get("trailingPE"),
            "forwardPE": info.get("forwardPE"),
            "priceToBook": info.get("priceToBook"),
            "priceToSalesTrailing12Months": info.get("priceToSalesTrailing12Months"),
            "pegRatio": info.get("pegRatio") or info.get("trailingPegRatio"),
            "dividendYield": info.get("dividendYield"),
            "payoutRatio": info.get("payoutRatio"),
            # Bonus metrics (for comprehensive fundamentals)
            "trailingEps": info.get("trailingEps"),
            "forwardEps": info.get("forwardEps"),
            "enterpriseValue": info.get("enterpriseValue"),
            "enterpriseToRevenue": info.get("enterpriseToRevenue"),
            "enterpriseToEbitda": info.get("enterpriseToEbitda"),
            "debtToEquity": info.get("debtToEquity"),
            "currentRatio": info.get("currentRatio"),
            "returnOnEquity": info.get("returnOnEquity"),
            "returnOnAssets": info.get("returnOnAssets"),
            "profitMargins": info.get("profitMargins"),
            "operatingMargins": info.get("operatingMargins"),
            "revenueGrowth": info.get("revenueGrowth"),
            "earningsGrowth": info.get("earningsGrowth"),
            # Ownership metrics (for GAP-008 institutional ownership)
            "heldPercentInstitutions": info.get("heldPercentInstitutions"),
            "heldPercentInsiders": info.get("heldPercentInsiders"),
        }

    def fetch_reference_payload(
        self, symbols: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        """Fetch company reference data from yfinance (see helper methods for payload building)."""
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

                payload_dict = self._build_reference_payload(symbol, info)
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
        self, symbols: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        """Fetch news articles using yfinance's symbol news feed."""
        records: list[dict[str, Any]] = []
        start_utc = start.astimezone(dt.UTC)
        end_utc = end.astimezone(dt.UTC)

        symbol_list = list(symbols) or ["__MARKET__"]

        for symbol in symbol_list:
            is_market = symbol in (None, "__MARKET__")
            target_symbol = self.MARKET_SYMBOL if is_market else symbol

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
                logger.debug(
                    "yfinance_news_empty",
                    symbol=target_symbol,
                )
                continue

            for item in news_items:
                content = item.get("content") or {}
                headline = content.get("title") or item.get("title")
                if not headline:
                    continue

                summary = (
                    content.get("summary")
                    or content.get("description")
                    or item.get("summary")
                    or item.get("description")
                )
                canonical = content.get("canonicalUrl") or item.get("canonicalUrl") or {}
                click_through = content.get("clickThroughUrl") or item.get("clickThroughUrl") or {}
                url = canonical.get("url") or click_through.get("url") or item.get("link")

                published_at = None
                publish_ts = (
                    content.get("pubDate")
                    or content.get("displayTime")
                    or item.get("providerPublishTime")
                    or item.get("published_at")
                )
                if isinstance(publish_ts, (int, float)):
                    published_at = dt.datetime.fromtimestamp(float(publish_ts), tz=dt.UTC)
                elif isinstance(publish_ts, str):
                    with contextlib.suppress(ValueError):
                        published_at = dt.datetime.fromisoformat(publish_ts.replace("Z", "+00:00"))

                if published_at and (published_at < start_utc or published_at > end_utc):
                    continue

                provider = content.get("provider") or item.get("provider") or {}
                publisher = (
                    provider.get("displayName") or provider.get("sourceId") or item.get("publisher")
                )

                thumb = content.get("thumbnail") or item.get("thumbnail") or {}
                resolutions = thumb.get("resolutions")
                image_url = None
                if isinstance(resolutions, list) and resolutions:
                    image_url = resolutions[0].get("url")
                else:
                    image_url = thumb.get("originalUrl")

                records.append(
                    {
                        "symbol": "__MARKET__" if is_market else symbol,
                        "headline": headline,
                        "url": url,
                        "summary": summary,
                        "news_source_name": publisher,
                        "author": None,
                        "image_url": image_url,
                        "published_at": published_at,
                        "raw_payload": json.dumps(item),
                        "source": "yfinance",
                    }
                )

            logger.debug(
                "yfinance_news_fetched",
                symbol=target_symbol,
                articles=len(news_items),
            )

        if not records:
            logger.info("yfinance_news_no_articles", symbols=symbol_list)
            return None

        return pl.DataFrame(records)

    # ============================================
    # GAP-004: Cash Flow Metrics
    # ============================================
    def fetch_cash_flow_data(self, symbol: str) -> dict[str, Any] | None:
        """Fetch cash flow statement data for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with cash flow metrics, or None if failed
        """
        try:
            yf_obj = yf.Ticker(symbol)
            cf = yf_obj.cashflow
            info = yf_obj.info

            if cf.empty:
                return None

            # Get most recent period
            latest = cf.iloc[:, 0]

            # Extract key metrics
            operating_cf = latest.get("Operating Cash Flow", 0) or 0
            capex = latest.get("Capital Expenditure", 0) or 0
            free_cf = operating_cf + capex  # capex is negative

            # Get market cap for FCF yield
            market_cap = info.get("marketCap", 0) or 0
            shares_outstanding = info.get("sharesOutstanding", 0) or 0
            revenue = info.get("totalRevenue", 0) or 0
            net_income = info.get("netIncomeToCommon", 0) or 0

            fcf_yield = free_cf / market_cap if market_cap > 0 else None
            fcf_per_share = free_cf / shares_outstanding if shares_outstanding > 0 else None
            cash_flow_margin = operating_cf / revenue if revenue > 0 else None
            cash_conversion = operating_cf / net_income if net_income != 0 else None

            return {
                "symbol": symbol,
                "operating_cash_flow": operating_cf,
                "capital_expenditure": capex,
                "free_cash_flow": free_cf,
                "fcf_yield": fcf_yield,
                "fcf_per_share": fcf_per_share,
                "cash_flow_margin": cash_flow_margin,
                "cash_conversion_ratio": cash_conversion,
            }

        except Exception as e:
            logger.warning(f"Failed to fetch cash flow for {symbol}: {e}")
            return None

    # ============================================
    # GAP-006: Insider Transactions
    # ============================================
    def fetch_insider_transactions(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch insider transactions for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            List of insider transaction dicts
        """
        try:
            yf_obj = yf.Ticker(symbol)
            insiders = yf_obj.insider_transactions

            if insiders is None or insiders.empty:
                return []

            transactions = []
            for _, row in insiders.iterrows():
                transactions.append({
                    "symbol": symbol,
                    "insider_name": row.get("Insider"),
                    "insider_title": row.get("Position"),
                    "transaction_type": row.get("Transaction"),
                    "transaction_date": row.get("Start Date"),
                    "shares": row.get("Shares"),
                    "value": row.get("Value"),
                    "shares_owned_after": row.get("Shares Owned After"),
                })

            logger.debug(f"Fetched {len(transactions)} insider transactions for {symbol}")
            return transactions

        except Exception as e:
            logger.warning(f"Failed to fetch insider transactions for {symbol}: {e}")
            return []

    # ============================================
    # GAP-007: Institutional Holdings
    # ============================================
    def fetch_institutional_holders(self, symbol: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Fetch institutional holders for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Tuple of (list of holder dicts, summary dict)
        """
        try:
            yf_obj = yf.Ticker(symbol)
            holders_df = yf_obj.institutional_holders
            info = yf_obj.info

            holders = []
            if holders_df is not None and not holders_df.empty:
                for _, row in holders_df.iterrows():
                    holders.append({
                        "symbol": symbol,
                        "holder_name": row.get("Holder"),
                        "shares": row.get("Shares"),
                        "value": row.get("Value"),
                        "pct_held": row.get("% Out"),
                        "report_date": row.get("Date Reported"),
                    })

            # Summary from info
            summary = {
                "symbol": symbol,
                "total_institutions": len(holders),
                "pct_held_institutions": info.get("heldPercentInstitutions"),
                "pct_held_insiders": info.get("heldPercentInsiders"),
            }

            logger.debug(f"Fetched {len(holders)} institutional holders for {symbol}")
            return holders, summary

        except Exception as e:
            logger.warning(f"Failed to fetch institutional holders for {symbol}: {e}")
            return [], {}

    # ============================================
    # GAP-011: Short Interest
    # ============================================
    def fetch_short_interest(self, symbol: str) -> dict[str, Any] | None:
        """Fetch short interest data for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with short interest metrics, or None if failed
        """
        try:
            yf_obj = yf.Ticker(symbol)
            info = yf_obj.info

            short_shares = info.get("sharesShort")
            short_ratio = info.get("shortRatio")
            short_pct_float = info.get("shortPercentOfFloat")
            shares_outstanding = info.get("sharesOutstanding")

            if not any([short_shares, short_ratio, short_pct_float]):
                return None

            short_pct_outstanding = None
            if short_shares and shares_outstanding:
                short_pct_outstanding = short_shares / shares_outstanding

            return {
                "symbol": symbol,
                "short_shares": short_shares,
                "short_ratio": short_ratio,
                "short_percent_of_float": short_pct_float,
                "short_percent_of_outstanding": short_pct_outstanding,
                "short_prior_month": info.get("sharesShortPriorMonth"),
                "short_pct_change": info.get("sharesShortPreviousMonthDate"),  # This is actually a date
            }

        except Exception as e:
            logger.warning(f"Failed to fetch short interest for {symbol}: {e}")
            return None

    # ============================================
    # Combined fundamental data fetch
    # ============================================
    def fetch_all_fundamental_data(self, symbol: str) -> dict[str, Any]:
        """Fetch all fundamental data for a symbol in one call.

        Combines cash flow, insider, institutional, and short data.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with all fundamental data
        """
        result = {
            "symbol": symbol,
            "cash_flow": self.fetch_cash_flow_data(symbol),
            "insider_transactions": self.fetch_insider_transactions(symbol),
            "short_interest": self.fetch_short_interest(symbol),
        }

        holders, summary = self.fetch_institutional_holders(symbol)
        result["institutional_holders"] = holders
        result["institutional_summary"] = summary

        return result
