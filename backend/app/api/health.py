"""Health check endpoints for portfolio-ai.

This module provides comprehensive health checks for monitoring
system status, dependencies, and service availability including multi-source data fetching.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..storage import get_storage

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

# Track application start time for uptime calculation
APP_START_TIME = datetime.now()


class SourceHealthCheck(BaseModel):
    """Health check for individual data source."""

    status: Literal["ok", "degraded", "down"]
    last_success: datetime | None = None
    success_rate: float | None = None
    avg_latency_ms: int | None = None
    rate_limit_hits: int = 0
    in_cooldown: bool = False
    cooldown_remaining_seconds: int = 0


class CheckResult(BaseModel):
    """Individual health check result."""

    status: Literal["ok", "degraded", "down"]
    latency_ms: int | None = None
    last_success: datetime | None = None
    message: str | None = None


class CacheStats(BaseModel):
    """Price cache statistics."""

    total_cached: int
    cache_age_minutes: float | None = None


class AgentStats(BaseModel):
    """Agent execution statistics."""

    total_runs: int
    completed_runs: int
    failed_runs: int
    avg_duration_s: float | None = None
    avg_cost_usd: float | None = None


class WatchlistStats(BaseModel):
    """Watchlist statistics."""

    total_items: int
    last_refresh: datetime | None = None
    refresh_age_minutes: float | None = None
    items_with_scores: int = 0


class HealthCheckResponse(BaseModel):
    """Complete health check response."""

    status: Literal["healthy", "degraded", "down"]
    timestamp: datetime = Field(default_factory=datetime.now)
    version: str = "1.0.0"
    uptime_seconds: int
    checks: dict[str, CheckResult]
    sources: dict[str, SourceHealthCheck] = Field(default_factory=dict)
    cache_stats: CacheStats | None = None
    agent_stats: AgentStats | None = None
    watchlist_stats: WatchlistStats | None = None


class HealthCheckService:
    """Service for performing health checks."""

    def __init__(self) -> None:
        """Initialize health check service."""
        self.storage = get_storage()

    def check_database(self) -> CheckResult:
        """Check database connectivity and performance.

        Returns:
            CheckResult with database health status
        """
        try:
            start = time.time()

            # Simple query to verify database is accessible
            df = self.storage.query("SELECT 1 as test")

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
                last_success=datetime.now(),
            )

        except Exception as e:
            logger.error("database_health_check_failed", error=str(e))
            return CheckResult(
                status="down",
                message=f"Database error: {e!s}",
            )

    def check_sources(self) -> dict[str, SourceHealthCheck]:
        """Check health of all data sources from source_performance table.

        Returns:
            Dict mapping source name to SourceHealthCheck
        """
        sources: dict[str, SourceHealthCheck] = {}

        try:
            df = self.storage.query(
                """
                SELECT
                    source_name,
                    success_count,
                    failure_count,
                    total_latency_ms,
                    rate_limit_hits,
                    last_success_at
                FROM source_performance
                """,
                [],
            )

            if df.is_empty():
                # No source data yet - return empty dict
                return sources

            for row in df.iter_rows(named=True):
                source_name = row["source_name"]
                success_count = row["success_count"] or 0
                failure_count = row["failure_count"] or 0
                total_latency_ms = row["total_latency_ms"] or 0
                rate_limit_hits = row["rate_limit_hits"] or 0
                last_success_at = row.get("last_success_at")

                # Calculate success rate
                total_requests = success_count + failure_count
                success_rate = (success_count / total_requests * 100) if total_requests > 0 else 0.0

                # Calculate average latency
                avg_latency_ms = (
                    int(total_latency_ms / success_count) if success_count > 0 else None
                )

                # Determine status based on last success and success rate
                if last_success_at:
                    time_since_success = datetime.now() - last_success_at
                    if time_since_success < timedelta(minutes=15):
                        if success_rate >= 80:
                            status: Literal["ok", "degraded", "down"] = "ok"
                        elif success_rate >= 50:
                            status = "degraded"
                        else:
                            status = "down"
                    elif time_since_success < timedelta(hours=1):
                        status = "degraded"  # Stale but not completely down
                    else:
                        status = "down"  # Very stale
                else:
                    status = "down"  # Never succeeded

                sources[source_name] = SourceHealthCheck(
                    status=status,
                    last_success=last_success_at,
                    success_rate=round(success_rate, 1),
                    avg_latency_ms=avg_latency_ms,
                    rate_limit_hits=rate_limit_hits,
                    in_cooldown=False,  # Would need real-time data from MultiSourceFetcher
                    cooldown_remaining_seconds=0,
                )

        except Exception as e:
            logger.error("check_sources_failed", error=str(e))

        return sources

    def get_last_price_fetch(self) -> datetime | None:
        """Get timestamp of last successful price fetch.

        Returns:
            Datetime of last price fetch, or None if no data
        """
        try:
            df = self.storage.query(
                """
                SELECT MAX(cached_at) as last_fetch
                FROM price_cache
                WHERE error IS NULL
                """
            )

            if df.is_empty():
                return None

            last_fetch = df.to_dicts()[0]["last_fetch"]
            return last_fetch if last_fetch else None

        except Exception as e:
            logger.error("get_last_price_fetch_failed", error=str(e))
            return None

    def get_cache_stats(self) -> CacheStats:
        """Get price cache statistics.

        Returns:
            CacheStats with cache metrics
        """
        try:
            df = self.storage.query(
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
                cache_age_minutes = (datetime.now() - last_cached).total_seconds() / 60

            return CacheStats(
                total_cached=total_cached,
                cache_age_minutes=cache_age_minutes,
            )

        except Exception as e:
            logger.error("get_cache_stats_failed", error=str(e))
            return CacheStats(total_cached=0)

    def get_agent_stats(self) -> AgentStats:
        """Get agent execution statistics.

        Returns:
            AgentStats with agent metrics
        """
        try:
            df = self.storage.query(
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

    def get_watchlist_stats(self) -> WatchlistStats:
        """Get watchlist statistics.

        Returns:
            WatchlistStats with watchlist metrics
        """
        try:
            # Get total items
            items_df = self.storage.query("SELECT COUNT(*) as total FROM watchlist_items")
            total_items = items_df.to_dicts()[0]["total"] if not items_df.is_empty() else 0

            # Get last refresh timestamp and count items with scores
            snapshots_df = self.storage.query(
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
                refresh_age_minutes = (datetime.now() - last_refresh).total_seconds() / 60

            return WatchlistStats(
                total_items=total_items,
                last_refresh=last_refresh,
                refresh_age_minutes=refresh_age_minutes,
                items_with_scores=items_with_scores,
            )

        except Exception as e:
            logger.error("get_watchlist_stats_failed", error=str(e))
            return WatchlistStats(total_items=0)

    def perform_health_check(self) -> HealthCheckResponse:
        """Perform all health checks including multi-source data fetching.

        Returns:
            HealthCheckResponse with all check results
        """
        checks: dict[str, CheckResult] = {}

        # Critical checks
        checks["database"] = self.check_database()

        # Data source checks (from source_performance table)
        sources = self.check_sources()

        # Determine overall status
        if checks["database"].status == "down":
            overall_status: Literal["healthy", "degraded", "down"] = "down"
        elif any(check.status == "degraded" for check in checks.values()):
            overall_status = "degraded"
        elif any(source.status == "down" for source in sources.values()):
            # If all sources are down, we're degraded (not completely down)
            if all(source.status == "down" for source in sources.values()) and sources:
                overall_status = "degraded"
            else:
                overall_status = "healthy"
        else:
            overall_status = "healthy"

        # Get statistics
        cache_stats = self.get_cache_stats()
        agent_stats = self.get_agent_stats()
        watchlist_stats = self.get_watchlist_stats()

        # Calculate uptime
        uptime_seconds = int((datetime.now() - APP_START_TIME).total_seconds())

        return HealthCheckResponse(
            status=overall_status,
            uptime_seconds=uptime_seconds,
            checks=checks,
            sources=sources,
            cache_stats=cache_stats,
            agent_stats=agent_stats,
            watchlist_stats=watchlist_stats,
        )


# Create singleton instance
health_service = HealthCheckService()


@router.get("", response_model=HealthCheckResponse)
async def health_check(response: Response) -> HealthCheckResponse:
    """Comprehensive health check endpoint.

    Returns health status, uptime, and metrics for all system components including
    multi-source data fetching health (yfinance, polygon, etc).
    Returns HTTP 503 if database is down, HTTP 200 otherwise.
    """
    result = health_service.perform_health_check()

    # Set appropriate HTTP status code
    if result.status == "down":
        response.status_code = 503

    # Build source status summary for logging
    source_status_summary = {name: src.status for name, src in result.sources.items()}

    logger.info(
        "health_check_performed",
        status=result.status,
        uptime_seconds=result.uptime_seconds,
        database_status=result.checks["database"].status,
        sources=source_status_summary,
        num_sources=len(result.sources),
    )

    return result


@router.get("/simple")
async def simple_health_check() -> dict[str, str]:
    """Simple health check endpoint (legacy compatibility).

    Returns:
        Simple status dict
    """
    return {"status": "healthy"}
