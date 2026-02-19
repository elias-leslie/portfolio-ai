"""Pydantic models for the strategies API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class StrategyListItem(BaseModel):
    """Strategy list item (summary view)."""

    id: str
    name: str
    symbol: str
    strategy_type: str
    status: Literal["testing", "active", "archived"]
    version: int
    expected_sharpe: float | None
    live_sharpe_ratio: float | None
    live_win_rate: float | None
    trades_count: int
    created_at: str
    activation_date: str | None
    # Performance variance indicator (Task 4.2)
    performance_variance: float | None = None  # Ratio of live vs expected Sharpe
    performance_flag: Literal["exceeding", "meeting", "underperforming", "no_data"] | None = None


class StrategyDetail(BaseModel):
    """Strategy detail view (full data)."""

    id: str
    name: str
    symbol: str
    strategy_type: str
    parameters: dict[str, Any]
    research_summary: dict[str, Any]
    generation_reasoning: str
    backtest_metrics: list[dict[str, Any]]
    expected_sharpe: float | None
    expected_win_rate: float | None
    expected_max_drawdown: float | None
    live_trades_count: int
    live_win_rate: float | None
    live_sharpe_ratio: float | None
    status: Literal["testing", "active", "archived"]
    version: int
    created_at: str
    activation_date: str | None
    archive_date: str | None
    archive_reason: str | None
    performance_history: list[dict[str, Any]]


class StrategySummary(BaseModel):
    """Summary statistics for strategies."""

    total: int
    active: int
    testing: int
    archived: int
    avg_expected_sharpe: float | None
    avg_live_sharpe: float | None
    total_trades: int
    exceeding_count: int
    meeting_count: int
    underperforming_count: int


class GenerateStrategyRequest(BaseModel):
    """Request to generate new strategy."""

    symbol: str = Field(min_length=1, max_length=10)
    force_regenerate: bool = False


class GenerateBatchRequest(BaseModel):
    """Request to generate strategies for multiple symbols."""

    symbols: list[str] | None = Field(
        default=None,
        description="Symbols to generate for. If None, uses top N watchlist symbols.",
    )
    top_n: int = Field(default=20, ge=1, le=50, description="Top N symbols if no list provided")
    force_regenerate: bool = False


class UpdateStrategyStatusRequest(BaseModel):
    """Request to update strategy status."""

    status: Literal["active", "archived"]
    archive_reason: str | None = Field(default=None, description="Reason for archival")
