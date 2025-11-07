"""Fear & Greed Index calculation engine.

Implements percentile-based ranking and composition of Fear & Greed score.
Uses 252-day rolling window for historical context (1 trading year).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import structlog

from ..storage import PortfolioStorage

logger = structlog.get_logger(__name__)

# Regime thresholds (score 0-100)
REGIME_EXTREME_FEAR = 25
REGIME_FEAR = 45
REGIME_NEUTRAL = 55
REGIME_GREED = 75

# Signal weights for 5-signal index (equal weight)
WEIGHTS_5_SIGNAL = [0.2, 0.2, 0.2, 0.2, 0.2]  # VIX, Momentum, RSI, P/C, Credit


class FearGreedEngine:
    """Calculate Fear & Greed Index scores from input signals."""

    def __init__(self, storage: PortfolioStorage) -> None:
        """Initialize calculation engine.

        Args:
            storage: Database storage instance
        """
        self.storage = storage

    def calculate_percentile(
        self, value: float, historical_series: list[float], invert: bool = False
    ) -> int:
        """Calculate percentile rank for a value within historical context.

        Args:
            value: Current value to rank
            historical_series: Historical values for context
            invert: If True, invert percentile (used for fear signals like VIX)

        Returns:
            Percentile rank (0-100)
        """
        if not historical_series:
            logger.warning("empty_historical_series")
            return 50  # Default to neutral if no history

        # Add current value to series for percentile calculation
        all_values = [*historical_series, value]
        percentile = (
            np.searchsorted(np.sort(all_values), value, side="right") / len(all_values)
        ) * 100

        # Invert for fear signals (high VIX = fear = low score)
        if invert:
            percentile = 100 - percentile

        # Clamp to 0-100 range
        clamped: float = float(max(0, min(100, percentile)))
        return int(clamped)

    def score_momentum(self, spy_close: float, spy_sma_200: float) -> int:
        """Calculate momentum score based on SPY vs 200-day MA.

        Args:
            spy_close: Current SPY closing price
            spy_sma_200: SPY 200-day simple moving average

        Returns:
            Momentum score (0-100, higher = more bullish)
        """
        # Calculate percent above/below SMA
        pct_above = ((spy_close / spy_sma_200) - 1) * 100

        # Convert to 0-100 score
        # ±10% from SMA = 0 or 100
        # At SMA = 50
        score = 50 + (pct_above * 5)  # 1% above = +5 points
        return int(max(0, min(100, score)))

    def fetch_historical_data(self, field: str, window_days: int = 252) -> list[float]:
        """Fetch historical data for percentile calculation.

        Args:
            field: Field name (vix_close, hy_spread, put_call_ratio)
            window_days: Lookback window in days

        Returns:
            List of historical values
        """
        try:
            with self.storage.connection() as conn:
                result = conn.execute(f"""
                    SELECT {field}
                    FROM fear_greed_inputs
                    WHERE {field} IS NOT NULL
                    AND as_of_date >= CURRENT_DATE - INTERVAL '{window_days} days'
                    ORDER BY as_of_date ASC
                """)
                results = result.fetchall()

                values = [float(row[0]) for row in results if row[0] is not None]
                logger.info(
                    "historical_data_fetched",
                    field=field,
                    window_days=window_days,
                    count=len(values),
                )
                return values

        except Exception as e:
            logger.error(
                "historical_data_fetch_failed",
                field=field,
                window_days=window_days,
                error=str(e),
            )
            return []

    def score_signals(self, inputs: dict[str, Any], window_days: int = 252) -> dict[str, int]:
        """Calculate percentile scores for all signals.

        Args:
            inputs: Input signal values
            window_days: Lookback window for percentile calculation

        Returns:
            Dict with percentile scores for each signal
        """
        scores: dict[str, int] = {}

        # VIX percentile (inverted: high VIX = fear = low score)
        if "vix_close" in inputs:
            historical_vix = self.fetch_historical_data("vix_close", window_days)
            scores["vix_pct"] = self.calculate_percentile(
                inputs["vix_close"], historical_vix, invert=True
            )

        # Momentum score (SPY vs SMA_200)
        if "spy_close" in inputs and "spy_sma_200" in inputs:
            scores["momentum_pct"] = self.score_momentum(inputs["spy_close"], inputs["spy_sma_200"])

        # RSI percentile (high RSI = overbought = greed)
        if "rsi_14" in inputs:
            # RSI is already 0-100, use as-is (could add percentile ranking later)
            scores["rsi_pct"] = int(inputs["rsi_14"])

        # Put/Call percentile (inverted: high P/C = bearish = fear = low score)
        if "put_call_ratio" in inputs:
            historical_pcr = self.fetch_historical_data("put_call_ratio", window_days)
            scores["pcr_pct"] = self.calculate_percentile(
                inputs["put_call_ratio"], historical_pcr, invert=True
            )

        # Credit spread percentile (inverted: high spread = fear = low score)
        if "hy_spread" in inputs:
            historical_hy = self.fetch_historical_data("hy_spread", window_days)
            scores["credit_pct"] = self.calculate_percentile(
                inputs["hy_spread"], historical_hy, invert=True
            )

        logger.info("signals_scored", scores=scores, window_days=window_days)
        return scores

    def compose_score(self, components: dict[str, int]) -> float:
        """Compose final Fear & Greed score from components.

        Args:
            components: Dict with percentile scores

        Returns:
            Composite score (0-100)
        """
        # Extract component values in order
        signal_names = ["vix_pct", "momentum_pct", "rsi_pct", "pcr_pct", "credit_pct"]
        values = [components.get(name, 50) for name in signal_names]

        # Equal weight for 5 signals
        weights = WEIGHTS_5_SIGNAL
        score = sum(v * w for v, w in zip(values, weights, strict=True))

        logger.info("score_composed", components=components, score=score)
        return round(score, 1)

    def assign_label(self, score: float) -> str:
        """Assign regime label based on score.

        Args:
            score: Fear & Greed score (0-100)

        Returns:
            Regime label
        """
        if score >= REGIME_GREED:
            return "Extreme Greed"
        if score >= REGIME_NEUTRAL:
            return "Greed"
        if score >= REGIME_FEAR:
            return "Neutral"
        if score >= REGIME_EXTREME_FEAR:
            return "Fear"
        return "Extreme Fear"

    def fetch_previous_score(self, target_date: date) -> float | None:
        """Fetch previous trading day's score for trend calculation.

        Args:
            target_date: Current date

        Returns:
            Previous score, or None if not found
        """
        try:
            with self.storage.connection() as conn:
                # Find most recent score before target_date
                result = conn.execute(
                    """
                    SELECT score
                    FROM fear_greed_daily
                    WHERE as_of_date < %s
                    ORDER BY as_of_date DESC
                    LIMIT 1
                """,
                    (target_date,),
                )
                result = result.fetchone()
                if result:
                    return float(result[0])
                return None

        except Exception as e:
            logger.error("previous_score_fetch_failed", date=target_date, error=str(e))
            return None

    def calculate(self, inputs: dict[str, Any], target_date: date) -> dict[str, Any]:
        """Calculate complete Fear & Greed Index for a given date.

        Args:
            inputs: Input signal values
            target_date: Date to calculate for

        Returns:
            Dict with score, label, components, and metadata
        """
        # Score all signals
        components = self.score_signals(inputs)

        # Compose final score
        score = self.compose_score(components)

        # Assign label
        label = self.assign_label(score)

        # Fetch previous score for trend
        previous_score = self.fetch_previous_score(target_date)
        score_change = round(score - previous_score, 1) if previous_score is not None else None

        result = {
            "date": target_date,
            "score": score,
            "label": label,
            "components": components,
            "previous_score": previous_score,
            "score_change": score_change,
            "signal_count": len(components),
        }

        logger.info(
            "fear_greed_calculated",
            date=target_date,
            score=score,
            label=label,
            signal_count=len(components),
        )

        return result
