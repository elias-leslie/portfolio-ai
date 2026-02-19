"""Database query functions for news quality metrics."""

from __future__ import annotations

from datetime import UTC, datetime

from ..storage import PortfolioStorage
from .news_quality_models import QualityWeights


def calculate_duplicate_rate(
    storage: PortfolioStorage,
    vendor: str,
    window_start: datetime,
    window_end: datetime,
) -> float:
    """Return duplicate rate (0.0=none, 1.0=all duplicates) for a vendor window."""
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
        return 0.0

    total = int(result[0])
    unique = int(result[1]) if result[1] is not None else 0
    return max(0.0, min(1.0, (total - unique) / total))


def calculate_avg_confidence(
    storage: PortfolioStorage,
    vendor: str,
    window_start: datetime,
    window_end: datetime,
) -> float:
    """Return average sentiment confidence (0.0-1.0) for a vendor window."""
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
    return max(0.0, min(1.0, float(result[0])))


def _compute_freshness(ages: list[float]) -> float:
    """Compute freshness score from list of article ages in hours."""
    if not ages:
        return 0.0
    avg_age_hours = sum(ages) / len(ages)
    if avg_age_hours <= 24:
        return 1.0
    if avg_age_hours >= 168:
        return 0.0
    return max(0.0, min(1.0, 1.0 - ((avg_age_hours - 24) / (168 - 24))))


def calculate_freshness_score(
    storage: PortfolioStorage,
    vendor: str,
    window_start: datetime,
    window_end: datetime,
    now: datetime | None = None,
) -> float:
    """Return freshness score (1.0=very fresh <24h, 0.0=stale >7d) for a vendor window."""
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

    ages: list[float] = []
    for row in result:
        published_at = row[0]
        if not isinstance(published_at, datetime):
            continue
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)
        age_hours = (now - published_at).total_seconds() / 3600.0
        ages.append(age_hours)

    return _compute_freshness(ages)


def calculate_user_useful_rate(
    storage: PortfolioStorage,
    vendor: str,
    user_id: str = "default",
) -> float | None:
    """Return % of articles rated useful (0.0-1.0), or None if no feedback."""
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
        return None

    useful = int(result[0] or 0) if result[0] is not None else 0
    total = int(result[1])
    if total == 0:
        return None
    return max(0.0, min(1.0, useful / total))


def load_quality_weights_from_preferences(
    storage: PortfolioStorage,
    user_id: str = "default",
) -> QualityWeights:
    """Load quality weights from user preferences, returning defaults if not found."""
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

    if not result or result[0] is None:
        return QualityWeights()

    return QualityWeights(
        duplicate_penalty=float(result[0]) if result[0] is not None else 0.3,
        diversity=float(result[1]) if result[1] is not None else 0.25,
        confidence=float(result[2]) if result[2] is not None else 0.2,
        freshness=float(result[3]) if result[3] is not None else 0.15,
        user_feedback=float(result[4]) if result[4] is not None else 0.1,
    )
