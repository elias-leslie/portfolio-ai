"""Configuration loader for system capabilities registry.

This module loads and validates the capabilities_config.yaml file,
providing centralized configuration access for scanning and AI analysis.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from ..logging_config import get_logger

logger = get_logger(__name__)

# Cache for loaded config (reload only if file changes)
_cached_config: dict[str, Any] | None = None
_config_mtime: float | None = None


def load_capabilities_config() -> dict[str, Any]:
    """Load capabilities configuration from YAML file.

    Returns cached config if file hasn't changed. Validates required fields.

    Returns:
        Dict with configuration structure:
            - scan_config: Settings for scanning (enabled, schedule, targets)
            - categorization: Rules for categorizing tables/tasks
            - freshness_rules: Rules for freshness status calculation

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If required fields are missing
    """
    global _cached_config, _config_mtime  # noqa: PLW0603

    # Locate config file
    config_path = Path(__file__).parent.parent / "config" / "capabilities_config.yaml"

    if not config_path.exists():
        error_msg = f"Capabilities config file not found: {config_path}"
        logger.error("config_file_missing", path=str(config_path))
        raise FileNotFoundError(error_msg)

    # Check if we can use cached config
    current_mtime = config_path.stat().st_mtime
    if _cached_config is not None and _config_mtime == current_mtime:
        logger.debug("using_cached_capabilities_config")
        return _cached_config

    # Load config from file
    logger.info("loading_capabilities_config", path=str(config_path))

    with config_path.open() as f:
        config = yaml.safe_load(f)

    # Validate required top-level keys
    required_keys = ["scan_config", "categorization"]
    missing_keys = [key for key in required_keys if key not in config]

    if missing_keys:
        error_msg = f"Missing required config keys: {missing_keys}"
        logger.error("invalid_config_structure", missing_keys=missing_keys)
        raise ValueError(error_msg)

    # Validate scan_config structure
    if "targets" not in config["scan_config"]:
        error_msg = "scan_config.targets is required"
        logger.error("invalid_config_structure", error=error_msg)
        raise ValueError(error_msg)

    # Cache config
    _cached_config = config
    _config_mtime = current_mtime

    logger.info(
        "capabilities_config_loaded",
        scan_enabled=config["scan_config"]["enabled"],
        db_enabled=config["scan_config"]["targets"]["database"]["enabled"],
        hatchet_enabled=config["scan_config"]["targets"]["hatchet"]["enabled"],
        api_enabled=config["scan_config"]["targets"]["api"]["enabled"],
        ai_enabled=config["scan_config"].get("ai_analysis", {}).get("enabled", False),
    )

    return cast(dict[str, Any], config)


def get_expected_freshness(table_name: str) -> str:
    """Get expected freshness for a table from config.

    Args:
        table_name: Database table name

    Returns:
        Expected freshness string (e.g., "daily", "hourly", "on-demand")
        Returns "daily" as default if table not found in config.
    """
    config = load_capabilities_config()

    expected_map = (
        config.get("scan_config", {})
        .get("targets", {})
        .get("database", {})
        .get("expected_freshness", {})
    )

    return cast(str, expected_map.get(table_name, "daily"))  # Default to daily


def get_freshness_thresholds(expected_freshness: str) -> dict[str, float]:
    """Get freshness status thresholds for a given expected freshness.

    Args:
        expected_freshness: Expected freshness string ("daily", "hourly", etc.)

    Returns:
        Dict with threshold days for each status:
            - current: Days threshold for "current" status
            - acceptable: Days threshold for "acceptable" status
            - stale: Days threshold for "stale" status
            - critical: Days threshold for "critical" status
    """
    config = load_capabilities_config()

    freshness_rules = config.get("freshness_rules", {})

    # Return rule for expected_freshness, or default to "daily"
    return cast(
        dict[str, float],
        freshness_rules.get(
            expected_freshness,
            freshness_rules.get(
                "daily",
                {
                    "current": 1,
                    "acceptable": 2,
                    "stale": 7,
                    "critical": 7,
                },
            ),
        ),
    )


def categorize_by_name(name: str, config_section: str = "categorization") -> str:
    """Categorize a table/task/endpoint by name using config patterns.

    Args:
        name: Table/task/endpoint name
        config_section: Config section to use (default: "categorization")

    Returns:
        Category string (e.g., "market_data", "news", "portfolio", "analytics", "infrastructure")
        Returns "infrastructure" as default if no pattern matches.
    """
    config = load_capabilities_config()

    categorization = config.get(config_section, {})

    # Check each category's patterns
    for category, category_config in categorization.items():
        patterns = category_config.get("patterns", [])
        for pattern in patterns:
            if pattern in name.lower():
                return cast(str, category)

    # Default to infrastructure if no match
    return "infrastructure"


def reload_config() -> dict[str, Any]:
    """Force reload of configuration from file (bypass cache).

    Useful for testing or when config file is updated externally.

    Returns:
        Freshly loaded config dict
    """
    global _cached_config, _config_mtime  # noqa: PLW0603
    _cached_config = None
    _config_mtime = None
    return load_capabilities_config()
