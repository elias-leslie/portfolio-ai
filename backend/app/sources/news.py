"""Google News RSS source for agents.

Simplified Google News integration for fetching market headlines.
"""

from __future__ import annotations

import time
from importlib import import_module
from types import ModuleType
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..logging_config import get_logger

feedparser: ModuleType = import_module("feedparser")

logger = get_logger(__name__)


class GoogleNewsSource:
    """Fetch news articles from Google News RSS feeds."""

    BASE_URL = "https://news.google.com/rss/search"

    def __init__(self) -> None:
        """Initialize Google News source."""
        self.rate_limit_delay = 2.0  # 2 seconds between requests
        self.last_request_time = 0.0
        self.user_agent = "PortfolioAI-NewsFetcher/1.0 (+https://github.com/kasadis/portfolio-ai)"
        self.request_timeout = 10.0

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
            url = self._build_request_url(query)
            feed = self._fetch_feed(url)

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

        except (TimeoutError, HTTPError, URLError) as e:
            logger.error(f"Failed to fetch news for {query}: {e}")
            return []
        except Exception as e:  # pragma: no cover - unexpected failure
            logger.exception(f"Unexpected error fetching news for {query}: {e}")
            return []

    def _build_request_url(self, query: str) -> str:
        params = {
            "q": query,
            "hl": "en-US",
            "gl": "US",
            "ceid": "US:en",
        }
        return f"{self.BASE_URL}?{urlencode(params)}"

    def _fetch_feed(self, url: str) -> Any:
        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
            },
        )
        with urlopen(request, timeout=self.request_timeout) as response:
            data = response.read()
        return feedparser.parse(data)

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
