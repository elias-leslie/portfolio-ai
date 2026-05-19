"""60/40 blender: combine L3 committee verdict with L2 quant composite.

Maps the typed PM decision (action + confidence ∈ [0,1]) to a 1-10
fundamental quality score and blends it 60/40 with the L2 scanner
``composite_pct`` (0-100) into a final ``blended_rank`` (1-10).

The mapping is intentionally coarse and explicit so the score is
auditable from the source numbers: a deep committee that lands on a
high-confidence BUY should land near 10, a HOLD should sit in the
middle, a high-confidence SELL near 1.

This module is pure — no DB, no IO. Persistence is the caller's job.
"""

from __future__ import annotations

from typing import Literal

from app.agents.committee.schemas import Action

CommitteeWeight = float  # 0.0 to 1.0; the rest goes to the quant score.

_DEFAULT_COMMITTEE_WEIGHT: CommitteeWeight = 0.4  # 60/40 quant/committee per spec.


def decision_to_quality_score(action: Action, confidence: float) -> float:
    """Map a PM decision to a 1-10 fundamental quality score.

    Buckets:
    - ``buy`` / ``add``: 5.5 → 10 by confidence (high-conviction BUY = 10)
    - ``hold``:          flat 5
    - ``trim``:          4 → 2 by confidence (high-conviction TRIM = 2)
    - ``sell``:          3 → 1 by confidence (high-conviction SELL = 1)

    Confidence is clamped to [0, 1]. Unknown actions default to 5.
    """
    c = max(0.0, min(1.0, float(confidence)))
    if action in ("buy", "add"):
        return 5.5 + c * 4.5
    if action == "hold":
        return 5.0
    if action == "trim":
        return 4.0 - c * 2.0
    if action == "sell":
        return 3.0 - c * 2.0
    return 5.0


def blend_committee_quant_score(
    *,
    action: Action,
    confidence: float,
    composite_pct: float,
    committee_weight: CommitteeWeight = _DEFAULT_COMMITTEE_WEIGHT,
) -> float:
    """60/40 blended 1-10 score.

    ``composite_pct`` is the L2 quant composite on a 0-100 scale, which
    we rescale to 1-10 by dividing by 10. The committee score comes from
    ``decision_to_quality_score``. The default 0.4 committee weight
    matches the video spec's 60/40 quant/committee split.

    Both inputs are clamped to their valid range first so an out-of-spec
    upstream value (e.g. composite_pct=120) can't push the blended score
    past 10.
    """
    weight = max(0.0, min(1.0, float(committee_weight)))
    committee_score = decision_to_quality_score(action, confidence)
    quant_score = max(1.0, min(10.0, float(composite_pct) / 10.0))
    blended = (committee_score * weight) + (quant_score * (1.0 - weight))
    return round(max(1.0, min(10.0, blended)), 2)


def describe_blend(
    *,
    action: Action,
    confidence: float,
    composite_pct: float,
    committee_weight: CommitteeWeight = _DEFAULT_COMMITTEE_WEIGHT,
) -> dict[str, float | str]:
    """Same math as ``blend_committee_quant_score`` but returns the components.

    Useful for the audit trail and the SSE event so a reader can see
    where the final number came from without re-running the math.
    """
    committee_score = decision_to_quality_score(action, confidence)
    quant_score = max(1.0, min(10.0, float(composite_pct) / 10.0))
    return {
        "action": action,
        "confidence": float(confidence),
        "committee_score": round(committee_score, 2),
        "composite_pct": float(composite_pct),
        "quant_score": round(quant_score, 2),
        "committee_weight": float(committee_weight),
        "blended_rank": blend_committee_quant_score(
            action=action,
            confidence=confidence,
            composite_pct=composite_pct,
            committee_weight=committee_weight,
        ),
    }


__all__ = (
    "blend_committee_quant_score",
    "decision_to_quality_score",
    "describe_blend",
)


# Static type-checker hint: re-export the literal type alias for callers
# that want it without re-importing from schemas.
BlendableAction = Literal["buy", "sell", "trim", "add", "hold"]
