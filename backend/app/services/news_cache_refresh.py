"""News cache refresh operations and credential management."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from ..logging_config import get_logger
from ..storage.credential_loader import load_credentials_from_database
from .news_constants import MARKET_SYMBOL

if TYPE_CHECKING:
    from ..storage import PortfolioStorage
    from .news_ai_features import NewsAIFeatures
    from .news_cache import NewsCacheManager
    from .news_processing import NewsProcessor
    from .news_quality_scoring import NewsQualityScorer
    from .news_vendor_manager import NewsVendorManager

logger = get_logger(__name__)

# Module-level credential loading state
_CREDENTIALS_LOADED = False
_CREDENTIALS_LOCK = threading.Lock()

# Constants
DEFAULT_TTL_HOURS = 6
DEFAULT_MAX_ARTICLES = 10
ARTICLE_OVERFETCH_MULTIPLIER = 3
ARTICLE_OVERFETCH_CAP = 45
ALLOWED_LOOKBACK_HOURS = {6, 12, 24, 48}


def ensure_credentials_loaded(*, force: bool = False) -> None:
    """Load credentials from database into environment once per process.

    Args:
        force: If True, reload credentials even if already loaded
    """
    global _CREDENTIALS_LOADED  # noqa: PLW0603

    if not force and _CREDENTIALS_LOADED:
        return

    with _CREDENTIALS_LOCK:
        if not force and _CREDENTIALS_LOADED:
            return
        try:
            load_credentials_from_database()
            _CREDENTIALS_LOADED = True
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(
                "news_credentials_load_failed",
                error=str(exc),
            )


class NewsCacheRefresher:
    """Handles cache refresh operations and TTL management."""

    def __init__(
        self,
        storage: PortfolioStorage,
        cache_manager: NewsCacheManager,
        vendor_manager: NewsVendorManager,
        processor: NewsProcessor,
        quality_scorer: NewsQualityScorer,
        ai_features: NewsAIFeatures,
        ttl: timedelta,
        selection_overfetch: int,
    ) -> None:
        self.storage = storage
        self.cache_manager = cache_manager
        self.vendor_manager = vendor_manager
        self.processor = processor
        self.quality_scorer = quality_scorer
        self.ai_features = ai_features
        self.ttl = ttl
        self.lookback_hours = max(1, int(ttl.total_seconds() // 3600))
        self.selection_overfetch = max(1, selection_overfetch)

    def set_ttl_hours(self, hours: int) -> None:
        """Update the active TTL/lookback window (in hours)."""
        validated = max(1, hours)
        self.ttl = timedelta(hours=validated)
        self.lookback_hours = validated

    def refresh_ttl_from_preferences(self) -> int:
        """Reload TTL configuration from user preferences."""
        hours = DEFAULT_TTL_HOURS
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT news_lookback_hours
                FROM user_preferences
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ).fetchone()

        if row:
            raw_value = row[0] if isinstance(row, (list, tuple)) else None
            if raw_value is None and hasattr(row, "news_lookback_hours"):
                raw_value = row.news_lookback_hours
            if raw_value is not None:
                try:
                    candidate = int(raw_value)
                    if candidate in ALLOWED_LOOKBACK_HOURS or candidate > 0:
                        hours = candidate
                except (TypeError, ValueError):
                    logger.debug("news_lookback_hours_parse_failed", raw_value=str(raw_value))

        self.set_ttl_hours(hours)
        return self.lookback_hours

    def refresh_cache(self, *, symbol: str, query: str, max_articles: int, now: datetime) -> None:
        """Refresh cache with new articles from vendors.

        Args:
            symbol: Symbol (or MARKET_SYMBOL for market news)
            query: Search query for vendors
            max_articles: Maximum number of articles to fetch
            now: Current timestamp
        """
        logger.info("news_cache_refreshing", symbol=symbol, query=query, max_articles=max_articles)

        fetch_limit = max(
            max_articles, min(max_articles * self.selection_overfetch, ARTICLE_OVERFETCH_CAP)
        )

        # Fetch from vendors
        vendor_entries, vendor_metadata = self.vendor_manager.fetch_vendor_entries(
            symbol=symbol,
            ttl=self.ttl,
            now=now,
            max_entries=fetch_limit,
        )
        self.vendor_manager.apply_vendor_metadata(vendor_metadata, now)

        pre_counts: dict[str, int] = {
            str(name): int(count) for name, count in (vendor_metadata.get("counts") or {}).items()
        }

        # Merge and deduplicate entries
        combined_entries, post_counts = self.processor.merge_entries(
            symbol=symbol,
            vendor_entries=vendor_entries,
            max_entries=fetch_limit,
        )

        if not combined_entries:
            logger.info("no_headlines_from_sources", symbol=symbol)
            return

        # Update mix summary
        self.vendor_manager.update_recent_mix_summary(
            symbol,
            timestamp=now,
            pre_counts=pre_counts,
            post_counts=post_counts,
            combined_entries=combined_entries,
        )

        # Score sentiment
        articles = self.processor.score_entries(symbol=symbol, entries=combined_entries, now=now)

        # Score article quality (ML predictions)
        articles = self.quality_scorer.score_articles(articles)

        # Apply AI features
        articles = self.ai_features.apply_story_clustering(articles)
        articles = self.ai_features.apply_insight_generation(articles, watchlist_symbols=None)

        # Save to cache
        self.cache_manager.save_articles(articles)

        logger.info(
            "news_cache_refreshed",
            symbol=symbol,
            articles=len(articles),
            vendor_counts=vendor_metadata.get("counts", {}),
        )

    def latest_fetched_at(self, *, market: bool) -> datetime | None:
        """Get latest fetch timestamp for health reporting.

        Args:
            market: If True, get market news timestamp; if False, get watchlist timestamp

        Returns:
            Latest fetch timestamp or None if no data
        """
        query = (
            "SELECT MAX(fetched_at) FROM news_cache WHERE symbol = %s"
            if market
            else "SELECT MAX(fetched_at) FROM news_cache WHERE symbol <> %s"
        )
        with self.storage.connection() as conn:
            row = conn.execute(query, [MARKET_SYMBOL]).fetchone()
        if not row:
            return None
        fetched_at = row[0]
        if fetched_at is None:
            return None
        if not isinstance(fetched_at, datetime):
            return None
        return fetched_at if fetched_at.tzinfo else fetched_at.replace(tzinfo=UTC)
