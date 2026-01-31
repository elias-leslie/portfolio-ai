"""Data models for strategy evolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BacktestMetrics:
    """Simplified backtest metrics for evolution."""

    sharpe_ratio: float
    win_rate: float
    max_drawdown: float
    total_return: float
    num_trades: int


@dataclass
class StrategyAnalysis:
    """Analysis of strategy performance over recent period."""

    strategy_id: str
    symbol: str
    days_analyzed: int

    # Performance metrics
    actual_sharpe: float
    expected_sharpe: float
    performance_ratio: float  # actual / expected

    # Trade statistics
    trades_count: int
    win_rate: float
    avg_pnl: float
    max_drawdown: float

    # Diagnosis
    underperforming: bool
    diagnosis: str  # LLM-generated analysis

    # Buy & Hold comparison
    buy_hold_sharpe: float
    beats_benchmark: bool


@dataclass
class StrategyMutation:
    """Proposed change to strategy parameters."""

    mutation_type: str  # "weight_adjustment", "threshold_change", "risk_tightening"
    parameter_changes: dict[str, Any]  # {param_name: new_value}
    reasoning: str  # Why this mutation should help
    confidence: float  # 0-1, LLM's confidence in this mutation


@dataclass
class EvolutionResult:
    """Result of strategy evolution attempt."""

    success: bool
    original_strategy_id: str
    new_strategy_id: str | None

    # Metrics comparison
    parent_sharpe: float
    child_sharpe: float | None
    buy_hold_sharpe: float

    # Lineage tracking
    changes_description: str
    evolution_reason: str

    # Metadata
    mutations_tested: int
    best_mutation: StrategyMutation | None
    message: str
