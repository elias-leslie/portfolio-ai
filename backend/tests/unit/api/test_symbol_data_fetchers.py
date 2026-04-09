"""Unit tests for symbol intelligence data fetchers."""

from __future__ import annotations

from unittest.mock import Mock

from app.api.symbols.data_fetchers import get_watchlist_data


def test_get_watchlist_data_uses_watchlist_items_without_decision_enrichment(mocker) -> None:
    """Symbol intelligence should not request recursive watchlist decisions."""
    watchlist_service = Mock()
    watchlist_service.get_items_with_scores.return_value = [{"symbol": "NVDA"}]
    build_mock = mocker.patch(
        "app.api.symbols.data_fetchers._build_watchlist_result",
        return_value={"symbol": "NVDA", "signal_type": "BUY"},
    )

    result = get_watchlist_data("nvda", watchlist_service)

    watchlist_service.get_items_with_scores.assert_called_once_with(include_decision=False)
    build_mock.assert_called_once_with({"symbol": "NVDA"})
    assert result == {"symbol": "NVDA", "signal_type": "BUY"}
