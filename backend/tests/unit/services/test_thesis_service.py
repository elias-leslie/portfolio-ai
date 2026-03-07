"""Unit tests for thesis service orchestration."""

from __future__ import annotations

from unittest.mock import Mock

from app.services.thesis_service import ThesisService


def test_generate_thesis_syncs_symbol_to_watchlist_before_save(mocker) -> None:
    """Thesis generation should ensure the watchlist FK row exists before persistence."""
    service = ThesisService()
    service._fetcher = Mock(fetch=Mock(return_value={"symbol": "AAPL"}))
    service._generator = Mock(generate_with_gemini=Mock(return_value={"action": "BUY"}))
    service._validator = Mock(
        validate_with_claude=Mock(return_value=Mock(approved=True, confidence=0.8, issues=[])),
        calculate_cross_validation_score=Mock(return_value=0.8),
    )
    built_thesis = Mock(id="thesis-1", symbol="AAPL", version=1)
    service._storage = Mock(
        get_thesis=Mock(return_value=None),
        save_thesis=Mock(),
        save_version=Mock(),
    )

    build_mock = mocker.patch(
        "app.services.thesis_service.ThesisBuilder.build",
        return_value=built_thesis,
    )
    ensure_mock = mocker.patch("app.services.thesis_service.ensure_symbols_in_watchlist")

    result = service.generate_thesis("AAPL", force=True)

    assert result is built_thesis
    ensure_mock.assert_called_once_with(service._app_storage, ["AAPL"], source="thesis")
    service._storage.save_thesis.assert_called_once_with(built_thesis)
    service._storage.save_version.assert_called_once_with(built_thesis, "created")
    build_mock.assert_called_once()
