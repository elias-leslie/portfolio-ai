"""Service process patterns for monitoring.

Used by service_monitor.py for process detection.
"""

from __future__ import annotations

# Process patterns for service detection (used by service_monitor.py)
# Maps service names to regex patterns for process matching
SERVICE_PROCESS_PATTERNS: dict[str, str] = {
    "portfolio-backend": r"uvicorn.*main:app",
    "portfolio-hatchet-worker": r"python.*app\.worker",
    "portfolio-frontend": r"(next.*dev|next.*start|next-server)",
    "portfolio-redis": r"redis-server",
}

__all__ = [
    "SERVICE_PROCESS_PATTERNS",
]
