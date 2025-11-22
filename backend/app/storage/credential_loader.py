"""Load API credentials from database into environment variables at startup.

This module ensures that API keys stored in the source_credentials table
are loaded into os.environ so that source adapters can access them via os.getenv().
"""

from __future__ import annotations

import os

from ..logging_config import get_logger
from .facade import get_storage

logger = get_logger(__name__)

# Map source_id + field to environment variable names (what source adapters expect)
ENV_VAR_MAPPINGS = {
    ("twelvedata", "apikey"): "TWELVEDATA_API_KEY",
    ("fmp", "apikey"): "FMP_API_KEY",
    ("polygon", "apiKey"): "POLYGON_API_KEY",
    ("polygon", "apikey"): "POLYGON_API_KEY",  # Case variation
    ("finnhub", "token"): "FINNHUB_API_KEY",
    ("finnhub", "apikey"): "FINNHUB_API_KEY",
    ("alphavantage", "apikey"): "ALPHAVANTAGE_API_KEY",
    ("fred", "api_key"): "FRED_API_KEY",
    ("newsapi", "apiKey"): "NEWSAPI_KEY",
    ("stockdata", "api_token"): "STOCKDATA_API_TOKEN",
    ("alpaca", "api_key"): "ALPACA_API_KEY",
    ("alpaca", "key_id"): "ALPACA_KEY_ID",
    ("alpaca", "secret_key"): "ALPACA_SECRET_KEY",
    ("yfinance", "apikey"): "YFINANCE_KEY",
}


def _load_single_credential(source_id: str, field: str, value: str) -> tuple[bool, bool]:
    """Load a single credential into environment.

    Returns:
        (loaded, skipped) - True if loaded, True if skipped (already set)
    """
    env_var = ENV_VAR_MAPPINGS.get((source_id, field))

    if not env_var:
        logger.warning(
            "credential_no_mapping",
            source=source_id,
            field=field,
            message=f"No environment variable mapping for {source_id}.{field}",
        )
        return False, False

    if env_var in os.environ:
        logger.debug(
            "credential_skipped_already_set",
            source=source_id,
            field=field,
            env_var=env_var,
        )
        return False, True

    os.environ[env_var] = value
    logger.debug("credential_loaded", source=source_id, field=field, env_var=env_var)
    return True, False


def load_credentials_from_database() -> None:
    """Load all API credentials from database into environment variables (see ENV_VAR_MAPPINGS)."""
    try:
        storage = get_storage()

        df = storage.query(
            "SELECT source_id, field, value FROM source_credentials ORDER BY source_id, field"
        )

        if df.is_empty():
            logger.warning(
                "credential_loader_no_credentials",
                message="No credentials found in database",
            )
            return

        loaded = 0
        skipped = 0

        for row in df.iter_rows(named=True):
            was_loaded, was_skipped = _load_single_credential(
                row["source_id"], row["field"], row["value"]
            )
            if was_loaded:
                loaded += 1
            if was_skipped:
                skipped += 1

        logger.info(
            "credentials_loaded_from_database",
            loaded=loaded,
            skipped=skipped,
            total=len(df),
        )

    except Exception as e:
        logger.error(
            "credential_loader_failed",
            error=str(e),
            message="Failed to load credentials from database",
        )
