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

from datetime import datetime

from ..logging_config import get_logger
from ..storage import PortfolioStorage
from ._news_quality_helpers import _token_overlap_similarity, _tokenize
from ._news_quality_queries import (
    calculate_avg_confidence,
    calculate_duplicate_rate,
    calculate_freshness_score,
    calculate_user_useful_rate,
    load_quality_weights_from_preferences,
)
from .news_quality_models import QualityWeights, SourceMetrics

logger = get_logger(__name__)

__all__ = [
    "QualityWeights",
    "SourceMetrics",
    "_token_overlap_similarity",
    "_tokenize",
    "calculate_all_metrics",
    "calculate_avg_confidence",
    "calculate_diversity_score",
    "calculate_duplicate_rate",
    "calculate_freshness_score",
    "calculate_quality_score",
    "calculate_user_useful_rate",
    "load_quality_weights_from_preferences",
]


def _compute_avg_pairwise_similarity(headlines: list[str]) -> float:
    """Return average pairwise Jaccard similarity across all headline pairs."""
    total_similarity = 0.0
    comparisons = 0
    for i, headline_a in enumerate(headlines):
        for headline_b in headlines[i + 1:]:
            total_similarity += _token_overlap_similarity(headline_a, headline_b)
            comparisons += 1
    if comparisons == 0:
        return 0.0
    return total_similarity / comparisons


def calculate_diversity_score(
    storage: PortfolioStorage,
    vendor: str,
    window_start: datetime,
    window_end: datetime,
) -> float:
    """Calculate headline diversity using token overlap.

    Returns:
        Float 0.0-1.0 where 1.0=all unique, 0.0=all same.
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
        return 1.0

    headlines = [str(row[0]).lower().strip() for row in result if row[0]]
    if len(headlines) < 2:
        return 1.0

    avg_similarity = _compute_avg_pairwise_similarity(headlines)
    return max(0.0, min(1.0, 1.0 - avg_similarity))


def _quality_without_feedback(metrics: SourceMetrics, normalized: QualityWeights) -> float:
    """Compute quality score when user_useful_rate is None (redistribute weight)."""
    total_other = (
        normalized.duplicate_penalty
        + normalized.diversity
        + normalized.confidence
        + normalized.freshness
    )
    if total_other == 0:
        return 0.0
    factor = 1.0 / total_other
    return (
        (1.0 - metrics.duplicate_rate) * normalized.duplicate_penalty * factor
        + metrics.diversity_score * normalized.diversity * factor
        + metrics.confidence_avg * normalized.confidence * factor
        + metrics.freshness_score * normalized.freshness * factor
    )


def _quality_with_feedback(metrics: SourceMetrics, normalized: QualityWeights) -> float:
    """Compute quality score when user_useful_rate is available."""
    return (
        (1.0 - metrics.duplicate_rate) * normalized.duplicate_penalty
        + metrics.diversity_score * normalized.diversity
        + metrics.confidence_avg * normalized.confidence
        + metrics.freshness_score * normalized.freshness
        + (metrics.user_useful_rate or 0.0) * normalized.user_feedback
    )


def calculate_quality_score(
    metrics: SourceMetrics,
    weights: QualityWeights,
) -> float:
    """Calculate composite quality score from metrics and weights.

    If user_useful_rate is None, its weight is redistributed proportionally.

    Returns:
        Float 0.0-1.0 representing composite quality.
    """
    normalized = weights.normalize()
    if metrics.user_useful_rate is None:
        quality = _quality_without_feedback(metrics, normalized)
    else:
        quality = _quality_with_feedback(metrics, normalized)
    return max(0.0, min(1.0, quality))


def _fetch_article_count(
    storage: PortfolioStorage,
    vendor: str,
    window_start: datetime,
    window_end: datetime,
) -> int:
    """Return article count for a vendor within the given window."""
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
    return int(result[0]) if result and result[0] is not None else 0


def calculate_all_metrics(
    storage: PortfolioStorage,
    vendor: str,
    window_start: datetime,
    window_end: datetime,
    weights: QualityWeights | None = None,
    user_id: str = "default",
) -> SourceMetrics:
    """Calculate all quality metrics for a vendor.

    Returns:
        Complete SourceMetrics object with composite quality score.
    """
    if weights is None:
        weights = QualityWeights()

    duplicate_rate = calculate_duplicate_rate(storage, vendor, window_start, window_end)
    diversity_score = calculate_diversity_score(storage, vendor, window_start, window_end)
    confidence_avg = calculate_avg_confidence(storage, vendor, window_start, window_end)
    freshness_score = calculate_freshness_score(storage, vendor, window_start, window_end)
    user_useful_rate = calculate_user_useful_rate(storage, vendor, user_id)
    article_count = _fetch_article_count(storage, vendor, window_start, window_end)

    metrics = SourceMetrics(
        vendor=vendor,
        duplicate_rate=duplicate_rate,
        diversity_score=diversity_score,
        confidence_avg=confidence_avg,
        freshness_score=freshness_score,
        user_useful_rate=user_useful_rate,
        quality_score=0.0,
        article_count=article_count,
        sample_period_start=window_start,
    )
    metrics.quality_score = calculate_quality_score(metrics, weights)
    return metrics
