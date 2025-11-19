"""Strategy parameter optimization using walk-forward validation.

This module implements parameter optimization via backtesting to find the best
configuration for a generated strategy template. Uses walk-forward validation
to avoid overfitting to historical data.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.backtest.replay import run_backtest
from app.backtest.strategies import SignalStrategy
from app.storage import PortfolioStorage

from .models import (
    OptimizedStrategyConfig,
    StrategyGenerationResult,
    StrategyParameters,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationWindow:
    """Walk-forward validation window dates."""

    train_start: date
    train_end: date
    val_start: date
    val_end: date


@dataclass
class BacktestMetrics:
    """Backtest performance metrics."""

    sharpe_ratio: float
    win_rate: float
    max_drawdown: float
    total_return: float
    num_trades: int
    profit_factor: float


class StrategyOptimizer:
    """Optimizer for strategy parameters using walk-forward validation."""

    def __init__(self) -> None:
        """Initialize strategy optimizer."""
        self.storage = PortfolioStorage()

    async def optimize_strategy_parameters(
        self,
        symbol: str,
        strategy_template: StrategyGenerationResult,
        lookback_days: int = 365,
        max_combinations: int = 50,
    ) -> OptimizedStrategyConfig:
        """Optimize strategy parameters using walk-forward validation.

        Args:
            symbol: Stock ticker
            strategy_template: Base strategy from agent
            lookback_days: Historical data to use (default 1 year)
            max_combinations: Maximum parameter combinations to test (default 50)

        Returns:
            OptimizedStrategyConfig with best parameters and metrics

        Raises:
            ValueError: If no viable strategies found or insufficient data
        """
        logger.info(
            "Starting strategy optimization",
            symbol=symbol,
            strategy_type=strategy_template.strategy_type,
            lookback_days=lookback_days,
            max_combinations=max_combinations,
        )

        # Generate parameter combinations
        param_combinations = self._generate_param_grid(strategy_template, max_combinations)

        logger.info(f"Generated {len(param_combinations)} parameter combinations to test")

        # Create walk-forward validation windows
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)
        windows = self._create_walk_forward_windows(start_date, end_date)

        logger.info(f"Created {len(windows)} validation windows")

        # Test each parameter combination across all windows
        results = []
        for idx, params in enumerate(param_combinations):
            logger.info(
                f"Testing combination {idx + 1}/{len(param_combinations)}",
                params=self._summarize_params(params),
            )

            try:
                window_results = await self._test_params_across_windows(symbol, params, windows)

                # Aggregate metrics across windows
                metrics = self._aggregate_window_metrics(window_results)

                results.append(
                    {
                        "params": params,
                        "metrics": metrics,
                        "window_results": window_results,
                    }
                )

                logger.info(
                    f"Combination {idx + 1} results",
                    avg_sharpe=metrics["avg_sharpe"],
                    max_drawdown=metrics["max_drawdown"],
                    avg_win_rate=metrics["avg_win_rate"],
                )

            except Exception as e:
                logger.warning(
                    f"Combination {idx + 1} failed: {e}", params=self._summarize_params(params)
                )
                continue

        if not results:
            raise ValueError("All parameter combinations failed during optimization")

        # Select best configuration
        best_config = self._select_best_configuration(results, strategy_template)

        logger.info(
            "Optimization complete",
            symbol=symbol,
            best_sharpe=best_config.avg_sharpe,
            best_win_rate=best_config.avg_win_rate,
            combinations_tested=len(results),
        )

        return best_config

    def _generate_param_grid(
        self,
        strategy_template: StrategyGenerationResult,
        max_combinations: int,
    ) -> list[StrategyParameters]:
        """Generate parameter combinations to test.

        Args:
            strategy_template: Base strategy from agent
            max_combinations: Maximum combinations to generate

        Returns:
            List of StrategyParameters to test
        """
        # Define parameter ranges to test
        # Start with agent's suggested values as baseline
        base_params = strategy_template.parameters

        # Generate variations around base values
        param_ranges = {
            "weight_price_trend": self._create_range(
                base_params.weight_price_trend, [0.10, 0.15, 0.20, 0.25]
            ),
            "weight_fundamentals": self._create_range(
                base_params.weight_fundamentals, [0.10, 0.15, 0.20, 0.25]
            ),
            "weight_news_sentiment": self._create_range(
                base_params.weight_news_sentiment, [0.10, 0.15, 0.20, 0.25]
            ),
            "weight_sector_alignment": self._create_range(
                base_params.weight_sector_alignment, [0.05, 0.10, 0.15, 0.20]
            ),
            "min_confirmations": self._create_range(base_params.min_confirmations, [5, 6, 7]),
            "stop_loss_atr_multiplier": self._create_range(
                float(base_params.stop_loss_atr_multiplier), [1.5, 2.0, 2.5]
            ),
            "max_holding_days": self._create_range(base_params.max_holding_days, [30, 45, 60, 90]),
        }

        # Generate all combinations (Cartesian product)
        keys = list(param_ranges.keys())
        values = [param_ranges[k] for k in keys]
        all_combinations = list(itertools.product(*values))

        # Limit to max_combinations
        if len(all_combinations) > max_combinations:
            # Sample evenly across space
            step = len(all_combinations) // max_combinations
            sampled = all_combinations[::step][:max_combinations]
        else:
            sampled = all_combinations

        # Build StrategyParameters objects
        param_objects = []
        for combo in sampled:
            combo_dict = dict(zip(keys, combo, strict=True))

            # Calculate other weights to sum to 1.0
            variable_weights = (
                combo_dict["weight_price_trend"]
                + combo_dict["weight_fundamentals"]
                + combo_dict["weight_news_sentiment"]
                + combo_dict["weight_sector_alignment"]
            )
            remaining = 1.0 - variable_weights

            # Distribute remaining to fixed weights
            weight_rsi_health = remaining * 0.3
            weight_momentum = remaining * 0.4
            weight_volume = remaining * 0.3

            try:
                params = StrategyParameters(
                    weight_price_trend=combo_dict["weight_price_trend"],
                    weight_rsi_health=weight_rsi_health,
                    weight_momentum=weight_momentum,
                    weight_volume=weight_volume,
                    weight_fundamentals=combo_dict["weight_fundamentals"],
                    weight_news_sentiment=combo_dict["weight_news_sentiment"],
                    weight_sector_alignment=combo_dict["weight_sector_alignment"],
                    min_confirmations=combo_dict["min_confirmations"],
                    min_weighted_score=base_params.min_weighted_score,
                    stop_loss_atr_multiplier=Decimal(str(combo_dict["stop_loss_atr_multiplier"])),
                    max_holding_days=combo_dict["max_holding_days"],
                    position_sizing_method=base_params.position_sizing_method,
                    position_size_value=base_params.position_size_value,
                    rsi_oversold_threshold=base_params.rsi_oversold_threshold,
                    rsi_overbought_threshold=base_params.rsi_overbought_threshold,
                    volume_multiplier_threshold=base_params.volume_multiplier_threshold,
                    news_sentiment_threshold=base_params.news_sentiment_threshold,
                )
                param_objects.append(params)
            except ValueError as e:
                # Skip invalid combinations (weights don't sum to 1.0)
                logger.debug(f"Skipping invalid combination: {e}")
                continue

        logger.info(f"Generated {len(param_objects)} valid parameter combinations")
        return param_objects

    def _create_range(
        self, base_value: float | int, options: list[float | int]
    ) -> list[float | int]:
        """Create parameter range around base value.

        Args:
            base_value: Agent's suggested value
            options: Possible values to test

        Returns:
            List including base value and nearby options
        """
        # Always include base value
        if base_value in options:
            return options

        # Find closest option and include it + neighbors
        closest = min(options, key=lambda x: abs(x - base_value))
        idx = options.index(closest)

        # Include base, closest, and one neighbor on each side
        range_values = [base_value, closest]
        if idx > 0:
            range_values.append(options[idx - 1])
        if idx < len(options) - 1:
            range_values.append(options[idx + 1])

        return sorted(set(range_values))

    def _create_walk_forward_windows(
        self, start_date: date, end_date: date
    ) -> list[ValidationWindow]:
        """Create walk-forward validation windows.

        Args:
            start_date: Start of historical period
            end_date: End of historical period (today)

        Returns:
            List of ValidationWindow objects
        """
        windows = []
        train_days = 180  # 6 months training
        val_days = 60  # 2 months validation
        step_days = 60  # Roll forward 2 months

        current_date = start_date
        while current_date + timedelta(days=train_days + val_days) <= end_date:
            train_start = current_date
            train_end = current_date + timedelta(days=train_days)
            val_start = train_end + timedelta(days=1)
            val_end = val_start + timedelta(days=val_days)

            windows.append(
                ValidationWindow(
                    train_start=train_start,
                    train_end=train_end,
                    val_start=val_start,
                    val_end=val_end,
                )
            )

            current_date += timedelta(days=step_days)

        return windows

    async def _test_params_across_windows(
        self,
        symbol: str,
        params: StrategyParameters,
        windows: list[ValidationWindow],
    ) -> list[BacktestMetrics]:
        """Test parameter configuration across validation windows.

        Args:
            symbol: Stock ticker
            params: Strategy parameters to test
            windows: Validation windows

        Returns:
            List of BacktestMetrics (one per validation window)
        """
        results = []

        for window in windows:
            # Run backtest on validation window
            strategy = SignalStrategy(
                min_signal_strength=params.min_confirmations,
                max_holding_days=params.max_holding_days,
                stop_loss_atr_multiplier=params.stop_loss_atr_multiplier,
            )

            backtest_result = run_backtest(
                storage=self.storage,
                symbol=symbol,
                start_date=window.val_start,
                end_date=window.val_end,
                strategy=strategy,
                initial_capital=Decimal("100000.00"),
            )

            # Extract metrics
            metrics = BacktestMetrics(
                sharpe_ratio=float(backtest_result.sharpe_ratio or 0.0),
                win_rate=float(backtest_result.win_rate or 0.0),
                max_drawdown=abs(float(backtest_result.max_drawdown_pct or 0.0)),
                total_return=float(backtest_result.total_return_pct or 0.0),
                num_trades=backtest_result.num_trades or 0,
                profit_factor=float(backtest_result.profit_factor or 0.0),
            )

            results.append(metrics)

        return results

    def _aggregate_window_metrics(self, window_results: list[BacktestMetrics]) -> dict[str, float]:
        """Aggregate metrics across validation windows.

        Args:
            window_results: Backtest metrics from each window

        Returns:
            Dict with aggregated metrics
        """
        if not window_results:
            return {
                "avg_sharpe": 0.0,
                "max_drawdown": 1.0,
                "avg_win_rate": 0.0,
                "avg_return": 0.0,
                "total_trades": 0,
            }

        return {
            "avg_sharpe": sum(r.sharpe_ratio for r in window_results) / len(window_results),
            "max_drawdown": max(r.max_drawdown for r in window_results),
            "avg_win_rate": sum(r.win_rate for r in window_results) / len(window_results),
            "avg_return": sum(r.total_return for r in window_results) / len(window_results),
            "total_trades": sum(r.num_trades for r in window_results),
        }

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
        # Filter viable strategies (Sharpe > 1.0, drawdown < 25%)
        viable = [
            r
            for r in results
            if r["metrics"]["avg_sharpe"] > 1.0 and r["metrics"]["max_drawdown"] < 0.25
        ]

        if not viable:
            # Relax filters if nothing passes
            viable = [
                r
                for r in results
                if r["metrics"]["avg_sharpe"] > 0.7 and r["metrics"]["max_drawdown"] < 0.35
            ]

        if not viable:
            raise ValueError("No viable strategies found (all failed Sharpe or drawdown filters)")

        # Rank by average Sharpe ratio
        best = max(viable, key=lambda x: x["metrics"]["avg_sharpe"])

        # Convert window results to dicts for storage
        optimization_metrics = [
            {
                "sharpe_ratio": m.sharpe_ratio,
                "win_rate": m.win_rate,
                "max_drawdown": m.max_drawdown,
                "total_return": m.total_return,
                "num_trades": m.num_trades,
            }
            for m in best["window_results"]
        ]

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


# Singleton instance
_optimizer_instance: StrategyOptimizer | None = None


def get_strategy_optimizer() -> StrategyOptimizer:
    """Get singleton instance of strategy optimizer."""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = StrategyOptimizer()
    return _optimizer_instance
