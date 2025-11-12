"""Individual health check functions.

Provides functions for checking database, sources, cache, agents, and watchlist health.

This module aggregates health check functionality from specialized sub-modules:
- health_database: Database connectivity checks
- health_services: Service health (sources, celery, agents, watchlist)
- health_storage: Storage/cache health (cache stats, quotas, API keys)
"""

from __future__ import annotations

# Re-export data classes from sub-modules for backward compatibility
from app.utils.health_database import CheckResult, check_database
from app.utils.health_services import (
    AgentStats,
    CeleryWorkerInfo,
    SourceHealthCheck,
    WatchlistStats,
    check_sources,
    get_agent_stats,
    get_celery_worker_info,
    get_watchlist_stats,
)
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
    # Data classes
    "CheckResult",
    "SourceHealthCheck",
    "CacheStats",
    "AgentStats",
    "WatchlistStats",
    "APIQuotaInfo",
    "DayBarFreshness",
    "CeleryWorkerInfo",
    "APIKeyStatus",
    # Functions - Database
    "check_database",
    # Functions - Services
    "check_sources",
    "get_agent_stats",
    "get_watchlist_stats",
    "get_celery_worker_info",
    # Functions - Storage
    "get_cache_stats",
    "get_api_quotas",
    "get_day_bars_freshness",
    "get_api_key_statuses",
    "load_quota_config",
]
