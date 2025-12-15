"""Data models for market events API.

Market-wide macro events (FOMC, CPI, NFP) for sentiment chart overlays.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MarketEventType = Literal[
    "fomc_decision",
    "cpi_release",
    "nfp_release",
    "fed_speech",
    "pce_release",
    "gdp_release",
]


class MarketEvent(BaseModel):
    """A single market event."""

    id: int = Field(..., description="Unique event ID")
    event_type: MarketEventType = Field(..., description="Event category")
    event_date: str = Field(..., description="Event date (YYYY-MM-DD)")
    event_time: str | None = Field(None, description="Event time (HH:MM:SS)")
    title: str = Field(..., description="Event title/headline")
    description: str | None = Field(None, description="Event description")

    # Economic values
    expected_value: float | None = Field(None, description="Consensus estimate")
    actual_value: float | None = Field(None, description="Released actual value")
    prior_value: float | None = Field(None, description="Previous period value")
    surprise_pct: float | None = Field(None, description="Surprise percentage")

    # Impact
    impact_score: int | None = Field(
        None, ge=-5, le=5, description="Impact score from -5 (bearish) to +5 (bullish)"
    )

    # Market reaction
    spy_change_1h: float | None = Field(None, description="SPY % change in first hour")
    spy_change_1d: float | None = Field(None, description="SPY % change end of day")

    # Metadata
    source: str = Field("manual", description="Data source")
    created_at: str | None = Field(None, description="Created timestamp")


class MarketEventCreate(BaseModel):
    """Create a new market event."""

    event_type: MarketEventType = Field(..., description="Event category")
    event_date: str = Field(..., description="Event date (YYYY-MM-DD)")
    event_time: str | None = Field(None, description="Event time (HH:MM:SS)")
    title: str = Field(..., description="Event title/headline")
    description: str | None = Field(None, description="Event description")
    expected_value: float | None = Field(None, description="Consensus estimate")
    actual_value: float | None = Field(None, description="Released actual value")
    prior_value: float | None = Field(None, description="Previous period value")
    impact_score: int | None = Field(None, ge=-5, le=5, description="Impact score")
    source: str = Field("manual", description="Data source")


class MarketEventUpdate(BaseModel):
    """Update an existing market event with actual values."""

    actual_value: float | None = Field(None, description="Released actual value")
    surprise_pct: float | None = Field(None, description="Surprise percentage")
    impact_score: int | None = Field(None, ge=-5, le=5, description="Impact score")
    spy_change_1h: float | None = Field(None, description="SPY % change in first hour")
    spy_change_1d: float | None = Field(None, description="SPY % change end of day")


class MarketEventsResponse(BaseModel):
    """Response for list of market events."""

    events: list[MarketEvent] = Field(..., description="List of market events")
    total: int = Field(..., description="Total count of events")
    start_date: str | None = Field(None, description="Filter start date")
    end_date: str | None = Field(None, description="Filter end date")


class EventTypeInfo(BaseModel):
    """Information about an event type."""

    event_type: MarketEventType = Field(..., description="Event type code")
    label: str = Field(..., description="Human-readable label")
    short_label: str = Field(..., description="Short label for UI")
    color: str = Field(..., description="Hex color for UI")
    frequency: str = Field(..., description="Typical frequency per year")
    impact: str = Field(..., description="Typical market impact level")


# Event type metadata for UI
EVENT_TYPE_INFO: dict[MarketEventType, EventTypeInfo] = {
    "fomc_decision": EventTypeInfo(
        event_type="fomc_decision",
        label="FOMC Rate Decision",
        short_label="FOMC",
        color="#3B82F6",  # Blue
        frequency="8/year",
        impact="HIGH",
    ),
    "cpi_release": EventTypeInfo(
        event_type="cpi_release",
        label="CPI Inflation",
        short_label="CPI",
        color="#EF4444",  # Red
        frequency="12/year",
        impact="HIGH",
    ),
    "nfp_release": EventTypeInfo(
        event_type="nfp_release",
        label="Non-Farm Payrolls",
        short_label="NFP",
        color="#22C55E",  # Green
        frequency="12/year",
        impact="HIGH",
    ),
    "fed_speech": EventTypeInfo(
        event_type="fed_speech",
        label="Fed Chair Speech",
        short_label="Fed",
        color="#8B5CF6",  # Purple
        frequency="~12/year",
        impact="MEDIUM",
    ),
    "pce_release": EventTypeInfo(
        event_type="pce_release",
        label="PCE Inflation",
        short_label="PCE",
        color="#F59E0B",  # Amber
        frequency="12/year",
        impact="MEDIUM",
    ),
    "gdp_release": EventTypeInfo(
        event_type="gdp_release",
        label="GDP Release",
        short_label="GDP",
        color="#06B6D4",  # Cyan
        frequency="4/year",
        impact="MEDIUM",
    ),
}
