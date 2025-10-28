"""Google News RSS source for agents.

Simplified Google News integration for fetching market headlines.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import feedparser  # type: ignore[import-untyped]  # feedparser doesn't ship type stubs

logger = logging.getLogger(__name__)


class GoogleNewsSource:
    """Fetch news articles from Google News RSS feeds."""

    BASE_URL = "https://news.google.com/rss/search"

    def __init__(self) -> None:
        """Initialize Google News source."""
        self.rate_limit_delay = 2.0  # 2 seconds between requests
        self.last_request_time = 0.0

    def is_enabled(self) -> bool:
        """Google News RSS is always available (no auth required)."""
        return True

    def _rate_limit_wait(self) -> None:
        """Apply rate limiting delay between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def fetch_headlines(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch news headlines from Google News.

        Args:
            query: Search query (e.g., "stock market", "AAPL stock")
            max_results: Maximum number of headlines to return

        Returns:
            List of headline dicts with title, link, published, and summary
        """
        self._rate_limit_wait()

        try:
            # Build RSS feed URL
            params = {
                "q": query,
                "hl": "en-US",
                "gl": "US",
                "ceid": "US:en",
            }
            url = f"{self.BASE_URL}?" + "&".join(f"{k}={v}" for k, v in params.items())

            # Fetch and parse RSS feed
            feed = feedparser.parse(url)

            headlines = []
            for entry in feed.entries[:max_results]:
                headline = {
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary": entry.get("summary", ""),
                    "source": entry.get("source", {}).get("title", "Unknown"),
                }
                headlines.append(headline)

            logger.info(f"Fetched {len(headlines)} headlines for query: {query}")
            return headlines

        except Exception as e:
            logger.error(f"Failed to fetch news for {query}: {e}")
            return []

    def fetch_market_headlines(self, max_results: int = 10) -> list[dict[str, Any]]:
        """Fetch general market headlines.

        Args:
            max_results: Maximum number of headlines to return

        Returns:
            List of headline dicts
        """
        return self.fetch_headlines("stock market", max_results)

    def fetch_symbol_headlines(
        self,
        symbol: str,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Fetch headlines for a specific symbol.

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            max_results: Maximum number of headlines to return

        Returns:
            List of headline dicts
        """
        return self.fetch_headlines(f"{symbol} stock", max_results)
