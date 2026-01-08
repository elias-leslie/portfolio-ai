"""
Pydantic request/response models for Backtest API.

All models are centralized here for consistent API contracts.
"""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

# ============================================================================
# Core Request Models
# ============================================================================


class StrategyParametersRequest(BaseModel):
    """Optional strategy parameters for backtest customization."""

    stop_loss_atr_multiplier: Decimal = Field(
        default=Decimal("2.0"), gt=0, le=5, description="Stop loss in ATR multiples (1.0-5.0)"
    )
    max_holding_days: int = Field(
        default=30, gt=0, le=365, description="Maximum holding period in days"
    )
    target_profit_pct: Decimal = Field(
        default=Decimal("15.0"), gt=0, le=100, description="Target profit percentage"
    )
    min_confirmations: int = Field(
        default=5, ge=3, le=8, description="Minimum confirmations for entry (3-8)"
    )


class StartBacktestRequest(BaseModel):
    """Request model for starting a backtest."""

    symbol: str = Field(..., min_length=1, max_length=20, description="Stock symbol (e.g., AAPL)")
    start_date: date = Field(..., description="Backtest start date")
    end_date: date = Field(..., description="Backtest end date")
    initial_capital: Decimal = Field(
        default=Decimal("100000.00"), gt=0, description="Starting capital in dollars"
    )
    strategy: Literal[
        "signal_classifier", "enhanced", "momentum", "mean_reversion", "trend_following"
    ] = Field(default="enhanced", description="Strategy to use")
    parameters: StrategyParametersRequest | None = Field(
        default=None, description="Optional strategy parameters"
    )
    position_sizing_method: Literal["fixed_dollars", "fixed_shares"] = Field(
        default="fixed_dollars"
    )
    position_size_value: Decimal = Field(
        default=Decimal("10000.00"), gt=0, description="Position size (dollars or shares)"
    )


class MonteCarloRequest(BaseModel):
    """Request model for Monte Carlo simulation."""

    num_simulations: int = Field(
        default=1000, ge=100, le=10000, description="Number of simulations"
    )
    seed: int | None = Field(default=None, description="Random seed for reproducibility")


class WalkForwardRequest(BaseModel):
    """Request model for walk-forward validation."""

    symbol: str = Field(..., min_length=1, max_length=20, description="Stock symbol (e.g., AAPL)")
    start_date: date = Field(..., description="Start of historical period")
    end_date: date = Field(..., description="End of historical period")
    strategy: Literal["signal_classifier", "enhanced"] = Field(
        default="enhanced", description="Strategy to use"
    )
    initial_capital: Decimal = Field(
        default=Decimal("100000.00"), gt=0, description="Starting capital per fold"
    )
    benchmark_symbol: str = Field(default="SPY", description="Benchmark for comparison")
    # Window configuration
    train_days: int = Field(default=180, ge=60, le=365, description="Training period days")
    val_days: int = Field(default=60, ge=30, le=180, description="Validation period days")
    test_days: int = Field(
        default=210, ge=200, le=365, description="Test period days (min 200 for indicator lookback)"
    )
    gap_days: int = Field(default=10, ge=1, le=30, description="Gap between periods")
    step_days: int = Field(default=60, ge=30, le=120, description="Roll-forward step size")
    # Strategy parameters
    min_confirmations: int = Field(default=5, ge=3, le=8, description="Min confirmations for entry")
    stop_loss_atr_multiplier: float = Field(
        default=2.0, gt=0.5, le=5.0, description="Stop loss ATR multiplier"
    )
    max_holding_days: int = Field(default=30, ge=5, le=120, description="Max holding period")


# ============================================================================
# Core Response Models
# ============================================================================


class StartBacktestResponse(BaseModel):
    """Response model for starting a backtest."""

    run_id: str
    task_id: str
    status: str
    message: str


class BacktestRunListItem(BaseModel):
    """Summary model for backtest run in list view."""

    id: str
    symbol: str
    strategy_name: str
    start_date: date
    end_date: date
    total_return_pct: Decimal | None
    sharpe_ratio: Decimal | None
    win_rate: Decimal | None
    num_trades: int | None
    status: str
    created_at: str


