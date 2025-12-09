"""API Sources endpoint for programmatic access to data source capabilities.

This endpoint provides agents and developers with comprehensive information
about available data source APIs, their capabilities, and rate limits.

Usage by agents:
    GET /api/sources - List all sources with capabilities
    GET /api/sources/{provider} - Detailed endpoint info for specific provider
    GET /api/sources/routing/{data_type} - Get routing recommendations for data type
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException

from ..logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/sources", tags=["sources"])

# Cache the YAML config
_sources_cache: dict[str, Any] | None = None


def _load_sources_config() -> dict[str, Any]:
    """Load and cache the API sources registry YAML."""
    global _sources_cache  # noqa: PLW0603

    if _sources_cache is not None:
        return _sources_cache

    config_path = Path(__file__).parent.parent / "config" / "api-sources-registry.yaml"

    if not config_path.exists():
        logger.error("api_sources_config_not_found", path=str(config_path))
        raise FileNotFoundError(f"API sources config not found: {config_path}")

    with config_path.open() as f:
        _sources_cache = yaml.safe_load(f)

    logger.info("api_sources_config_loaded", path=str(config_path))
    return _sources_cache


@router.get("")
@router.get("/")
def list_sources() -> dict[str, Any]:
    """List all available data source providers with summary info.

    Returns:
        Dict with providers list and data routing recommendations

    Example response:
        {
            "providers": [
                {
                    "name": "yfinance",
                    "tier": "FREE",
                    "api_key_required": false,
                    "rate_limits": {"per_minute": null, "per_day": null},
                    "capabilities": ["ohlcv", "fundamentals", "news", "reference"],
                    "gap_coverage": ["GAP-003", "GAP-006", "GAP-007", "GAP-033"]
                },
                ...
            ],
            "data_routing": {...},
            "version": "1.1.0"
        }
    """
    try:
        config = _load_sources_config()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail="API sources config not found") from e

    providers_list = []
    for name, provider in config.get("providers", {}).items():
        # Extract capabilities
        capabilities = []
        for cap, enabled in provider.get("capabilities", {}).items():
            if enabled:
                capabilities.append(cap)

        # Extract GAP coverage from endpoints
        gap_coverage = set()
        for endpoint in provider.get("endpoints", {}).values():
            if isinstance(endpoint, dict):
                gap_id = endpoint.get("gap_id")
                if gap_id:
                    # Handle single or comma-separated GAP IDs
                    for gid in str(gap_id).split(","):
                        gap_coverage.add(gid.strip())

        providers_list.append(
            {
                "name": name,
                "display_name": provider.get("name", name),
                "tier": provider.get("tier", "FREE"),
                "api_key_required": provider.get("api_key_required", True),
                "priority": provider.get("priority", 99),
                "rate_limits": provider.get("rate_limits", {}),
                "capabilities": capabilities,
                "gap_coverage": sorted(gap_coverage),
                "use_cases": provider.get("use_cases", []),
            }
        )

    # Sort by priority
    providers_list.sort(key=lambda x: x["priority"])

    return {
        "version": config.get("version", "1.0.0"),
        "providers": providers_list,
        "data_routing": config.get("data_routing", {}),
        "credentials": config.get("credentials", {}),
    }


@router.get("/{provider}")
def get_source_detail(provider: str) -> dict[str, Any]:
    """Get detailed endpoint information for a specific provider.

    Args:
        provider: Provider name (e.g., 'yfinance', 'finnhub', 'polygon')

    Returns:
        Dict with full provider configuration including all endpoints

    Example response:
        {
            "name": "yfinance",
            "tier": "FREE",
            "endpoints": {
                "history": {...},
                "info": {...},
                "earnings_history": {...}
            },
            "premium_only": [...],
            "implementation": {...}
        }
    """
    try:
        config = _load_sources_config()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail="API sources config not found") from e

    providers = config.get("providers", {})

    if provider not in providers:
        available = list(providers.keys())
        raise HTTPException(
            status_code=404, detail=f"Provider '{provider}' not found. Available: {available}"
        )

    provider_config = providers[provider]

    # Get implementation file path from config
    implementation = config.get("implementation", {})
    adapter_path = implementation.get("adapters", {}).get(provider, "")

    return {
        "name": provider,
        "display_name": provider_config.get("name", provider),
        "tier": provider_config.get("tier", "FREE"),
        "api_key_required": provider_config.get("api_key_required", True),
        "env_var": provider_config.get("env_var"),
        "db_key": provider_config.get("db_key"),
        "priority": provider_config.get("priority", 99),
        "rate_limits": provider_config.get("rate_limits", {}),
        "data_delay": provider_config.get("data_delay"),
        "capabilities": provider_config.get("capabilities", {}),
        "endpoints": provider_config.get("endpoints", {}),
        "premium_only": provider_config.get("premium_only", []),
        "use_cases": provider_config.get("use_cases", []),
        "implementation_file": adapter_path,
    }


@router.get("/routing/{data_type}")
def get_data_routing(data_type: str) -> dict[str, Any]:
    """Get recommended providers for a specific data type.

    Args:
        data_type: Type of data needed (e.g., 'ohlcv_daily', 'fundamentals', 'news')

    Returns:
        Dict with primary and fallback providers for the data type
    """
    try:
        config = _load_sources_config()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail="API sources config not found") from e

    routing = config.get("data_routing", {})

    if data_type not in routing:
        available = list(routing.keys())
        raise HTTPException(
            status_code=404, detail=f"Data type '{data_type}' not found. Available: {available}"
        )

    return {"data_type": data_type, "routing": routing[data_type]}
