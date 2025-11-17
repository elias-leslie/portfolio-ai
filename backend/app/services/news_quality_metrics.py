"""News source quality profiling metrics calculation.

This module provides functions to calculate 6 core quality metrics for news vendors:
1. Duplicate rate - % of articles that are duplicates
2. Diversity score - Uniqueness of headlines using token overlap
3. Confidence average - Average sentiment confidence from FinBERT/VADER
4. Freshness score - How recent articles are (24h=1.0, 7d=0.0)
5. User useful rate - % of articles rated as useful by user
6. Quality score - Weighted composite of above metrics

Phase 1: Foundation for intelligent news source quality monitoring and personalization.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..storage import PortfolioStorage

logger = get_logger(__name__)


class QualityWeights(BaseModel):
    """User-adjustable weights for quality score calculation."""

    duplicate_penalty: float = Field(default=0.30, ge=0.0, le=1.0)
    diversity: float = Field(default=0.25, ge=0.0, le=1.0)
    confidence: float = Field(default=0.20, ge=0.0, le=1.0)
    freshness: float = Field(default=0.15, ge=0.0, le=1.0)
    user_feedback: float = Field(default=0.10, ge=0.0, le=1.0)

    def normalize(self) -> QualityWeights:
        """Normalize weights to sum to 1.0."""
        total = (
            self.duplicate_penalty
            + self.diversity
            + self.confidence
            + self.freshness
            + self.user_feedback
        )
        if total == 0:
            return QualityWeights()  # Return defaults if all zeros

        return QualityWeights(
            duplicate_penalty=self.duplicate_penalty / total,
            diversity=self.diversity / total,
            confidence=self.confidence / total,
            freshness=self.freshness / total,
            user_feedback=self.user_feedback / total,
        )


class SourceMetrics(BaseModel):
    """Complete quality metrics for a news source/vendor."""

    vendor: str = Field(..., description="Vendor/source identifier")
    duplicate_rate: float = Field(
        ..., ge=0.0, le=1.0, description="0=no duplicates, 1=all duplicates"
    )
    diversity_score: float = Field(..., ge=0.0, le=1.0, description="0=all same, 1=all unique")
    confidence_avg: float = Field(..., ge=0.0, le=1.0, description="Average sentiment confidence")
    freshness_score: float = Field(..., ge=0.0, le=1.0, description="1=very fresh, 0=stale")
    user_useful_rate: float | None = Field(
        default=None, ge=0.0, le=1.0, description="% useful, None if no feedback"
    )
    quality_score: float = Field(..., ge=0.0, le=1.0, description="Weighted composite score")
    article_count: int = Field(..., ge=0, description="Number of articles in sample")
    sample_period_start: datetime = Field(..., description="Start of sample window")
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def calculate_duplicate_rate(
    storage: PortfolioStorage,
    vendor: str,
    window_start: datetime,
    window_end: datetime,
) -> float:
    """Calculate duplicate rate for a vendor.

    Args:
        storage: Database connection
        vendor: Vendor identifier
        window_start: Start of analysis window
        window_end: End of analysis window

    Returns:
        Float 0.0-1.0 where 0.0=no duplicates, 1.0=all duplicates
    """
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT
                COUNT(*) AS total_articles,
                COUNT(DISTINCT content_hash) AS unique_articles
            FROM news_cache
            WHERE raw_payload->'raw'->>'vendor' = %s
              AND fetched_at >= %s
              AND fetched_at < %s
            """,
            [vendor, window_start, window_end],
        ).fetchone()

    if not result or result[0] is None or result[0] == 0:
        return 0.0  # No articles = no duplicates

    total = int(result[0]) if result[0] is not None else 0
    unique = int(result[1]) if result[1] is not None else 0

    # Duplicate rate = (total - unique) / total
    # Example: 10 total, 8 unique = 2 duplicates = 0.20 duplicate rate
    duplicate_rate = (total - unique) / total
    return max(0.0, min(1.0, duplicate_rate))


