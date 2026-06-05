"""Watchlist CRUD route tests."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from app.api.watchlist.crud_router import list_watchlist_items


@pytest.mark.asyncio
async def test_list_watchlist_items_skips_decision_enrichment() -> None:
    """The scanner list endpoint should not build unused decision payloads."""
    service = Mock()
    service.get_items_with_scores.return_value = [{"symbol": "NVDA"}]

    with (
        patch("app.api.watchlist.crud_router._get_watchlist_service", return_value=service),
        patch("app.api.watchlist.crud_router.build_watchlist_item_responses", return_value=[]),
    ):
        response = await list_watchlist_items(Mock())

    service.get_items_with_scores.assert_called_once_with(include_decision=False)
    assert response.total_count == 1
