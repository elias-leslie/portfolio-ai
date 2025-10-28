"""Health check endpoints for portfolio-ai.

This module provides comprehensive health checks for monitoring
system status, dependencies, and service availability.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Literal

import yfinance as yf
from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..storage import get_storage

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

# Track application start time for uptime calculation
APP_START_TIME = datetime.now()


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


class HealthCheckResponse(BaseModel):
    """Complete health check response."""

    status: Literal["healthy", "degraded", "down"]
    timestamp: datetime = Field(default_factory=datetime.now)
    version: str = "1.0.0"
    uptime_seconds: int
    checks: dict[str, CheckResult]
    cache_stats: CacheStats | None = None
    agent_stats: AgentStats | None = None


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

    def check_yfinance(self) -> CheckResult:
        """Check yfinance API availability.

        Returns:
            CheckResult with yfinance health status
        """
        try:
            start = time.time()

            # Try to fetch AAPL price as a health check
            ticker = yf.Ticker("AAPL")
            info = ticker.info
            price = info.get("currentPrice") or info.get("regularMarketPrice")

            latency_ms = int((time.time() - start) * 1000)

            if not price:
                return CheckResult(
                    status="degraded",
                    latency_ms=latency_ms,
                    message="yfinance returned no price data",
                )

            return CheckResult(
                status="ok",
                latency_ms=latency_ms,
                last_success=datetime.now(),
                message=f"AAPL: ${price}",
            )

        except Exception as e:
            logger.warning("yfinance_health_check_failed", error=str(e))
            return CheckResult(
                status="degraded",
                message=f"yfinance error: {e!s}",
            )

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

    def perform_health_check(self) -> HealthCheckResponse:
        """Perform all health checks.

        Returns:
            HealthCheckResponse with all check results
        """
        checks: dict[str, CheckResult] = {}

        # Critical checks
        checks["database"] = self.check_database()
        checks["yfinance"] = self.check_yfinance()

        # Determine overall status
        if checks["database"].status == "down":
            overall_status: Literal["healthy", "degraded", "down"] = "down"
        elif any(check.status == "degraded" for check in checks.values()):
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        # Get statistics
        cache_stats = self.get_cache_stats()
        agent_stats = self.get_agent_stats()

        # Calculate uptime
        uptime_seconds = int((datetime.now() - APP_START_TIME).total_seconds())

        return HealthCheckResponse(
            status=overall_status,
            uptime_seconds=uptime_seconds,
            checks=checks,
            cache_stats=cache_stats,
            agent_stats=agent_stats,
        )


# Create singleton instance
health_service = HealthCheckService()


@router.get("", response_model=HealthCheckResponse)
async def health_check(response: Response) -> HealthCheckResponse:
    """Comprehensive health check endpoint.

    Returns health status, uptime, and metrics for all system components.
    Returns HTTP 503 if database is down, HTTP 200 otherwise.
    """
    result = health_service.perform_health_check()

    # Set appropriate HTTP status code
    if result.status == "down":
        response.status_code = 503

    logger.info(
        "health_check_performed",
        status=result.status,
        uptime_seconds=result.uptime_seconds,
        database_status=result.checks["database"].status,
        yfinance_status=result.checks["yfinance"].status,
    )

    return result


@router.get("/simple")
async def simple_health_check() -> dict[str, str]:
    """Simple health check endpoint (legacy compatibility).

    Returns:
        Simple status dict
    """
    return {"status": "healthy"}
