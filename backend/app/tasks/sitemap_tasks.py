"""Tasks for sitemap health monitoring.

These tasks run on schedule to:
- Check health of all sitemap entries (hourly)
- Discover new endpoints (daily)
- Clean up old health history (daily)
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from ..logging_config import get_logger
from ..services.sitemap import SitemapService

logger = get_logger(__name__)


def check_sitemap_health() -> dict[str, Any]:
    """Periodic health check for all sitemap entries.

    Runs every 1 hour to check:
    - HTTP status for all entries
    - Console errors/warnings for frontend pages
    - Response time tracking

    Returns:
        Dict with check results summary
    """
    start_time = time.time()
    logger.info("sitemap_health_check_started")

    try:
        service = SitemapService()
        result = asyncio.run(service.check_all_health())

        duration = time.time() - start_time
        logger.info(
            "sitemap_health_check_complete",
            checked=result.get("checked", 0),
            healthy=result.get("healthy", 0),
            warnings=result.get("warnings", 0),
            errors=result.get("errors", 0),
            duration_seconds=round(duration, 2),
        )

        return {
            "status": "success",
            **result,
            "duration_seconds": round(duration, 2),
        }

    except Exception as e:
        logger.error("sitemap_health_check_failed", error=str(e))
        return {"status": "error", "error": str(e)}


def discover_sitemap_entries() -> dict[str, Any]:
    """Discover new sitemap entries from OpenAPI and crawling.

    Runs daily to find new endpoints:
    - Parses /openapi.json for backend endpoints
    - Crawls frontend pages following links
    - Imports from existing api_capabilities

    Returns:
        Dict with discovery results summary
    """
    start_time = time.time()
    logger.info("sitemap_discovery_started")

    try:
        service = SitemapService()
        result = asyncio.run(service.run_discovery())

        duration = time.time() - start_time
        logger.info(
            "sitemap_discovery_complete",
            backend_discovered=result.get("backend_discovered", 0),
            frontend_discovered=result.get("frontend_discovered", 0),
            api_imported=result.get("api_imported", 0),
            total_saved=result.get("total_saved", 0),
            duration_seconds=round(duration, 2),
        )

        return {
            "status": "success",
            **result,
            "duration_seconds": round(duration, 2),
        }

    except Exception as e:
        logger.error("sitemap_discovery_failed", error=str(e))
        return {"status": "error", "error": str(e)}


def cleanup_sitemap_history(retention_days: int = 7) -> dict[str, Any]:
    """Delete health history older than retention period.

    Runs daily to keep history table size manageable.

    Args:
        retention_days: Number of days to keep (default 7)

    Returns:
        Dict with cleanup results
    """
    start_time = time.time()
    logger.info("sitemap_cleanup_started", retention_days=retention_days)

    try:
        service = SitemapService()
        deleted = service.cleanup_old_history(days=retention_days)

        duration = time.time() - start_time
        logger.info(
            "sitemap_cleanup_complete",
            deleted=deleted,
            retention_days=retention_days,
            duration_seconds=round(duration, 2),
        )

        return {
            "status": "success",
            "deleted": deleted,
            "retention_days": retention_days,
            "duration_seconds": round(duration, 2),
        }

    except Exception as e:
        logger.error("sitemap_cleanup_failed", error=str(e))
        return {"status": "error", "error": str(e)}
