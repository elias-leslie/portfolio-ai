"""Parameter grid generation for strategy optimization.

This module provides parameter range creation and grid generation.
"""

from __future__ import annotations

import itertools
import logging
from decimal import Decimal

from .models import StrategyGenerationResult, StrategyParameters

logger = logging.getLogger(__name__)


def create_range(base_value: float | int, options: list[float | int]) -> list[float | int]:
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


def generate_param_grid(
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
        "weight_price_trend": create_range(
            base_params.weight_price_trend, [0.10, 0.15, 0.20, 0.25]
        ),
        "weight_fundamentals": create_range(
            base_params.weight_fundamentals, [0.10, 0.15, 0.20, 0.25]
        ),
        "weight_news_sentiment": create_range(
            base_params.weight_news_sentiment, [0.10, 0.15, 0.20, 0.25]
        ),
        "weight_sector_alignment": create_range(
            base_params.weight_sector_alignment, [0.05, 0.10, 0.15, 0.20]
        ),
        # Note: Backtest mode uses technical-only signals (4-6 confirmations typical)
        # Lower thresholds allow trades in backtest validation
        "min_confirmations": create_range(base_params.min_confirmations, [3, 4, 5]),
        "stop_loss_atr_multiplier": create_range(
            float(base_params.stop_loss_atr_multiplier), [1.5, 2.0, 2.5]
        ),
        "max_holding_days": create_range(base_params.max_holding_days, [30, 45, 60, 90]),
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
                min_confirmations=int(combo_dict["min_confirmations"]),
                min_weighted_score=base_params.min_weighted_score,
                stop_loss_atr_multiplier=Decimal(str(combo_dict["stop_loss_atr_multiplier"])),
                max_holding_days=int(combo_dict["max_holding_days"]),
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
