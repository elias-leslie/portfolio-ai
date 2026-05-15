"""YFinance data parsing utilities.

Extracts and transforms raw yfinance data into standardized formats.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json

import pandas as pd
import polars as pl

from ..logging_config import get_logger

logger = get_logger(__name__)


_SESSION_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("postMarketPrice", "postMarketTime", "post_market"),
    ("preMarketPrice", "preMarketTime", "pre_market"),
    ("regularMarketPrice", "regularMarketTime", "regular"),
)


def extract_price_from_info(
    info: dict[str, object],
) -> tuple[float | None, str | None]:
    """Pick the freshest price across regular / pre-market / post-market sessions.

    Returns (price, session_label). Compares the *Time epoch fields and picks the
    most recent. Falls back to currentPrice (yfinance financialData) and finally
    previousClose when no timestamped session quote is available.
    """
    candidates: list[tuple[int, float, str]] = []
    for price_field, time_field, label in _SESSION_FIELDS:
        price = info.get(price_field)
        ts = info.get(time_field)
        if (
            isinstance(price, (int, float))
            and price > 0
            and isinstance(ts, (int, float))
            and ts > 0
        ):
            candidates.append((int(ts), float(price), label))

    if candidates:
        candidates.sort(key=lambda row: row[0], reverse=True)
        _, price, label = candidates[0]
        return price, label

    current = info.get("currentPrice")
    if isinstance(current, (int, float)) and current > 0:
        return float(current), "current_price"

    previous = info.get("previousClose")
    if isinstance(previous, (int, float)) and previous > 0:
        return float(previous), "previous_close"

    return None, None


def calculate_volatility_from_52w_range(info: dict[str, object]) -> float | None:
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


def _build_reference_metrics(info: dict[str, object]) -> dict[str, object]:
    """Extract valuation, bonus, and ownership metrics from info dict."""
    return {
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


def build_reference_payload(symbol: str, info: dict[str, object]) -> dict[str, object]:
    """Build reference payload from yfinance info dict."""
    price, price_session = extract_price_from_info(info)
    beta = info.get("beta")
    volatility = calculate_volatility_from_52w_range(info)

    base = {
        "symbol": symbol,
        "price": price,
        "price_session": price_session,
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
    }
    base.update(_build_reference_metrics(info))
    return base


def parse_ohlcv_to_polars(
    hist_df: pd.DataFrame,
    symbol: str,
    ingest_run_id: str | None = None,
) -> pl.DataFrame:
    """Convert pandas OHLCV DataFrame to Polars with standardized schema."""
    hist_df = hist_df.reset_index()

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

    if ingest_run_id:
        df = df.with_columns(pl.lit(ingest_run_id).alias("ingest_run_id"))

    return df


def _extract_news_url(item: dict[str, object], content: dict[str, object]) -> str | None:
    """Extract URL from a news item."""
    canonical: dict[str, object] = content.get("canonicalUrl") or item.get("canonicalUrl") or {}  # type: ignore[assignment]
    click_through: dict[str, object] = content.get("clickThroughUrl") or item.get("clickThroughUrl") or {}  # type: ignore[assignment]
    return canonical.get("url") or click_through.get("url") or item.get("link")  # type: ignore[return-value]


def _extract_news_published_at(
    item: dict[str, object], content: dict[str, object]
) -> dt.datetime | None:
    """Extract and parse publish timestamp from a news item."""
    publish_ts = (
        content.get("pubDate")
        or content.get("displayTime")
        or item.get("providerPublishTime")
        or item.get("published_at")
    )
    if isinstance(publish_ts, (int, float)):
        return dt.datetime.fromtimestamp(float(publish_ts), tz=dt.UTC)
    if isinstance(publish_ts, str):
        with contextlib.suppress(ValueError):
            return dt.datetime.fromisoformat(publish_ts.replace("Z", "+00:00"))
    return None


def _extract_news_publisher(item: dict[str, object], content: dict[str, object]) -> str | None:
    """Extract publisher name from a news item."""
    provider_raw = content.get("provider") or item.get("provider")
    provider = provider_raw if isinstance(provider_raw, dict) else {}
    for key in ("displayName", "sourceId"):
        value = provider.get(key)
        if isinstance(value, str) and value:
            return value
    publisher = item.get("publisher")
    return publisher if isinstance(publisher, str) and publisher else None


def _extract_news_image(item: dict[str, object], content: dict[str, object]) -> str | None:
    """Extract image URL from a news item."""
    thumb_raw = content.get("thumbnail") or item.get("thumbnail")
    thumb = thumb_raw if isinstance(thumb_raw, dict) else {}
    resolutions = thumb.get("resolutions")
    if isinstance(resolutions, list) and resolutions:
        first = resolutions[0]
        if isinstance(first, dict):
            url = first.get("url")
            if isinstance(url, str) and url:
                return url
    original_url = thumb.get("originalUrl")
    return original_url if isinstance(original_url, str) and original_url else None


def parse_news_item(
    item: dict[str, object],
    symbol: str,
    is_market: bool,
    start_utc: dt.datetime,
    end_utc: dt.datetime,
) -> dict[str, object] | None:
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
    content: dict[str, object] = item.get("content") or {}  # type: ignore[assignment]
    headline = content.get("title") or item.get("title")
    if not headline:
        return None

    summary = (
        content.get("summary")
        or content.get("description")
        or item.get("summary")
        or item.get("description")
    )
    url = _extract_news_url(item, content)
    published_at = _extract_news_published_at(item, content)

    if published_at and (published_at < start_utc or published_at > end_utc):
        return None

    return {
        "symbol": "__MARKET__" if is_market else symbol,
        "headline": headline,
        "url": url,
        "summary": summary,
        "news_source_name": _extract_news_publisher(item, content),
        "author": None,
        "image_url": _extract_news_image(item, content),
        "published_at": published_at,
        "raw_payload": json.dumps(item),
        "source": "yfinance",
    }


def parse_cash_flow_data(
    cf_df: pd.DataFrame, info: dict[str, object], symbol: str
) -> dict[str, object] | None:
    """Parse cash flow statement data."""
    if cf_df.empty:
        return None

    latest = cf_df.iloc[:, 0]

    operating_cf = latest.get("Operating Cash Flow", 0) or 0
    capex = latest.get("Capital Expenditure", 0) or 0
    free_cf = operating_cf + capex  # capex is negative

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


def parse_insider_transactions(
    insiders_df: pd.DataFrame | None, symbol: str
) -> list[dict[str, object]]:
    """Parse insider transactions DataFrame."""
    if insiders_df is None or insiders_df.empty:
        return []

    return [
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
        for _, row in insiders_df.iterrows()
    ]


def parse_institutional_holders(
    holders_df: pd.DataFrame | None, info: dict[str, object], symbol: str
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Parse institutional holders DataFrame."""
    holders: list[dict[str, object]] = []
    if holders_df is not None and not holders_df.empty:
        holders = [
            {
                "symbol": symbol,
                "holder_name": row.get("Holder"),
                "shares": row.get("Shares"),
                "value": row.get("Value"),
                "pct_held": row.get("% Out"),
                "report_date": row.get("Date Reported"),
            }
            for _, row in holders_df.iterrows()
        ]

    summary: dict[str, object] = {
        "symbol": symbol,
        "total_institutions": len(holders),
        "pct_held_institutions": info.get("heldPercentInstitutions"),
        "pct_held_insiders": info.get("heldPercentInsiders"),
    }

    return holders, summary


def parse_short_interest(info: dict[str, object], symbol: str) -> dict[str, object] | None:
    """Parse short interest data from info dict."""
    short_shares = info.get("sharesShort")
    short_ratio = info.get("shortRatio")
    short_pct_float = info.get("shortPercentOfFloat")
    shares_outstanding = info.get("sharesOutstanding")

    if not any([short_shares, short_ratio, short_pct_float]):
        return None

    short_pct_outstanding = None
    if short_shares and shares_outstanding:
        short_pct_outstanding = float(short_shares) / float(shares_outstanding)

    return {
        "symbol": symbol,
        "short_shares": short_shares,
        "short_ratio": short_ratio,
        "short_percent_of_float": short_pct_float,
        "short_percent_of_outstanding": short_pct_outstanding,
        "short_prior_month": info.get("sharesShortPriorMonth"),
        "short_pct_change": info.get("sharesShortPreviousMonthDate"),  # This is actually a date
    }
