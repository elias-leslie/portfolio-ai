"""Watchlist CRUD service for managing watchlist items and retrieving scores.

This module handles:
- Watchlist item CRUD operations
- Score retrieval and display
- Item management through the WatchlistService class
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from ..logging_config import get_logger
from ..portfolio.price_fetcher import PriceDataFetcher
from ..storage import PortfolioStorage
from ..utils.preferences_loader import UserPreferences
from .data_loaders import (
    load_default_weights,
    load_latest_technical,
    load_stale_ttl_minutes,
)
from .models import (
    KeyEvent,
    NewsIntelligence,
    TechnicalSnapshot,
    WatchlistScoreInputs,
    WatchlistSnapshot,
)
from .priority import calculate_priority_indicators
from .refresh_builders import _extract_article_publisher, _extract_article_vendor
from .scoring import _is_stale as scoring_is_stale
from .scoring import calculate_watchlist_scores
from .watchlist_repository import WatchlistRepository

logger = get_logger(__name__)


def _format_time_ago(dt: datetime | None) -> str:
    """Format datetime as 'X hours/days ago'."""
    if dt is None:
        return "unknown"

    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    delta = now - dt
    hours = delta.total_seconds() / 3600

    if hours < 1:
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if hours < 24:
        hours_int = int(hours)
        return f"{hours_int} hour{'s' if hours_int != 1 else ''} ago"
    days = int(hours / 24)
    return f"{days} day{'s' if days != 1 else ''} ago"


def _get_event_icon(event_category: str | None, is_material: bool) -> str:
    """Get icon for event category."""
    if not event_category:
        return "📰"

    # Map event categories to icons
    icon_map = {
        "earnings": "📋",
        "insider_buy": "📈",
        "insider_sell": "📉",
        "analyst_upgrade": "📈",
        "analyst_downgrade": "📉",
        "m_and_a": "🤝",
        "exec_change": "👔",
        "fda_approval": "✅",
        "fda_rejection": "❌",
        "lawsuit": "⚖️",
        "guidance_raised": "📈",
        "guidance_lowered": "📉",
        "dividend": "💰",
        "sec_investigation": "⚠️",
    }

    # Match category prefix
    for prefix, icon in icon_map.items():
        if event_category.startswith(prefix):
            return icon

    return "⚠️" if is_material else "📰"


def _normalize_recent_news_payload(news_payload: dict[str, Any]) -> dict[str, Any]:
    """Ensure vendor + publisher metadata is surfaced for stored news payloads."""
    if not isinstance(news_payload, dict):
        return news_payload

    articles = news_payload.get("articles")
    if not isinstance(articles, list):
        return news_payload

    normalized_articles: list[dict[str, Any]] = []
    changed = False

    for article in articles:
        if not isinstance(article, dict):
            normalized_articles.append(article)
            continue

        normalized_article = dict(article)

        vendor = _extract_article_vendor(normalized_article)
        if vendor and vendor != normalized_article.get("vendor"):
            normalized_article["vendor"] = vendor
            changed = True

        publisher = _extract_article_publisher(normalized_article)
        if publisher and publisher != normalized_article.get("source"):
            normalized_article["source"] = publisher
            changed = True

        if normalized_article.setdefault(
            "publisher", normalized_article.get("source")
        ) != article.get("publisher"):
            changed = True

        normalized_articles.append(normalized_article)

    if not changed:
        return news_payload

    payload = dict(news_payload)
    payload["articles"] = normalized_articles
    return payload


def _calculate_price_change(
    storage: PortfolioStorage, symbol: str, price: float | None, item_id: str | None = None
) -> tuple[float | None, bool]:
    """Calculate price change percentage for a symbol.

    Returns:
        Tuple of (change_pct, has_historical_data)
    """
    if price is None or price <= 0:
        return (None, False)

    # Try day_bars historical data first
    df = storage.query(
        """
        SELECT close
        FROM day_bars
        WHERE ticker = ?
        ORDER BY date DESC
        LIMIT 2
        """,
        [symbol],
    )
    if df.height >= 2:
        prev_close = df["close"][1]
        if prev_close not in (0, None):
            return (float((price - prev_close) / prev_close * 100.0), True)

    # Fallback: Use previous watchlist snapshot
    if item_id:
        snapshot_df = storage.query(
            """
            SELECT price
            FROM watchlist_snapshots
            WHERE item_id = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            [item_id],
        )
        if snapshot_df.height > 0:
            prev_price = snapshot_df["price"][0]
            if prev_price and prev_price > 0:
                return (float((price - prev_price) / prev_price * 100.0), False)

    return (None, False)


