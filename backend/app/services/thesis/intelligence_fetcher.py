"""Intelligence Fetcher - Fetches intelligence data from internal API."""

from __future__ import annotations

from typing import Any

import httpx

from ...config import settings
from ...constants import DEFAULT_HTTP_TIMEOUT
from ...logging_config import get_logger

logger = get_logger(__name__)


class IntelligenceFetcher:
    """Fetches intelligence data from internal symbols API."""

    def __init__(self, api_base_url: str | None = None) -> None:
        """Initialize fetcher.

        Args:
            api_base_url: Base URL for internal API calls
        """
        self._api_base_url = api_base_url or settings.backend_url

    def fetch(self, symbol: str) -> dict[str, Any]:
        """Fetch intelligence data from internal API.

        Args:
            symbol: Stock symbol

        Returns:
            Intelligence data dictionary

        Raises:
            RuntimeError: If API call fails
        """
        url = f"{self._api_base_url}/api/symbols/{symbol}/intelligence"

        try:
            logger.info("fetching_intelligence", symbol=symbol, url=url)
            response = httpx.get(url, timeout=DEFAULT_HTTP_TIMEOUT)
            response.raise_for_status()
            data: dict[str, Any] = response.json()

            if data.get("error"):
                raise RuntimeError(f"Intelligence API returned error: {data['error']}")

            logger.info("intelligence_fetched", symbol=symbol, sections=list(data.keys()))
            return data

        except httpx.HTTPError as e:
            logger.error("intelligence_fetch_failed", symbol=symbol, error=str(e), exc_info=True)
            raise RuntimeError(f"Failed to fetch intelligence for {symbol}: {e}") from e
