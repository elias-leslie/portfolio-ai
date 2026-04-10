"""Health monitoring and metrics for news pipeline."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

from ..logging_config import get_logger
from .news_types import (
    ArticleMixMetricsDict,
    FallbackMetricsDict,
    NewsPipelineHealthDict,
    VendorHealthStatusDict,
    VendorStatsDict,
)

if TYPE_CHECKING:
    from ..storage import PortfolioStorage
    from .news_vendor_manager import NewsVendorManager

logger = get_logger(__name__)


class NewsHealthMetrics:
    """Handles health metrics collection and reporting for news pipeline."""

    def __init__(
        self,
        storage: PortfolioStorage,
        vendor_manager: NewsVendorManager,
        ttl: timedelta,
    ) -> None:
        self.storage = storage
        self.vendor_manager = vendor_manager
        self.ttl = ttl

    @staticmethod
    def to_iso(dt: datetime | None) -> str | None:
        """Convert datetime to ISO 8601 string with Z suffix."""
        if not dt:
            return None
        return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")

    @staticmethod
    def latest_timestamp(*values: object) -> datetime | None:
        """Return the newest timezone-aware datetime from a candidate list."""
        candidates: list[datetime] = []
        for value in values:
            if not isinstance(value, datetime):
                continue
            candidates.append(value if value.tzinfo else value.replace(tzinfo=UTC))
        if not candidates:
            return None
        return max(candidates)

    @staticmethod
    def format_duration_hours(hours: float) -> str:
        """Format durations compactly for status summaries."""
        if hours >= 48:
            return f"{hours / 24:.0f}d"
        if hours >= 24:
            return f"{hours / 24:.1f}d"
        if hours >= 1:
            if hours.is_integer():
                return f"{int(hours)}h"
            return f"{hours:.1f}h"
        return f"{round(hours * 60)}m"

    @staticmethod
    def build_pipeline_health(
        *,
        now: datetime,
        ttl: timedelta,
        headlines_24h: int,
        fallback_headlines_24h: int,
        market_last_refreshed_at: datetime | None,
        watchlist_last_refreshed_at: datetime | None,
    ) -> NewsPipelineHealthDict:
        """Derive user-facing news health from freshness and article counts."""
        latest_refresh = NewsHealthMetrics.latest_timestamp(
            market_last_refreshed_at,
            watchlist_last_refreshed_at,
        )
        ttl_hours = ttl.total_seconds() / 3600.0
        age_hours = (
            (now - latest_refresh).total_seconds() / 3600.0
            if latest_refresh is not None
            else None
        )
        ttl_label = NewsHealthMetrics.format_duration_hours(ttl_hours)
        freshness_suffix = (
            "No successful news refresh is recorded."
            if age_hours is None
            else (
                "Latest refresh "
                f"{NewsHealthMetrics.format_duration_hours(age_hours)} ago; "
                f"expected every {ttl_label}."
            )
        )

        if headlines_24h <= 0:
            return {
                "status": "down",
                "message": f"No fresh news in 24h. {freshness_suffix}",
                "latest_refreshed_at": latest_refresh,
                "latest_refresh_age_hours": round(age_hours, 2)
                if age_hours is not None
                else None,
            }

        if age_hours is None:
            return {
                "status": "degraded",
                "message": (
                    f"{headlines_24h} headlines cached in 24h, "
                    "but refresh timing is unknown."
                ),
                "latest_refreshed_at": None,
                "latest_refresh_age_hours": None,
            }

        if age_hours > ttl_hours:
            return {
                "status": "degraded",
                "message": (
                    f"{headlines_24h} headlines cached in 24h. "
                    f"{freshness_suffix}"
                ),
                "latest_refreshed_at": latest_refresh,
                "latest_refresh_age_hours": round(age_hours, 2),
            }

        sentiment_suffix = (
            f" {fallback_headlines_24h} used backup sentiment scoring."
            if fallback_headlines_24h > 0
            else ""
        )
        return {
            "status": "healthy",
            "message": (
                f"{headlines_24h} headlines refreshed in 24h."
                f"{sentiment_suffix}"
            ),
            "latest_refreshed_at": latest_refresh,
            "latest_refresh_age_hours": round(age_hours, 2),
        }

    def get_fallback_metrics(self, window_start: datetime) -> FallbackMetricsDict:
        """Get sentiment fallback metrics for health check.

        Args:
            window_start: Start of time window (now - 24 hours)

        Returns:
            Dict with fallback counts, rates, latencies
        """
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN sentiment_model <> %s THEN 1 ELSE 0 END) AS fallback_count,
                    COUNT(*) AS total_count,
                    AVG(
                        CASE
                            WHEN jsonb_exists(raw_payload, 'sentiment_fallback')
                            THEN (raw_payload->'sentiment_fallback'->>'latency_ms')::DOUBLE PRECISION
                        END
                    ) AS avg_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (
                        ORDER BY (raw_payload->'sentiment_fallback'->>'latency_ms')::DOUBLE PRECISION
                    ) FILTER (WHERE jsonb_exists(raw_payload, 'sentiment_fallback')) AS p95_latency_ms,
                    MAX(fetched_at) FILTER (WHERE jsonb_exists(raw_payload, 'sentiment_fallback')) AS last_fallback_at
                FROM news_cache
                WHERE fetched_at >= %s
                """,
                ["finbert", window_start],
            ).fetchone()

        fallback_count = int(row[0] or 0) if row else 0
        total_count = int(row[1] or 0) if row else 0
        avg_latency_ms = float(row[2]) if row and row[2] is not None else None
        p95_latency_ms = float(row[3]) if row and row[3] is not None else None
        last_fallback_at = row[4] if row and isinstance(row[4], datetime) else None
        fallback_rate = (fallback_count / total_count) if total_count else 0.0

        return {
            "fallback_count": fallback_count,
            "total_count": total_count,
            "fallback_rate": fallback_rate,
            "avg_latency_ms": avg_latency_ms,
            "p95_latency_ms": p95_latency_ms,
            "last_fallback_at": last_fallback_at,
        }

    def get_article_mix_metrics(self, now: datetime) -> ArticleMixMetricsDict:
        """Get article mix metrics from vendor manager.

        Args:
            now: Current timestamp

        Returns:
            Dict with pre/post dedupe counts by vendor
        """
        recent_mix_summary = self.vendor_manager.get_recent_mix_summary()
        mix_total_pre = 0
        mix_total_post = 0
        mix_vendor_pre: Counter[str] = Counter()
        mix_vendor_post: Counter[str] = Counter()
        last_mix_timestamp: datetime | None = None

        pruning_threshold = now - (self.ttl * 2)
        for stats in list(recent_mix_summary.values()):
            timestamp = stats.get("timestamp")
            if isinstance(timestamp, datetime) and timestamp < pruning_threshold:
                continue

            if isinstance(timestamp, datetime) and (
                not last_mix_timestamp or timestamp > last_mix_timestamp
            ):
                last_mix_timestamp = timestamp

            mix_total_pre += int(stats.get("total_pre", 0) or 0)
            mix_total_post += int(stats.get("total_post", 0) or 0)

            for vendor_name, count in (stats.get("per_vendor_pre") or {}).items():
                mix_vendor_pre[vendor_name] += int(count or 0)
            for vendor_name, count in (stats.get("per_vendor_post") or {}).items():
                mix_vendor_post[vendor_name] += int(count or 0)

        return {
            "total_pre": mix_total_pre,
            "total_post": mix_total_post,
            "vendor_pre": mix_vendor_pre,
            "vendor_post": mix_vendor_post,
            "last_timestamp": last_mix_timestamp,
        }

    def get_vendor_stats(self, window_start: datetime) -> dict[str, VendorStatsDict]:
        """Get per-vendor article stats from database.

        Args:
            window_start: Start of time window

        Returns:
            Dict mapping vendor name to stats
        """
        with self.storage.connection() as conn:
            vendor_rows = conn.execute(
                """
                SELECT
                    raw_payload->'raw'->>'vendor' AS vendor,
                    COUNT(*) AS article_count,
                    MAX(fetched_at) AS last_article_at
                FROM news_cache
                WHERE fetched_at >= %s
                GROUP BY vendor
                """,
                [window_start],
            ).fetchall()

        vendor_stats: dict[str, VendorStatsDict] = {}
        for vendor_name, article_count, last_article_at in vendor_rows:
            key = vendor_name.strip() if isinstance(vendor_name, str) else "unknown"

            # Ensure last_article_at is a datetime (skip if None)
            if not isinstance(last_article_at, datetime):
                continue

            # Ensure timezone-aware
            last_at = (
                last_article_at if last_article_at.tzinfo else last_article_at.replace(tzinfo=UTC)
            )

            vendor_stats[key] = VendorStatsDict(
                articles_last_24h=int(article_count or 0),
                last_article_at=last_at,
            )

        return vendor_stats

    def build_vendor_health(
        self,
        vendor_stats: dict[str, VendorStatsDict],
        now: datetime,
    ) -> dict[str, VendorHealthStatusDict]:
        """Build vendor health status from config, runtime, and stats.

        Args:
            vendor_stats: Per-vendor article stats
            now: Current timestamp

        Returns:
            Dict mapping vendor name to health status
        """
        vendor_config = self.vendor_manager.get_vendor_config()
        vendor_runtime = self.vendor_manager.get_vendor_runtime()
        vendor_health: dict[str, VendorHealthStatusDict] = {}

        for vendor_name, config in vendor_config.items():
            runtime = vendor_runtime.get(
                vendor_name,
                {
                    "last_attempt_at": None,
                    "last_success_at": None,
                    "last_error_at": None,
                    "last_error": None,
                    "articles_last_fetch": 0,
                },
            )
            stats: VendorStatsDict | dict[str, object] = vendor_stats.get(vendor_name, {})
            last_article_at_dt = stats.get("last_article_at")
            articles_last_24h = stats.get("articles_last_24h", 0)
            last_success_at_dt = self.latest_timestamp(
                runtime.get("last_success_at"),
                last_article_at_dt,
            )
            active = False
            if config.get("enabled") and isinstance(last_article_at_dt, datetime):
                active = (now - last_article_at_dt) <= (self.ttl * 2)

            vendor_health[vendor_name] = VendorHealthStatusDict(
                configured=bool(config.get("configured")),
                enabled=bool(config.get("enabled")),
                active=active,
                last_attempt_at=self.to_iso(cast(datetime | None, runtime.get("last_attempt_at"))),
                last_success_at=self.to_iso(last_success_at_dt),
                last_error_at=self.to_iso(cast(datetime | None, runtime.get("last_error_at"))),
                last_error=runtime.get("last_error"),
                articles_last_fetch=int(runtime.get("articles_last_fetch", 0)),
                articles_last_fetch_post_dedupe=int(runtime.get("articles_last_fetch_post", 0)),
                articles_last_24h=(
                    int(articles_last_24h) if isinstance(articles_last_24h, int) else 0
                ),
                last_article_at=self.to_iso(cast(datetime | None, last_article_at_dt)),
                notes=config.get("notes"),
                reason=config.get("reason"),
            )

        return vendor_health
