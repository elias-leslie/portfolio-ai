"""Decision eligibility checks for stored investment theses."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from ...models.thesis import Thesis, ThesisDecisionEligibility, ThesisStatus
from .thesis_triggers import THESIS_RECENCY_HOURS

PRICE_DRIFT_THRESHOLD = 0.15
FEAR_GREED_DRIFT_THRESHOLD = 10.0
VIX_DRIFT_THRESHOLD = 5.0

_CURRENT_PRICE_PATTERNS = (
    re.compile(
        r"current(?:\s+price)?(?:\s*(?:of|at|is|=|:))?\s*\$([0-9][0-9,]*(?:\.\d+)?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\$([0-9][0-9,]*(?:\.\d+)?)\s+(?:current|current price)",
        re.IGNORECASE,
    ),
)
_FEAR_GREED_PATTERN = re.compile(
    r"Fear\s*&\s*Greed(?:\s*(?:at|=|of|score))?\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_VIX_PATTERN = re.compile(r"\bVIX(?:\s*(?:at|=|of))?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_MATERIAL_ISSUE_PREFIXES = (
    "FACTUAL ERROR",
    "LOGICAL INCONSISTENCY",
    "RISK UNDERSTATEMENT",
    "COMPLETENESS GAP",
    "ALERT MISMATCH",
    "POSITION SIZE",
    "OPTIONS DATA",
    "DATA QUALITY",
)


def unavailable_thesis_eligibility(
    *,
    now: datetime | None = None,
) -> ThesisDecisionEligibility:
    evaluated_at = (now or datetime.now(UTC)).isoformat()
    return ThesisDecisionEligibility(
        eligible=False,
        status="unavailable",
        reasons=["No thesis is available for this symbol."],
        evaluated_at=evaluated_at,
    )


def evaluate_thesis_decision_eligibility(
    thesis: Thesis | None,
    intelligence: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    max_age_hours: float = THESIS_RECENCY_HOURS,
) -> ThesisDecisionEligibility:
    """Return computed current-decision eligibility for a stored thesis."""
    if thesis is None:
        return unavailable_thesis_eligibility(now=now)

    evaluated_at = now or datetime.now(UTC)
    age_hours = _thesis_age_hours(thesis, evaluated_at)
    reasons: list[str] = []

    if thesis.status == ThesisStatus.INVALIDATED:
        reasons.append(thesis.invalidation_reason or "Thesis has been invalidated.")

    if age_hours is not None and age_hours > max_age_hours:
        reasons.append(
            f"Thesis is {age_hours / 24:.0f}d old; refresh required before using it as current decision evidence."
        )

    material_issues = _material_validation_issues(thesis)
    if material_issues:
        reasons.append(
            f"Validation has {len(material_issues)} material issue(s), including: "
            f"{_compact_issue(material_issues[0])}"
        )

    if intelligence is None:
        reasons.append("Live symbol intelligence is unavailable for drift checks.")
    else:
        reasons.extend(_drift_reasons(thesis, intelligence))

    eligible = not reasons
    status = "eligible"
    if not eligible:
        status = "invalidated" if thesis.status == ThesisStatus.INVALIDATED else "review_required"

    return ThesisDecisionEligibility(
        eligible=eligible,
        status=status,
        reasons=reasons,
        age_hours=round(age_hours, 2) if age_hours is not None else None,
        evaluated_at=evaluated_at.isoformat(),
    )


def _thesis_age_hours(thesis: Thesis, now: datetime) -> float | None:
    try:
        created_at = datetime.fromisoformat(thesis.updated_at or thesis.created_at)
    except ValueError:
        return None
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return max((now - created_at).total_seconds() / 3600, 0.0)


def _material_validation_issues(thesis: Thesis) -> list[str]:
    issues = list(thesis.claude_validation.issues if thesis.claude_validation else [])
    issues.extend(thesis.gemini_validation.issues if thesis.gemini_validation else [])
    material: list[str] = []

    for issue in issues:
        normalized = issue.strip().upper()
        if not normalized or normalized.startswith("MINOR"):
            continue
        if normalized.startswith(_MATERIAL_ISSUE_PREFIXES):
            material.append(issue)
            continue
        if "MATERIAL" in normalized or "STALE" in normalized:
            material.append(issue)

    if thesis.claude_validation and not thesis.claude_validation.approved:
        material.insert(0, "Claude validation did not approve this thesis.")
    if thesis.gemini_validation and not thesis.gemini_validation.approved:
        material.insert(0, "Gemini validation did not approve this thesis.")
    return material


def _drift_reasons(thesis: Thesis, intelligence: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    text = "\n".join(_thesis_text(thesis))

    live_price = _live_price(intelligence)
    price_refs = _current_price_references(text)
    if live_price is not None and price_refs:
        stale_price = max(price_refs, key=lambda value: abs(live_price - value) / live_price)
        drift = abs(live_price - stale_price) / live_price
        if drift >= PRICE_DRIFT_THRESHOLD:
            reasons.append(
                f"Price assumption drifted from ${stale_price:.2f} in thesis to ${live_price:.2f} live."
            )

    live_fear_greed = _nested_number(intelligence, ["market", "fear_greed_score"])
    fear_greed_refs = _number_matches(_FEAR_GREED_PATTERN, text)
    if live_fear_greed is not None and fear_greed_refs:
        stale_fear_greed = fear_greed_refs[0]
        if abs(live_fear_greed - stale_fear_greed) >= FEAR_GREED_DRIFT_THRESHOLD:
            reasons.append(
                f"Fear & Greed drifted from {stale_fear_greed:.0f} in thesis to {live_fear_greed:.0f} live."
            )

    live_vix = _nested_number(intelligence, ["market", "vix"])
    vix_refs = _number_matches(_VIX_PATTERN, text)
    if live_vix is not None and vix_refs:
        stale_vix = vix_refs[0]
        if abs(live_vix - stale_vix) >= VIX_DRIFT_THRESHOLD:
            reasons.append(f"VIX drifted from {stale_vix:.1f} in thesis to {live_vix:.1f} live.")

    return reasons


def _thesis_text(thesis: Thesis) -> list[str]:
    text: list[str] = []
    text.extend(reason.reason for reason in thesis.core_reasons)
    text.extend(catalyst.catalyst for catalyst in thesis.key_catalysts)
    for risk in thesis.risks:
        text.append(risk.risk)
        if risk.mitigation:
            text.append(risk.mitigation)
    if thesis.value_drivers:
        text.extend(
            part
            for part in thesis.value_drivers.model_dump().values()
            if isinstance(part, str)
        )
    for validation in (thesis.claude_validation, thesis.gemini_validation):
        if validation:
            text.append(validation.review_summary)
            text.extend(validation.issues)
    return text


def _current_price_references(text: str) -> list[float]:
    refs: list[float] = []
    for pattern in _CURRENT_PRICE_PATTERNS:
        refs.extend(_number_matches(pattern, text))
    return [value for value in refs if 10 <= value <= 10000]


def _number_matches(pattern: re.Pattern[str], text: str) -> list[float]:
    values: list[float] = []
    for match in pattern.finditer(text):
        try:
            values.append(float(match.group(1).replace(",", "")))
        except ValueError:
            continue
    return values


def _live_price(intelligence: dict[str, Any]) -> float | None:
    return (
        _nested_number(intelligence, ["scores", "pillars", "price", "metadata", "price"])
        or _nested_number(intelligence, ["trading", "entry_price"])
    )


def _nested_number(data: dict[str, Any], path: list[str]) -> float | None:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if isinstance(current, int | float):
        return float(current)
    return None


def _compact_issue(issue: str) -> str:
    compact = " ".join(issue.split())
    return compact if len(compact) <= 180 else f"{compact[:177]}..."
