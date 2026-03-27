"""News sentiment aggregation for symbol-level scoring (GAP-015).

Aggregates news_cache sentiment_score into a daily symbol-level score
that can be used as a dedicated scoring pillar (15-20% weight).

Based on Tetlock (2007): Positive news clusters predict outperformance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from app.logging_config import get_logger
from app.storage.types import ParameterValue

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)

# Default lookback windows
SHORT_WINDOW_DAYS = 7   # Recent news (most weighted)
MEDIUM_WINDOW_DAYS = 30  # Monthly news
LONG_WINDOW_DAYS = 90   # Quarterly news

# Minimum articles for valid score
MIN_ARTICLES_SHORT = 3
MIN_ARTICLES_MEDIUM = 5

# Sentiment queries
_SINGLE_QUERY = (
    "SELECT"
    "  COUNT(CASE WHEN published_at >= %s THEN 1 END) AS count_7d,"
    "  AVG(CASE WHEN published_at >= %s THEN sentiment_score END) AS avg_7d,"
    "  COUNT(CASE WHEN published_at >= %s THEN 1 END) AS count_30d,"
    "  AVG(CASE WHEN published_at >= %s THEN sentiment_score END) AS avg_30d"
    " FROM news_cache"
    " WHERE symbol = %s AND sentiment_score IS NOT NULL AND published_at <= %s"
)
_BATCH_QUERY_TEMPLATE = (
    "SELECT symbol,"
    "  COUNT(CASE WHEN published_at >= %s THEN 1 END) AS count_7d,"
    "  AVG(CASE WHEN published_at >= %s THEN sentiment_score END) AS avg_7d,"
    "  COUNT(CASE WHEN published_at >= %s THEN 1 END) AS count_30d,"
    "  AVG(CASE WHEN published_at >= %s THEN sentiment_score END) AS avg_30d"
    " FROM news_cache"
    " WHERE symbol IN ({placeholders})"
    "   AND sentiment_score IS NOT NULL AND published_at <= %s"
    " GROUP BY symbol"
)


@dataclass
class NewsSentimentScore:
    """Aggregated news sentiment score for a symbol."""

    symbol: str
    sentiment_score: float | None = None  # 0-100 score (50 = neutral)
    sentiment_label: str | None = None    # "bullish", "neutral", "bearish"
    article_count_7d: int = 0
    article_count_30d: int = 0
    avg_sentiment_7d: float | None = None  # Raw -1 to +1 average
    avg_sentiment_30d: float | None = None
    sentiment_trend: str | None = None    # "improving", "stable", "declining"
    confidence: float = 0.0               # 0-1 confidence based on article count
    error: str | None = None


def _sentiment_to_score(raw_sentiment: float) -> float:
    """Convert raw sentiment (-1 to +1) to 0-100 score."""
    clamped = max(-1.0, min(1.0, raw_sentiment))
    return (clamped + 1.0) * 50.0


def _score_to_label(score: float) -> str:
    """Convert score to sentiment label."""
    if score >= 60:
        return "bullish"
    if score <= 40:
        return "bearish"
    return "neutral"


def _calculate_trend(short_avg: float | None, medium_avg: float | None) -> str:
    """Determine sentiment trend direction."""
    if short_avg is None or medium_avg is None:
        return "unknown"
    delta = short_avg - medium_avg
    if delta > 0.05:
        return "improving"
    if delta < -0.05:
        return "declining"
    return "stable"


def _calculate_confidence(article_count: int) -> float:
    """Calculate confidence based on article count."""
    if article_count == 0:
        return 0.0
    if article_count < MIN_ARTICLES_SHORT:
        return 0.3
    if article_count < MIN_ARTICLES_MEDIUM:
        return 0.6
    if article_count < 20:
        return 0.8
    return 0.95


def _build_date_windows(as_of_date: date) -> tuple[datetime, datetime, datetime]:
    """Return (as_of_dt, window_7d, window_30d) for the given date."""
    as_of_dt = datetime.combine(as_of_date, datetime.max.time(), tzinfo=UTC)
    return as_of_dt, as_of_dt - timedelta(days=7), as_of_dt - timedelta(days=30)


def _weighted_avg(avg_7d: float | None, avg_30d: float | None) -> float:
    """Calculate weighted average (70% recent, 30% medium-term)."""
    if avg_7d is not None and avg_30d is not None:
        return avg_7d * 0.7 + avg_30d * 0.3
    return avg_7d if avg_7d is not None else (avg_30d if avg_30d is not None else 0.0)


def _extract_row_values(row: dict) -> tuple[int, int, float | None, float | None]:
    """Extract and coerce typed values from a query result row."""
    count_7d = int(row["count_7d"] or 0)
    count_30d = int(row["count_30d"] or 0)
    avg_7d = float(row["avg_7d"]) if row["avg_7d"] is not None else None
    avg_30d = float(row["avg_30d"]) if row["avg_30d"] is not None else None
    return count_7d, count_30d, avg_7d, avg_30d


def _build_score(
    symbol: str,
    count_7d: int,
    count_30d: int,
    avg_7d: float | None,
    avg_30d: float | None,
    insufficient_msg: str,
) -> NewsSentimentScore:
    """Build a NewsSentimentScore from extracted row values."""
    if count_7d < MIN_ARTICLES_SHORT and count_30d < MIN_ARTICLES_MEDIUM:
        return NewsSentimentScore(
            symbol=symbol,
            article_count_7d=count_7d,
            article_count_30d=count_30d,
            confidence=0.0,
            error=insufficient_msg,
        )
    score = _sentiment_to_score(_weighted_avg(avg_7d, avg_30d))
    return NewsSentimentScore(
        symbol=symbol,
        sentiment_score=round(score, 2),
        sentiment_label=_score_to_label(score),
        article_count_7d=count_7d,
        article_count_30d=count_30d,
        avg_sentiment_7d=round(avg_7d, 4) if avg_7d else None,
        avg_sentiment_30d=round(avg_30d, 4) if avg_30d else None,
        sentiment_trend=_calculate_trend(avg_7d, avg_30d),
        confidence=_calculate_confidence(count_7d + count_30d),
    )


def get_symbol_sentiment(
    storage: PortfolioStorage,
    symbol: str,
    as_of_date: date | None = None,
) -> NewsSentimentScore:
    """Get aggregated news sentiment score for a symbol.

    Combines short-term (7d) and medium-term (30d) sentiment with recency
    weighting (70% recent / 30% medium-term).  Returns NewsSentimentScore.
    """
    if as_of_date is None:
        as_of_date = date.today()
    as_of_dt, window_7d, window_30d = _build_date_windows(as_of_date)
    params = [window_7d, window_7d, window_30d, window_30d, symbol, as_of_dt]
    try:
        result = storage.query(_SINGLE_QUERY, params)
        if result.is_empty():
            return NewsSentimentScore(symbol=symbol, error="No news articles found")
        count_7d, count_30d, avg_7d, avg_30d = _extract_row_values(result.row(0, named=True))
        return _build_score(symbol, count_7d, count_30d, avg_7d, avg_30d, "Insufficient news coverage")
    except Exception as e:
        logger.error("news_sentiment_error", symbol=symbol, error=str(e), exc_info=True)
        return NewsSentimentScore(symbol=symbol, error=str(e))


def get_batch_sentiment(
    storage: PortfolioStorage,
    symbols: list[str],
    as_of_date: date | None = None,
) -> dict[str, NewsSentimentScore]:
    """Get sentiment scores for multiple symbols efficiently.

    Returns a dict mapping each symbol to its NewsSentimentScore.
    """
    if not symbols:
        return {}
    if as_of_date is None:
        as_of_date = date.today()
    as_of_dt, window_7d, window_30d = _build_date_windows(as_of_date)
    query = _BATCH_QUERY_TEMPLATE.format(placeholders=", ".join(["%s"] * len(symbols)))
    params: list[ParameterValue] = [window_7d, window_7d, window_30d, window_30d, *symbols, as_of_dt]
    try:
        result = storage.query(query, params)
        results = {s: NewsSentimentScore(symbol=s, error="No data") for s in symbols}
        for row in result.iter_rows(named=True):
            sym = row["symbol"]
            count_7d, count_30d, avg_7d, avg_30d = _extract_row_values(row)
            results[sym] = _build_score(sym, count_7d, count_30d, avg_7d, avg_30d, "Insufficient coverage")
        return results
    except Exception as e:
        logger.error("batch_sentiment_error", error=str(e), symbols_count=len(symbols), exc_info=True)
        return {s: NewsSentimentScore(symbol=s, error=str(e)) for s in symbols}
