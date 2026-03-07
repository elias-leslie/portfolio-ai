"""Unit tests for portfolio payload parsing."""

from __future__ import annotations

from datetime import UTC, datetime

from app.portfolio._payload_parser import parse_payload_row
from app.portfolio._price_cache import get_cached_prices
from app.storage import PortfolioStorage


class _StubStorage(PortfolioStorage):
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def query(self, sql: str, params: list[object] | None = None):  # type: ignore[override]
        import polars as pl

        return pl.DataFrame(self._rows)


def test_parse_payload_row_uses_sector_fallback_for_known_equity() -> None:
    """Known single-name stocks should get a sector label even if source metadata is blank."""
    parsed = parse_payload_row(
        {
            "symbol": "NVDA",
            "source": "test",
            "payload": {"price": 177.82, "sector": None},
        }
    )

    assert parsed.sector == "Technology"


def test_parse_payload_row_uses_category_fallback_for_known_fund() -> None:
    """Broad ETFs should surface a plain label instead of Unknown."""
    parsed = parse_payload_row(
        {
            "symbol": "VTI",
            "source": "test",
            "payload": {"price": 331.41, "sector": ""},
        }
    )

    assert parsed.sector == "Broad Market Index"


def test_get_cached_prices_applies_sector_fallback_for_known_fund() -> None:
    """Cache hits should use the same sector/category fallback as fresh fetches."""
    storage = _StubStorage(
        [
            {
                "symbol": "VTI",
                "price": 331.41,
                "beta": None,
                "volatility": None,
                "sector": None,
                "bid": None,
                "ask": None,
                "bid_size": None,
                "ask_size": None,
                "cached_at": datetime.now(UTC),
                "source": "cache",
                "error": None,
            }
        ]
    )

    cached = get_cached_prices(["VTI"], storage, cache_ttl_minutes=15)

    assert cached["VTI"].sector == "Broad Market Index"
