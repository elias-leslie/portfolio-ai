"""YFinance data parsing utilities.

Extracts and transforms raw yfinance data into standardized formats.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
from typing import Any

import polars as pl

from ..logging_config import get_logger

logger = get_logger(__name__)


def extract_price_from_info(info: dict[str, Any]) -> float | None:
    """Extract price from yfinance info dict (tries multiple fields)."""
    return info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")


def calculate_volatility_from_52w_range(info: dict[str, Any]) -> float | None:
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


def build_reference_payload(symbol: str, info: dict[str, Any]) -> dict[str, Any]:
    """Build reference payload from yfinance info dict."""
    price = extract_price_from_info(info)
    beta = info.get("beta")
    volatility = calculate_volatility_from_52w_range(info)

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


def parse_ohlcv_to_polars(
    hist_df,
    symbol: str,
    ingest_run_id: str | None = None,
) -> pl.DataFrame:
    """Convert pandas OHLCV DataFrame to Polars with standardized schema."""
    # Reset index to get Date as a column
    hist_df = hist_df.reset_index()

    # Map column names to our schema
    df = pl.from_pandas(hist_df).select(
        [
            pl.col("Date").cast(pl.Date).alias("date"),
            pl.lit(symbol).alias("symbol"),
            pl.col("Open").alias("open"),
            pl.col("High").alias("high"),
            pl.col("Low").alias("low"),
            pl.col("Close").alias("close"),
            pl.col("Volume").cast(pl.Int64).alias("volume"),
            pl.lit(None).cast(pl.Float64).alias("vwap"),  # yfinance doesn't provide VWAP
            pl.lit("yfinance").alias("source"),
        ]
    )

    # Add ingest_run_id if provided
    if ingest_run_id:
        df = df.with_columns(pl.lit(ingest_run_id).alias("ingest_run_id"))

    return df


def parse_news_item(
    item: dict[str, Any],
    symbol: str,
    is_market: bool,
    start_utc: dt.datetime,
    end_utc: dt.datetime,
) -> dict[str, Any] | None:
    """Parse a single yfinance news item into standardized format.

    Args:
        item: Raw news item from yfinance
        symbol: Stock symbol
        is_market: Whether this is a market-level news item
        start_utc: Filter start time
        end_utc: Filter end time

    Returns:
        Parsed news dict or None if item should be filtered
    """
    content = item.get("content") or {}
    headline = content.get("title") or item.get("title")
    if not headline:
        return None

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
        return None

    provider = content.get("provider") or item.get("provider") or {}
    publisher = provider.get("displayName") or provider.get("sourceId") or item.get("publisher")

    thumb = content.get("thumbnail") or item.get("thumbnail") or {}
    resolutions = thumb.get("resolutions")
    image_url = None
    if isinstance(resolutions, list) and resolutions:
        image_url = resolutions[0].get("url")
    else:
        image_url = thumb.get("originalUrl")

    return {
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


def parse_cash_flow_data(cf_df, info: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    """Parse cash flow statement data."""
    if cf_df.empty:
        return None

    # Get most recent period
    latest = cf_df.iloc[:, 0]

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


def parse_insider_transactions(insiders_df, symbol: str) -> list[dict[str, Any]]:
    """Parse insider transactions DataFrame."""
    if insiders_df is None or insiders_df.empty:
        return []

    transactions = []
    for _, row in insiders_df.iterrows():
        transactions.append(
            {
                "symbol": symbol,
                "insider_name": row.get("Insider"),
                "insider_title": row.get("Position"),
                "transaction_type": row.get("Transaction"),
                "transaction_date": row.get("Start Date"),
                "shares": row.get("Shares"),
                "value": row.get("Value"),
                "shares_owned_after": row.get("Shares Owned After"),
            }
        )

    return transactions


def parse_institutional_holders(
    holders_df, info: dict[str, Any], symbol: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parse institutional holders DataFrame."""
    holders = []
    if holders_df is not None and not holders_df.empty:
        for _, row in holders_df.iterrows():
            holders.append(
                {
                    "symbol": symbol,
                    "holder_name": row.get("Holder"),
                    "shares": row.get("Shares"),
                    "value": row.get("Value"),
                    "pct_held": row.get("% Out"),
                    "report_date": row.get("Date Reported"),
                }
            )

    # Summary from info
    summary = {
        "symbol": symbol,
        "total_institutions": len(holders),
        "pct_held_institutions": info.get("heldPercentInstitutions"),
        "pct_held_insiders": info.get("heldPercentInsiders"),
    }

    return holders, summary


def parse_short_interest(info: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    """Parse short interest data from info dict."""
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