def calculate_diversity_score(
    storage: PortfolioStorage,
    vendor: str,
    window_start: datetime,
    window_end: datetime,
) -> float:
    """Calculate headline diversity using token overlap.

    Args:
        storage: Database connection
        vendor: Vendor identifier
        window_start: Start of analysis window
        window_end: End of analysis window

    Returns:
        Float 0.0-1.0 where 1.0=all unique, 0.0=all same
    """
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT headline
            FROM news_cache
            WHERE raw_payload->'raw'->>'vendor' = %s
              AND fetched_at >= %s
              AND fetched_at < %s
              AND headline IS NOT NULL
            ORDER BY fetched_at DESC
            LIMIT 100
            """,
            [vendor, window_start, window_end],
        ).fetchall()

    if not result or len(result) < 2:
        return 1.0  # Too few articles = assume diverse

    headlines = [str(row[0]).lower().strip() for row in result if row[0]]
    if len(headlines) < 2:
        return 1.0

    # Token overlap approach: Calculate average pairwise similarity
    # Then diversity = 1 - similarity
    total_similarity = 0.0
    comparisons = 0

    for i in range(len(headlines)):
        for j in range(i + 1, len(headlines)):
            similarity = _token_overlap_similarity(headlines[i], headlines[j])
            total_similarity += similarity
            comparisons += 1

    if comparisons == 0:
        return 1.0

    avg_similarity = total_similarity / comparisons
    diversity = 1.0 - avg_similarity
    return max(0.0, min(1.0, diversity))


def _token_overlap_similarity(text1: str, text2: str) -> float:
    """Calculate token overlap similarity between two texts.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Float 0.0-1.0 where 1.0=identical tokens, 0.0=no overlap
    """
    # Tokenize by splitting on whitespace and removing punctuation
    tokens1 = set(_tokenize(text1))
    tokens2 = set(_tokenize(text2))

    if not tokens1 or not tokens2:
        return 0.0

    # Jaccard similarity: intersection / union
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    if union == 0:
        return 0.0

    return intersection / union


def _tokenize(text: str) -> list[str]:
    """Tokenize text by splitting on whitespace and removing punctuation.

    Args:
        text: Input text

    Returns:
        List of normalized tokens
    """
    # Remove common punctuation
    for char in ".,!?;:()[]{}\"'":
        text = text.replace(char, " ")

    # Split and filter short tokens
    tokens = [token.strip() for token in text.split() if len(token.strip()) > 2]
    return tokens


def calculate_avg_confidence(
    storage: PortfolioStorage,
    vendor: str,
    window_start: datetime,
    window_end: datetime,
) -> float:
    """Calculate average sentiment confidence for a vendor.

    Args:
        storage: Database connection
        vendor: Vendor identifier
        window_start: Start of analysis window
        window_end: End of analysis window

    Returns:
        Float 0.0-1.0 representing average confidence
    """
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT AVG(sentiment_confidence) AS avg_confidence
            FROM news_cache
            WHERE raw_payload->'raw'->>'vendor' = %s
              AND fetched_at >= %s
              AND fetched_at < %s
              AND sentiment_confidence IS NOT NULL
            """,
            [vendor, window_start, window_end],
        ).fetchone()

    if not result or result[0] is None:
        return 0.0

    avg = float(result[0])
    return max(0.0, min(1.0, avg))


def calculate_freshness_score(
    storage: PortfolioStorage,
    vendor: str,
    window_start: datetime,
    window_end: datetime,
    now: datetime | None = None,
) -> float:
    """Calculate freshness score for a vendor.

    Freshness measures how recent articles are:
    - 24h old = 1.0 (very fresh)
    - 7d old = 0.0 (stale)
    - Linear interpolation between

    Args:
        storage: Database connection
        vendor: Vendor identifier
        window_start: Start of analysis window
        window_end: End of analysis window
        now: Current time (defaults to datetime.now(UTC))

    Returns:
        Float 0.0-1.0 where 1.0=very fresh, 0.0=stale
    """
    if now is None:
        now = datetime.now(UTC)

    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT published_at
            FROM news_cache
            WHERE raw_payload->'raw'->>'vendor' = %s
              AND fetched_at >= %s
              AND fetched_at < %s
              AND published_at IS NOT NULL
            """,
            [vendor, window_start, window_end],
        ).fetchall()

    if not result:
        return 0.0

    # Calculate average age in hours
    ages: list[float] = []
    for row in result:
        published_at = row[0]
        if not isinstance(published_at, datetime):
            continue

        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)

        age_seconds = (now - published_at).total_seconds()
        age_hours = age_seconds / 3600.0
        ages.append(age_hours)

    if not ages:
        return 0.0

    avg_age_hours = sum(ages) / len(ages)

    # Normalize: 24h=1.0, 168h (7d)=0.0, linear scale
    if avg_age_hours <= 24:
        return 1.0
    if avg_age_hours >= 168:
        return 0.0

    freshness = 1.0 - ((avg_age_hours - 24) / (168 - 24))
    return max(0.0, min(1.0, freshness))


def calculate_user_useful_rate(
    storage: PortfolioStorage,
    vendor: str,
    user_id: str = "default",
) -> float | None:
    """Calculate user useful rate for a vendor.

    Args:
        storage: Database connection
        vendor: Vendor identifier
        user_id: User identifier (default: "default")

    Returns:
        Float 0.0-1.0 representing % useful, or None if no feedback
    """
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT
                SUM(CASE WHEN is_useful THEN 1 ELSE 0 END) AS useful_count,
                COUNT(*) AS total_count
            FROM user_article_feedback
            WHERE vendor = %s
              AND user_id = %s
            """,
            [vendor, user_id],
        ).fetchone()

    if not result or result[1] is None or result[1] == 0:
        return None  # No feedback yet

    useful = int(result[0] or 0) if result[0] is not None else 0
    total = int(result[1]) if result[1] is not None else 0

    if total == 0:
        return None

    useful_rate = useful / total
    return max(0.0, min(1.0, useful_rate))


