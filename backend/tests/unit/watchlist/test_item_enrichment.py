"""Watchlist item enrichment tests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

from app.portfolio.models import PriceData
from app.watchlist._service.item_enrichment import build_quote_map


def test_build_quote_map_uses_cached_quotes_only(mocker) -> None:
    """Scanner reads should not block on vendor quote fetches."""
    fetcher = Mock()
    fetcher.fetch_cached_price_data.return_value = {
        "NVDA": PriceData(
            symbol="NVDA",
            price=122.04,
            cached_at=datetime.now(UTC),
            source="cache",
        )
    }
    price_fetcher_cls = mocker.patch(
        "app.watchlist._service.item_enrichment.PriceDataFetcher",
        return_value=fetcher,
    )

    result = build_quote_map(Mock(), ["nvda"])

    price_fetcher_cls.assert_called_once()
    fetcher.fetch_cached_price_data.assert_called_once_with(
        ["NVDA"],
        max_age_minutes=24 * 60,
    )
    fetcher.fetch_price_data.assert_not_called()
    assert result["NVDA"]["price"] == 122.04
    assert result["NVDA"]["source"] == "cache"


def test_build_quote_map_omits_missing_or_error_quotes(mocker) -> None:
    """Missing/error quotes should surface as scanner issues, not fresh fetches."""
    fetcher = Mock()
    fetcher.fetch_cached_price_data.return_value = {
        "BAD": PriceData(
            symbol="BAD",
            price=0,
            cached_at=datetime.now(UTC),
            source="cache",
            error="upstream failed",
        )
    }
    mocker.patch(
        "app.watchlist._service.item_enrichment.PriceDataFetcher",
        return_value=fetcher,
    )

    result = build_quote_map(Mock(), ["bad", "missing"])

    assert result == {}
    fetcher.fetch_price_data.assert_not_called()
