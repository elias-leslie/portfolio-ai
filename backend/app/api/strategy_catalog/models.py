"""Pydantic models for the strategy catalog API."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class CatalogItem(BaseModel):
    """One screened strategy, ranked by edge_score."""

    symbol: str
    strategy_type: str
    run_date: date
    edge_score: float | None
    mean_sharpe: float | None
    mean_win_rate: float | None
    max_drawdown_pct: float | None
    mean_excess_vs_bh: float | None
    pct_folds_beat_bh: float | None
    wilcoxon_p_value: float | None
    statistically_significant: bool
    significance_level: str | None
    num_folds: int
    total_trades: int
    backtest_start_date: date | None
    backtest_end_date: date | None
    is_followed: bool


class CatalogResponse(BaseModel):
    """Catalog top-N response."""

    items: list[CatalogItem]
    total_count: int
    latest_run_date: date | None


class FollowResponse(BaseModel):
    """Result of following or unfollowing a catalog symbol."""

    symbol: str
    is_followed: bool
    strategy_id: str | None
