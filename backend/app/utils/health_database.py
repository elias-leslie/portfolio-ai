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
