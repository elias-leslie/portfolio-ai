"""Telemetry data models and constants."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class TokenUsage(TypedDict):
    """Token usage breakdown."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


class ProviderMetrics(BaseModel):
    """Metrics for a specific LLM provider."""

    provider: str
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    success_rate: float = 0.0
    total_tokens: int = 0
    avg_tokens_per_run: float = 0.0
    avg_duration_ms: float = 0.0
    total_cost_usd: float = 0.0


class DailyTelemetry(BaseModel):
    """Daily aggregated telemetry."""

    date: str
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    avg_duration_ms: float = 0.0
    estimated_cost_usd: float = 0.0


class TelemetrySummary(BaseModel):
    """Summary telemetry for a time period."""

    period_start: str
    period_end: str
    period_days: int
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    success_rate: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    avg_tokens_per_run: float = 0.0
    avg_duration_ms: float = 0.0
    total_cost_usd: float = 0.0
    by_provider: list[ProviderMetrics] = Field(default_factory=list)
    daily_data: list[DailyTelemetry] = Field(default_factory=list)


class AgentRunDetail(BaseModel):
    """Detailed agent run information."""

    id: str
    agent_type: str
    started_at: str
    completed_at: str | None = None
    status: str
    provider: str | None = None
    model: str | None = None
    duration_ms: int | None = None
    token_usage: TokenUsage | None = None
    error: str | None = None


# Cost per 1M tokens (estimates for CLI execution - effectively free)
# These are placeholder costs for tracking, actual CLI execution is $0
COST_PER_MILLION_TOKENS: dict[str, dict[str, float]] = {
    "gemini": {"input": 0.0, "output": 0.0},  # Free via CLI
    "claude": {"input": 0.0, "output": 0.0},  # Free via CLI
    "anthropic_api": {"input": 3.0, "output": 15.0},  # If using API directly
}

__all__ = [
    "COST_PER_MILLION_TOKENS",
    "AgentRunDetail",
    "DailyTelemetry",
    "ProviderMetrics",
    "TelemetrySummary",
    "TokenUsage",
]
