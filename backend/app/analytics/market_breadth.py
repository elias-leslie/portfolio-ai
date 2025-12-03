"""Enhanced market breadth analysis for GAP-017.

Extends basic sector breadth with:
- Multi-timeframe breadth analysis (1d, 5d, 20d)
- Breadth momentum (rate of change)
- Breadth divergence detection vs SPY
- Thrust signals (extreme breadth readings)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import TYPE_CHECKING

from ..constants import SECTOR_ETF_SYMBOLS
from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..storage.facade import PortfolioStorage

logger = get_logger(__name__)

# Import from centralized constants (DRY principle)
SECTOR_ETFS = SECTOR_ETF_SYMBOLS


class BreadthSignal(Enum):
    """Market breadth signal types."""

    THRUST_UP = "thrust_up"  # >90% sectors advancing
    STRONG_UP = "strong_up"  # 70-90% advancing
    MODERATE_UP = "moderate_up"  # 55-70% advancing
    NEUTRAL = "neutral"  # 45-55%
    MODERATE_DOWN = "moderate_down"  # 30-45%
    STRONG_DOWN = "strong_down"  # 10-30%
    THRUST_DOWN = "thrust_down"  # <10% advancing


@dataclass
class BreadthReading:
    """Single breadth reading for a date."""

    date: date
    advancing: int
    declining: int
    unchanged: int
    breadth_pct: float  # 0-100


@dataclass
class BreadthAnalysis:
    """Comprehensive breadth analysis result."""

    current_date: date
    breadth_1d: float  # Today's breadth %
    breadth_5d_avg: float  # 5-day average
    breadth_20d_avg: float  # 20-day average
    signal: BreadthSignal
    momentum: float  # 5d breadth - 20d breadth
    spy_performance_1d: float  # SPY daily return
    spy_performance_5d: float  # SPY 5-day return
    divergence: str | None  # "bullish_divergence", "bearish_divergence", None
    thrust_reading: bool  # True if >90% or <10%
    breadth_score: int  # -2 to +2 for signal integration


def calculate_breadth_reading(
    storage: PortfolioStorage,
    target_date: date,
) -> BreadthReading | None:
    """Calculate breadth reading for a single date.

    Args:
        storage: Database storage instance
        target_date: Date to calculate breadth for

    Returns:
        BreadthReading or None if insufficient data
    """
    query = """
        WITH price_data AS (
            SELECT
                ticker,
                date,
                close as current_close,
                LAG(close) OVER (PARTITION BY symbol ORDER BY date) as prev_close
            FROM day_bars
            WHERE symbol = ANY($1)
              AND date <= $2
              AND date >= $2 - INTERVAL '10 days'
        )
        SELECT symbol, current_close, prev_close
        FROM price_data
        WHERE date = $2
    """

    sector_list: list[str | int | float | bool | None] = list(SECTOR_ETFS)
    result = storage.query(query, [sector_list, str(target_date)])

    if result.height < 8:  # Require at least 8 of 11 sectors
        return None

    advancing = 0
    declining = 0
    unchanged = 0

    for row in result.iter_rows():
        current = row[1]
        prev = row[2]
        if current is None or prev is None:
            continue

        if current > prev:
            advancing += 1
        elif current < prev:
            declining += 1
        else:
            unchanged += 1

    total = advancing + declining + unchanged
    if total == 0:
        return None

    breadth_pct = (advancing / total) * 100

    return BreadthReading(
        date=target_date,
        advancing=advancing,
        declining=declining,
        unchanged=unchanged,
        breadth_pct=breadth_pct,
    )


def get_breadth_history(
    storage: PortfolioStorage,
    end_date: date,
    lookback_days: int = 30,
) -> list[BreadthReading]:
    """Get breadth history for multiple days.

    Args:
        storage: Database storage instance
        end_date: End date
        lookback_days: Days to look back

    Returns:
        List of BreadthReading, newest first
    """
    readings = []
    current = end_date

    for _ in range(lookback_days):
        reading = calculate_breadth_reading(storage, current)
        if reading:
            readings.append(reading)
        current -= timedelta(days=1)
        # Skip weekends
        while current.weekday() >= 5:
            current -= timedelta(days=1)

    return readings


def classify_breadth_signal(breadth_pct: float) -> BreadthSignal:  # noqa: PLR0911
    """Classify breadth percentage into signal.

    Args:
        breadth_pct: Breadth percentage (0-100)

    Returns:
        BreadthSignal enum
    """
    if breadth_pct >= 90:
        return BreadthSignal.THRUST_UP
    if breadth_pct >= 70:
        return BreadthSignal.STRONG_UP
    if breadth_pct >= 55:
        return BreadthSignal.MODERATE_UP
    if breadth_pct >= 45:
        return BreadthSignal.NEUTRAL
    if breadth_pct >= 30:
        return BreadthSignal.MODERATE_DOWN
    if breadth_pct >= 10:
        return BreadthSignal.STRONG_DOWN
    return BreadthSignal.THRUST_DOWN


def get_spy_returns(
    storage: PortfolioStorage,
    target_date: date,
) -> tuple[float, float]:
    """Get SPY returns for divergence analysis.

    Args:
        storage: Database storage instance
        target_date: Reference date

    Returns:
        Tuple of (1-day return, 5-day return) as percentages
    """
    query = """
        SELECT date, close
        FROM day_bars
        WHERE symbol = 'SPY'
          AND date <= $1
        ORDER BY date DESC
        LIMIT 20
    """

    result = storage.query(query, [str(target_date)])
    if result.height < 6:
        return 0.0, 0.0

    # Results are newest first
    closes = [row[1] for row in result.iter_rows()]

    # 1-day return
    return_1d = ((closes[0] - closes[1]) / closes[1]) * 100 if closes[1] else 0.0

    # 5-day return
    return_5d = ((closes[0] - closes[5]) / closes[5]) * 100 if closes[5] else 0.0

    return return_1d, return_5d


def detect_divergence(
    breadth_momentum: float,
    spy_5d_return: float,
) -> str | None:
    """Detect breadth/price divergence.

    Bullish divergence: breadth improving while SPY falling
    Bearish divergence: breadth weakening while SPY rising

    Args:
        breadth_momentum: 5d - 20d breadth average
        spy_5d_return: SPY 5-day return percentage

    Returns:
        "bullish_divergence", "bearish_divergence", or None
    """
    momentum_threshold = 5.0  # Significant breadth change
    return_threshold = 2.0  # Significant price change

    if breadth_momentum > momentum_threshold and spy_5d_return < -return_threshold:
        return "bullish_divergence"
    if breadth_momentum < -momentum_threshold and spy_5d_return > return_threshold:
        return "bearish_divergence"
    return None


def analyze_market_breadth(
    storage: PortfolioStorage,
    target_date: date | None = None,
) -> BreadthAnalysis | None:
    """Perform comprehensive breadth analysis.

    Args:
        storage: Database storage instance
        target_date: Date to analyze (defaults to latest)

    Returns:
        BreadthAnalysis or None if insufficient data
    """
    if target_date is None:
        # Get latest date from day_bars
        query = "SELECT MAX(date) FROM day_bars WHERE symbol = 'SPY'"
        result = storage.query(query, [])
        if result.is_empty() or result.row(0)[0] is None:
            return None
        target_date = result.row(0)[0]

    # Get breadth history
    history = get_breadth_history(storage, target_date, lookback_days=25)
    if len(history) < 5:
        return None

    # Current reading
    breadth_1d = history[0].breadth_pct

    # 5-day average
    breadth_5d_avg = sum(r.breadth_pct for r in history[:5]) / min(5, len(history))

    # 20-day average
    breadth_20d_avg = sum(r.breadth_pct for r in history[:20]) / min(20, len(history))

    # Signal classification
    signal = classify_breadth_signal(breadth_1d)

    # Momentum (5d vs 20d)
    momentum = breadth_5d_avg - breadth_20d_avg

    # SPY returns
    spy_1d, spy_5d = get_spy_returns(storage, target_date)

    # Divergence detection
    divergence = detect_divergence(momentum, spy_5d)

    # Thrust reading
    thrust_reading = breadth_1d >= 90 or breadth_1d <= 10

    # Calculate score for signal integration (-2 to +2)
    breadth_score = calculate_breadth_score(signal, momentum, divergence)

    return BreadthAnalysis(
        current_date=target_date,
        breadth_1d=breadth_1d,
        breadth_5d_avg=breadth_5d_avg,
        breadth_20d_avg=breadth_20d_avg,
        signal=signal,
        momentum=momentum,
        spy_performance_1d=spy_1d,
        spy_performance_5d=spy_5d,
        divergence=divergence,
        thrust_reading=thrust_reading,
        breadth_score=breadth_score,
    )


def calculate_breadth_score(
    signal: BreadthSignal,
    momentum: float,
    divergence: str | None,
) -> int:
    """Calculate breadth score for signal integration.

    Args:
        signal: Current breadth signal
        momentum: Breadth momentum
        divergence: Divergence type if any

    Returns:
        Score from -2 to +2
    """
    # Base score from signal
    signal_scores = {
        BreadthSignal.THRUST_UP: 2,
        BreadthSignal.STRONG_UP: 2,
        BreadthSignal.MODERATE_UP: 1,
        BreadthSignal.NEUTRAL: 0,
        BreadthSignal.MODERATE_DOWN: -1,
        BreadthSignal.STRONG_DOWN: -2,
        BreadthSignal.THRUST_DOWN: -2,
    }
    score = signal_scores.get(signal, 0)

    # Divergence adjustment
    if divergence == "bullish_divergence":
        score = min(2, score + 1)
    elif divergence == "bearish_divergence":
        score = max(-2, score - 1)

    return score
