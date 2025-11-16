"""Type definitions for gap detection."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class CapabilityRequirement(TypedDict, total=False):
    """Single capability requirement from trading_requirements.yaml."""

    capability: str
    gap_id: str
    criticality: Literal["P0", "P1", "P2", "P3"]
    current_state: str
    desired_state: str
    why: str
    data_sources: list[dict[str, Any]]
    tables: list[str]
    freshness_requirement: str
    coverage_requirement: str
    notes: str | None


class GapInfo(TypedDict):
    """Identified gap with metadata."""

    gap_id: str
    capability: str
    analysis_type: str
    criticality: Literal["P0", "P1", "P2", "P3"]
    current_state: str
    desired_state: str
    impact: str  # "why" field from requirements
    data_sources: list[dict[str, Any]]
    effort: Literal["LOW", "MEDIUM", "HIGH"]
    blocks_strategies: list[str]
    recommendation: str
    severity: Literal["blocking", "limiting", "optional"]


class CoverageResult(TypedDict):
    """Coverage calculation result for an analysis type."""

    analysis_type: str
    description: str
    total_capabilities: int
    available_capabilities: int
    missing_capabilities: int
    coverage_pct: float
    maturity_level: int
    gaps: list[GapInfo]


class GapAnalysisResult(TypedDict):
    """Complete gap analysis result."""

    timestamp: str
    total_gaps: int
    p0_gaps: int
    p1_gaps: int
    p2_gaps: int
    p3_gaps: int
    analysis_types: dict[str, CoverageResult]
    top_10_priorities: list[GapInfo]
    mvp_roadmap: dict[str, Any]
