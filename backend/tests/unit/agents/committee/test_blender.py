"""Unit tests for the 60/40 quant+committee blender."""

from __future__ import annotations

import pytest

from app.agents.committee import blender

# ---------- decision_to_quality_score ----------


@pytest.mark.parametrize(
    "action,confidence,expected",
    [
        ("buy", 1.0, 10.0),
        ("buy", 0.0, 5.5),
        ("add", 1.0, 10.0),
        ("hold", 0.0, 5.0),
        ("hold", 1.0, 5.0),
        ("trim", 0.0, 4.0),
        ("trim", 1.0, 2.0),
        ("sell", 0.0, 3.0),
        ("sell", 1.0, 1.0),
    ],
)
def test_decision_to_quality_score_at_bucket_endpoints(
    action: str, confidence: float, expected: float
) -> None:
    assert blender.decision_to_quality_score(action, confidence) == pytest.approx(expected)


def test_decision_to_quality_score_clamps_confidence_above_one() -> None:
    assert blender.decision_to_quality_score("buy", 1.5) == pytest.approx(10.0)


def test_decision_to_quality_score_clamps_negative_confidence() -> None:
    assert blender.decision_to_quality_score("buy", -0.2) == pytest.approx(5.5)


# ---------- blend_committee_quant_score ----------


def test_blend_default_weight_is_sixty_forty_quant_committee() -> None:
    # High-conviction BUY (committee=10) + perfect quant (composite_pct=100, quant=10)
    # → blended = 10 * 0.4 + 10 * 0.6 = 10
    assert blender.blend_committee_quant_score(
        action="buy", confidence=1.0, composite_pct=100.0
    ) == pytest.approx(10.0)


def test_blend_high_committee_low_quant_lands_between_them() -> None:
    # committee=10 (buy@1.0), quant=2.0 (composite_pct=20)
    # → 10 * 0.4 + 2.0 * 0.6 = 4.0 + 1.2 = 5.2
    assert blender.blend_committee_quant_score(
        action="buy", confidence=1.0, composite_pct=20.0
    ) == pytest.approx(5.2)


def test_blend_low_committee_high_quant_lands_between_them() -> None:
    # committee=1.0 (sell@1.0), quant=10.0 (composite_pct=100)
    # → 1.0 * 0.4 + 10.0 * 0.6 = 0.4 + 6.0 = 6.4
    assert blender.blend_committee_quant_score(
        action="sell", confidence=1.0, composite_pct=100.0
    ) == pytest.approx(6.4)


def test_blend_clamps_composite_pct_above_100() -> None:
    # Upstream bug shouldn't bleed through; quant component caps at 10.
    assert blender.blend_committee_quant_score(
        action="buy", confidence=1.0, composite_pct=200.0
    ) == pytest.approx(10.0)


def test_blend_clamps_composite_pct_below_zero() -> None:
    # composite_pct=-50 → quant=1.0; buy@0 → committee=5.5
    # → 5.5 * 0.4 + 1.0 * 0.6 = 2.2 + 0.6 = 2.8
    assert blender.blend_committee_quant_score(
        action="buy", confidence=0.0, composite_pct=-50.0
    ) == pytest.approx(2.8)


def test_custom_committee_weight_respected() -> None:
    # weight=1.0 means pure committee score
    assert blender.blend_committee_quant_score(
        action="hold", confidence=0.5, composite_pct=100.0, committee_weight=1.0
    ) == pytest.approx(5.0)
    # weight=0.0 means pure quant score
    assert blender.blend_committee_quant_score(
        action="sell", confidence=1.0, composite_pct=100.0, committee_weight=0.0
    ) == pytest.approx(10.0)


def test_blend_result_rounded_to_two_decimals() -> None:
    # 5.5 * 0.4 + 7.3 * 0.6 = 2.2 + 4.38 = 6.58
    result = blender.blend_committee_quant_score(
        action="buy", confidence=0.0, composite_pct=73.0
    )
    assert result == pytest.approx(6.58)


# ---------- describe_blend ----------


def test_describe_blend_returns_all_components() -> None:
    desc = blender.describe_blend(
        action="buy", confidence=0.8, composite_pct=75.0
    )
    assert desc["action"] == "buy"
    assert desc["confidence"] == pytest.approx(0.8)
    assert desc["committee_weight"] == pytest.approx(0.4)
    # committee_score derivation: bucket(buy)=5.5 + confidence(0.8)*4.5 -> 9.1
    assert desc["committee_score"] == pytest.approx(9.1)
    # quant_score derivation: composite_pct(75)/10 -> 7.5
    assert desc["quant_score"] == pytest.approx(7.5)
    # blended_rank derivation: 9.1*0.4 + 7.5*0.6 = 3.64 + 4.5 -> 8.14
    assert desc["blended_rank"] == pytest.approx(8.14)


def test_describe_blend_blended_rank_matches_blend_function() -> None:
    for action in ("buy", "sell", "trim", "add", "hold"):
        for confidence in (0.0, 0.3, 0.7, 1.0):
            for composite in (10.0, 50.0, 90.0):
                desc = blender.describe_blend(
                    action=action, confidence=confidence, composite_pct=composite
                )
                expected = blender.blend_committee_quant_score(
                    action=action, confidence=confidence, composite_pct=composite
                )
                assert desc["blended_rank"] == pytest.approx(expected)
