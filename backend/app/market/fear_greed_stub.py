"""Fear & Greed Index service.

Queries the fear_greed_daily table for the latest Fear & Greed Index score.
The score is computed by scheduled workflows and stored in the database.

Uses Redis caching since F&G updates only once daily at 03:00 UTC.

See ARCHITECTURE.md lines 475-671 for complete specification.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Literal

import redis

from app.config import REDIS_URL
from app.logging_config import get_logger
from app.storage import get_storage

logger = get_logger(__name__)

_redis_client: redis.Redis[str] | None = None  # redis.Redis with decode_responses=True

_CACHE_KEY = "fear_greed:latest"
_CACHE_TTL = 1800  # 30 minutes (reduced from 1 hour for fresher data)
_CACHE_SCHEMA_VERSION = 2
_MARKET_CLOSE_UTC = dt.time(21, 0, 0)

FearGreedDict = dict[str, int | float | str | bool | None]


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
        date: str | None = None,
    ):
        self.score = score
        self.label = label
        self.score_change = score_change
        self.signal_count = signal_count
        self.is_stale = is_stale
        self.age_days = age_days
        self.trend = trend
        self.trend_change = trend_change
        self.date = date or dt.datetime.now(dt.UTC).isoformat()

    def to_dict(self) -> FearGreedDict:
        """Serialize to dictionary for caching."""
        return {
            "schema_version": _CACHE_SCHEMA_VERSION,
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
    def from_dict(cls, data: FearGreedDict) -> FearGreedReading:
        """Deserialize from dictionary."""
        if data.get("schema_version") != _CACHE_SCHEMA_VERSION:
            raise ValueError("Invalid Fear & Greed cache schema version")
        score = data["score"]
        label = data["label"]
        if not isinstance(score, int):
            raise ValueError(f"Invalid score type in cache: {type(score)}")
        if not isinstance(label, str):
            raise ValueError(f"Invalid label type in cache: {type(label)}")
        score_change = data.get("score_change")
        signal_count = data.get("signal_count", 4)
        is_stale = data.get("is_stale", False)
        age_days = data.get("age_days", 0)
        trend_raw = data.get("trend")
        trend_change = data.get("trend_change")
        date_value = data.get("date")
        trend: Literal["up", "down", "flat"] | None = None
        if trend_raw in ("up", "down", "flat"):
            trend = trend_raw  # type: ignore[assignment]
        return cls(
            score=score,
            label=label,
            score_change=float(score_change) if score_change is not None else None,
            signal_count=int(signal_count) if signal_count is not None else 4,
            is_stale=bool(is_stale),
            age_days=int(age_days) if age_days is not None else 0,
            trend=trend,
            trend_change=int(trend_change) if trend_change is not None else None,
            date=str(date_value) if date_value else None,
        )


def _date_to_market_close_iso(as_of_date: dt.date) -> str:
    return dt.datetime.combine(as_of_date, _MARKET_CLOSE_UTC, tzinfo=dt.UTC).isoformat()


def invalidate_fear_greed_redis_cache() -> bool:
    """Invalidate Fear & Greed Redis cache.

    Call this after calculate_fear_greed task writes new data.

    Returns:
        True if cache was invalidated, False if Redis unavailable
    """
    try:
        redis_client = _get_redis_client()
        redis_client.delete(_CACHE_KEY)
        return True
    except Exception as e:
        logger.debug("redis_cache_invalidation_failed", error=str(e))
        return False


def _read_from_redis_cache() -> FearGreedReading | None:
    """Read Fear & Greed reading from Redis cache. Returns None on miss or error."""
    try:
        redis_client = _get_redis_client()
        cached = redis_client.get(_CACHE_KEY)
        if not cached:
            return None
        data: FearGreedDict = json.loads(cached)
        return FearGreedReading.from_dict(data)
    except Exception as e:
        logger.debug("redis_cache_read_failed", error=str(e))
        return None


def _write_to_redis_cache(reading: FearGreedReading) -> None:
    """Write Fear & Greed reading to Redis cache. Silently ignores errors."""
    try:
        redis_client = _get_redis_client()
        redis_client.setex(_CACHE_KEY, _CACHE_TTL, json.dumps(reading.to_dict()))
    except Exception as e:
        logger.debug("redis_cache_write_failed", error=str(e))


def _calculate_trend(
    conn: object,
    as_of_date: dt.date,
    current_score: int,
) -> tuple[Literal["up", "down", "flat"] | None, int | None]:
    """Calculate 7-day trend by querying score from 7 days ago.

    Returns:
        Tuple of (trend direction, trend_change points) or (None, None) on error.
    """
    try:
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
        if not row_7d or row_7d[0] is None:
            return None, None
        score_7d_ago = int(row_7d[0])
        trend_change = current_score - score_7d_ago
        if trend_change > 5:
            return "up", trend_change
        if trend_change < -5:
            return "down", trend_change
        return "flat", trend_change
    except Exception as e:
        logger.debug("fear_greed_trend_calc_failed", error=str(e))
        return None, None


def _build_reading_from_row(conn: object, row: object) -> FearGreedReading:
    """Build a FearGreedReading from a database row.

    Args:
        conn: Active database connection for the trend query.
        row:  Result row from fear_greed_daily (score, label, score_change,
              signal_count, as_of_date).

    Returns:
        FearGreedReading populated from the row.

    Raises:
        ValueError: If row contains unexpected types.
    """
    if not isinstance(row[0], (int, float)):  # type: ignore[index]
        raise ValueError(f"Invalid score type: {type(row[0])}")  # type: ignore[index]
    if not isinstance(row[1], str):  # type: ignore[index]
        raise ValueError(f"Invalid label type: {type(row[1])}")  # type: ignore[index]
    if not isinstance(row[4], dt.date):  # type: ignore[index]
        raise ValueError(f"Invalid as_of_date type: {type(row[4])}")  # type: ignore[index]

    current_score = int(row[0])  # type: ignore[index]
    as_of_date: dt.date = row[4]  # type: ignore[index]
    today = dt.date.today()
    age_days = (today - as_of_date).days
    is_stale = age_days > 2

    trend, trend_change = _calculate_trend(conn, as_of_date, current_score)

    return FearGreedReading(
        score=current_score,
        label=row[1],  # type: ignore[index]
        score_change=float(row[2]) if row[2] is not None else 0.0,  # type: ignore[index]
        signal_count=int(row[3]) if row[3] is not None else 4,  # type: ignore[index]
        is_stale=is_stale,
        age_days=age_days,
        trend=trend,
        trend_change=trend_change,
        date=_date_to_market_close_iso(as_of_date),
    )


def _neutral_fallback() -> FearGreedReading:
    """Return a neutral fallback reading when no database data is available."""
    return FearGreedReading(
        score=50,
        label="Neutral",
        score_change=0.0,
        signal_count=4,
        is_stale=True,
        age_days=999,  # Large number to indicate no data
    )


def get_fear_greed_score() -> FearGreedReading:
    """Get current Fear & Greed Index score from database with Redis caching.

    Queries the fear_greed_daily table for the most recent score.
    Falls back to neutral (50) if no data is available.

    Caching: Uses Redis with 30-minute TTL (reduced from 1hr for fresher data).

    Data is considered stale if >2 days old (trading days, not calendar days).

    Returns:
        FearGreedReading with score, label, staleness info, and metadata
    """
    cached = _read_from_redis_cache()
    if cached is not None:
        return cached

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
            if not row:
                return _neutral_fallback()

            reading = _build_reading_from_row(conn, row)
            _write_to_redis_cache(reading)
            return reading
    except Exception as e:
        logger.warning("fear_greed_db_query_failed", error=str(e))

    return _neutral_fallback()
