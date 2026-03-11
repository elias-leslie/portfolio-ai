"""Symbol context building and fallback evaluation for Jenny reviews."""

from __future__ import annotations

from typing import Any

from app.models.thesis import Thesis


def should_use_insufficient_evidence_fallback(
    thesis: Thesis | None,
    symbol_profile: dict[str, Any],
    min_data_quality_pct: float,
) -> bool:
    if thesis is not None:
        return False
    data_quality_pct = symbol_profile.get("data_quality_pct")
    return data_quality_pct is not None and data_quality_pct < min_data_quality_pct


def build_symbol_context(
    symbol: str,
    thesis: Thesis | None,
    price_data: Any,
    symbol_profile: dict[str, Any],
    min_data_quality_pct: float,
    invalidation_triggers: list[str],
) -> dict[str, Any]:
    price = getattr(price_data, "price", None) if price_data else None
    is_passive_fund = bool(symbol_profile.get("is_passive_fund"))
    data_quality_pct = symbol_profile.get("data_quality_pct")

    evidence_status = (
        "thin"
        if data_quality_pct is not None and data_quality_pct < min_data_quality_pct
        else "usable"
    )
    thesis_status = (
        thesis.status.value
        if thesis
        else "not_required_for_fund"
        if is_passive_fund
        else "missing"
    )

    return {
        "symbol": symbol,
        "current_price": price,
        "security_type": symbol_profile.get("security_type"),
        "symbol_profile": symbol_profile,
        "review_mode": "allocation" if is_passive_fund else "thesis",
        "data_quality_pct": data_quality_pct,
        "evidence_status": evidence_status,
        "thesis_status": thesis_status,
        "thesis_action": thesis.action.value if thesis else None,
        "expected_return_pct": thesis.expected_return_pct if thesis else None,
        "expected_timeframe_days": thesis.expected_timeframe_days if thesis else None,
        "cross_validation_score": thesis.cross_validation_score if thesis else None,
        "core_reasons": [reason.reason for reason in thesis.core_reasons] if thesis else [],
        "risks": [risk.risk for risk in thesis.risks] if thesis else [],
        "key_catalysts": [catalyst.catalyst for catalyst in thesis.key_catalysts] if thesis else [],
        "invalidation_triggers": invalidation_triggers,
    }


def _thin_evidence_fields() -> dict[str, Any]:
    return {
        "rationale": "There is not enough fresh evidence to form a trustworthy review yet.",
        "recommendation": "Wait for fresher price, signal, and catalyst data before acting.",
        "strengths": ["Jenny avoided pretending the evidence was stronger than it is."],
        "weaknesses": ["Fresh data is too thin for a trustworthy review right now."],
    }


def _passive_fund_fields(profile: dict[str, Any]) -> dict[str, Any]:
    rationale = (
        "This passive fund is being treated as an allocation review instead of a missing company thesis."
    )
    if profile.get("is_live_position"):
        recommendation = (
            "Use portfolio weight, overlap, and cash needs to decide whether to hold or trim. "
            "Avoid adding until the next review completes."
        )
    else:
        recommendation = (
            "Review whether you still need this broad exposure in the watchlist before adding it."
        )
    return {
        "rationale": rationale,
        "recommendation": recommendation,
        "strengths": ["Passive fund holdings do not require a single-company thesis to stay actionable."],
        "weaknesses": ["Fund reviews rely more on allocation and concentration than company-specific catalysts."],
    }


def _active_buy_fields() -> dict[str, Any]:
    return {
        "verdict": "hold",
        "rationale": "Active thesis exists, but Jenny could not refresh the agent review.",
    }


def fallback_evaluation(
    symbol: str,
    thesis: Thesis | None,
    *,
    agent_name: str = "fallback_operator",
    symbol_profile: dict[str, Any] | None = None,
    min_data_quality_pct: float,
) -> dict[str, Any]:
    verdict = "review"
    rationale = "Jenny could not reach Agent Hub, so this symbol needs manual review."
    recommendation = "Check the thesis and current price action before taking action."
    strengths = [
        "Existing thesis is still stored."
        if thesis
        else "Keeps the workflow running without fake certainty."
    ]
    weaknesses = ["Agent Hub unavailable, so confidence is limited."]
    profile = symbol_profile or {}
    data_quality_pct = profile.get("data_quality_pct")

    if data_quality_pct is not None and data_quality_pct < min_data_quality_pct and thesis is None:
        fields = _thin_evidence_fields()
        rationale, recommendation, strengths, weaknesses = (
            fields["rationale"], fields["recommendation"], fields["strengths"], fields["weaknesses"]
        )
    elif profile.get("is_passive_fund") and thesis is None:
        fields = _passive_fund_fields(profile)
        rationale, recommendation, strengths, weaknesses = (
            fields["rationale"], fields["recommendation"], fields["strengths"], fields["weaknesses"]
        )

    if thesis and thesis.status.value == "active" and thesis.action.value == "BUY":
        fields = _active_buy_fields()
        verdict, rationale = fields["verdict"], fields["rationale"]

    return {
        "agent_name": agent_name,
        "provider": None,
        "model": None,
        "verdict": verdict,
        "confidence": 0.35,
        "rationale": rationale,
        "recommendation": recommendation,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "metadata": {
            "fallback": True,
            "symbol": symbol,
            "symbol_profile": profile,
            "invalidation_triggers": [],
        },
        "agent_run_id": None,
    }
