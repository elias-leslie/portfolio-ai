"""Load API credentials from database into environment variables at startup.

This module ensures that API keys stored in the source_credentials table
are loaded into os.environ so that source adapters can access them via os.getenv().
"""

from __future__ import annotations

import os

from ..logging_config import get_logger
from .facade import get_storage

logger = get_logger(__name__)


def load_credentials_from_database() -> None:
    """Load all API credentials from database into environment variables.

    This function is called at application startup to ensure that API keys
    stored in the database are available via os.getenv() for source adapters.

    Raises:
        Exception: If database query fails (logged, not raised)
    """
    try:
        storage = get_storage()

        # Query all credentials from database
        df = storage.query(
            """
            SELECT source_id, field, value
            FROM source_credentials
            ORDER BY source_id, field
            """
        )

        if df.is_empty():
            logger.warning(
                "credential_loader_no_credentials",
                message="No credentials found in database",
            )
            return

        # Map source_id + field to environment variable names
        # This mapping should match what source adapters expect
        env_var_mappings = {
            ("twelvedata", "apikey"): "TWELVEDATA_API_KEY",
            ("fmp", "apikey"): "FMP_API_KEY",
            ("polygon", "apiKey"): "POLYGON_API_KEY",
            ("polygon", "apikey"): "POLYGON_API_KEY",  # Handle case variations
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

        loaded = 0
        skipped = 0

        for row in df.iter_rows(named=True):
            source_id = row["source_id"]
            field = row["field"]
            value = row["value"]

            # Get environment variable name
            env_var = env_var_mappings.get((source_id, field))

            if env_var:
                # Only set if not already in environment (don't override)
                if env_var not in os.environ:
                    os.environ[env_var] = value
                    loaded += 1
                    logger.debug(
                        "credential_loaded",
                        source=source_id,
                        field=field,
                        env_var=env_var,
                    )
                else:
                    skipped += 1
                    logger.debug(
                        "credential_skipped_already_set",
                        source=source_id,
                        field=field,
                        env_var=env_var,
                    )
            else:
                logger.warning(
                    "credential_no_mapping",
                    source=source_id,
                    field=field,
                    message=f"No environment variable mapping for {source_id}.{field}",
                )

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
        # Don't raise - allow app to start even if credential loading fails
