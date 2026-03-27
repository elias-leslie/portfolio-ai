"""Storage, cache, and API quota health check functions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.logging_config import get_logger
from app.storage import PortfolioStorage
from app.utils.quota_helpers import build_quota_info, is_api_key_configured

logger = get_logger(__name__)


class CacheStats(BaseModel):
    """Price cache statistics."""

    total_cached: int
    cache_age_minutes: float | None = None


class APIQuotaInfo(BaseModel):
    """API quota information for external data sources."""

    source_name: str
    configured: bool
    rate_limit: str | None = None
    daily_limit: str | None = None
    estimated_capacity: int | None = None


class DayBarFreshness(BaseModel):
    """Freshness data for a symbol's day_bars."""

    symbol: str
    last_updated: datetime | None = None
    age_days: int | None = None


class APIKeyStatus(BaseModel):
    """API key configuration and validation status."""

    source: str
    configured: bool
    env_var: str


def get_cache_stats(storage: PortfolioStorage) -> CacheStats:
    """Get price cache statistics.

    Args:
        storage: PortfolioStorage instance

    Returns:
        CacheStats with cache metrics
    """
    try:
        df = storage.query(
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
            cache_age_minutes = (datetime.now(UTC) - last_cached).total_seconds() / 60

        return CacheStats(
            total_cached=total_cached,
            cache_age_minutes=cache_age_minutes,
        )

    except Exception as e:
        logger.error("get_cache_stats_failed", error=str(e), exc_info=True)
        return CacheStats(total_cached=0)


def load_quota_config() -> dict[str, dict[str, Any]]:
    """Load API quota configuration from JSON file.

    Returns:
        Dictionary mapping source_id to quota configuration
    """
    import json  # noqa: PLC0415

    config_path = Path(__file__).parent.parent / "config" / "quota_config.json"
    try:
        with config_path.open(encoding="utf-8") as f:
            config_data: dict[str, Any] = json.load(f)
            sources: dict[str, dict[str, Any]] = config_data.get("sources", {})
            return sources
    except Exception as e:
        logger.warning("failed_to_load_quota_config", error=str(e), path=str(config_path))
        return {}


def get_api_quotas(storage: PortfolioStorage) -> list[APIQuotaInfo]:
    """Get API quota information from source configuration files.

    Args:
        storage: PortfolioStorage instance

    Returns:
        List of APIQuotaInfo for each configured data source
    """
    quotas: list[APIQuotaInfo] = []

    try:
        # Load quota metadata from configuration file
        quota_map = load_quota_config()

        for source_id, quota_info in quota_map.items():
            # Check if API key is configured
            configured = is_api_key_configured(source_id, quota_info["env_var"], storage)

            # Build and append quota info
            quota_data = build_quota_info(source_id, quota_info, configured)
            quotas.append(APIQuotaInfo(**quota_data))

    except Exception as e:
        logger.error("get_api_quotas_failed", error=str(e), exc_info=True)

    return quotas


def _compute_age_days(last_updated: Any, now: datetime) -> int | None:
    """Compute age in days from last_updated value.

    Args:
        last_updated: datetime or date object, or None
        now: current UTC datetime

    Returns:
        Age in days, or None if last_updated is falsy
    """
    from datetime import date as date_type  # noqa: PLC0415

    if not last_updated:
        return None
    if isinstance(last_updated, datetime):
        return (now - last_updated).days
    if isinstance(last_updated, date_type):
        last_updated_dt = datetime.combine(last_updated, datetime.min.time(), tzinfo=UTC)
        return (now - last_updated_dt).days
    return timedelta(days=0).days


def _build_freshness_list(df: Any) -> list[DayBarFreshness]:
    """Build freshness list from query result dataframe.

    Args:
        df: Polars dataframe with symbol and last_updated columns

    Returns:
        List of DayBarFreshness entries
    """
    freshness_list: list[DayBarFreshness] = []
    now = datetime.now(UTC)
    for row in df.iter_rows(named=True):
        symbol = row["symbol"]
        last_updated = row.get("last_updated")
        age_days = _compute_age_days(last_updated, now)
        freshness_list.append(
            DayBarFreshness(symbol=symbol, last_updated=last_updated, age_days=age_days)
        )
    return freshness_list


def get_day_bars_freshness(storage: PortfolioStorage) -> list[DayBarFreshness]:
    """Get data freshness for each symbol in day_bars table.

    Args:
        storage: PortfolioStorage instance

    Returns:
        List of DayBarFreshness with last updated date per symbol
    """
    try:
        df = storage.query(
            """
            SELECT symbol, MAX(date) as last_updated
            FROM day_bars
            GROUP BY symbol
            ORDER BY symbol
            """
        )

        if df.is_empty():
            logger.info("get_day_bars_freshness_empty_table")
            return []

        freshness_list = _build_freshness_list(df)
        logger.info("get_day_bars_freshness_success", symbol_count=len(freshness_list))
        return freshness_list

    except Exception as e:
        logger.error("get_day_bars_freshness_failed", error=str(e), exc_info=True)
        return []


def get_api_key_statuses(storage: PortfolioStorage) -> list[APIKeyStatus]:
    """Get API key configuration status for all sources.

    Args:
        storage: PortfolioStorage instance

    Returns:
        List of APIKeyStatus for each configured source
    """
    import os  # noqa: PLC0415

    statuses: list[APIKeyStatus] = []

    try:
        # Load quota config to get list of sources with env vars
        quota_map = load_quota_config()

        for source_id, quota_info in quota_map.items():
            env_var = quota_info.get("env_var", "")
            configured = bool(os.environ.get(env_var))

            statuses.append(APIKeyStatus(source=source_id, configured=configured, env_var=env_var))

        statuses.sort(key=lambda x: x.source)

    except Exception as e:
        logger.error("get_api_key_statuses_failed", error=str(e), exc_info=True)

    return statuses
