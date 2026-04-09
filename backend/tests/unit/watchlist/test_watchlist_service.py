"""Unit tests for watchlist service decision controls."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

from app.watchlist._service.watchlist_service import WatchlistService


class _ItemsFrame:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def is_empty(self) -> bool:
        return not self._rows

    def iter_rows(self, *, named: bool = False):
        assert named
        return iter(self._rows)


def test_get_items_with_scores_skips_decision_map_when_disabled(mocker) -> None:
    """Internal callers can opt out of decision enrichment to avoid recursion."""
    now = datetime.now(UTC)
    service = WatchlistService(Mock())
    service.repo = Mock(
        get_all_items_with_snapshots=Mock(
            return_value=_ItemsFrame(
                [
                    {
                        "id": "item-1",
                        "symbol": "NVDA",
                        "note": None,
                        "source": "manual",
                        "created_at": now,
                        "updated_at": now,
                        "overall_score": None,
                    }
                ]
            )
        )
    )

    prefs = Mock()
    prefs.get_stale_ttl_minutes.return_value = 45
    mocker.patch(
        "app.watchlist._service.watchlist_service.UserPreferences.load_all",
        return_value=prefs,
    )
    mocker.patch(
        "app.watchlist._service.watchlist_service.build_news_intelligence_map",
        return_value={"NVDA": None},
    )
    mocker.patch(
        "app.watchlist._service.watchlist_service.build_data_quality_map",
        return_value={"NVDA": None},
    )
    decision_mock = mocker.patch(
        "app.watchlist._service.watchlist_service.build_watchlist_decision_map",
        return_value={"NVDA": {"headline": "Buy more"}},
    )
    enrich_mock = mocker.patch(
        "app.watchlist._service.watchlist_service.enrich_priority_indicators",
    )

    results = service.get_items_with_scores(include_decision=False)

    decision_mock.assert_not_called()
    enrich_mock.assert_called_once()
    assert len(results) == 1
    assert results[0]["symbol"] == "NVDA"
    assert results[0].get("decision") is None
