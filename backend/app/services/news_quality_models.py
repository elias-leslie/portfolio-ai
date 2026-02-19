"""Pydantic models for news source quality metrics."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class QualityWeights(BaseModel):
    """User-adjustable weights for quality score calculation."""

    duplicate_penalty: float = Field(default=0.30, ge=0.0, le=1.0)
    diversity: float = Field(default=0.25, ge=0.0, le=1.0)
    confidence: float = Field(default=0.20, ge=0.0, le=1.0)
    freshness: float = Field(default=0.15, ge=0.0, le=1.0)
    user_feedback: float = Field(default=0.10, ge=0.0, le=1.0)

    def normalize(self) -> QualityWeights:
        """Normalize weights to sum to 1.0."""
        total = (
            self.duplicate_penalty
            + self.diversity
            + self.confidence
            + self.freshness
            + self.user_feedback
        )
        if total == 0:
            return QualityWeights()
        return QualityWeights(
            duplicate_penalty=self.duplicate_penalty / total,
            diversity=self.diversity / total,
            confidence=self.confidence / total,
            freshness=self.freshness / total,
            user_feedback=self.user_feedback / total,
        )


class SourceMetrics(BaseModel):
    """Complete quality metrics for a news source/vendor."""

    vendor: str = Field(..., description="Vendor/source identifier")
    duplicate_rate: float = Field(
        ..., ge=0.0, le=1.0, description="0=no duplicates, 1=all duplicates"
    )
    diversity_score: float = Field(..., ge=0.0, le=1.0, description="0=all same, 1=all unique")
    confidence_avg: float = Field(..., ge=0.0, le=1.0, description="Average sentiment confidence")
    freshness_score: float = Field(..., ge=0.0, le=1.0, description="1=very fresh, 0=stale")
    user_useful_rate: float | None = Field(
        default=None, ge=0.0, le=1.0, description="% useful, None if no feedback"
    )
    quality_score: float = Field(..., ge=0.0, le=1.0, description="Weighted composite score")
    article_count: int = Field(..., ge=0, description="Number of articles in sample")
    sample_period_start: datetime = Field(..., description="Start of sample window")
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
