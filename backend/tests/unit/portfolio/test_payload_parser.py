"""Unit tests for portfolio payload parsing."""

from __future__ import annotations

from app.portfolio._payload_parser import parse_payload_row


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
