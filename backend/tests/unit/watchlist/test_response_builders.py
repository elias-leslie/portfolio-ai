"""Unit tests for watchlist response builders (amateur-first redesign fields)."""

from __future__ import annotations

from typing import Any

from app.watchlist.response_builders import WatchlistItemResponse


def _base_item(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": "item-1",
        "symbol": "AAPL",
        "created_at": "2026-03-11T12:00:00Z",
        "updated_at": "2026-03-11T12:05:00Z",
    }
    item.update(overrides)
    return item


class TestWatchlistItemResponseCompanyName:
    """The scanner row needs a human-readable company name per item."""

    def test_serializes_company_name(self) -> None:
        response = WatchlistItemResponse.from_service_dict(
            _base_item(company_name="Apple Inc.")
        )
        assert response.company_name == "Apple Inc."

    def test_company_name_defaults_to_none(self) -> None:
        response = WatchlistItemResponse.from_service_dict(_base_item())
        assert response.company_name is None
