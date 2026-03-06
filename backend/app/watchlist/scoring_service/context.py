"""Scoring context initialization for watchlist refresh operations.

This module handles:
- Scoring context setup and initialization
- Credentials and preferences loading
- Pre-fetching of price and news data
- Service setup and configuration
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ...logging_config import get_logger
from ...portfolio.price_fetcher import PriceDataFetcher
from ...services import NewsService
from ...storage import PortfolioStorage
from ...storage.credential_loader import load_credentials_from_database
from ...utils.preferences_loader import UserPreferences
from ..models import ScoreWeights, TechnicalSnapshot
from .batch_loader import (
    fetch_news_batch,
    fetch_prices_in_batches,
    load_latest_technical,
    load_watchlist_items,
    trigger_auto_backfill,
)
from .redis_tracker import init_refresh_status

logger = get_logger(__name__)


# NOTE: User preferences loading moved to UserPreferences.load_all()
# in app.utils.preferences_loader to eliminate duplicate queries (Issue #3)


def initialize_scoring_context(
    storage: PortfolioStorage,
    symbols: list[str],
    account_id: str | None,
    price_fetcher: PriceDataFetcher | None,
    news_service: NewsService | None,
    batch_size: int,
    batch_delay_seconds: float,
) -> tuple[
    pl.DataFrame,
    int,
    str,
    PriceDataFetcher,
    UserPreferences,
    NewsService,
    dict[str, TechnicalSnapshot],
    ScoreWeights,
    int,
    float,
    dict[str, Any],
    int,
    dict[str, Any],
]:
    """Initialize all context needed for watchlist scoring.

    Args:
        storage: Database storage instance
        symbols: Sorted list of watchlist symbols (already fetched)
        account_id: Optional account ID
        price_fetcher: Optional price fetcher instance
        batch_size: Batch size for price fetching
        batch_delay_seconds: Delay between batches

    Returns:
        Tuple containing:
        - items_df: DataFrame with watchlist items
        - total_items: Count of total items
        - redis_key: Redis key for progress tracking
        - fetcher: Price data fetcher instance
        - prefs: User preferences
        - news_service: News service instance
        - technical_map: Technical indicators for symbols
        - default_weights: Score weights from preferences
        - stale_ttl_minutes: Stale data TTL
        - risk_budget: Risk budget from preferences
        - price_map: Pre-fetched price data for all symbols
        - total_batches: Number of price fetch batches
        - news_bundles: Pre-fetched news for all symbols
    """

    # Load full item data for processing (we still need IDs for snapshots)
    items_df = load_watchlist_items(storage, account_id)
    total_items = len(items_df)

    # AUTO-BACKFILL: Check for missing or stale historical data
    trigger_auto_backfill(storage, symbols)

    # Initialize refresh status in Redis
    redis_key = init_refresh_status(account_id, symbols, total_items)

    # Setup fetcher and load credentials
    fetcher = price_fetcher or PriceDataFetcher(storage)
    load_credentials_from_database()

    # Load ALL user preferences in ONE query (Issue #3 fix)
    prefs = UserPreferences.load_all(storage)

    # Setup news service with preferences
    resolved_news_service = news_service or NewsService(storage)
    resolved_news_service.lookback_hours = prefs.news_lookback_hours
    news_max_articles = prefs.news_max_articles

    # Load technical indicators and extract preferences
    technical_map = load_latest_technical(storage, symbols)
    default_weights = ScoreWeights(
        price=prefs.watchlist_price_weight,
        technical=prefs.watchlist_technical_weight,
    )
    stale_ttl_minutes = prefs.get_stale_ttl_minutes()
    risk_budget = prefs.watchlist_risk_budget

    # Batch-fetch price data and news BEFORE processing loop
    price_map = fetch_prices_in_batches(fetcher, symbols, batch_size, batch_delay_seconds)
    total_batches = len([symbols[i : i + batch_size] for i in range(0, len(symbols), batch_size)])
    news_bundles = fetch_news_batch(resolved_news_service, symbols, news_max_articles)

    return (
        items_df,
        total_items,
        redis_key,
        fetcher,
        prefs,
        resolved_news_service,
        technical_map,
        default_weights,
        stale_ttl_minutes,
        risk_budget,
        price_map,
        total_batches,
        news_bundles,
    )
