"""Pydantic models for watchlist domain objects."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from ..portfolio.models import PriceData


class SignalType(str, Enum):
    """Signal classification type for watchlist items."""

    BUY = "BUY"
    HOLD = "HOLD"
    AVOID = "AVOID"


class SignalStrength(BaseModel):
    """Signal strength on a 0-10 scale."""

    value: int = Field(ge=0, le=10)

    @field_validator("value")
    @classmethod
    def validate_range(cls, v: int) -> int:
        """Validate that value is between 0 and 10."""
        if not 0 <= v <= 10:
            raise ValueError("Signal strength must be between 0 and 10")
        return v


class SignalClassification(BaseModel):
    """Signal classification with type, strength, and reasoning."""

    signal_type: SignalType
    strength: SignalStrength
    reasons: list[str] = Field(default_factory=list)


class ScoreWeights(BaseModel):
    """Weights used to compute overall watchlist score."""

    price: float = 50.0
    technical: float = 50.0

    @property
    def total(self) -> float:
        return self.price + self.technical

    def normalized(self) -> dict[str, float]:
        total = self.total
        if total <= 0:
            return {"price": 0.5, "technical": 0.5}
        return {"price": self.price / total, "technical": self.technical / total}


class ScoreComponent(BaseModel):
    """Individual score component."""

    score: float = 0.0
    weight: float = 0.0
    stale: bool = False
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    @field_validator("score", mode="before")
    def clamp_score(cls, value: float) -> float:
        return max(0.0, min(100.0, float(value)))


class ScoreBreakdown(BaseModel):
    """Score breakdown for a watchlist item."""

    price: ScoreComponent
    technical: ScoreComponent
    overall: float

    @classmethod
    @field_validator("overall", mode="before")
    def clamp_overall(cls, value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    def to_snapshot_payload(self) -> dict[str, Any]:
        """Serialize score metadata for persistence."""
        return {
            "price": self.price.model_dump(mode="json"),
            "technical": self.technical.model_dump(mode="json"),
            "overall": self.overall,
        }


class TechnicalSnapshot(BaseModel):
    """Technical indicator snapshot used for scoring."""

    rsi_14: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    price: float | None = None
    calculated_at: datetime | None = None


class WatchlistScoreInputs(BaseModel):
    """Inputs required to compute watchlist scores."""

    price: PriceData
    price_change_pct: float | None = None
    technical: TechnicalSnapshot = Field(default_factory=TechnicalSnapshot)
    weights: ScoreWeights = Field(default_factory=ScoreWeights)
    now: datetime = Field(default_factory=lambda: datetime.now(UTC))
    stale_ttl_minutes: int = 15  # Default to 15 minutes (3x default 5min refresh)


class WatchlistItem(BaseModel):
    """Watchlist item model."""

    id: str
    account_id: str
    symbol: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WatchlistSnapshot(BaseModel):
    """Watchlist scoring snapshot for persistence and analytics."""

    item_id: str
    fetched_at: datetime
    price: float | None = None
    change_pct: float | None = None
    beta: float | None = None
    volatility: float | None = None
    news_score: float | None = None
    technical_score: float | None = None
    fundamental_score: float | None = None
    ai_score: float | None = None
    ai_confidence: float | None = None
    sector_score: float | None = None
    competitor_score: float | None = None
    overall_score: float | None = None
    is_stale: bool = False
    raw_metrics: dict[str, Any] = Field(default_factory=dict)

    def to_upsert_params(self) -> dict[str, Any]:
        """Return dictionary for persistence helpers."""
        payload = self.model_dump()
        payload["raw_metrics"] = self.raw_metrics or None
        return payload