class NormalizedEquityPointResponse(BaseModel):
    """Normalized equity point for comparison charts."""

    date: date
    cumulative_return_pct: Decimal


class RunMetricsResponse(BaseModel):
    """Metrics summary for a single backtest run with rankings."""

    run_id: str
    symbol: str
    strategy_name: str
    start_date: date
    end_date: date
    total_return_pct: Decimal | None
    sharpe_ratio: Decimal | None
    max_drawdown_pct: Decimal | None
    win_rate: Decimal | None
    num_trades: int | None
    profit_factor: Decimal | None
    return_rank: int | None
    sharpe_rank: int | None
    drawdown_rank: int | None
    # Benchmark comparison fields
    buy_hold_return: Decimal | None = None
    excess_return: Decimal | None = None
    beats_buy_hold: bool | None = None
    alpha: Decimal | None = None
    information_ratio: Decimal | None = None
    beta: Decimal | None = None
    benchmark_symbol: str | None = None


class ComparisonResponse(BaseModel):
    """Complete comparison response for multiple backtest runs."""

    equity_curves: dict[str, list[NormalizedEquityPointResponse]]
    metrics: list[RunMetricsResponse]
    correlation_matrix: dict[str, dict[str, float]] | None


# ============================================================================
# Monte Carlo Response Models
# ============================================================================


class MonteCarloStatisticsResponse(BaseModel):
    """Statistics from Monte Carlo simulation."""

    num_simulations: int
    percentile_5: float
    percentile_25: float
    percentile_50: float
    percentile_75: float
    percentile_95: float
    probability_of_loss: float
    value_at_risk_95: float
    expected_shortfall: float
    mean_return: float
    std_dev: float
    skewness: float
    kurtosis: float
    original_return: float


class HistogramBin(BaseModel):
    """Single histogram bin."""

    bin_start: float
    bin_end: float
    frequency: float


class EquityBand(BaseModel):
    """Single equity band data point."""

    step: int
    p5: float
    p50: float
    p95: float


class MonteCarloResponse(BaseModel):
    """Complete Monte Carlo simulation response."""

    statistics: MonteCarloStatisticsResponse
    histogram_data: list[HistogramBin]
    equity_bands: list[EquityBand]
    created_at: str


# ============================================================================
# Strategy Metadata Response Models
# ============================================================================


class StrategyDetailsResponse(BaseModel):
    """Detailed strategy information for UI and AI agent consumption."""

    id: str
    name: str
    short_description: str
    when_to_use: str
    market_conditions: str
    holding_period: str
    risk_level: Literal["Low", "Medium", "High"]
    best_for: str
    avoid_when: str


# ============================================================================
# Walk-Forward Response Models
# ============================================================================


class FoldMetricsResponse(BaseModel):
    """Metrics for a single walk-forward fold."""

    fold_number: int
    # Strategy metrics
    total_return_pct: float
    sharpe_ratio: float
    win_rate: float
    max_drawdown_pct: float
    num_trades: int
    profit_factor: float
    # B&H comparison
    buy_hold_return_pct: float
    excess_return_pct: float
    beats_buy_hold: bool
    alpha: float | None
    beta: float | None
    # Period info
    test_start: date
    test_end: date


class WalkForwardResponse(BaseModel):
    """Complete walk-forward validation response."""

    # Per-fold results
    folds: list[FoldMetricsResponse]
    num_folds: int

    # Aggregated metrics
    mean_return_pct: float
    std_return_pct: float
    mean_sharpe: float
    std_sharpe: float
    mean_win_rate: float
    max_drawdown_pct: float
    total_trades: int

    # B&H comparison
    mean_excess_vs_bh: float
    pct_folds_beat_bh: float  # e.g., 0.8 = 80%

    # Statistical significance
    wilcoxon_p_value: float | None
    statistically_significant: bool
    significance_level: Literal["strong", "moderate", "weak", "none"]

    # Request metadata
    symbol: str
    strategy: str
    benchmark_symbol: str
