"""Data sources for portfolio-ai.

This module provides data sources for news and macroeconomic indicators.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..logging_config import get_logger

if TYPE_CHECKING:
    from .base import BaseSource

from .fred import FREDSource

logger = get_logger(__name__)

# Module-level cache for data sources (expensive to recreate per task)
_cached_sources: list[BaseSource] | None = None


def initialize_data_sources() -> list[BaseSource]:
    """Initialize all available OHLCV data sources for multi-source fetching.

    Only instantiates sources that have their API keys configured.
    YFinanceSource is always included as it doesn't require an API key.

    Returns:
        List of configured data source instances in priority order:
        1. YFinance (no API key needed)
        2. TwelveData
        3. FMP
        4. Polygon
        5. Finnhub
        6. AlphaVantage
    """
    global _cached_sources  # noqa: PLW0603
    if _cached_sources is not None:
        return _cached_sources

    # Import here to avoid circular imports (lazy loading pattern)
    from .alphavantage_source import AlphaVantageSource  # noqa: PLC0415
    from .finnhub_source import FinnhubSource  # noqa: PLC0415
    from .fmp_source import FMPSource  # noqa: PLC0415
    from .polygon_source import PolygonSource  # noqa: PLC0415
    from .twelvedata_source import TwelveDataSource  # noqa: PLC0415
    from .yfinance_source import YFinanceSource  # noqa: PLC0415

    sources: list[BaseSource] = []
    source_names: list[str] = []
    skipped_sources: list[str] = []

    # YFinanceSource doesn't require API key - always available
    sources.append(YFinanceSource())
    source_names.append("yfinance")

    # Try to initialize other sources - skip if API key missing
    source_classes = [
        ("twelvedata", TwelveDataSource),
        ("fmp", FMPSource),
        ("polygon", PolygonSource),
        ("finnhub", FinnhubSource),
        ("alphavantage", AlphaVantageSource),
    ]

    for name, source_class in source_classes:
        try:
            source = source_class()
            sources.append(source)
            source_names.append(name)
            logger.debug("data_source_initialized", source=source_class.__name__)
        except (RuntimeError, ValueError) as e:
            # API key not configured - skip this source
            skipped_sources.append(name)
            logger.info(
                "data_source_skipped",
                source=source_class.__name__,
                reason=str(e),
            )

    logger.info(
        "data_sources_initialized",
        sources=source_names,
        skipped=skipped_sources,
        count=len(sources),
    )

    _cached_sources = sources
    return sources


__all__ = ["FREDSource", "initialize_data_sources"]
