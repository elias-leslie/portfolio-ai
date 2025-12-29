"""Health check strategies for sitemap endpoints.

Provides strategy pattern for determining how to health check different endpoint types.
Extracted from sitemap_service.py to reduce file size and improve maintainability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

# Endpoints that should only be probed (quick check, accept any response)
# These are checked with short timeout and ANY response (even 4xx) = route exists
# This verifies the endpoint is reachable without triggering expensive operations
PROBE_CHECK_PATTERNS: list[str] = [
    # Market data endpoints - trigger external API calls
    "/api/market/intelligence",  # Fetches live market data from yfinance/polygon
    "/api/market/prices",  # Fetches live prices
    "/api/market/movers",  # Fetches market movers
    "/api/market/status",  # May fetch external data
    # Symbol intelligence - potentially expensive
    "/api/symbols/{symbol}/intelligence",  # Heavy aggregation
    # Analytics endpoints with symbol params - expensive external fetches
    "/api/analytics/rvol/",  # Fetches historical data
    "/api/analytics/peers/",  # Fetches peer data
    "/api/analytics/short-interest/",  # Fetches short interest
    "/api/analytics/cash-flow/",  # Fetches financial data
    "/api/analytics/insider-transactions/",  # Fetches insider data
    "/api/analytics/institutional-holdings/",  # Fetches holdings data
    # News endpoints - may trigger external fetches
    "/api/news/intelligence",  # Fetches news from APIs
    # Valuation endpoints - expensive calculations
    "/api/valuation/metrics",
    # Celery endpoints - may interact with worker
    "/api/celery/",  # Celery inspection can be slow
    # Backup endpoints - may trigger filesystem operations
    "/api/backup/status",
    "/api/backup/latest",
    # ML endpoints - expensive operations
    "/api/ml/",
    # Backtest endpoints - heavy computation
    "/api/backtest/run",
]

# Endpoints that should be completely skipped (circular dependency risk)
SKIP_HEALTH_CHECK_PATTERNS: list[str] = [
    "/health",  # Skip health endpoints to avoid circular calls
    "/api/health",  # Skip all health endpoints
]


def matches_pattern(path: str, pattern: str) -> bool:
    """Check if a path matches a pattern (exact, prefix, or path-param).

    Args:
        path: The endpoint path to check
        pattern: Pattern to match against

    Returns:
        True if path matches pattern
    """
    # Exact match
    if path == pattern:
        return True

    # Prefix match (patterns ending with /)
    if pattern.endswith("/") and path.startswith(pattern):
        return True

    # Path parameter patterns like {symbol}
    if "{" in pattern:
        regex_pattern = re.sub(r"\{[^}]+\}", r"[^/]+", pattern)
        if re.fullmatch(regex_pattern, path):
            return True

    # Simple prefix match for patterns without trailing /
    return not pattern.endswith("/") and path.startswith(pattern + "/")


@dataclass
class CheckDecision:
    """Result of check type decision."""

    should_skip: bool
    is_probe: bool
    skip_message: str | None = None
    probe_pattern: str | None = None


class HealthCheckStrategy:
    """Strategy for determining how to health check endpoints."""

    probe_patterns: ClassVar[list[str]] = PROBE_CHECK_PATTERNS
    skip_patterns: ClassVar[list[str]] = SKIP_HEALTH_CHECK_PATTERNS

    @classmethod
    def should_skip_health_check(cls, path: str) -> str | None:
        """Check if a path should be completely skipped during health checks.

        Only returns skip reason for endpoints that could cause circular dependencies
        (like health check endpoints calling health check endpoints).

        Args:
            path: The endpoint path to check

        Returns:
            Skip reason string if should skip, None otherwise
        """
        for pattern in cls.skip_patterns:
            if matches_pattern(path, pattern):
                return f"Skipped (circular: {pattern})"
        return None

    @classmethod
    def should_probe_check(cls, path: str) -> str | None:
        """Check if a path needs lightweight probe check instead of full execution.

        Probe checks use short timeout and accept any response (even 4xx) as "route exists".
        This verifies reachability without triggering expensive external API calls.

        Args:
            path: The endpoint path to check

        Returns:
            Pattern that matched if should probe, None for normal check
        """
        for pattern in cls.probe_patterns:
            if matches_pattern(path, pattern):
                return pattern
        return None

    @classmethod
    def get_check_decision(
        cls, path: str, method: str, has_path_params: bool
    ) -> CheckDecision:
        """Determine the check strategy for an endpoint.

        Args:
            path: Endpoint path
            method: HTTP method
            has_path_params: Whether the path has path parameters

        Returns:
            CheckDecision with skip/probe info
        """
        is_streaming = "/stream" in path or "/ws" in path.lower() or method == "WS"
        is_mutating = method in ("POST", "PUT", "DELETE", "PATCH")
        skip_reason = cls.should_skip_health_check(path)
        probe_pattern = cls.should_probe_check(path)

        # Path parameter endpoints should ALWAYS use probe logic
        if has_path_params and not probe_pattern:
            probe_pattern = "path-param"

        # Determine skip status and message
        if is_streaming:
            return CheckDecision(
                should_skip=True,
                is_probe=False,
                skip_message="Skipped (streaming)",
            )
        if is_mutating:
            return CheckDecision(
                should_skip=True,
                is_probe=False,
                skip_message="Skipped (mutating method)",
            )
        if skip_reason:
            return CheckDecision(
                should_skip=True,
                is_probe=False,
                skip_message=skip_reason,
            )

        return CheckDecision(
            should_skip=False,
            is_probe=probe_pattern is not None,
            probe_pattern=probe_pattern,
        )
