"""Multi-horizon momentum calculations (GAP-012).

Implements multi-timeframe momentum analysis based on Jegadeesh & Titman (1993):
- 5-day (weekly): Short-term momentum, high noise
- 20-day (monthly): Tactical momentum, moderate signal
- 60-day (quarterly): Intermediate momentum, strong signal
- 252-day (annual): Long-term trend, strongest signal

Momentum factor has been shown to predict returns across asset classes.
Cross-sectional ranks provide relative strength vs market.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)

# Standard momentum horizons (trading days)
MOMENTUM_HORIZONS = [5, 20, 60, 252]

# Regime thresholds (percentage of 252-day momentum)
STRONG_UPTREND = 20.0  # >20% annual momentum = strong uptrend
WEAK_UPTREND = 5.0  # 5-20% = weak uptrend
CHOPPY_RANGE = -5.0  # -5% to 5% = choppy/range-bound
WEAK_DOWNTREND = -20.0  # -20% to -5% = weak downtrend
# <-20% = strong downtrend


@dataclass
class MomentumMetrics:
    """Multi-horizon momentum metrics for a ticker."""

    ticker: str
    as_of_date: date
    momentum_5d: float | None  # 5-day return %
    momentum_20d: float | None  # 20-day return %
    momentum_60d: float | None  # 60-day return %
    momentum_252d: float | None  # 252-day return %
    regime: str  # "STRONG_UP", "UP", "CHOPPY", "DOWN", "STRONG_DOWN"
    trend_alignment: bool  # True if all horizons agree on direction


def calculate_momentum(
    storage: PortfolioStorage,
    ticker: str,
    target_date: date | None = None,
) -> MomentumMetrics | None:
    """Calculate multi-horizon momentum for a ticker.

    Args:
        storage: Database storage
        ticker: Stock ticker symbol
        target_date: Date to calculate momentum for (default: most recent)

    Returns:
        MomentumMetrics or None if insufficient data
    """
    if target_date is None:
        target_date = date.today()

    # Fetch OHLCV data for longest horizon + buffer
    lookback = max(MOMENTUM_HORIZONS) + 10  # Extra days for weekends/holidays

    query = """
        SELECT date, close
        FROM day_bars
        WHERE ticker = $1 AND date <= $2
        ORDER BY date DESC
        LIMIT $3
    """
    result = storage.query(query, [ticker, str(target_date), lookback])

    if result.is_empty():
        logger.warning("momentum_no_data", ticker=ticker)
        return None

    # Convert to dict: date -> close
    prices: dict[date, float] = {}
    for row in result.iter_rows(named=True):
        row_date = row["date"]
        if isinstance(row_date, str):
            from datetime import datetime

            row_date = datetime.strptime(row_date, "%Y-%m-%d").date()
        prices[row_date] = float(row["close"])

    if not prices:
        return None

    # Get latest date and close
    sorted_dates = sorted(prices.keys(), reverse=True)
    latest_date = sorted_dates[0]
    latest_close = prices[latest_date]

    # Calculate momentum for each horizon
    momentum_values: dict[int, float | None] = {}

    for horizon in MOMENTUM_HORIZONS:
        # Find the close price ~horizon trading days ago
        prior_close = _get_prior_close(prices, sorted_dates, horizon)

        if prior_close is not None and prior_close > 0:
            pct_change = ((latest_close - prior_close) / prior_close) * 100
            momentum_values[horizon] = pct_change
        else:
            momentum_values[horizon] = None

    # Determine regime based on 252-day momentum
    regime = _determine_regime(momentum_values.get(252))

    # Check trend alignment
    trend_alignment = _check_trend_alignment(momentum_values)

    return MomentumMetrics(
        ticker=ticker,
        as_of_date=latest_date,
        momentum_5d=momentum_values.get(5),
        momentum_20d=momentum_values.get(20),
        momentum_60d=momentum_values.get(60),
        momentum_252d=momentum_values.get(252),
        regime=regime,
        trend_alignment=trend_alignment,
    )


def _get_prior_close(
    prices: dict[date, float],
    sorted_dates: list[date],
    horizon: int,
) -> float | None:
    """Get close price approximately horizon trading days ago.

    Args:
        prices: Date -> close price mapping
        sorted_dates: Dates sorted descending (most recent first)
        horizon: Number of trading days to look back

    Returns:
        Close price or None if not enough data
    """
    if len(sorted_dates) <= horizon:
        return None

    # Use the date at position [horizon] in sorted descending list
    # e.g., for horizon=5, we want the 6th date (index 5)
    prior_date = sorted_dates[horizon]
    return prices.get(prior_date)


def _determine_regime(momentum_252d: float | None) -> str:
    """Determine market regime based on 252-day momentum.

    Args:
        momentum_252d: 252-day return percentage

    Returns:
        Regime string: "STRONG_UP", "UP", "CHOPPY", "DOWN", "STRONG_DOWN"
    """
    if momentum_252d is None:
        return "UNKNOWN"

    if momentum_252d >= STRONG_UPTREND:
        return "STRONG_UP"
    elif momentum_252d >= WEAK_UPTREND:
        return "UP"
    elif momentum_252d >= CHOPPY_RANGE:
        return "CHOPPY"
    elif momentum_252d >= WEAK_DOWNTREND:
        return "DOWN"
    else:
        return "STRONG_DOWN"


def _check_trend_alignment(momentum_values: dict[int, float | None]) -> bool:
    """Check if all momentum horizons agree on direction.

    All horizons positive or all negative = aligned.
    Mixed signals = not aligned.

    Args:
        momentum_values: Dict of horizon -> momentum percentage

    Returns:
        True if all non-None values have same sign
    """
    non_null = [v for v in momentum_values.values() if v is not None]

    if len(non_null) < 2:
        return False  # Not enough data to determine alignment

    all_positive = all(v > 0 for v in non_null)
    all_negative = all(v < 0 for v in non_null)

    return all_positive or all_negative


def calculate_momentum_score(
    momentum: MomentumMetrics | None,
) -> tuple[int, list[str]]:
    """Calculate 0-5 point momentum score for signal classification.

    Scoring:
    - +2 if 252d momentum > 10% (strong long-term trend)
    - +1 if 252d momentum 0-10% (weak uptrend)
    - +1 if all horizons aligned (confluence)
    - +1 if 60d > 20d > 5d (accelerating momentum)
    - -1 if 252d < -10% (strong downtrend)

    Args:
        momentum: MomentumMetrics or None

    Returns:
        (score, reasons) where score is 0-5
    """
    if momentum is None:
        return 0, []

    score = 0
    reasons: list[str] = []

    # Long-term momentum component (0-2 points)
    if momentum.momentum_252d is not None:
        if momentum.momentum_252d >= 20.0:
            score += 2
            reasons.append(f"Strong 252d momentum: +{momentum.momentum_252d:.1f}%")
        elif momentum.momentum_252d >= 10.0:
            score += 2
            reasons.append(f"Positive 252d momentum: +{momentum.momentum_252d:.1f}%")
        elif momentum.momentum_252d >= 0.0:
            score += 1
            reasons.append(f"Weak 252d momentum: +{momentum.momentum_252d:.1f}%")
        elif momentum.momentum_252d <= -20.0:
            score -= 1
            reasons.append(f"Strong 252d downtrend: {momentum.momentum_252d:.1f}%")

    # Trend alignment bonus (+1 point)
    if momentum.trend_alignment:
        score += 1
        reasons.append("All momentum horizons aligned")

    # Acceleration check (+1 point if momentum accelerating)
    if (
        momentum.momentum_60d is not None
        and momentum.momentum_20d is not None
        and momentum.momentum_5d is not None
    ):
        if momentum.momentum_5d > momentum.momentum_20d > 0:
            # Short-term catching up to medium-term = acceleration
            score += 1
            reasons.append("Momentum accelerating (5d > 20d)")

    # Clamp to 0-5 range
    score = max(0, min(5, score))

    return score, reasons


def get_momentum_inputs(
    storage: PortfolioStorage,
    ticker: str,
) -> dict[str, float | bool | str | None]:
    """Get momentum inputs for signal classification.

    Args:
        storage: Database storage
        ticker: Stock ticker symbol

    Returns:
        Dict with momentum_5d, momentum_20d, momentum_60d, momentum_252d,
        momentum_regime, momentum_aligned
    """
    momentum = calculate_momentum(storage, ticker)

    if momentum is None:
        return {
            "momentum_5d": None,
            "momentum_20d": None,
            "momentum_60d": None,
            "momentum_252d": None,
            "momentum_regime": None,
            "momentum_aligned": None,
        }

    return {
        "momentum_5d": momentum.momentum_5d,
        "momentum_20d": momentum.momentum_20d,
        "momentum_60d": momentum.momentum_60d,
        "momentum_252d": momentum.momentum_252d,
        "momentum_regime": momentum.regime,
        "momentum_aligned": momentum.trend_alignment,
    }
