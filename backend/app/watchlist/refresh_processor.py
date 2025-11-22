"""Per-ticker processing logic for watchlist refresh.

This module handles the per-ticker data gathering and snapshot creation
during watchlist refresh operations.

Extracted from scoring_service.py to reduce file size and improve modularity.

Architecture:
- refresh_data_fetchers.py: Data fetching (fundamentals, volume, news, price changes)
- refresh_narrative.py: Signal classification and narrative generation
- refresh_builders.py: Snapshot building and payload preparation
- refresh_processor.py (this file): Main orchestration

"""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict

from ..logging_config import get_logger
from ..portfolio.models import PriceData
from ..services import NewsService
from ..services.news_models import NewsBundle
from ..storage import PortfolioStorage
from .models import ScoreWeights, TechnicalSnapshot, WatchlistScoreInputs, WatchlistSnapshot
from .refresh_builders import (
    build_recent_news_payload,
    build_watchlist_snapshot,
    handle_price_change_and_backfill,
    prepare_technical_snapshot,
)
from .refresh_data_fetchers import fetch_auxiliary_data, fetch_fundamentals_and_earnings
from .refresh_narrative import generate_narrative_and_trade_levels
from .scoring import calculate_watchlist_scores

logger = get_logger(__name__)


class ProcessorConfig(TypedDict):
    """Configuration parameters for ticker processing.

    Attributes:
        default_weights: Score weights from user preferences
        stale_ttl_minutes: Staleness threshold in minutes
        risk_budget: Risk budget for position sizing (0.0-1.0)
        max_news_articles: Maximum articles to fetch per ticker
        now: Current timestamp (UTC) for consistency
    """

    default_weights: ScoreWeights
    stale_ttl_minutes: int
    risk_budget: float
    max_news_articles: int
    now: datetime


class TickerInputData(TypedDict):
    """Input data for ticker processing.

    Attributes:
        price_data: Price data object from PriceDataFetcher
        technical_map: Map of symbol -> TechnicalSnapshot
        news_bundle: Optional pre-fetched NewsBundle (for batch optimization)
    """

    price_data: PriceData
    technical_map: dict[str, TechnicalSnapshot]
    news_bundle: NewsBundle | None


def process_ticker_snapshot(
    storage: PortfolioStorage,
    symbol: str,
    item_id: str,
    input_data: TickerInputData,
    config: ProcessorConfig,
    news_service: NewsService,
) -> WatchlistSnapshot:
    """Process ticker and generate watchlist snapshot.

    This is the main orchestration function that coordinates:
    1. Price change calculation and backfill detection
    2. Technical snapshot preparation
    3. Fundamental and earnings data fetching
    4. Scoring (3-pillar: price/technical/fundamental)
    5. Auxiliary data fetching (volume, SMA5, news)
    6. Narrative generation and trade level calculation
    7. Final snapshot building

    Args:
        storage: Database storage instance
        symbol: Ticker symbol
        item_id: Watchlist item ID
        input_data: TickerInputData with price_data, technical_map, news_bundle
        config: ProcessorConfig with weights, TTL, risk budget, etc.
        news_service: NewsService instance for fetching news

    Returns:
        Complete WatchlistSnapshot ready to persist
    """
    # Extract input data
    price_data, technical_map, news_bundle = (
        input_data["price_data"],
        input_data["technical_map"],
        input_data["news_bundle"],
    )

    # Extract config
    default_weights, stale_ttl_minutes, risk_budget, max_news_articles, now = (
        config["default_weights"],
        config["stale_ttl_minutes"],
        config["risk_budget"],
        config["max_news_articles"],
        config["now"],
    )

    # Step 1: Calculate price change and queue backfill if needed
    change_pct = handle_price_change_and_backfill(storage, symbol, price_data.price, item_id)

    # Step 2: Get technical snapshot with current price
    technical_snapshot = prepare_technical_snapshot(technical_map, symbol, price_data.price)

    # Step 3: Fetch fundamentals and earnings data
    (
        fundamentals_data,
        company_health_str,
        earnings_date_obj,
        earnings_days_away_val,
    ) = fetch_fundamentals_and_earnings(storage, symbol, now)

    # Step 4: Calculate scores (3-pillar: price/technical/fundamental)
    breakdown = calculate_watchlist_scores(
        WatchlistScoreInputs(
            price=price_data,
            price_change_pct=change_pct,
            technical=technical_snapshot,
            fundamental=fundamentals_data,
            weights=default_weights,
            now=now,
            stale_ttl_minutes=stale_ttl_minutes,
        )
    )

    # Step 5: Fetch auxiliary data (volume, SMA5, news)
    current_volume, avg_volume_20d, sma_5_prev, news_sentiment_value, news_bundle_result = (
        fetch_auxiliary_data(storage, news_service, symbol, max_news_articles, news_bundle)
    )

    # Build recent news payload if we have a news bundle
    recent_news_value: dict[str, Any] | None = None
    if news_bundle_result:
        recent_news_value = build_recent_news_payload(news_bundle_result)

    # Step 6: Generate narrative intelligence and calculate trade levels
    narrative_result = generate_narrative_and_trade_levels(
        storage=storage,
        symbol=symbol,
        price_data=price_data,
        technical_snapshot=technical_snapshot,
        current_volume=current_volume,
        avg_volume_20d=avg_volume_20d,
        sma_5_prev=sma_5_prev,
        company_health_str=company_health_str,
        news_sentiment_value=news_sentiment_value,
        earnings_days_away_val=earnings_days_away_val,
        fundamentals_data=fundamentals_data,
        risk_budget=risk_budget,
    )

    # Step 7: Build and return final snapshot
    return build_watchlist_snapshot(
        item_id=item_id,
        now=now,
        price_data=price_data,
        change_pct=change_pct,
        breakdown=breakdown,
        narrative_result=narrative_result,
        company_health_str=company_health_str,
        earnings_date_obj=earnings_date_obj,
        earnings_days_away_val=earnings_days_away_val,
        news_sentiment_value=news_sentiment_value,
        recent_news_value=recent_news_value,
    )
