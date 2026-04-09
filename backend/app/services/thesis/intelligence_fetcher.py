"""Intelligence Fetcher - builds symbol intelligence in process."""

from __future__ import annotations

from typing import Any

from ...api.symbols.service import build_symbol_intelligence
from ...logging_config import get_logger

logger = get_logger(__name__)


class IntelligenceFetcher:
    """Fetches thesis intelligence from the shared symbol assembly."""

    def fetch(self, symbol: str) -> dict[str, Any]:
        """Build intelligence data without an internal HTTP round-trip.

        Args:
            symbol: Stock symbol

        Returns:
            Intelligence data dictionary

        Raises:
            RuntimeError: If intelligence assembly fails
        """
        symbol = symbol.upper()

        try:
            logger.info("building_intelligence", symbol=symbol)
            data = build_symbol_intelligence(
                symbol,
                include_market=True,
                include_strategies=True,
                include_decision=False,
            ).model_dump(mode="json")
            if data.get("error"):
                raise RuntimeError(f"Intelligence API returned error: {data['error']}")
            logger.info("intelligence_built", symbol=symbol, sections=list(data.keys()))
            return data
        except Exception as e:
            logger.error("intelligence_build_failed", symbol=symbol, error=str(e), exc_info=True)
            raise RuntimeError(f"Failed to fetch intelligence for {symbol}: {e}") from e