class WatchlistService:
    """Service layer for watchlist operations."""

    def __init__(self, storage: PortfolioStorage):
        """Initialize watchlist service."""
        self.storage = storage
        self.price_fetcher = PriceDataFetcher(storage)
        self.repo = WatchlistRepository(storage)

    def _parse_json_field(self, value: Any) -> dict[str, Any] | None:
        """Parse JSON field if it's a string, otherwise return as-is.

        Args:
            value: Field value (might be string, dict, or None)

        Returns:
            Parsed dictionary or None if parsing fails
        """
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else None
            except (json.JSONDecodeError, TypeError):
                return None
        return value if isinstance(value, dict) else None

    def _add_staleness_info(
        self,
        raw_metrics: dict[str, Any],
        fetched_at: datetime | None,
        stale_ttl_minutes: int,
    ) -> None:
        """Add staleness information to raw_metrics in place.

        Args:
            raw_metrics: Metrics dictionary to update
            fetched_at: When metrics were fetched
            stale_ttl_minutes: TTL for staleness check
        """
        if not fetched_at or not isinstance(raw_metrics, dict):
            return

        if isinstance(fetched_at, datetime) and fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)

        current_time = datetime.now(UTC)
        fetched_at_iso = fetched_at.isoformat().replace("+00:00", "Z")

        for metric_type in ["price", "technical"]:
            if metric_type in raw_metrics and isinstance(raw_metrics[metric_type], dict):
                raw_metrics[metric_type]["stale"] = scoring_is_stale(
                    fetched_at, stale_ttl_minutes, current_time
                )
                raw_metrics[metric_type]["updated_at"] = fetched_at_iso

    def _build_snapshot_data(
        self,
        item_data: dict[str, Any],
        row: dict[str, Any],
        stale_ttl_minutes: int,
    ) -> None:
        """Build and add snapshot data to item_data in place.

        Args:
            item_data: Item dictionary to update
            row: Database row with snapshot fields
            stale_ttl_minutes: TTL for staleness check
        """
        # Parse JSON fields
        raw_metrics = self._parse_json_field(row.get("raw_metrics", {})) or {}
        news_payload = self._parse_json_field(row.get("recent_news_headlines"))

        # Add staleness info
        fetched_at = row.get("fetched_at")
        self._add_staleness_info(raw_metrics, fetched_at, stale_ttl_minutes)

        # Check for score alert
        alert = self._check_score_alert(row["id"], row["overall_score"])

        # Build score dict (only if we have valid metric data)
        # Empty dicts cause Pydantic validation errors in ScoreComponentResponse
        price_data = raw_metrics.get("price")
        tech_data = raw_metrics.get("technical")
        fund_data = raw_metrics.get("fundamental")

        # Only include score if we have at least price or technical data with required fields
        if (price_data and "score" in price_data) or (tech_data and "score" in tech_data):
            item_data["score"] = {
                "price": price_data if (price_data and "score" in price_data) else {},
                "technical": tech_data if (tech_data and "score" in tech_data) else {},
                "fundamental": fund_data if (fund_data and "score" in fund_data) else {},
                "overall": row["overall_score"],
            }
        else:
            # No valid score data - set to None so response builder can handle it
            item_data["score"] = None

        item_data["score_alert"] = alert

        # Add all narrative and trading fields
        narrative_fields = [
            "signal_type",
            "signal_strength",
            "narrative_headline",
            "recommended_style",
            "style_confidence",
            "optimal_holding_period",
            "risk_level",
            "entry_price",
            "stop_loss",
            "profit_target",
            "position_size_shares",
            "narrative_action_plan",
            "narrative_position_sizing",
            "narrative_company_health",
            "narrative_special_notes",
            "company_health",
            "news_sentiment_score",
        ]

        for field in narrative_fields:
            item_data[field] = row.get(field)

        # Special handling for earnings_date (convert to ISO string)
        earnings_date_value = row.get("earnings_date")
        item_data["earnings_date"] = (
            earnings_date_value.isoformat() if earnings_date_value is not None else None
        )
        item_data["earnings_days_away"] = row.get("earnings_days_away")
        item_data["recent_news"] = news_payload

    def _format_timestamp(self, ts: Any) -> Any:
        """Format timestamp to ISO string if it has isoformat method."""
        if hasattr(ts, "isoformat"):
            return ts.isoformat()
        return ts

    def _build_base_item_data(self, row: dict[str, Any]) -> dict[str, Any]:
        """Build base watchlist item data from query row."""
        return {
            "id": row["id"],
            "symbol": row["symbol"],
            "note": row.get("note"),
            "source": row.get("source", "manual"),
            "created_at": self._format_timestamp(row["created_at"]),
            "updated_at": self._format_timestamp(row["updated_at"]),
            "score": None,
            "score_alert": False,
        }

    def get_items_with_scores(self) -> list[dict[str, Any]]:
        """Get all watchlist items with latest scores (LATERAL JOIN eliminates N+1 pattern)."""
        items_df = self.repo.get_all_items_with_snapshots()

        if items_df.is_empty():
            return []

        # Load preferences once (not per-item)
        prefs = UserPreferences.load_all(self.storage)
        stale_ttl_minutes = prefs.get_stale_ttl_minutes()

        results: list[dict[str, Any]] = []

        for row in items_df.iter_rows(named=True):
            item_data = self._build_base_item_data(row)

            # Add snapshot data if available
            if row.get("overall_score") is not None:
                self._build_snapshot_data(item_data, row, stale_ttl_minutes)

            # Build news intelligence
            try:
                news_intel = self.build_news_intelligence(row["symbol"])
                item_data["news_intelligence"] = (
                    news_intel.model_dump(mode="json") if news_intel else None
                )
            except Exception as e:
                logger.warning(
                    "watchlist_news_intelligence_failed",
                    symbol=row["symbol"],
                    error=str(e),
                )
                item_data["news_intelligence"] = None

            results.append(item_data)

        # Calculate priority indicators
        for item in results:
            indicators = calculate_priority_indicators(results, item)
            item["priority_indicators"] = [ind.model_dump() for ind in indicators]

        return results

    def get_item_with_score_by_id(self, item_id: str) -> dict[str, Any] | None:
        """Get a single watchlist item by ID with its latest score."""
        item_df = self.repo.get_item_by_id(item_id)

        if item_df.is_empty():
            return None

        row = item_df.to_dicts()[0]

        created_at = row["created_at"]
        if hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()
        updated_at = row["updated_at"]
        if hasattr(updated_at, "isoformat"):
            updated_at = updated_at.isoformat()

        item_data = {
            "id": row["id"],
            "symbol": row["symbol"],
            "note": row.get("note"),
            "created_at": created_at,
            "updated_at": updated_at,
            "score": None,
            "score_alert": False,
        }

        snapshot_df = self.repo.get_latest_snapshot(item_id)

        if not snapshot_df.is_empty():
            snap_row = snapshot_df.to_dicts()[0]

            # Load preferences once
            prefs = UserPreferences.load_all(self.storage)
            stale_ttl_minutes = prefs.get_stale_ttl_minutes()

            # Use helper to build snapshot data (same as get_items_with_scores)
            self._build_snapshot_data(item_data, snap_row, stale_ttl_minutes)

            # Normalize news payload if present
            news_payload = item_data.get("recent_news")
            if isinstance(news_payload, dict):
                item_data["recent_news"] = _normalize_recent_news_payload(news_payload)

        # Build news intelligence summary
        try:
            news_intel = self.build_news_intelligence(row["symbol"])
            item_data["news_intelligence"] = (
                news_intel.model_dump(mode="json") if news_intel else None
            )
        except Exception as e:
            logger.warning(
                "watchlist_news_intelligence_failed",
                symbol=row["symbol"],
                error=str(e),
            )
            item_data["news_intelligence"] = None

        return item_data

    def _check_score_alert(self, item_id: str, current_score: float) -> bool:
        """Check if score changed >10 points in last 7 days."""
        history_df = self.storage.query(
            """
            SELECT overall_score
            FROM watchlist_snapshots
            WHERE item_id = ?
              AND fetched_at >= current_timestamp - INTERVAL '7 days'
            ORDER BY fetched_at ASC
            LIMIT 1
            """,
            [item_id],
        )

        if history_df.is_empty():
            return False

        week_ago_score = float(history_df["overall_score"][0])
        return abs(current_score - week_ago_score) > 10.0

    def _query_recent_news(self, symbol: str, hours: int = 24) -> list[tuple[Any, ...]]:
        """Query news cache for recent articles.

        Args:
            symbol: Ticker symbol
            hours: Number of hours to lookback

        Returns:
            List of row tuples from news_cache
        """
        return self.repo.get_recent_news(symbol, hours=hours, limit=20)

    def _parse_news_article(
        self,
        row: tuple[Any, ...],
        key_events: list[KeyEvent],
    ) -> tuple[dict[str, Any], float | None]:
        """Parse news article row into article dict and extract sentiment.

        Args:
            row: Database row tuple
            key_events: List to append key events to (modified in place)

        Returns:
            Tuple of (article_dict, sentiment_score)
        """
        (
            ticker,
            headline,
            url,
            summary_text,
            news_source_name,
            author,
            image_url,
            published_at,
            sentiment_score,
            sentiment_label,
            sentiment_confidence,
            _sentiment_model,
            raw_payload,
            _content_hash,
            _fetched_at,
            filing_type,
            is_material_event,
            plain_language_headline,
            _story_id,
            _is_primary_article,
            _coverage_count,
            impact_summary,
            actionable_insight,
        ) = row

        # Build article dict
        article = {
            "ticker": ticker,
            "headline": headline,
            "url": url,
            "summary": summary_text,
            "source": news_source_name,
            "author": author,
            "image_url": image_url,
            "published_at": published_at.isoformat() if published_at else None,
            "sentiment_score": float(sentiment_score) if sentiment_score else 0.0,
            "sentiment_label": sentiment_label or "neutral",
            "sentiment_confidence": (float(sentiment_confidence) if sentiment_confidence else 0.0),
            "filing_type": filing_type,
            "is_material_event": bool(is_material_event),
            "plain_language_headline": plain_language_headline or headline,
            "impact_summary": impact_summary,
            "actionable_insight": actionable_insight,
        }

        # Extract key events (material events only, max 3)
        if is_material_event and len(key_events) < 3:
            # Try to extract event category from raw_payload
            event_category = None
            if raw_payload:
                try:
                    payload_dict = (
                        json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
                    )
                    event_category = payload_dict.get("event_category")
                except Exception:
                    pass

            key_events.append(
                KeyEvent(
                    icon=_get_event_icon(event_category, True),
                    text=plain_language_headline or headline,
                    time_ago=_format_time_ago(published_at),
                    is_material=True,
                    event_category=event_category,
                    published_at=published_at,
                )
            )

        return article, float(sentiment_score) if sentiment_score is not None else None

    def _generate_news_headline(
        self,
        key_events: list[KeyEvent],
        avg_sentiment: float,
        article_count: int,
    ) -> str:
        """Generate summary headline from news intelligence.

        Args:
            key_events: List of key events
            avg_sentiment: Average sentiment score
            article_count: Number of articles

        Returns:
            Generated headline string
        """
        if len(key_events) >= 2:
            # Multiple events - summarize
            event_types = [
                evt.text.split(" - ")[0] if " - " in evt.text else evt.text[:30]
                for evt in key_events[:2]
            ]
            return f"{event_types[0]} + {event_types[1]}"
        if len(key_events) == 1:
            return key_events[0].text
        if avg_sentiment > 0.3:
            return f"Positive news flow ({article_count} articles)"
        if avg_sentiment < -0.3:
            return f"Negative news flow ({article_count} articles)"
        return f"Mixed news ({article_count} articles in 24h)"

    def build_news_intelligence(self, symbol: str) -> NewsIntelligence | None:
        """Build news intelligence summary for a ticker.

        Args:
            symbol: Ticker symbol

        Returns:
            NewsIntelligence object or None if no recent news
        """
        # Query news cache for recent articles
        rows = self._query_recent_news(symbol, hours=24)
        if not rows:
            return None

        # Parse articles and extract key events
        articles: list[dict[str, Any]] = []
        sentiment_scores: list[float] = []
        key_events: list[KeyEvent] = []

        for row in rows:
            article, sentiment = self._parse_news_article(row, key_events)
            articles.append(article)
            if sentiment is not None:
                sentiment_scores.append(sentiment)

        # Calculate average sentiment
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0

        # Determine sentiment label
        if avg_sentiment > 0.15:
            sentiment_label = "Positive"
        elif avg_sentiment < -0.15:
            sentiment_label = "Negative"
        else:
            sentiment_label = "Neutral"

        # Generate headline summary
        headline = self._generate_news_headline(key_events, avg_sentiment, len(articles))

        return NewsIntelligence(
            headline=headline[:100],  # Limit headline length
            sentiment_score=round(avg_sentiment, 2),
            sentiment_label=sentiment_label,
            article_count_24h=len(articles),
            key_events=key_events,
            recent_articles=articles[:5],  # Top 5 most recent
        )

    def refresh_scores(self, item_id: str, symbol: str) -> None:
        """Refresh scores for a single watchlist item."""
        price_data = self.price_fetcher.fetch_price_data([symbol]).get(symbol)
        if not price_data or price_data.price <= 0:
            raise ValueError(f"Unable to fetch price data for {symbol}")

        change_pct, has_historical_data = _calculate_price_change(
            self.storage, symbol, price_data.price, item_id
        )

        if not has_historical_data:
            try:
                from ..tasks.data_ingestion_tasks import ingest_historical_ohlcv  # noqa: PLC0415

                ingest_historical_ohlcv.delay([symbol], days=252)
                logger.info(
                    "watchlist_refresh_scores_queued_backfill",
                    symbol=symbol,
                    item_id=item_id,
                )
            except Exception as e:
                logger.warning(
                    "watchlist_refresh_scores_backfill_failed", symbol=symbol, error=str(e)
                )

        if change_pct is None:
            raise ValueError(f"Insufficient historical data for {symbol} - need at least 2 days")

        technical_map = load_latest_technical(self.storage, [symbol])
        technical_snapshot = technical_map.get(symbol, TechnicalSnapshot())
        technical_snapshot.price = price_data.price

        default_weights = load_default_weights(self.storage)
        stale_ttl_minutes = load_stale_ttl_minutes(self.storage)
        now = datetime.now(UTC)

        breakdown = calculate_watchlist_scores(
            WatchlistScoreInputs(
                price=price_data,
                price_change_pct=change_pct,
                technical=technical_snapshot,
                weights=default_weights,
                now=now,
                stale_ttl_minutes=stale_ttl_minutes,
            )
        )

        snapshot = WatchlistSnapshot(
            item_id=item_id,
            fetched_at=now,
            price=price_data.price,
            change_pct=change_pct,
            beta=price_data.beta,
            volatility=price_data.volatility,
            overall_score=breakdown.overall,
            technical_score=breakdown.technical.score,
            raw_metrics=breakdown.to_snapshot_payload(),
        )

        self.repo.upsert_snapshot(snapshot.to_upsert_params())
        logger.info("Watchlist item scores refreshed", item_id=item_id, symbol=symbol)


__all__ = [
    "WatchlistService",
    "_calculate_price_change",
]
