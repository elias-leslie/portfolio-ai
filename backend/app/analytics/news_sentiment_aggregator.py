"""News sentiment aggregation for symbol-level scoring (GAP-015).

Aggregates news_cache sentiment_score into a daily symbol-level score
that can be used as a dedicated scoring pillar (15-20% weight).

Based on Tetlock (2007): Positive news clusters predict outperformance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)

# Default lookback windows
SHORT_WINDOW_DAYS = 7  # Recent news (most weighted)
MEDIUM_WINDOW_DAYS = 30  # Monthly news
LONG_WINDOW_DAYS = 90  # Quarterly news

# Minimum articles for valid score
MIN_ARTICLES_SHORT = 3
MIN_ARTICLES_MEDIUM = 5


@dataclass
class NewsSentimentScore:
    """Aggregated news sentiment score for a symbol."""

    symbol: str
    sentiment_score: float | None = None  # 0-100 score (50 = neutral)
    sentiment_label: str | None = None  # "bullish", "neutral", "bearish"
    article_count_7d: int = 0
    article_count_30d: int = 0
    avg_sentiment_7d: float | None = None  # Raw -1 to +1 average
    avg_sentiment_30d: float | None = None
    sentiment_trend: str | None = None  # "improving", "stable", "declining"
    confidence: float = 0.0  # 0-1 confidence based on article count
    error: str | None = None


def _sentiment_to_score(raw_sentiment: float) -> float:
    """Convert raw sentiment (-1 to +1) to 0-100 score.

    -1.0 -> 0 (very bearish)
     0.0 -> 50 (neutral)
    +1.0 -> 100 (very bullish)
    """
    clamped = max(-1.0, min(1.0, raw_sentiment))
    return (clamped + 1.0) * 50.0


def _score_to_label(score: float) -> str:
    """Convert score to sentiment label."""
    if score >= 60:
        return "bullish"
    if score <= 40:
        return "bearish"
    return "neutral"


def _calculate_trend(
    short_avg: float | None,
    medium_avg: float | None,
) -> str:
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
    """Calculate confidence based on article count.

    More articles = higher confidence in the sentiment signal.
    """
    if article_count == 0:
        return 0.0
    if article_count < MIN_ARTICLES_SHORT:
        return 0.3
    if article_count < MIN_ARTICLES_MEDIUM:
        return 0.6
    if article_count < 20:
        return 0.8
    return 0.95


def get_symbol_sentiment(
    storage: PortfolioStorage,
    symbol: str,
    as_of_date: date | None = None,
) -> NewsSentimentScore:
    """Get aggregated news sentiment score for a symbol.

    Combines short-term (7d) and medium-term (30d) sentiment with
    recency weighting. More recent articles have higher weight.

    Args:
        storage: Database storage instance
        symbol: Stock symbol
        as_of_date: Date to calculate sentiment for (default: today)

    Returns:
        NewsSentimentScore with aggregated sentiment
    """
    if as_of_date is None:
        as_of_date = date.today()

    # Query sentiment data for different windows
    query = """
        SELECT
            -- 7-day window (most recent)
            COUNT(CASE WHEN published_at >= %s - INTERVAL '7 days' THEN 1 END) as count_7d,
            AVG(CASE WHEN published_at >= %s - INTERVAL '7 days' THEN sentiment_score END) as avg_7d,

            -- 30-day window
            COUNT(CASE WHEN published_at >= %s - INTERVAL '30 days' THEN 1 END) as count_30d,
            AVG(CASE WHEN published_at >= %s - INTERVAL '30 days' THEN sentiment_score END) as avg_30d

        FROM news_cache
        WHERE symbol = %s
          AND sentiment_score IS NOT NULL
          AND published_at <= %s
    """

    try:
        result = storage.query(
            query,
            [
                as_of_date.isoformat(),
                as_of_date.isoformat(),
                as_of_date.isoformat(),
                as_of_date.isoformat(),
                symbol,
                as_of_date.isoformat(),
            ],
        )

        if result.is_empty():
            return NewsSentimentScore(
                symbol=symbol,
                error="No news articles found",
            )

        row = result.row(0, named=True)

        count_7d = int(row["count_7d"] or 0)
        count_30d = int(row["count_30d"] or 0)
        avg_7d = float(row["avg_7d"]) if row["avg_7d"] is not None else None
        avg_30d = float(row["avg_30d"]) if row["avg_30d"] is not None else None

        # Not enough data
        if count_7d < MIN_ARTICLES_SHORT and count_30d < MIN_ARTICLES_MEDIUM:
            return NewsSentimentScore(
                symbol=symbol,
                article_count_7d=count_7d,
                article_count_30d=count_30d,
                confidence=0.0,
                error="Insufficient news coverage",
            )

        # Calculate weighted average (70% recent, 30% medium-term)
        if avg_7d is not None and avg_30d is not None:
            weighted_avg = avg_7d * 0.7 + avg_30d * 0.3
        elif avg_7d is not None:
            weighted_avg = avg_7d
        elif avg_30d is not None:
            weighted_avg = avg_30d
        else:
            weighted_avg = 0.0

        score = _sentiment_to_score(weighted_avg)
        label = _score_to_label(score)
        trend = _calculate_trend(avg_7d, avg_30d)
        confidence = _calculate_confidence(count_7d + count_30d)

        return NewsSentimentScore(
            symbol=symbol,
            sentiment_score=round(score, 2),
            sentiment_label=label,
            article_count_7d=count_7d,
            article_count_30d=count_30d,
            avg_sentiment_7d=round(avg_7d, 4) if avg_7d else None,
            avg_sentiment_30d=round(avg_30d, 4) if avg_30d else None,
            sentiment_trend=trend,
            confidence=confidence,
        )

    except Exception as e:
        logger.error("news_sentiment_error", symbol=symbol, error=str(e))
        return NewsSentimentScore(
            symbol=symbol,
            error=str(e),
        )


def get_batch_sentiment(
    storage: PortfolioStorage,
    symbols: list[str],
    as_of_date: date | None = None,
) -> dict[str, NewsSentimentScore]:
    """Get sentiment scores for multiple symbols efficiently.

    Args:
        storage: Database storage instance
        symbols: List of stock symbols
        as_of_date: Date to calculate sentiment for

    Returns:
        Dictionary mapping symbol to NewsSentimentScore
    """
    if not symbols:
        return {}

    if as_of_date is None:
        as_of_date = date.today()

    # Batch query for efficiency
    placeholders = ", ".join(["%s"] * len(symbols))
    query = f"""
        SELECT
            symbol,
            COUNT(CASE WHEN published_at >= %s - INTERVAL '7 days' THEN 1 END) as count_7d,
            AVG(CASE WHEN published_at >= %s - INTERVAL '7 days' THEN sentiment_score END) as avg_7d,
            COUNT(CASE WHEN published_at >= %s - INTERVAL '30 days' THEN 1 END) as count_30d,
            AVG(CASE WHEN published_at >= %s - INTERVAL '30 days' THEN sentiment_score END) as avg_30d
        FROM news_cache
        WHERE symbol IN ({placeholders})
          AND sentiment_score IS NOT NULL
          AND published_at <= %s
        GROUP BY symbol
    """

    params = [as_of_date, as_of_date, as_of_date, as_of_date, *symbols, as_of_date]

    try:
        result = storage.query(query, params)

        # Initialize results for all symbols
        results = {s: NewsSentimentScore(symbol=s, error="No data") for s in symbols}

        for row in result.iter_rows(named=True):
            symbol = row["symbol"]
            count_7d = int(row["count_7d"] or 0)
            count_30d = int(row["count_30d"] or 0)
            avg_7d = float(row["avg_7d"]) if row["avg_7d"] is not None else None
            avg_30d = float(row["avg_30d"]) if row["avg_30d"] is not None else None

            if count_7d < MIN_ARTICLES_SHORT and count_30d < MIN_ARTICLES_MEDIUM:
                results[symbol] = NewsSentimentScore(
                    symbol=symbol,
                    article_count_7d=count_7d,
                    article_count_30d=count_30d,
                    confidence=0.0,
                    error="Insufficient coverage",
                )
                continue

            # Weighted average
            if avg_7d is not None and avg_30d is not None:
                weighted_avg = avg_7d * 0.7 + avg_30d * 0.3
            elif avg_7d is not None:
                weighted_avg = avg_7d
            elif avg_30d is not None:
                weighted_avg = avg_30d
            else:
                weighted_avg = 0.0

            score = _sentiment_to_score(weighted_avg)

            results[symbol] = NewsSentimentScore(
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

        return results

    except Exception as e:
        logger.error("batch_sentiment_error", error=str(e))
        return {s: NewsSentimentScore(symbol=s, error=str(e)) for s in symbols}
