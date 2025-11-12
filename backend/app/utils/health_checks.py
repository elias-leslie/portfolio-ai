"""Individual health check functions.

Provides functions for checking database, sources, cache, agents, and watchlist health.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from app.logging_config import get_logger
from app.storage import PortfolioStorage
from app.utils.quota_helpers import build_quota_info, is_api_key_configured

logger = get_logger(__name__)


class CheckResult:
    """Individual health check result."""

    def __init__(
        self,
        status: Literal["ok", "degraded", "down"],
        latency_ms: int | None = None,
        last_success: datetime | None = None,
        message: str | None = None,
    ):
        self.status = status
        self.latency_ms = latency_ms
        self.last_success = last_success
        self.message = message


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


class CacheStats:
    """Price cache statistics."""

    def __init__(self, total_cached: int, cache_age_minutes: float | None = None):
        self.total_cached = total_cached
        self.cache_age_minutes = cache_age_minutes


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


class APIQuotaInfo:
    """API quota information for external data sources."""

    def __init__(
        self,
        source_name: str,
        configured: bool,
        rate_limit: str | None = None,
        daily_limit: str | None = None,
        estimated_capacity: int | None = None,
    ):
        self.source_name = source_name
        self.configured = configured
        self.rate_limit = rate_limit
        self.daily_limit = daily_limit
        self.estimated_capacity = estimated_capacity


class DayBarFreshness:
    """Freshness data for a ticker's day_bars."""

    def __init__(self, ticker: str, last_updated: datetime | None, age_days: int | None):
        self.ticker = ticker
        self.last_updated = last_updated
        self.age_days = age_days


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


class APIKeyStatus:
    """API key configuration and validation status."""

    def __init__(self, source: str, configured: bool, env_var: str):
        self.source = source
        self.configured = configured
        self.env_var = env_var


def check_database(storage: PortfolioStorage) -> CheckResult:
    """Check database connectivity and performance.

    Args:
        storage: PortfolioStorage instance

    Returns:
        CheckResult with database health status
    """
    try:
        start = time.time()

        # Simple query to verify database is accessible
        df = storage.query("SELECT 1 as test")

        latency_ms = int((time.time() - start) * 1000)

        if df.is_empty():
            return CheckResult(
                status="down",
                latency_ms=latency_ms,
                message="Database query returned empty result",
            )

        return CheckResult(
            status="ok",
            latency_ms=latency_ms,
            last_success=datetime.now(UTC),
        )

    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
        return CheckResult(
            status="down",
            message=f"Database error: {e!s}",
        )


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


def get_cache_stats(storage: PortfolioStorage) -> CacheStats:
    """Get price cache statistics.

    Args:
        storage: PortfolioStorage instance

    Returns:
        CacheStats with cache metrics
    """
    try:
        df = storage.query(
            """
            SELECT
                COUNT(*) as total_cached,
                MAX(cached_at) as last_cached
            FROM price_cache
            WHERE error IS NULL
            """
        )

        if df.is_empty():
            return CacheStats(total_cached=0)

        row = df.to_dicts()[0]
        total_cached = row["total_cached"]
        last_cached = row["last_cached"]

        cache_age_minutes = None
        if last_cached:
            cache_age_minutes = (datetime.now(UTC) - last_cached).total_seconds() / 60

        return CacheStats(
            total_cached=total_cached,
            cache_age_minutes=cache_age_minutes,
        )

    except Exception as e:
        logger.error("get_cache_stats_failed", error=str(e))
        return CacheStats(total_cached=0)


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
            FROM watchlist_snapshots
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


def load_quota_config() -> dict[str, dict[str, Any]]:
    """Load API quota configuration from JSON file.

    Returns:
        Dictionary mapping source_id to quota configuration
    """
    import json  # noqa: PLC0415

    config_path = Path(__file__).parent.parent / "config" / "quota_config.json"
    try:
        with config_path.open() as f:
            config_data: dict[str, Any] = json.load(f)
            sources: dict[str, dict[str, Any]] = config_data.get("sources", {})
            return sources
    except Exception as e:
        logger.warning("failed_to_load_quota_config", error=str(e), path=str(config_path))
        return {}


def get_api_quotas(storage: PortfolioStorage) -> list[APIQuotaInfo]:
    """Get API quota information from source configuration files.

    Args:
        storage: PortfolioStorage instance

    Returns:
        List of APIQuotaInfo for each configured data source
    """
    quotas: list[APIQuotaInfo] = []

    try:
        # Find config directory
        config_dir = Path(__file__).parent.parent.parent / "config" / "sources"

        if not config_dir.exists():
            logger.warning("get_api_quotas_no_config_dir", config_dir=str(config_dir))
            return quotas

        # Load quota metadata from configuration file
        quota_map = load_quota_config()

        for source_id, quota_info in quota_map.items():
            # Check if API key is configured
            configured = is_api_key_configured(source_id, quota_info["env_var"], storage)

            # Build and append quota info
            quota_data = build_quota_info(source_id, quota_info, configured)
            quotas.append(APIQuotaInfo(**quota_data))

    except Exception as e:
        logger.error("get_api_quotas_failed", error=str(e))

    return quotas


def get_day_bars_freshness(storage: PortfolioStorage) -> list[DayBarFreshness]:
    """Get data freshness for each ticker in day_bars table.

    Args:
        storage: PortfolioStorage instance

    Returns:
        List of DayBarFreshness with last updated date per ticker
    """
    freshness_list: list[DayBarFreshness] = []

    try:
        df = storage.query(
            """
            SELECT ticker, MAX(date) as last_updated
            FROM day_bars
            GROUP BY ticker
            ORDER BY ticker
            """
        )

        if df.is_empty():
            logger.info("get_day_bars_freshness_empty_table")
            return freshness_list

        now = datetime.now(UTC)
        for row in df.iter_rows(named=True):
            ticker = row["ticker"]
            last_updated = row.get("last_updated")

            age_days = None
            if last_updated:
                # Convert date to datetime for age calculation
                if isinstance(last_updated, datetime):
                    age_delta = now - last_updated
                else:
                    # If it's a date object, convert to datetime
                    from datetime import date as date_type  # noqa: PLC0415

                    if isinstance(last_updated, date_type):
                        last_updated_dt = datetime.combine(
                            last_updated, datetime.min.time(), tzinfo=UTC
                        )
                        age_delta = now - last_updated_dt
                    else:
                        age_delta = timedelta(days=0)

                age_days = age_delta.days

            freshness_list.append(
                DayBarFreshness(ticker=ticker, last_updated=last_updated, age_days=age_days)
            )

        logger.info("get_day_bars_freshness_success", ticker_count=len(freshness_list))

    except Exception as e:
        logger.error("get_day_bars_freshness_failed", error=str(e))

    return freshness_list


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


def get_api_key_statuses(storage: PortfolioStorage) -> list[APIKeyStatus]:
    """Get API key configuration status for all sources.

    Args:
        storage: PortfolioStorage instance

    Returns:
        List of APIKeyStatus for each configured source
    """
    import os  # noqa: PLC0415

    statuses: list[APIKeyStatus] = []

    try:
        # Load quota config to get list of sources with env vars
        quota_map = load_quota_config()

        for source_id, quota_info in quota_map.items():
            env_var = quota_info.get("env_var", "")
            configured = bool(os.environ.get(env_var))

            statuses.append(APIKeyStatus(source=source_id, configured=configured, env_var=env_var))

        statuses.sort(key=lambda x: x.source)

    except Exception as e:
        logger.error("get_api_key_statuses_failed", error=str(e))

    return statuses
