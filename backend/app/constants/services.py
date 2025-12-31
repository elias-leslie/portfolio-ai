"""Service name mappings for systemd units and monitoring.

This module centralizes service-related constants to avoid duplication
across status_logs.py and service_monitor.py.
"""

from __future__ import annotations

# =============================================================================
# SYSTEMD SERVICE MAPPINGS
# =============================================================================

# Maps logical service names (used in API) to systemd unit names
# Used by status_logs.py for journalctl queries and service_monitor.py for status checks
SERVICE_UNIT_MAPPING: dict[str, str] = {
    "backend": "portfolio-backend",
    "celery_worker": "portfolio-celery",
    "celery_beat": "portfolio-beat",
    "frontend": "portfolio-frontend",
    "redis": "redis-server",
    "postgresql": "postgresql@16-main",
}

# Process patterns for service detection (used by service_monitor.py)
# Maps systemd unit names to regex patterns for process matching
SERVICE_PROCESS_PATTERNS: dict[str, str] = {
    "portfolio-backend": r"uvicorn.*main:app",
    "portfolio-celery": r"celery.*worker",
    "portfolio-celery-beat": r"celery.*beat",
    "portfolio-frontend": r"next.*dev",
    "portfolio-redis": r"redis-server",
    "portfolio-dev-companion": r"dev-companion",
}

# Valid service names for API validation
VALID_SERVICES: frozenset[str] = frozenset(SERVICE_UNIT_MAPPING.keys())

__all__ = [
    "SERVICE_PROCESS_PATTERNS",
    "SERVICE_UNIT_MAPPING",
    "VALID_SERVICES",
]
