"""Service health check functions (sources, celery, agents, watchlist)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from app.logging_config import get_logger
from app.storage import PortfolioStorage

logger = get_logger(__name__)


class SourceHealthCheck:
    """Health check for individual data source."""

    def __init__(
        self,
        status: Literal["ok", "degraded", "down"],
        last_success: datetime | None = None,
        success_rate: float | None = None,
        avg_latency_ms: int | None = None,
        rate_limit_hits: int = 0,
        in_cooldown: bool = False,
        cooldown_remaining_seconds: int = 0,
    ):
        self.status = status
        self.last_success = last_success
        self.success_rate = success_rate
        self.avg_latency_ms = avg_latency_ms
        self.rate_limit_hits = rate_limit_hits
        self.in_cooldown = in_cooldown
        self.cooldown_remaining_seconds = cooldown_remaining_seconds


class AgentStats:
    """Agent execution statistics."""

    def __init__(
        self,
        total_runs: int,
        completed_runs: int,
        failed_runs: int,
        avg_duration_s: float | None = None,
        avg_cost_usd: float | None = None,
    ):
        self.total_runs = total_runs
        self.completed_runs = completed_runs
        self.failed_runs = failed_runs
        self.avg_duration_s = avg_duration_s
        self.avg_cost_usd = avg_cost_usd


class WatchlistStats:
    """Watchlist statistics."""

    def __init__(
        self,
        total_items: int,
        last_refresh: datetime | None = None,
        refresh_age_minutes: float | None = None,
        items_with_scores: int = 0,
    ):
        self.total_items = total_items
        self.last_refresh = last_refresh
        self.refresh_age_minutes = refresh_age_minutes
        self.items_with_scores = items_with_scores


class CeleryWorkerInfo:
    """Celery worker status information."""

    def __init__(
        self,
        active: bool,
        pool_size: int | None = None,
        active_tasks: int | None = None,
        message: str = "",
    ):
        self.active = active
        self.pool_size = pool_size
        self.active_tasks = active_tasks
        self.message = message


def _get_news_cache_timestamp(storage: PortfolioStorage) -> datetime | None:
    """Get latest news cache timestamp for RSS sources."""
    try:
        news_df = storage.query("SELECT MAX(fetched_at) as last_fetch FROM news_cache", [])
        if not news_df.is_empty():
            return news_df.to_dicts()[0].get("last_fetch")
    except Exception:
        pass  # news_cache might not exist yet
    return None


def _calculate_source_metrics(
    success_count: int, failure_count: int, total_latency_ms: int
) -> tuple[float, int | None]:
    """Calculate success rate and average latency for a source."""
    total_requests = success_count + failure_count
    success_rate = (success_count / total_requests * 100) if total_requests > 0 else 0.0
    avg_latency_ms = int(total_latency_ms / success_count) if success_count > 0 else None
    return success_rate, avg_latency_ms


def _determine_source_status(
    last_success_at: datetime | None, success_rate: float
) -> Literal["ok", "degraded", "down"]:
    """Determine source status based on last success time and success rate.

    Thresholds designed for mixed usage patterns:
    - Real-time sources: Should succeed within hours
    - Periodic sources: May go 24h+ between refreshes
    """
    if not last_success_at:
        return "down"  # Never succeeded

    time_since_success = datetime.now(UTC) - last_success_at

    if time_since_success < timedelta(hours=2):
        # Recent success - status based on success rate
        if success_rate >= 80:
            return "ok"
        if success_rate >= 50:
            return "degraded"
        return "down"
    if time_since_success < timedelta(hours=24):
        return "degraded"  # Stale but within 24h (common for RSS/periodic)
    return "down"  # Very stale (> 24h) - likely a real issue


def check_sources(storage: PortfolioStorage) -> dict[str, SourceHealthCheck]:
    """Check health of all data sources (see _get_news_cache_timestamp for RSS handling)."""
    sources: dict[str, SourceHealthCheck] = {}

    try:
        news_cache_timestamp = _get_news_cache_timestamp(storage)

        df = storage.query(
            """
            SELECT source_name, success_count, failure_count, total_latency_ms,
                   rate_limit_hits, last_success_at
            FROM source_performance
            """,
            [],
        )

        if df.is_empty():
            return sources

        for row in df.iter_rows(named=True):
            source_name = row["source_name"]
            success_count = row["success_count"] or 0
            failure_count = row["failure_count"] or 0
            total_latency_ms = row["total_latency_ms"] or 0
            rate_limit_hits = row["rate_limit_hits"] or 0
            last_success_at = row.get("last_success_at")

            # RSS sources: use news_cache timestamp (actually updated during ops)
            if "_rss" in source_name and news_cache_timestamp:
                last_success_at = news_cache_timestamp

            success_rate, avg_latency_ms = _calculate_source_metrics(
                success_count, failure_count, total_latency_ms
            )

            status = _determine_source_status(last_success_at, success_rate)

            sources[source_name] = SourceHealthCheck(
                status=status,
                last_success=last_success_at,
                success_rate=round(success_rate, 1),
                avg_latency_ms=avg_latency_ms,
                rate_limit_hits=rate_limit_hits,
                in_cooldown=False,
                cooldown_remaining_seconds=0,
            )

    except Exception as e:
        logger.error("check_sources_failed", error=str(e))

    return sources


def get_agent_stats(storage: PortfolioStorage) -> AgentStats:
    """Get agent execution statistics.

    Args:
        storage: PortfolioStorage instance

    Returns:
        AgentStats with agent metrics
    """
    try:
        df = storage.query(
            """
            SELECT
                COUNT(*) as total_runs,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_runs,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_runs,
                AVG(CASE
                    WHEN status = 'completed' AND completed_at IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (completed_at - started_at))
                    ELSE NULL
                END) as avg_duration_s,
                AVG(cost_usd) as avg_cost_usd
            FROM agent_runs
            """
        )

        if df.is_empty():
            return AgentStats(
                total_runs=0,
                completed_runs=0,
                failed_runs=0,
            )

        row = df.to_dicts()[0]

        return AgentStats(
            total_runs=row["total_runs"] or 0,
            completed_runs=row["completed_runs"] or 0,
            failed_runs=row["failed_runs"] or 0,
            avg_duration_s=round(row["avg_duration_s"], 2) if row["avg_duration_s"] else None,
            avg_cost_usd=round(row["avg_cost_usd"], 4) if row["avg_cost_usd"] else None,
        )

    except Exception as e:
        logger.error("get_agent_stats_failed", error=str(e))
        return AgentStats(
            total_runs=0,
            completed_runs=0,
            failed_runs=0,
        )


def get_watchlist_stats(storage: PortfolioStorage) -> WatchlistStats:
    """Get watchlist statistics.

    Args:
        storage: PortfolioStorage instance

    Returns:
        WatchlistStats with watchlist metrics
    """
    try:
        # Get total items
        items_df = storage.query("SELECT COUNT(*) as total FROM watchlist_items")
        total_items = items_df.to_dicts()[0]["total"] if not items_df.is_empty() else 0

        # Get last refresh timestamp and count items with scores
        snapshots_df = storage.query(
            """
            SELECT
                MAX(fetched_at) as last_refresh,
                COUNT(DISTINCT item_id) as items_with_scores
            FROM watchlist_snapshots_v
            """
        )

        if snapshots_df.is_empty():
            return WatchlistStats(
                total_items=total_items,
                items_with_scores=0,
            )

        row = snapshots_df.to_dicts()[0]
        last_refresh = row.get("last_refresh")
        items_with_scores = row.get("items_with_scores") or 0

        refresh_age_minutes = None
        if last_refresh:
            refresh_age_minutes = (datetime.now(UTC) - last_refresh).total_seconds() / 60

        return WatchlistStats(
            total_items=total_items,
            last_refresh=last_refresh,
            refresh_age_minutes=refresh_age_minutes,
            items_with_scores=items_with_scores,
        )

    except Exception as e:
        logger.error("get_watchlist_stats_failed", error=str(e))
        return WatchlistStats(total_items=0)


def get_celery_worker_info() -> CeleryWorkerInfo:
    """Get Celery worker active status and stats.

    Returns:
        CeleryWorkerInfo with worker status
    """
    try:
        # Import here to avoid circular dependency
        from app.celery_app import celery_app  # noqa: PLC0415

        inspect = celery_app.control.inspect(timeout=2.0)
        try:
            stats = inspect.stats()

            if not stats:
                return CeleryWorkerInfo(active=False, message="No workers responding to inspect")

            # Get stats from first worker
            worker_name = next(iter(stats.keys()))
            worker_stats = stats[worker_name]

            pool_size = worker_stats.get("pool", {}).get("max-concurrency")

            # Get active tasks count
            active = inspect.active()
            active_tasks = len(active.get(worker_name, [])) if active else None

            return CeleryWorkerInfo(
                active=True,
                pool_size=pool_size,
                active_tasks=active_tasks,
                message="Worker responding",
            )

        finally:
            # Close the inspect connection to prevent connection leaks
            if hasattr(inspect, "close"):
                inspect.close()

    except Exception as e:
        logger.error("get_celery_worker_info_failed", error=str(e))
        return CeleryWorkerInfo(active=False, message=f"Worker check failed: {e!s}")
