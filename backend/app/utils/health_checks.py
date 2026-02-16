"""Individual health check functions.

Provides functions for checking database, sources, cache, agents, and watchlist health.

This module aggregates health check functionality from specialized sub-modules:
- health_database: Database connectivity checks
- health_checks_impl: Service health (sources, workers, agents, watchlist)
- health_storage: Storage/cache health (cache stats, quotas, API keys)
"""

from __future__ import annotations

from app.utils.health_checks_impl import (
    AgentStats,
    SourceHealthCheck,
    WatchlistStats,
    WorkerInfo,
    check_sources,
    get_agent_stats,
    get_watchlist_stats,
    get_worker_info,
)

# Re-export data classes from sub-modules for backward compatibility
from app.utils.health_database import CheckResult, check_database
from app.utils.health_storage import (
    APIKeyStatus,
    APIQuotaInfo,
    CacheStats,
    DayBarFreshness,
    get_api_key_statuses,
    get_api_quotas,
    get_cache_stats,
    get_day_bars_freshness,
    load_quota_config,
)

__all__ = [
    "APIKeyStatus",
    "APIQuotaInfo",
    "AgentStats",
    "CacheStats",
    "CheckResult",
    "DayBarFreshness",
    "SourceHealthCheck",
    "WatchlistStats",
    "WorkerInfo",
    "check_database",
    "check_sources",
    "get_agent_stats",
    "get_api_key_statuses",
    "get_api_quotas",
    "get_cache_stats",
    "get_day_bars_freshness",
    "get_watchlist_stats",
    "get_worker_info",
    "load_quota_config",
]