def calculate_quality_score(
    metrics: SourceMetrics,
    weights: QualityWeights,
) -> float:
    """Calculate composite quality score from metrics and weights.

    Formula:
        quality = (1 - duplicate_rate) * w1 +
                  diversity_score * w2 +
                  confidence_avg * w3 +
                  freshness_score * w4 +
                  user_useful_rate * w5

    If user_useful_rate is None, redistribute its weight proportionally.

    Args:
        metrics: Source metrics
        weights: Quality weights

    Returns:
        Float 0.0-1.0 representing composite quality
    """
    # Normalize weights
    normalized = weights.normalize()

    # If no user feedback, redistribute that weight
    if metrics.user_useful_rate is None:
        total_other = (
            normalized.duplicate_penalty
            + normalized.diversity
            + normalized.confidence
            + normalized.freshness
        )
        if total_other == 0:
            return 0.0

        # Redistribute user_feedback weight proportionally
        redistribution_factor = 1.0 / total_other
        quality = (
            (1.0 - metrics.duplicate_rate) * normalized.duplicate_penalty * redistribution_factor
            + metrics.diversity_score * normalized.diversity * redistribution_factor
            + metrics.confidence_avg * normalized.confidence * redistribution_factor
            + metrics.freshness_score * normalized.freshness * redistribution_factor
        )
    else:
        quality = (
            (1.0 - metrics.duplicate_rate) * normalized.duplicate_penalty
            + metrics.diversity_score * normalized.diversity
            + metrics.confidence_avg * normalized.confidence
            + metrics.freshness_score * normalized.freshness
            + metrics.user_useful_rate * normalized.user_feedback
        )

    return max(0.0, min(1.0, quality))


def calculate_all_metrics(
    storage: PortfolioStorage,
    vendor: str,
    window_start: datetime,
    window_end: datetime,
    weights: QualityWeights | None = None,
    user_id: str = "default",
) -> SourceMetrics:
    """Calculate all quality metrics for a vendor.

    Args:
        storage: Database connection
        vendor: Vendor identifier
        window_start: Start of analysis window
        window_end: End of analysis window
        weights: Quality weights (defaults to QualityWeights())
        user_id: User identifier for feedback

    Returns:
        Complete SourceMetrics object
    """
    if weights is None:
        weights = QualityWeights()

    # Calculate all 5 base metrics
    duplicate_rate = calculate_duplicate_rate(storage, vendor, window_start, window_end)
    diversity_score = calculate_diversity_score(storage, vendor, window_start, window_end)
    confidence_avg = calculate_avg_confidence(storage, vendor, window_start, window_end)
    freshness_score = calculate_freshness_score(storage, vendor, window_start, window_end)
    user_useful_rate = calculate_user_useful_rate(storage, vendor, user_id)

    # Get article count
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT COUNT(*) FROM news_cache
            WHERE raw_payload->'raw'->>'vendor' = %s
              AND fetched_at >= %s
              AND fetched_at < %s
            """,
            [vendor, window_start, window_end],
        ).fetchone()

    article_count = int(result[0]) if result and result[0] is not None else 0

    # Create preliminary metrics object
    metrics = SourceMetrics(
        vendor=vendor,
        duplicate_rate=duplicate_rate,
        diversity_score=diversity_score,
        confidence_avg=confidence_avg,
        freshness_score=freshness_score,
        user_useful_rate=user_useful_rate,
        quality_score=0.0,  # Will be calculated next
        article_count=article_count,
        sample_period_start=window_start,
    )

    # Calculate composite quality score
    metrics.quality_score = calculate_quality_score(metrics, weights)

    return metrics


def load_quality_weights_from_preferences(
    storage: PortfolioStorage,
    user_id: str = "default",
) -> QualityWeights:
    """Load quality weights from user preferences.

    Args:
        storage: Database connection
        user_id: User identifier

    Returns:
        QualityWeights loaded from preferences, or defaults if not found
    """
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT
                source_duplicate_weight,
                source_diversity_weight,
                source_confidence_weight,
                source_freshness_weight,
                source_feedback_weight
            FROM user_preferences
            WHERE id = %s
            """,
            [user_id],
        ).fetchone()

    if not result:
        return QualityWeights()

    # Check if columns exist (they won't until migration runs)
    if result[0] is None:
        return QualityWeights()

    return QualityWeights(
        duplicate_penalty=float(result[0]) if result[0] is not None else 0.3,
        diversity=float(result[1]) if result[1] is not None else 0.25,
        confidence=float(result[2]) if result[2] is not None else 0.2,
        freshness=float(result[3]) if result[3] is not None else 0.15,
        user_feedback=float(result[4]) if result[4] is not None else 0.1,
    )
