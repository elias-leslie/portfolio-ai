"""Volatility regime detection for GAP-018.

Classifies market conditions into regimes based on VIX levels,
historical volatility percentiles, and regime transitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..storage.facade import PortfolioStorage

logger = get_logger(__name__)


class VolatilityRegime(Enum):
    """Market volatility regimes."""

    LOW = "low"  # VIX < 15, calm markets
    NORMAL = "normal"  # VIX 15-20, typical conditions
    ELEVATED = "elevated"  # VIX 20-30, heightened uncertainty
    HIGH = "high"  # VIX 30-50, fear/crisis
    EXTREME = "extreme"  # VIX > 50, panic


# VIX thresholds for regime classification
VIX_THRESHOLDS = {
    VolatilityRegime.LOW: (0, 15),
    VolatilityRegime.NORMAL: (15, 20),
    VolatilityRegime.ELEVATED: (20, 30),
    VolatilityRegime.HIGH: (30, 50),
    VolatilityRegime.EXTREME: (50, float("inf")),
}

# Regime-specific trading adjustments
REGIME_ADJUSTMENTS = {
    VolatilityRegime.LOW: {
        "position_size_multiplier": 1.2,  # Can size up in calm markets
        "stop_loss_multiplier": 0.8,  # Tighter stops OK
        "correlation_threshold": 0.7,  # Normal correlation limits
    },
    VolatilityRegime.NORMAL: {
        "position_size_multiplier": 1.0,
        "stop_loss_multiplier": 1.0,
        "correlation_threshold": 0.7,
    },
    VolatilityRegime.ELEVATED: {
        "position_size_multiplier": 0.8,  # Reduce size
        "stop_loss_multiplier": 1.2,  # Wider stops
        "correlation_threshold": 0.6,  # Tighter correlation limits
    },
    VolatilityRegime.HIGH: {
        "position_size_multiplier": 0.5,  # Half size
        "stop_loss_multiplier": 1.5,  # Much wider stops
        "correlation_threshold": 0.5,  # Very tight correlation
    },
    VolatilityRegime.EXTREME: {
        "position_size_multiplier": 0.25,  # Quarter size or cash
        "stop_loss_multiplier": 2.0,  # Very wide stops
        "correlation_threshold": 0.4,  # Minimal correlation
    },
}


@dataclass
class RegimeAnalysis:
    """Analysis of current volatility regime."""

    current_vix: float
    regime: VolatilityRegime
    vix_percentile: float  # 0-100, where current VIX sits historically
    regime_duration_days: int  # How long in current regime
    previous_regime: VolatilityRegime | None
    transition_signal: str | None  # "entering_high", "exiting_elevated", etc.
    trading_adjustments: dict[str, float]


def classify_vix_regime(vix: float) -> VolatilityRegime:
    """Classify VIX into a volatility regime.

    Args:
        vix: Current VIX value

    Returns:
        VolatilityRegime enum value
    """
    for regime, (low, high) in VIX_THRESHOLDS.items():
        if low <= vix < high:
            return regime
    return VolatilityRegime.EXTREME  # Safety fallback


def calculate_vix_percentile(  # noqa: PLR0911
    current_vix: float,
    storage: PortfolioStorage,
    lookback_days: int = 252,
) -> float:
    """Calculate where current VIX sits in historical distribution.

    Args:
        current_vix: Current VIX value
        storage: Database storage instance
        lookback_days: Days of history to consider

    Returns:
        Percentile (0-100) of current VIX in historical distribution
    """
    # Query VIX history from fear_greed_inputs or similar
    query = """
        SELECT vix
        FROM fear_greed_inputs
        WHERE date >= $1
        AND vix IS NOT NULL
        ORDER BY date
    """
    cutoff_date = datetime.now(UTC).date() - timedelta(days=lookback_days)
    result = storage.query(query, [str(cutoff_date)])

    if result.is_empty():
        # Fallback: use typical VIX distribution
        # Historical VIX median ~17, mean ~19
        if current_vix <= 12:
            return 10.0
        if current_vix <= 15:
            return 25.0
        if current_vix <= 18:
            return 50.0
        if current_vix <= 22:
            return 75.0
        if current_vix <= 30:
            return 90.0
        return 95.0

    vix_values = sorted([row[0] for row in result.iter_rows()])
    count_below = sum(1 for v in vix_values if v < current_vix)
    return (count_below / len(vix_values)) * 100


def get_regime_history(
    storage: PortfolioStorage,
    lookback_days: int = 30,
) -> list[tuple[date, VolatilityRegime]]:
    """Get recent regime history for transition detection.

    Args:
        storage: Database storage instance
        lookback_days: Days to look back

    Returns:
        List of (date, regime) tuples
    """
    query = """
        SELECT date, vix
        FROM fear_greed_inputs
        WHERE date >= $1
        AND vix IS NOT NULL
        ORDER BY date DESC
    """
    cutoff_date = datetime.now(UTC).date() - timedelta(days=lookback_days)
    result = storage.query(query, [str(cutoff_date)])

    return [(row[0], classify_vix_regime(row[1])) for row in result.iter_rows()]


def detect_regime_transition(
    current_regime: VolatilityRegime,
    regime_history: list[tuple[date, VolatilityRegime]],
) -> tuple[str | None, int, VolatilityRegime | None]:
    """Detect regime transitions and duration.

    Args:
        current_regime: Current volatility regime
        regime_history: Recent regime history

    Returns:
        Tuple of (transition_signal, duration_days, previous_regime)
    """
    if not regime_history:
        return None, 0, None

    # Find when current regime started
    duration_days = 0
    previous_regime = None

    for _, regime in regime_history:
        if regime == current_regime:
            duration_days += 1
        else:
            previous_regime = regime
            break

    # Detect transition signals
    transition_signal = None
    if duration_days <= 3 and previous_regime:
        # Recent transition
        if current_regime.value > previous_regime.value:
            transition_signal = f"entering_{current_regime.value}"
        else:
            transition_signal = f"exiting_to_{current_regime.value}"

    return transition_signal, duration_days, previous_regime


def analyze_volatility_regime(
    storage: PortfolioStorage,
    current_vix: float | None = None,
) -> RegimeAnalysis:
    """Perform comprehensive volatility regime analysis.

    Args:
        storage: Database storage instance
        current_vix: Optional override for VIX value

    Returns:
        RegimeAnalysis with current regime and trading adjustments
    """
    # Get current VIX if not provided
    if current_vix is None:
        query = """
            SELECT vix FROM fear_greed_inputs
            WHERE vix IS NOT NULL
            ORDER BY date DESC
            LIMIT 1
        """
        result = storage.query(query, [])
        current_vix = result.row(0)[0] if not result.is_empty() else 20.0  # Default to normal

    # Classify current regime
    regime = classify_vix_regime(current_vix)

    # Get historical percentile
    vix_percentile = calculate_vix_percentile(current_vix, storage)

    # Get regime history for transition detection
    regime_history = get_regime_history(storage)

    # Detect transitions
    transition_signal, duration_days, previous_regime = detect_regime_transition(
        regime, regime_history
    )

    # Get trading adjustments for current regime
    adjustments = REGIME_ADJUSTMENTS[regime]

    return RegimeAnalysis(
        current_vix=current_vix,
        regime=regime,
        vix_percentile=vix_percentile,
        regime_duration_days=duration_days,
        previous_regime=previous_regime,
        transition_signal=transition_signal,
        trading_adjustments=adjustments,
    )


def get_regime_score(regime: VolatilityRegime) -> int:
    """Get numeric score for regime (for signal integration).

    Lower regimes are better for entering positions.

    Args:
        regime: Current volatility regime

    Returns:
        Score from -2 to +2 for signal adjustment
    """
    scores = {
        VolatilityRegime.LOW: 2,  # Great for new positions
        VolatilityRegime.NORMAL: 1,  # Good conditions
        VolatilityRegime.ELEVATED: 0,  # Neutral/cautious
        VolatilityRegime.HIGH: -1,  # Avoid new positions
        VolatilityRegime.EXTREME: -2,  # Stay out
    }
    return scores.get(regime, 0)
