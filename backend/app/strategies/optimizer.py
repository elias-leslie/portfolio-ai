"""Strategy parameter optimization using walk-forward validation.

This module implements parameter optimization via backtesting to find the best
configuration for a generated strategy template. Uses walk-forward validation
to avoid overfitting to historical data.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.logging_config import get_logger
from app.storage import PortfolioStorage

from .models import (
    OptimizedStrategyConfig,
    ResearchInsights,
    StrategyGenerationResult,
    StrategyParameters,
)
from .optimizer_metrics import aggregate_window_metrics, select_best_metrics
from .optimizer_params import generate_param_grid
from .optimizer_persistence import extract_fundamental_data, persist_best_backtest
from .optimizer_validation import create_walk_forward_windows, test_params_across_windows

logger = get_logger(__name__)


class StrategyOptimizer:
    """Optimizer for strategy parameters using walk-forward validation."""

    def __init__(self) -> None:
        """Initialize strategy optimizer."""
        self.storage = PortfolioStorage()
        self._fundamental_data: dict[str, object] = {}

    async def optimize_strategy_parameters(
        self,
        symbol: str,
        strategy_template: StrategyGenerationResult,
        research: ResearchInsights | None = None,
        lookback_days: int = 365,
        max_combinations: int = 50,
    ) -> OptimizedStrategyConfig:
        """Optimize strategy parameters using walk-forward validation.

        Args:
            symbol: Stock symbol
            strategy_template: Base strategy from agent
            research: Real fundamental data from ResearchAggregator
            lookback_days: Historical data to use (default 1 year)
            max_combinations: Maximum parameter combinations to test (default 50)

        Returns:
            OptimizedStrategyConfig with best parameters and metrics

        Raises:
            ValueError: If no viable strategies found or insufficient data
        """
        # Extract fundamental data from research for signal classifier
        self._fundamental_data = extract_fundamental_data(research)
        logger.info(
            f"Starting strategy optimization for {symbol} (type={strategy_template.strategy_type}, "
            f"lookback={lookback_days}d, max_combinations={max_combinations})"
        )

        # Generate parameter combinations
        param_combinations = generate_param_grid(strategy_template, max_combinations)

        logger.info("param_combinations_generated", count=len(param_combinations))

        # Create walk-forward validation windows
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)
        windows = create_walk_forward_windows(start_date, end_date)

        logger.info("validation_windows_created", count=len(windows))

        # Test each parameter combination across all windows
        results = []
        for idx, params in enumerate(param_combinations):
            logger.info(
                "testing_combination", index=idx + 1, total=len(param_combinations), params=self._summarize_params(params)
            )

            try:
                window_results = await test_params_across_windows(
                    self.storage, symbol, params, windows, self._fundamental_data
                )

                # Aggregate metrics across windows
                metrics = aggregate_window_metrics(window_results)

                results.append(
                    {
                        "params": params,
                        "metrics": metrics,
                        "window_results": window_results,
                    }
                )

                logger.info(
                    f"Combination {idx + 1} results: Sharpe={metrics['avg_sharpe']:.2f}, "
                    f"Drawdown={metrics['max_drawdown']:.1%}, WinRate={metrics['avg_win_rate']:.1%}"
                )

            except Exception as e:
                logger.warning(
                    f"Combination {idx + 1} failed: {e} (params={self._summarize_params(params)})"
                )
                continue

        if not results:
            raise ValueError("All parameter combinations failed during optimization")

        # Select best configuration
        best_config = self._select_best_configuration(results, strategy_template)

        logger.info(
            f"Optimization complete for {symbol}: Best Sharpe={best_config.avg_sharpe:.2f}, "
            f"WinRate={best_config.avg_win_rate:.1%}, tested {len(results)} combinations"
        )

        return best_config

    def _select_best_configuration(
        self,
        results: list[dict[str, Any]],
        strategy_template: StrategyGenerationResult,
    ) -> OptimizedStrategyConfig:
        """Select best parameter configuration from results.

        Args:
            results: List of result dicts with params and metrics
            strategy_template: Original strategy template

        Returns:
            OptimizedStrategyConfig with best parameters

        Raises:
            ValueError: If no viable strategies found
        """
        best, optimization_metrics = select_best_metrics(results)

        return OptimizedStrategyConfig(
            strategy_type=strategy_template.strategy_type,
            parameters=best["params"],
            optimization_metrics=optimization_metrics,
            confidence=strategy_template.confidence * 0.9,  # Slight penalty
            avg_sharpe=best["metrics"]["avg_sharpe"],
            max_drawdown=best["metrics"]["max_drawdown"],
            avg_win_rate=best["metrics"]["avg_win_rate"],
        )

    def _summarize_params(self, params: StrategyParameters) -> dict[str, Any]:
        """Create summary of key parameters for logging.

        Args:
            params: Strategy parameters

        Returns:
            Dict with key parameter values
        """
        return {
            "weight_price": params.weight_price_trend,
            "weight_fund": params.weight_fundamentals,
            "weight_news": params.weight_news_sentiment,
            "min_conf": params.min_confirmations,
            "stop_loss": float(params.stop_loss_atr_multiplier),
            "max_hold": params.max_holding_days,
        }

    def persist_backtest(
        self,
        symbol: str,
        strategy_name: str,
        params: StrategyParameters,
        metrics: dict[str, float],
        strategy_id: str | None = None,
    ) -> str:
        """Persist the best backtest run to database.

        Args:
            symbol: Stock symbol
            strategy_name: Strategy name
            params: Optimized parameters
            metrics: Aggregated metrics from optimization
            strategy_id: Optional strategy ID to link

        Returns:
            Backtest run ID
        """
        return persist_best_backtest(
            storage=self.storage,
            symbol=symbol,
            strategy_name=strategy_name,
            params=params,
            metrics=metrics,
            fundamental_data=self._fundamental_data,
            strategy_id=strategy_id,
        )


# Singleton instance
_optimizer_instance: StrategyOptimizer | None = None


def get_strategy_optimizer() -> StrategyOptimizer:
    """Get singleton instance of strategy optimizer."""
    global _optimizer_instance  # noqa: PLW0603
    if _optimizer_instance is None:
        _optimizer_instance = StrategyOptimizer()
    return _optimizer_instance
