"""Unit tests for Jenny symbol profile helpers."""

from __future__ import annotations

from unittest.mock import Mock

from app.services.jenny_operator_service import JennyOperatorService
from app.services.jenny_symbol_profile_service import JennySymbolProfileService


def _service() -> JennyOperatorService:
    return JennyOperatorService()


def test_ensure_thesis_skips_generation_for_passive_fund() -> None:
    helper = JennySymbolProfileService()
    service = _service()
    service.thesis_service = Mock()
    service.thesis_service.get_thesis.return_value = None

    thesis = helper.ensure_thesis(
        service,
        "VTI",
        {"security_type": "etf", "is_passive_fund": True, "data_quality_pct": 88.0},
    )

    assert thesis is None
    service.thesis_service.generate_thesis.assert_not_called()


def test_default_symbol_profile_uses_normalized_type() -> None:
    helper = JennySymbolProfileService()
    service = _service()

    profile = helper.default_symbol_profile(service, "VTI")

    assert profile["security_type"] == "etf"
    assert profile["is_passive_fund"] is True
    assert profile["is_live_position"] is False
