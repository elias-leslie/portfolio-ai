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
from .refresh_processor import _extract_article_publisher, _extract_article_vendor
from .scoring import _is_stale as scoring_is_stale
from .scoring import calculate_watchlist_scores

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

    def get_items_with_scores(self, account_id: str) -> list[dict[str, Any]]:
        """Get all watchlist items for an account with their latest scores."""
        items_df = self.storage.query(
            """
            SELECT wi.id, wi.account_id, wi.symbol, wi.note,
                   wi.created_at, wi.updated_at
            FROM watchlist_items wi
            WHERE wi.account_id = ?
            ORDER BY wi.created_at DESC
            """,
            [account_id],
        )

        if items_df.is_empty():
            return []

        results: list[dict[str, Any]] = []

        for row in items_df.iter_rows(named=True):
            created_at = row["created_at"]
            if hasattr(created_at, "isoformat"):
                created_at = created_at.isoformat()
            updated_at = row["updated_at"]
            if hasattr(updated_at, "isoformat"):
                updated_at = updated_at.isoformat()

            item_data = {
                "id": row["id"],
                "account_id": row["account_id"],
                "symbol": row["symbol"],
                "note": row.get("note"),
                "created_at": created_at,
                "updated_at": updated_at,
                "score": None,
                "score_alert": False,
            }

            # Get latest snapshot
            snapshot_df = self.storage.query(
                """
                SELECT overall_score, technical_score, fetched_at, raw_metrics,
                       signal_type, signal_strength, narrative_headline,
                       recommended_style, style_confidence, optimal_holding_period, risk_level,
                       entry_price, stop_loss, profit_target, position_size_shares,
                       narrative_action_plan, narrative_position_sizing,
                       narrative_company_health, narrative_special_notes,
                       company_health, earnings_date, earnings_days_away,
                       news_sentiment_score, recent_news_headlines
                FROM watchlist_snapshots
                WHERE item_id = ?
                ORDER BY fetched_at DESC
                LIMIT 1
                """,
                [row["id"]],
            )

            if not snapshot_df.is_empty():
                snap_row = snapshot_df.to_dicts()[0]
                raw_metrics = snap_row.get("raw_metrics", {})

                if isinstance(raw_metrics, str):
                    try:
                        raw_metrics = json.loads(raw_metrics)
                    except (json.JSONDecodeError, TypeError):
                        raw_metrics = {}

                news_payload = snap_row.get("recent_news_headlines")
                if isinstance(news_payload, str):
                    try:
                        news_payload = json.loads(news_payload)
                    except (json.JSONDecodeError, TypeError):
                        news_payload = None

                fetched_at = snap_row.get("fetched_at")
                if fetched_at and isinstance(raw_metrics, dict):
                    if isinstance(fetched_at, datetime) and fetched_at.tzinfo is None:
                        fetched_at = fetched_at.replace(tzinfo=UTC)

                    stale_ttl_minutes = load_stale_ttl_minutes(self.storage)
                    current_time = datetime.now(UTC)
                    fetched_at_iso = fetched_at.isoformat().replace("+00:00", "Z")

                    if "price" in raw_metrics and isinstance(raw_metrics["price"], dict):
                        raw_metrics["price"]["stale"] = scoring_is_stale(
                            fetched_at, stale_ttl_minutes, current_time
                        )
                        raw_metrics["price"]["updated_at"] = fetched_at_iso
                    if "technical" in raw_metrics and isinstance(raw_metrics["technical"], dict):
                        raw_metrics["technical"]["stale"] = scoring_is_stale(
                            fetched_at, stale_ttl_minutes, current_time
                        )
                        raw_metrics["technical"]["updated_at"] = fetched_at_iso

                alert = self._check_score_alert(row["id"], snap_row["overall_score"])

                item_data["score"] = {
                    "price": raw_metrics.get("price", {}),
                    "technical": raw_metrics.get("technical", {}),
                    "overall": snap_row["overall_score"],
                }
                item_data["score_alert"] = alert
                item_data["signal_type"] = snap_row.get("signal_type")
                item_data["signal_strength"] = snap_row.get("signal_strength")
                item_data["narrative_headline"] = snap_row.get("narrative_headline")
                item_data["recommended_style"] = snap_row.get("recommended_style")
                item_data["style_confidence"] = snap_row.get("style_confidence")
                item_data["optimal_holding_period"] = snap_row.get("optimal_holding_period")
                item_data["risk_level"] = snap_row.get("risk_level")
                item_data["entry_price"] = snap_row.get("entry_price")
                item_data["stop_loss"] = snap_row.get("stop_loss")
                item_data["profit_target"] = snap_row.get("profit_target")
                item_data["position_size_shares"] = snap_row.get("position_size_shares")
                item_data["narrative_action_plan"] = snap_row.get("narrative_action_plan")
                item_data["narrative_position_sizing"] = snap_row.get("narrative_position_sizing")
                item_data["narrative_company_health"] = snap_row.get("narrative_company_health")
                item_data["narrative_special_notes"] = snap_row.get("narrative_special_notes")
                item_data["company_health"] = snap_row.get("company_health")
                earnings_date_value = snap_row.get("earnings_date")
                item_data["earnings_date"] = (
                    earnings_date_value.isoformat() if earnings_date_value is not None else None
                )
                item_data["earnings_days_away"] = snap_row.get("earnings_days_away")
                item_data["news_sentiment_score"] = snap_row.get("news_sentiment_score")
                item_data["recent_news"] = news_payload

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

            results.append(item_data)

        return results

    def get_item_with_score_by_id(self, item_id: str) -> dict[str, Any] | None:
        """Get a single watchlist item by ID with its latest score."""
        item_df = self.storage.query(
            """
            SELECT wi.id, wi.account_id, wi.symbol, wi.note,
                   wi.created_at, wi.updated_at
            FROM watchlist_items wi
            WHERE wi.id = ?
            """,
            [item_id],
        )

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
            "account_id": row["account_id"],
            "symbol": row["symbol"],
            "note": row.get("note"),
            "created_at": created_at,
            "updated_at": updated_at,
            "score": None,
            "score_alert": False,
        }

        snapshot_df = self.storage.query(
            """
            SELECT overall_score, technical_score, fetched_at, raw_metrics,
                   signal_type, signal_strength, narrative_headline,
                   recommended_style, style_confidence, optimal_holding_period, risk_level,
                   entry_price, stop_loss, profit_target, position_size_shares,
                   narrative_action_plan, narrative_position_sizing,
                   narrative_company_health, narrative_special_notes,
                   company_health, earnings_date, earnings_days_away,
                   news_sentiment_score, recent_news_headlines
            FROM watchlist_snapshots
            WHERE item_id = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            [item_id],
        )

        if not snapshot_df.is_empty():
            snap_row = snapshot_df.to_dicts()[0]
            raw_metrics = snap_row.get("raw_metrics", {})

            if isinstance(raw_metrics, str):
                try:
                    raw_metrics = json.loads(raw_metrics)
                except (json.JSONDecodeError, TypeError):
                    raw_metrics = {}

            news_payload = snap_row.get("recent_news_headlines")
            if isinstance(news_payload, str):
                try:
                    news_payload = json.loads(news_payload)
                except (json.JSONDecodeError, TypeError):
                    news_payload = None
            if isinstance(news_payload, dict):
                news_payload = _normalize_recent_news_payload(news_payload)
            if isinstance(news_payload, dict):
                news_payload = _normalize_recent_news_payload(news_payload)

            fetched_at = snap_row.get("fetched_at")
            if fetched_at and isinstance(raw_metrics, dict):
                if isinstance(fetched_at, datetime) and fetched_at.tzinfo is None:
                    fetched_at = fetched_at.replace(tzinfo=UTC)

                stale_ttl_minutes = load_stale_ttl_minutes(self.storage)
                current_time = datetime.now(UTC)
                fetched_at_iso = fetched_at.isoformat().replace("+00:00", "Z")

                if "price" in raw_metrics and isinstance(raw_metrics["price"], dict):
                    raw_metrics["price"]["stale"] = scoring_is_stale(
                        fetched_at, stale_ttl_minutes, current_time
                    )
                    raw_metrics["price"]["updated_at"] = fetched_at_iso
                if "technical" in raw_metrics and isinstance(raw_metrics["technical"], dict):
                    raw_metrics["technical"]["stale"] = scoring_is_stale(
                        fetched_at, stale_ttl_minutes, current_time
                    )
                    raw_metrics["technical"]["updated_at"] = fetched_at_iso

            alert = self._check_score_alert(item_id, snap_row["overall_score"])

            item_data["score"] = {
                "price": raw_metrics.get("price", {}),
                "technical": raw_metrics.get("technical", {}),
                "overall": snap_row["overall_score"],
            }
            item_data["score_alert"] = alert
            item_data["signal_type"] = snap_row.get("signal_type")
            item_data["signal_strength"] = snap_row.get("signal_strength")
            item_data["narrative_headline"] = snap_row.get("narrative_headline")
            item_data["recommended_style"] = snap_row.get("recommended_style")
            item_data["style_confidence"] = snap_row.get("style_confidence")
            item_data["optimal_holding_period"] = snap_row.get("optimal_holding_period")
            item_data["risk_level"] = snap_row.get("risk_level")
            item_data["entry_price"] = snap_row.get("entry_price")
            item_data["stop_loss"] = snap_row.get("stop_loss")
            item_data["profit_target"] = snap_row.get("profit_target")
            item_data["position_size_shares"] = snap_row.get("position_size_shares")
            item_data["narrative_action_plan"] = snap_row.get("narrative_action_plan")
            item_data["narrative_position_sizing"] = snap_row.get("narrative_position_sizing")
            item_data["narrative_company_health"] = snap_row.get("narrative_company_health")
            item_data["narrative_special_notes"] = snap_row.get("narrative_special_notes")
            item_data["company_health"] = snap_row.get("company_health")
            earnings_date_value = snap_row.get("earnings_date")
            item_data["earnings_date"] = (
                earnings_date_value.isoformat() if earnings_date_value is not None else None
            )
            item_data["earnings_days_away"] = snap_row.get("earnings_days_away")
            item_data["news_sentiment_score"] = snap_row.get("news_sentiment_score")
            item_data["recent_news"] = news_payload

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

    def build_news_intelligence(self, symbol: str) -> NewsIntelligence | None:
        """Build news intelligence summary for a ticker.

        Args:
            symbol: Ticker symbol

        Returns:
            NewsIntelligence object or None if no recent news
        """
        # Query news_cache for articles in last 24h
        now = datetime.now(UTC)
        start_time = now - timedelta(hours=24)

        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    ticker,
                    headline,
                    url,
                    summary,
                    news_source_name,
                    author,
                    image_url,
                    published_at,
                    sentiment_score,
                    sentiment_label,
                    sentiment_confidence,
                    sentiment_model,
                    raw_payload,
                    content_hash,
                    fetched_at,
                    filing_type,
                    is_material_event,
                    plain_language_headline,
                    story_id,
                    is_primary_article,
                    coverage_count,
                    impact_summary,
                    actionable_insight
                FROM news_cache
                WHERE ticker = %s
                  AND published_at >= %s
                  AND (is_primary_article = true OR is_primary_article IS NULL)
                ORDER BY published_at DESC, is_material_event DESC
                LIMIT 20
                """,
                [symbol, start_time],
            ).fetchall()

        if not rows:
            return None

        # Parse articles
        articles: list[dict[str, Any]] = []
        sentiment_scores: list[float] = []
        key_events: list[KeyEvent] = []

        for row in rows:
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
                "sentiment_confidence": (
                    float(sentiment_confidence) if sentiment_confidence else 0.0
                ),
                "filing_type": filing_type,
                "is_material_event": bool(is_material_event),
                "plain_language_headline": plain_language_headline or headline,
                "impact_summary": impact_summary,
                "actionable_insight": actionable_insight,
            }

            articles.append(article)

            # Track sentiment scores
            if sentiment_score is not None:
                sentiment_scores.append(float(sentiment_score))

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
        if len(key_events) >= 2:
            # Multiple events - summarize
            event_types = [
                evt.text.split(" - ")[0] if " - " in evt.text else evt.text[:30]
                for evt in key_events[:2]
            ]
            headline = f"{event_types[0]} + {event_types[1]}"
        elif len(key_events) == 1:
            headline = key_events[0].text
        elif avg_sentiment > 0.3:
            headline = f"Positive news flow ({len(articles)} articles)"
        elif avg_sentiment < -0.3:
            headline = f"Negative news flow ({len(articles)} articles)"
        else:
            headline = f"Mixed news ({len(articles)} articles in 24h)"

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

        self.storage.query_mgr.upsert_watchlist_snapshot(**snapshot.to_upsert_params())
        logger.info("Watchlist item scores refreshed", item_id=item_id, symbol=symbol)


__all__ = [
    "WatchlistService",
    "_calculate_price_change",
]
