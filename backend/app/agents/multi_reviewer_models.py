"""Data models for Multi-LLM Strategy Reviewer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DisagreementSeverity(StrEnum):
    """Severity of disagreement between providers."""

    NONE = "none"  # Both providers agree
    MINOR = "minor"  # Same direction but different concerns
    MAJOR = "major"  # Conflicting assessments (bullish vs bearish)


@dataclass
class ProviderReview:
    """Individual provider review result."""

    provider: str
    review_text: str
    is_valid: bool
    disagreement: bool  # LLM vs rules disagreement
    usage: dict[str, int]
    error: str | None = None


@dataclass
class DualReviewResult:
    """Combined result from dual-provider review."""

    symbol: str
    review_pair_id: str
    gemini_review: ProviderReview | None
    claude_review: ProviderReview | None
    agreement_score: float  # 0.0 to 1.0
    disagreement_severity: DisagreementSeverity
    provider_disagreement: bool  # True if providers disagree with each other
    consensus_summary: str  # Human-readable summary of consensus
