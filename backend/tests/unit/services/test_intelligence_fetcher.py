"""Unit tests for in-process thesis intelligence fetching."""

from __future__ import annotations

import pytest

from app.services.thesis.intelligence_fetcher import IntelligenceFetcher


def test_fetch_builds_symbol_intelligence_in_process(mocker) -> None:
    """The fetcher should use the shared in-process intelligence builder."""
    response = mocker.Mock()
    response.model_dump.return_value = {"symbol": "NVDA", "generated_at": "2026-04-08T22:00:00Z"}
    build_mock = mocker.patch(
        "app.services.thesis.intelligence_fetcher.build_symbol_intelligence",
        return_value=response,
    )

    result = IntelligenceFetcher().fetch("nvda")

    build_mock.assert_called_once_with(
        "NVDA",
        include_market=True,
        include_strategies=True,
        include_decision=False,
    )
    response.model_dump.assert_called_once_with(mode="json")
    assert result == {"symbol": "NVDA", "generated_at": "2026-04-08T22:00:00Z"}


def test_fetch_wraps_symbol_intelligence_failures(mocker) -> None:
    """Unexpected build failures should still surface as RuntimeError."""
    mocker.patch(
        "app.services.thesis.intelligence_fetcher.build_symbol_intelligence",
        side_effect=ValueError("boom"),
    )

    with pytest.raises(RuntimeError, match="Failed to fetch intelligence for NVDA: boom"):
        IntelligenceFetcher().fetch("NVDA")
