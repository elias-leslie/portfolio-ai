"""Priority indicator calculation for watchlist items.

This module provides 8 priority indicator checks:
1. 🔥 Hot Opportunity - Top 3 BUY signals
2. 📋 Earnings Alert - Earnings within 7 days
3. 📰 Breaking News - 10+ articles in 24h
4. 📈 Insider Buying - Recent insider purchases
5. 📉 Negative Catalyst - News sentiment < -0.3
6. 💎 Value Play - Strong fundamentals, weak price
7. ⚡ Momentum - Strong price AND technical
8. ⚠️ Caution - Score misalignment

NO ARBITRARY CAP - All relevant indicators are returned.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from .models import WatchlistItemDict


class PriorityIndicator(BaseModel):
    """Priority indicator model."""

    icon: str  # "🔥", "📋", "📰", "📈", "📉", "💎", "⚡", "⚠️"
    label: str  # "Hot Opportunity", "Earnings Alert", etc.
    tooltip: str  # Full explanation for hover
    priority: int  # 1-8 for sorting (1 = highest)
    category: str  # "time_sensitive", "risk", "opportunity", "caution"


# Priority order constants (lower = higher priority)
PRIORITY_ORDER = {
    "hot_opportunity": 1,
    "earnings_alert": 2,
    "breaking_news": 3,
    "insider_buying": 4,
    "negative_catalyst": 5,
    "value_play": 6,
    "momentum": 7,
    "caution": 8,
}


def check_hot_opportunity(item: WatchlistItemDict, rank: int) -> PriorityIndicator | None:
    """Check if item is a top 3 BUY signal by overall score.

    Args:
        item: Watchlist item dict with signal_type and score
        rank: Item's rank by overall score (1 = highest)

    Returns:
        PriorityIndicator if top 3 BUY, else None
    """
    if item.get("signal_type") == "BUY" and rank <= 3:
        return PriorityIndicator(
            icon="🔥",
            label="Hot Opportunity",
            tooltip=(
                f"Top #{rank} highest-scoring BUY signal. "
                "Strong technical and fundamental alignment."
            ),
            priority=PRIORITY_ORDER["hot_opportunity"],
            category="opportunity",
        )
    return None


def check_earnings_alert(item: WatchlistItemDict) -> PriorityIndicator | None:
    """Check if earnings are within 7 days.

    Args:
        item: Watchlist item dict with earnings_days_away field

    Returns:
        PriorityIndicator if earnings soon, else None
    """
    days_away = item.get("earnings_days_away")
    if days_away is not None and 0 <= days_away <= 7:
        return PriorityIndicator(
            icon="📋",
            label="Earnings Alert",
            tooltip=f"Earnings report in {days_away} days. Volatility expected.",
            priority=PRIORITY_ORDER["earnings_alert"],
            category="time_sensitive",
        )
    return None


def check_breaking_news(item: WatchlistItemDict) -> PriorityIndicator | None:
    """Check if 10+ articles published in last 24h.

    Args:
        item: Watchlist item dict with news_intelligence.article_count_24h

    Returns:
        PriorityIndicator if breaking news, else None
    """
    news_intel = item.get("news_intelligence")
    if news_intel and isinstance(news_intel, dict) and news_intel.get("article_count_24h", 0) >= 10:
        count = news_intel["article_count_24h"]
        return PriorityIndicator(
            icon="📰",
            label="Breaking News",
            tooltip=f"{count} articles in 24h. Major news flow - investigate.",
            priority=PRIORITY_ORDER["breaking_news"],
            category="time_sensitive",
        )
    return None


def check_insider_buying(item: WatchlistItemDict) -> PriorityIndicator | None:
    """Check for insider trading activity from news key_events.

    Args:
        item: Watchlist item dict with news_intelligence.key_events

    Returns:
        PriorityIndicator if insider buying detected, else None
    """
    news_intel = item.get("news_intelligence")
    if not news_intel:
        return None

    key_events = news_intel.get("key_events", [])
    for event in key_events:
        if event.get("event_category") == "insider_buy":
            return PriorityIndicator(
                icon="📈",
                label="Insider Buying",
                tooltip="Recent insider purchases detected. Bullish signal.",
                priority=PRIORITY_ORDER["insider_buying"],
                category="opportunity",
            )
    return None


def check_negative_catalyst(item: WatchlistItemDict) -> PriorityIndicator | None:
    """Check if news sentiment is very negative (<-0.3).

    Args:
        item: Watchlist item dict with news_sentiment_score

    Returns:
        PriorityIndicator if bearish news, else None
    """
    sentiment = item.get("news_sentiment_score")
    if sentiment is not None and sentiment < -0.3:
        return PriorityIndicator(
            icon="📉",
            label="Negative Catalyst",
            tooltip=f"Bearish news flow (sentiment: {sentiment:.2f}). Wait for clarity.",
            priority=PRIORITY_ORDER["negative_catalyst"],
            category="risk",
        )
    return None


def check_value_play(item: WatchlistItemDict) -> PriorityIndicator | None:
    """Check if strong fundamentals but weak price action.

    Criteria: fundamental_score > 70 AND price_score < 50

    Args:
        item: Watchlist item dict with score breakdown

    Returns:
        PriorityIndicator if value opportunity, else None
    """
    score = item.get("score")
    if not score or not isinstance(score, dict):
        return None

    fundamental_obj: Any = score.get("fundamental", {})
    price_obj: Any = score.get("price", {})
    if not isinstance(fundamental_obj, dict) or not isinstance(price_obj, dict):
        return None

    fundamental = fundamental_obj.get("score")
    price = price_obj.get("score")

    if fundamental and price and fundamental > 70 and price < 50:
        return PriorityIndicator(
            icon="💎",
            label="Value Play",
            tooltip=(
                f"Strong fundamentals ({fundamental:.0f}) but low price momentum "
                f"({price:.0f}). Contrarian opportunity."
            ),
            priority=PRIORITY_ORDER["value_play"],
            category="opportunity",
        )
    return None


def check_momentum(item: WatchlistItemDict) -> PriorityIndicator | None:
    """Check if strong price AND technical momentum.

    Criteria: price_score > 70 AND technical_score > 70

    Args:
        item: Watchlist item dict with score breakdown

    Returns:
        PriorityIndicator if momentum play, else None
    """
    score = item.get("score")
    if not score or not isinstance(score, dict):
        return None

    price_obj: Any = score.get("price", {})
    technical_obj: Any = score.get("technical", {})
    if not isinstance(price_obj, dict) or not isinstance(technical_obj, dict):
        return None

    price = price_obj.get("score")
    technical = technical_obj.get("score")

    if price and technical and price > 70 and technical > 70:
        return PriorityIndicator(
            icon="⚡",
            label="Momentum",
            tooltip=(
                f"Strong price ({price:.0f}) and technical ({technical:.0f}) momentum. Trend play."
            ),
            priority=PRIORITY_ORDER["momentum"],
            category="opportunity",
        )
    return None


def check_caution(item: WatchlistItemDict) -> PriorityIndicator | None:
    """Check for score misalignment between price and fundamentals.

    Criteria:
    - Price > 70 AND fundamental < 40 (overpriced)
    - Price < 30 AND fundamental > 70 (underpriced but falling)

    Args:
        item: Watchlist item dict with score breakdown

    Returns:
        PriorityIndicator if mixed signals, else None
    """
    score = item.get("score")
    if not score or not isinstance(score, dict):
        return None

    price_obj: Any = score.get("price", {})
    fundamental_obj: Any = score.get("fundamental", {})
    if not isinstance(price_obj, dict) or not isinstance(fundamental_obj, dict):
        return None

    price = price_obj.get("score")
    fundamental = fundamental_obj.get("score")

    if not price or not fundamental:
        return None

    if (price > 70 and fundamental < 40) or (price < 30 and fundamental > 70):
        return PriorityIndicator(
            icon="⚠️",
            label="Caution",
            tooltip=(
                f"Score mismatch (price: {price:.0f}, fundamental: {fundamental:.0f}). "
                "Mixed signals - wait for confirmation."
            ),
            priority=PRIORITY_ORDER["caution"],
            category="caution",
        )
    return None


def calculate_priority_indicators(
    all_items: list[WatchlistItemDict],
    current_item: WatchlistItemDict,
) -> list[PriorityIndicator]:
    """Calculate priority indicators for a watchlist item.

    NO ARBITRARY CAP - returns ALL applicable indicators, sorted by priority.

    Args:
        all_items: All watchlist items (for ranking hot opportunities)
        current_item: Item being evaluated

    Returns:
        List of priority indicators, sorted by priority (highest first)
    """
    # Rank items by overall score for hot_opportunity check
    # Filter out None values first
    valid_items = [item for item in all_items if item is not None]
    sorted_items = sorted(
        valid_items,
        key=lambda x: (x.get("score") or {}).get("overall", 0),
        reverse=True,
    )
    rank = sorted_items.index(current_item) + 1 if current_item in sorted_items else 999

    # Run all 8 indicator checks
    checks = [
        check_hot_opportunity(current_item, rank),
        check_earnings_alert(current_item),
        check_breaking_news(current_item),
        check_insider_buying(current_item),
        check_negative_catalyst(current_item),
        check_value_play(current_item),
        check_momentum(current_item),
        check_caution(current_item),
    ]

    # Collect non-None results
    indicators = [ind for ind in checks if ind is not None]

    # Sort by priority (1 = highest)
    indicators.sort(key=lambda x: x.priority)

    return indicators
