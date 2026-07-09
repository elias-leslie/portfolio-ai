"""Database health check functions."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from app.logging_config import get_logger
from app.storage import PortfolioStorage

logger = get_logger(__name__)


class CheckResult(BaseModel):
    """Individual health check result."""

    status: Literal["ok", "degraded", "down"]
    latency_ms: int | None = None
    last_success: datetime | None = None
    message: str | None = None
    details: dict[str, int | float] | None = None


def check_database(storage: PortfolioStorage) -> CheckResult:
    """Check database connectivity and performance.

    Args:
        storage: PortfolioStorage instance

    Returns:
        CheckResult with database health status
    """
    try:
        start = time.time()

        # Verify connectivity and surface shared-host connection pressure before
        # PostgreSQL starts refusing ordinary application connections.
        df = storage.query(
            """
            SELECT
                1 AS test,
                (SELECT COUNT(*) FROM pg_stat_activity) AS used_connections,
                current_setting('max_connections')::integer AS max_connections
            """
        )

        latency_ms = int((time.time() - start) * 1000)

        if df.is_empty():
            return CheckResult(
                status="down",
                latency_ms=latency_ms,
                message="Database query returned empty result",
            )

        row = df.to_dicts()[0]
        used_connections = int(row.get("used_connections") or 0)
        max_connections = int(row.get("max_connections") or 0)
        utilization_pct = (
            round(used_connections / max_connections * 100, 1) if max_connections > 0 else 0.0
        )
        status: Literal["ok", "degraded"] = (
            "degraded" if utilization_pct >= 80 else "ok"
        )
        message = (
            f"PostgreSQL connection usage is {utilization_pct:.1f}% "
            f"({used_connections}/{max_connections})."
            if status == "degraded"
            else None
        )
        return CheckResult(
            status=status,
            latency_ms=latency_ms,
            last_success=datetime.now(UTC),
            message=message,
            details={
                "used_connections": used_connections,
                "max_connections": max_connections,
                "utilization_pct": utilization_pct,
            },
        )

    except Exception as e:
        logger.error("database_health_check_failed", error=str(e), exc_info=True)
        return CheckResult(
            status="down",
            message=f"Database error: {e!s}",
        )
