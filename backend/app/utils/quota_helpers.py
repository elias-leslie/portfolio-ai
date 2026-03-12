"""Helper functions for API quota management.

This module provides utilities for checking API key configuration
and managing quota information for external data sources.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..storage.facade import PortfolioStorage

logger = get_logger(__name__)


def is_api_key_configured(
    source_id: str,
    env_var: str,
    storage: PortfolioStorage,
) -> bool:
    """Check if an API key is configured for a given source.

    Checks database first, then falls back to environment variable.

    Args:
        source_id: Source identifier (e.g., "twelvedata", "polygon")
        env_var: Environment variable name for the API key
        storage: Storage instance for database queries

    Returns:
        True if API key is configured and not a placeholder value
    """
    # Check database first
    try:
        cred_df = storage.query(
            "SELECT value FROM source_credentials WHERE source_id = ? AND field = 'apikey'",
            [source_id],
        )
        if not cred_df.is_empty():
            db_value = cred_df.to_dicts()[0]["value"]
            # Database has a row: return True only if value is valid (non-empty, non-placeholder)
            return bool(db_value and db_value not in ("your_key_here", "PLACEHOLDER"))
    except Exception as e:
        logger.debug("api_key_db_check_failed", source_id=source_id, error=str(e))

    # Fall back to environment variable
    key_value = os.getenv(env_var, "")
    return bool(key_value and key_value not in ("your_key_here", "PLACEHOLDER"))


def build_quota_info(
    source_id: str,
    quota_config: dict[str, Any],
    configured: bool,
) -> dict[str, Any]:
    """Build APIQuotaInfo dictionary from quota configuration.

    Args:
        source_id: Source identifier
        quota_config: Quota configuration dict with rate_limit, daily_limit, capacity
        configured: Whether the API key is configured

    Returns:
        Dictionary suitable for APIQuotaInfo model initialization
    """
    return {
        "source_name": source_id,
        "configured": configured,
        "rate_limit": quota_config.get("rate_limit"),
        "daily_limit": quota_config.get("daily_limit"),
        "estimated_capacity": quota_config.get("capacity"),
    }
