"""Historical market data endpoints (fear-greed, news sentiment, indicators, sectors)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Query, Request

from app.api.market_responses import (
    FearGreedHistoryResponse,
    IndicatorDataPoint,
    IndicatorHistoryResponse,
    NewsSentimentHistoryResponse,
    SectorHistory,
    SectorHistoryResponse,
)
from app.api.market_transformers import (
    build_indicator_data_points,
    build_sector_history,
    sort_sectors_by_performance,
)
from app.constants import CACHE_TTL_MEDIUM, CACHE_TTL_SHORT, SECTOR_ETFS
from app.logging_config import get_logger
from app.middleware.cache import cache_response
from app.repositories.market_repository import MarketRepository
from app.sources.yfinance_source import YFinanceSource
from app.storage import get_storage
from app.utils.formatters import format_db_date

router = APIRouter()
logger = get_logger(__name__)

_state: dict[str, MarketRepository] = {}


def _get_market_repo() -> MarketRepository:
    """Lazy singleton to avoid DB connection at import time."""
    if "repo" not in _state:
        _state["repo"] = MarketRepository(get_storage())
    return _state["repo"]

# Historical data limits
MAX_HISTORICAL_DAYS = 1825  # ~5 years

# Indicator symbol to key mapping
INDICATOR_SYMBOLS: dict[str, str] = {
    "vix": "^VIX",
    "sp500": "^GSPC",
    "tnx": "^TNX",
    "dxy": "DX-Y.NYB",
}

# Sector threshold constants for validation
SECTOR_MAX_LOSS_THRESHOLD = -60.0
SECTOR_MAX_GAIN_THRESHOLD = 200.0


def _validate_sector_price_change(rows: list[tuple[Any, float]], symbol: str) -> bool:
    """Validate that sector price change is within reasonable bounds.

    Checks if the percentage change between first and last price is realistic
    (not > 60% loss or > 200% gain), which could indicate data issues.

    Args:
        rows: List of (date, close_price) tuples
        symbol: Sector ETF symbol for logging

    Returns:
        True if price change is valid (within bounds), False if unrealistic
    """
    if len(rows) < 2:
        return True

    first_close = rows[0][1]
    last_close = rows[-1][1]
    pct_change = ((last_close - first_close) / first_close) * 100

    if pct_change < SECTOR_MAX_LOSS_THRESHOLD or pct_change > SECTOR_MAX_GAIN_THRESHOLD:
        logger.error(
            "sector_history_unrealistic_change",
            symbol=symbol,
            first_close=first_close,
            last_close=last_close,
            pct_change=pct_change,
        )
        return False

    return True


# API endpoints
@router.get("/fear-greed-history", response_model=FearGreedHistoryResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_fear_greed_history(
    request: Request,
    days: int = Query(365, ge=30, le=MAX_HISTORICAL_DAYS, description="Number of days of history"),
) -> FearGreedHistoryResponse:
    """Get Fear & Greed historical data for trend charts.

    Includes put/call ratio overlay data when available.
    """
    # Use repository for data access
    rows = _get_market_repo().get_fear_greed_history_data(days)

    dates: list[str] = []
    scores: list[float] = []
    labels: list[str] = []
    put_call_ratios: list[float | None] = []
    for row in rows:
        if row[0] and row[1] is not None:
            formatted_date = format_db_date(row[0])
            if formatted_date is None:
                continue  # Skip if not a valid date type
            dates.append(formatted_date)
            scores.append(float(row[1]))
            labels.append(str(row[2]) if row[2] else "Unknown")
            # P/C ratio may be null for dates before we started collecting
            put_call_ratios.append(float(row[3]) if row[3] is not None else None)

    return FearGreedHistoryResponse(
        dates=dates, scores=scores, labels=labels, put_call_ratios=put_call_ratios
    )


@router.get("/news-sentiment-history", response_model=NewsSentimentHistoryResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_news_sentiment_history(
    request: Request,
    days: int = Query(30, ge=1, le=MAX_HISTORICAL_DAYS, description="Number of days of history"),
    granularity: str = Query(
        "daily",
        description="Data granularity: 'daily' for day-level, 'hourly' for hour-level",
    ),
) -> NewsSentimentHistoryResponse:
    """Get news sentiment historical data for trend charts.

    Returns daily or hourly aggregated sentiment scores from news_summary_log.
    Scores range from -1 (very negative) to +1 (very positive).
    """
    if granularity == "hourly":
        rows = _get_market_repo().get_news_sentiment_hourly(days)
    else:
        rows = _get_market_repo().get_news_sentiment_daily(days)

    dates: list[str] = []
    scores: list[float] = []
    positive_counts: list[int] = []
    negative_counts: list[int] = []
    article_counts: list[int] = []

    for row in rows:
        period, avg_score, pos_count, neg_count, total_count = row
        if period and avg_score is not None:
            formatted_date = format_db_date(period)
            if formatted_date is None:
                continue
            dates.append(formatted_date)
            scores.append(float(avg_score))
            positive_counts.append(int(pos_count) if pos_count else 0)
            negative_counts.append(int(neg_count) if neg_count else 0)
            article_counts.append(int(total_count) if total_count else 0)

    return NewsSentimentHistoryResponse(
        dates=dates,
        scores=scores,
        positive_counts=positive_counts,
        negative_counts=negative_counts,
        article_counts=article_counts,
    )


@router.get("/indicator-history", response_model=IndicatorHistoryResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_indicator_history(
    request: Request,
    days: int = Query(365, ge=30, le=MAX_HISTORICAL_DAYS, description="Number of days of history"),
) -> IndicatorHistoryResponse:
    """Get key indicator historical data for trend charts."""
    result_data: dict[str, list[dict[str, Any]]] = {}
    period_start = ""
    period_end = ""

    for key, symbol in INDICATOR_SYMBOLS.items():
        # Use repository for data access
        rows = _get_market_repo().get_indicator_history_data(symbol, days)

        data_points, period_start, period_end = build_indicator_data_points(
            rows, period_start, period_end
        )
        result_data[key] = data_points

    return IndicatorHistoryResponse(
        sp500=[IndicatorDataPoint(**dp) for dp in result_data.get("sp500", [])],
        vix=[IndicatorDataPoint(**dp) for dp in result_data.get("vix", [])],
        tnx=[IndicatorDataPoint(**dp) for dp in result_data.get("tnx", [])],
        dxy=[IndicatorDataPoint(**dp) for dp in result_data.get("dxy", [])],
        period_start=period_start,
        period_end=period_end,
    )


@router.get("/sector-history", response_model=SectorHistoryResponse)
@cache_response(ttl=CACHE_TTL_MEDIUM)
async def get_sector_history(
    request: Request,
    days: int = Query(365, ge=30, le=MAX_HISTORICAL_DAYS, description="Number of days of history"),
) -> SectorHistoryResponse:
    """Get sector ETF historical data for performance charts.

    Uses YFinanceSource to ensure adjusted prices (accounting for splits/dividends).
    This is necessary because DB stores prices at ingestion time which become stale
    after corporate actions like stock splits.
    """
    sectors: list[SectorHistory] = []
    period_start = ""
    period_end = ""

    # Calculate date range
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # Use YFinanceSource for data access (layer separation)
    yf_source = YFinanceSource()

    for symbol, name in SECTOR_ETFS.items():
        # Fetch fresh adjusted prices via YFinanceSource
        rows = yf_source.fetch_sector_history(symbol, start_date, end_date)

        if not rows:
            logger.warning("sector_history_no_data", symbol=symbol)
            continue

        # Skip this sector if price change is unrealistic (data quality issue)
        if not _validate_sector_price_change(rows, symbol):
            continue

        sector_history, period_start, period_end = build_sector_history(
            symbol, name, rows, period_start, period_end
        )
        sectors.append(sector_history)

    # Sort by current performance descending
    sectors = sort_sectors_by_performance(sectors)

    return SectorHistoryResponse(
        sectors=sectors,
        period_start=period_start,
        period_end=period_end,
    )
