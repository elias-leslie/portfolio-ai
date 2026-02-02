"""Vendor source configuration and initialization."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from ..logging_config import get_logger
from ..sources.base import BaseSource
from ..sources.finnhub_source import FinnhubSource
from ..sources.fmp_source import FMPSource
from ..sources.polygon_source import PolygonSource
from ..sources.rss_source import (
    CNBCRssSource,
    FinancialTimesRssSource,
    FortuneRssSource,
    GoogleNewsRssSource,
    InvestingRssSource,
    MarketWatchRssSource,
    NasdaqRssSource,
    SeekingAlphaRssSource,
)
from ..sources.sec_edgar_source import SECEdgarSource
from ..sources.yfinance_source import YFinanceSource

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)


def env_flag(name: str, default: bool = False) -> bool:
    """Parse boolean-like environment variables."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def init_free_vendor(
    vendor_name: str,
    source_cls: type[BaseSource],
    env_var: str,
    notes: str,
    storage: PortfolioStorage | None,
    default_enabled: bool = True,
    *,
    sources: list[BaseSource],
    register_callback: Any,
) -> None:
    """Initialize a free vendor (no API key required).

    Args:
        vendor_name: Vendor identifier (e.g., 'sec_edgar')
        source_cls: Source class to instantiate
        env_var: Environment variable for enable flag
        notes: Description of vendor
        storage: Storage instance (for vendors that need it)
        default_enabled: Default enable state if env var not set
        sources: List to append initialized source to
        register_callback: Function to call to register vendor
    """
    flag = env_flag(env_var, default=default_enabled)
    enabled = bool(flag)
    reason: str | None = None if flag else "disabled_by_flag"

    if enabled:
        try:
            # Pass storage to SEC EDGAR, YFinance doesn't need it
            if vendor_name == "sec_edgar" and storage is not None:
                sources.append(source_cls(storage))  # type: ignore[call-arg]
            else:
                sources.append(source_cls())
        except Exception as exc:
            reason = f"init_failed: {exc}"
            enabled = False
            logger.warning(f"{vendor_name}_source_init_failed", error=str(exc))

    register_callback(vendor_name, configured=True, enabled=enabled, notes=notes, reason=reason)


def init_api_vendor(
    vendor_name: str,
    source_cls: type[BaseSource],
    api_key_env: str,
    flag_env: str,
    notes: str | None,
    default_enabled: bool = True,
    *,
    sources: list[BaseSource],
    register_callback: Any,
) -> None:
    """Initialize a vendor requiring an API key.

    Args:
        vendor_name: Vendor identifier (e.g., 'polygon')
        source_cls: Source class to instantiate
        api_key_env: Environment variable for API key
        flag_env: Environment variable for enable flag
        notes: Description of vendor
        default_enabled: Default enable state if flag not set
        sources: List to append initialized source to
        register_callback: Function to call to register vendor
    """
    api_key = os.getenv(api_key_env)
    flag = env_flag(flag_env, default=default_enabled)
    configured = bool(api_key)
    enabled = configured and flag

    # Determine reason for disabled state
    reason: str | None = None
    if not configured:
        reason = "missing_api_key"
    elif not flag:
        reason = "disabled_by_flag"

    if enabled:
        try:
            sources.append(source_cls())
        except Exception as exc:
            reason = f"init_failed: {exc}"
            enabled = False
            logger.warning(f"{vendor_name}_news_source_init_failed", error=str(exc))

    register_callback(
        vendor_name, configured=configured, enabled=enabled, notes=notes, reason=reason
    )


def init_rss_vendors(sources: list[BaseSource], register_callback: Any) -> None:
    """Initialize all RSS news vendors.

    Args:
        sources: List to append initialized RSS sources to
        register_callback: Function to call to register vendor
    """
    rss_configs: list[tuple[str, type[BaseSource], str, str]] = [
        ("cnbc_rss", CNBCRssSource, "CNBC finance/earnings RSS feed", "CNBC_RSS_ENABLED"),
        (
            "marketwatch_rss",
            MarketWatchRssSource,
            "MarketWatch Top Stories RSS feed",
            "MARKETWATCH_RSS_ENABLED",
        ),
        (
            "nasdaq_rss",
            NasdaqRssSource,
            "Nasdaq original & symbol RSS feeds",
            "NASDAQ_RSS_ENABLED",
        ),
        ("fortune_rss", FortuneRssSource, "Fortune business RSS feed", "FORTUNE_RSS_ENABLED"),
        (
            "investing_rss",
            InvestingRssSource,
            "Investing.com market overview RSS feed",
            "INVESTING_RSS_ENABLED",
        ),
        (
            "ft_rss",
            FinancialTimesRssSource,
            "Financial Times global markets RSS feed",
            "FT_RSS_ENABLED",
        ),
        (
            "seeking_alpha_rss",
            SeekingAlphaRssSource,
            "Seeking Alpha combined RSS feed",
            "SEEKING_ALPHA_RSS_ENABLED",
        ),
        (
            "google_news_rss",
            GoogleNewsRssSource,
            "Google News aggregated market & symbol RSS feeds",
            "GOOGLE_NEWS_RSS_ENABLED",
        ),
    ]

    for vendor_name, source_cls, notes, env_var in rss_configs:
        init_free_vendor(
            vendor_name,
            source_cls,
            env_var,
            notes,
            None,
            sources=sources,
            register_callback=register_callback,
        )


def prepare_vendor_sources(
    storage: PortfolioStorage,
    vendor_sources_override: Any,
    register_callback: Any,
) -> list[BaseSource]:
    """Initialise vendor sources from overrides or environment configuration.

    Args:
        storage: Storage instance for vendors that need it
        vendor_sources_override: Optional list of sources to use instead of env config
        register_callback: Function to call to register vendor

    Returns:
        List of enabled vendor sources
    """
    sources: list[BaseSource] = []

    # Handle override sources
    if vendor_sources_override is not None:
        for source in vendor_sources_override:
            sources.append(source)
            register_callback(source.name, configured=True, enabled=True, notes=None, reason=None)
        return sources

    # Initialize primary news vendors
    init_free_vendor(
        "sec_edgar",
        SECEdgarSource,
        "SEC_EDGAR_ENABLED",
        "SEC EDGAR filings (8-K, 10-Q, 10-K, Form 4) - highest quality free source.",
        storage,
        sources=sources,
        register_callback=register_callback,
    )
    init_api_vendor(
        "polygon",
        PolygonSource,
        "POLYGON_API_KEY",
        "POLYGON_NEWS_ENABLED",
        None,
        sources=sources,
        register_callback=register_callback,
    )
    init_api_vendor(
        "finnhub",
        FinnhubSource,
        "FINNHUB_API_KEY",
        "FINNHUB_NEWS_ENABLED",
        None,
        sources=sources,
        register_callback=register_callback,
    )
    init_api_vendor(
        "fmp",
        FMPSource,
        "FMP_API_KEY",
        "FMP_NEWS_ENABLED",
        "FMP news endpoints require paid tier; enable via FMP_NEWS_ENABLED=1.",
        default_enabled=False,
        sources=sources,
        register_callback=register_callback,
    )
    init_free_vendor(
        "yfinance",
        YFinanceSource,
        "YFINANCE_NEWS_ENABLED",
        "Yahoo Finance symbol feed via yfinance; no API key required.",
        None,
        sources=sources,
        register_callback=register_callback,
    )

    # Initialize RSS vendors
    init_rss_vendors(sources, register_callback)

    return [source for source in sources if source.is_enabled()]
