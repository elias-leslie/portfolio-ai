"""Unit tests for thesis generation prompt preparation."""

from __future__ import annotations

from unittest.mock import Mock

from app.services.thesis.thesis_generation import ThesisGenerator


def test_generate_thesis_sanitizes_invalid_trading_guidance_before_prompt() -> None:
    """Prompt context should hide unusable stop and sizing fields instead of passing junk through."""
    llm = Mock()
    llm.generate.return_value = Mock(content='{"action": "BUY"}')
    generator = ThesisGenerator(llm_client=llm)
    generator.parse_json_response = Mock(return_value={"action": "BUY"})

    intelligence = {
        "symbol": "AAPL",
        "trading": {
            "entry_price": 257.46,
            "stop_loss": 257.4599914550781,
            "profit_target": 277.86,
            "position_size_shares": 58_514_285,
            "position_size_dollars": 15_065_087_816.10,
        },
        "portfolio": {
            "held": False,
            "context": {
                "total_value": 0.0,
            },
        },
    }

    generator.generate_thesis(intelligence)

    prompt = llm.generate.call_args.kwargs["prompt"]
    assert '"stop_loss": null' in prompt
    assert '"position_size_shares": null' in prompt
    assert '"position_size_dollars": null' in prompt
    assert "15.0650878161" not in prompt
    assert "analysis_constraints" in prompt
    assert "Ignore unavailable trading guidance fields" in prompt
