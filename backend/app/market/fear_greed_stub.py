"""Fear & Greed Index service.

Queries the fear_greed_daily table for the latest Fear & Greed Index score.
The score is computed by Celery tasks and stored in the database.

Uses Redis caching since F&G updates only once daily at 03:00 UTC.

See ARCHITECTURE.md lines 475-671 for complete specification.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from typing import Any, Literal

import redis

from app.storage import get_storage

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
_redis_client: redis.Redis[str] | None = None  # redis.Redis with decode_responses=True


def _get_redis_client() -> redis.Redis[str]:
    """Get or create Redis client for caching."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


class FearGreedReading:
    """Fear & Greed Index reading with staleness tracking and 7-day trend."""

    def __init__(
        self,
        score: int,
        label: str,
        score_change: float | None = None,
        signal_count: int = 4,
        is_stale: bool = False,
        age_days: int = 0,
        trend: Literal["up", "down", "flat"] | None = None,
        trend_change: int | None = None,
    ):
        self.score = score
        self.label = label
        self.score_change = score_change
        self.signal_count = signal_count
        self.is_stale = is_stale
        self.age_days = age_days
        self.trend = trend
        self.trend_change = trend_change
        self.date = dt.datetime.now(dt.UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for caching."""
        return {
            "score": self.score,
            "label": self.label,
            "score_change": self.score_change,
            "signal_count": self.signal_count,
            "is_stale": self.is_stale,
            "age_days": self.age_days,
            "trend": self.trend,
            "trend_change": self.trend_change,
            "date": self.date,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FearGreedReading:
        """Deserialize from dictionary."""
        return cls(
            score=data["score"],
            label=data["label"],
            score_change=data.get("score_change"),
            signal_count=data.get("signal_count", 4),
            is_stale=data.get("is_stale", False),
            age_days=data.get("age_days", 0),
            trend=data.get("trend"),
            trend_change=data.get("trend_change"),
        )


def invalidate_fear_greed_redis_cache() -> bool:
    """Invalidate Fear & Greed Redis cache.

    Call this after calculate_fear_greed task writes new data.

    Returns:
        True if cache was invalidated, False if Redis unavailable
    """
    try:
        redis_client = _get_redis_client()
        redis_client.delete("fear_greed:latest")
        return True
    except Exception:
        return False


def get_fear_greed_score() -> FearGreedReading:
    """Get current Fear & Greed Index score from database with Redis caching.

    Queries the fear_greed_daily table for the most recent score.
    Falls back to neutral (50) if no data is available.

    Caching: Uses Redis with 30-minute TTL (reduced from 1hr for fresher data).

    Data is considered stale if >2 days old (trading days, not calendar days).

    Returns:
        FearGreedReading with score, label, staleness info, and metadata
    """
    cache_key = "fear_greed:latest"
    cache_ttl = 1800  # 30 minutes (reduced from 1 hour for fresher data)

    # Try Redis cache first
    try:
        redis_client = _get_redis_client()
        cached = redis_client.get(cache_key)
        if cached:
            data = json.loads(cached)
            return FearGreedReading.from_dict(data)
    except Exception:
        # If Redis fails, fall through to database query
        pass

    storage = get_storage()

    try:
        with storage.connection() as conn:
            result = conn.execute(
                """
                SELECT score, label, score_change, signal_count, as_of_date
                FROM fear_greed_daily
                ORDER BY as_of_date DESC
                LIMIT 1
                """
            )
            row = result.fetchone()

            if row:
                # Type narrowing for current_score
                if not isinstance(row[0], (int, float)):
                    raise ValueError(f"Invalid score type: {type(row[0])}")
                current_score = int(row[0])

                # Type narrowing for as_of_date
                if not isinstance(row[4], dt.date):
                    raise ValueError(f"Invalid as_of_date type: {type(row[4])}")
                as_of_date = row[4]

                # Calculate age in days
                today = dt.date.today()
                age_days = (today - as_of_date).days

                # Flag as stale if >2 days old
                is_stale = age_days > 2

                # Calculate 7-day trend
                trend: Literal["up", "down", "flat"] | None = None
                trend_change: int | None = None
                try:
                    # Get score from 7 days ago
                    result_7d = conn.execute(
                        """
                        SELECT score
                        FROM fear_greed_daily
                        WHERE as_of_date <= %s
                        ORDER BY as_of_date DESC
                        LIMIT 1 OFFSET 7
                        """,
                        (as_of_date,),
                    )
                    row_7d = result_7d.fetchone()
                    if row_7d and row_7d[0] is not None:
                        score_7d_ago = int(row_7d[0])
                        trend_change = current_score - score_7d_ago

                        # Determine trend: >5 points = up, <-5 points = down, else flat
                        if trend_change > 5:
                            trend = "up"
                        elif trend_change < -5:
                            trend = "down"
                        else:
                            trend = "flat"
                except Exception:
                    # If trend calculation fails, just skip it
                    pass

                # Type narrowing for label
                if not isinstance(row[1], str):
                    raise ValueError(f"Invalid label type: {type(row[1])}")

                reading = FearGreedReading(
                    score=current_score,
                    label=row[1],
                    score_change=float(row[2]) if row[2] is not None else 0.0,
                    signal_count=int(row[3]) if row[3] is not None else 4,
                    is_stale=is_stale,
                    age_days=age_days,
                    trend=trend,
                    trend_change=trend_change,
                )

                # Cache the result
                try:
                    redis_client = _get_redis_client()
                    redis_client.setex(cache_key, cache_ttl, json.dumps(reading.to_dict()))
                except Exception:
                    # If caching fails, continue anyway
                    pass

                return reading
    except Exception:
        # Fall through to default if query fails
        pass

    # Fallback: Return neutral score if no data available
    # Mark as stale since we have no real data
    return FearGreedReading(
        score=50,
        label="Neutral",
        score_change=0.0,
        signal_count=4,
        is_stale=True,
        age_days=999,  # Large number to indicate no data
    )
