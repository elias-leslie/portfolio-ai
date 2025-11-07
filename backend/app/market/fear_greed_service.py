"""Fear & Greed Index service layer.

Orchestrates data fetching, calculation, and persistence.
Provides high-level API for computing and retrieving Fear & Greed Index data.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import structlog

from ..storage import PortfolioStorage
from .fear_greed import FearGreedEngine
from .fear_greed_data import FearGreedDataFetcher

logger = structlog.get_logger(__name__)


class FearGreedService:
    """Service for Fear & Greed Index operations."""

    def __init__(self, storage: PortfolioStorage) -> None:
        """Initialize service.

        Args:
            storage: Database storage instance
        """
        self.storage = storage
        self.fetcher = FearGreedDataFetcher(storage)
        self.engine = FearGreedEngine(storage)

    def persist_inputs(self, target_date: date, inputs: dict[str, Any]) -> None:
        """Persist input signal data to database.

        Args:
            target_date: Date for the data
            inputs: Input signal values
        """
        try:
            with self.storage.connection() as conn:
                conn.execute(
                    """
                INSERT INTO fear_greed_inputs
                (as_of_date, vix_close, spy_close, spy_sma_200, rsi_14,
                put_call_ratio, hy_spread, source_map)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (as_of_date)
                DO UPDATE SET
                vix_close = EXCLUDED.vix_close,
                spy_close = EXCLUDED.spy_close,
                spy_sma_200 = EXCLUDED.spy_sma_200,
                rsi_14 = EXCLUDED.rsi_14,
                put_call_ratio = EXCLUDED.put_call_ratio,
                hy_spread = EXCLUDED.hy_spread,
                source_map = EXCLUDED.source_map,
                created_at = NOW()
                """,
                    (
                        target_date,
                        inputs.get("vix_close"),
                        inputs.get("spy_close"),
                        inputs.get("spy_sma_200"),
                        inputs.get("rsi_14"),
                        inputs.get("put_call_ratio"),
                        inputs.get("hy_spread"),
                        json.dumps(inputs.get("source_map", {})),
                    ),
                )
                conn.commit()
                logger.info("inputs_persisted", date=target_date)

        except Exception as e:
            logger.error("inputs_persist_failed", date=target_date, error=str(e))
            raise

    def persist_components(
        self, target_date: date, components: dict[str, int], window_days: int = 252
    ) -> None:
        """Persist component percentiles to database.

        Args:
            target_date: Date for the data
            components: Component percentile scores
            window_days: Lookback window used for calculation
        """
        try:
            with self.storage.connection() as conn:
                conn.execute(
                    """
                INSERT INTO fear_greed_components
                (as_of_date, vix_pct, momentum_pct, rsi_pct, pcr_pct, credit_pct, window_days)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (as_of_date)
                DO UPDATE SET
                vix_pct = EXCLUDED.vix_pct,
                momentum_pct = EXCLUDED.momentum_pct,
                rsi_pct = EXCLUDED.rsi_pct,
                pcr_pct = EXCLUDED.pcr_pct,
                credit_pct = EXCLUDED.credit_pct,
                window_days = EXCLUDED.window_days,
                created_at = NOW()
                """,
                    (
                        target_date,
                        components.get("vix_pct"),
                        components.get("momentum_pct"),
                        components.get("rsi_pct"),
                        components.get("pcr_pct"),
                        components.get("credit_pct"),
                        window_days,
                    ),
                )
                conn.commit()
                logger.info("components_persisted", date=target_date, components=components)

        except Exception as e:
            logger.error("components_persist_failed", date=target_date, error=str(e))
            raise

    def persist_score(self, target_date: date, result: dict[str, Any]) -> None:
        """Persist final Fear & Greed score to database.

        Args:
            target_date: Date for the data
            result: Calculation result with score, label, etc.
        """
        try:
            with self.storage.connection() as conn:
                conn.execute(
                    """
                INSERT INTO fear_greed_daily
                (as_of_date, score, label, previous_score, score_change, signal_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (as_of_date)
                DO UPDATE SET
                score = EXCLUDED.score,
                label = EXCLUDED.label,
                previous_score = EXCLUDED.previous_score,
                score_change = EXCLUDED.score_change,
                signal_count = EXCLUDED.signal_count,
                created_at = NOW()
                """,
                    (
                        target_date,
                        result["score"],
                        result["label"],
                        result.get("previous_score"),
                        result.get("score_change"),
                        result.get("signal_count", 5),
                    ),
                )
                conn.commit()
                logger.info(
                    "score_persisted",
                    date=target_date,
                    score=result["score"],
                    label=result["label"],
                )

        except Exception as e:
            logger.error("score_persist_failed", date=target_date, error=str(e))
            raise

    def compute_for_date(self, target_date: date) -> dict[str, Any]:
        """Compute Fear & Greed Index for a specific date.

        Orchestrates:
        1. Fetch input signals
        2. Calculate components and score
        3. Persist all results

        Args:
            target_date: Date to compute for

        Returns:
            Complete calculation result
        """
        logger.info("fear_greed_compute_start", date=target_date)

        try:
            # Fetch all input signals
            inputs = self.fetcher.fetch_all_inputs(target_date)

            # Check if we have minimum required signals
            required = ["vix_close", "spy_close", "rsi_14"]
            missing = [s for s in required if s not in inputs]
            if missing:
                logger.error(
                    "insufficient_signals",
                    date=target_date,
                    missing=missing,
                )
                raise ValueError(f"Missing required signals: {missing}")

            # Persist inputs
            self.persist_inputs(target_date, inputs)

            # Calculate components and score
            result = self.engine.calculate(inputs, target_date)

            # Persist components
            self.persist_components(target_date, result["components"])

            # Persist score
            self.persist_score(target_date, result)

            logger.info(
                "fear_greed_compute_complete",
                date=target_date,
                score=result["score"],
                label=result["label"],
            )

            return result

        except Exception as e:
            logger.error("fear_greed_compute_failed", date=target_date, error=str(e))
            raise

    def get_latest(self) -> dict[str, Any] | None:
        """Get latest Fear & Greed score.

        Returns:
            Latest score data, or None if no data
        """
        try:
            with self.storage.connection() as conn:
                result = conn.execute(
                    """
                SELECT as_of_date, score, label, previous_score, score_change, signal_count
                FROM fear_greed_daily
                ORDER BY as_of_date DESC
                LIMIT 1
                """
                )
                result = result.fetchone()

                if result:
                    return {
                        "date": result[0],
                        "score": float(result[1]),
                        "label": result[2],
                        "previous_score": float(result[3]) if result[3] else None,
                        "score_change": float(result[4]) if result[4] else None,
                        "signal_count": result[5],
                    }
                return None

        except Exception as e:
            logger.error("get_latest_failed", error=str(e))
            return None

    def get_by_date(self, target_date: date) -> dict[str, Any] | None:
        """Get Fear & Greed score for a specific date.

        Args:
            target_date: Date to retrieve

        Returns:
            Score data for the date, or None if not found
        """
        try:
            with self.storage.connection() as conn:
                result = conn.execute(
                    """
                SELECT as_of_date, score, label, previous_score, score_change, signal_count
                FROM fear_greed_daily
                WHERE as_of_date = %s
                """,
                    (target_date,),
                )
                result = result.fetchone()

                if result:
                    return {
                        "date": result[0],
                        "score": float(result[1]),
                        "label": result[2],
                        "previous_score": float(result[3]) if result[3] else None,
                        "score_change": float(result[4]) if result[4] else None,
                        "signal_count": result[5],
                    }
                return None

        except Exception as e:
            logger.error("get_by_date_failed", date=target_date, error=str(e))
            return None

    def get_history(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        """Get Fear & Greed history for a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of score data dicts
        """
        try:
            with self.storage.connection() as conn:
                result = conn.execute(
                    """
                SELECT as_of_date, score, label, previous_score, score_change, signal_count
                FROM fear_greed_daily
                WHERE as_of_date >= %s AND as_of_date <= %s
                ORDER BY as_of_date ASC
                """,
                    (start_date, end_date),
                )
                results = result.fetchall()

                return [
                    {
                        "date": row[0],
                        "score": float(row[1]),
                        "label": row[2],
                        "previous_score": float(row[3]) if row[3] else None,
                        "score_change": float(row[4]) if row[4] else None,
                        "signal_count": row[5],
                    }
                    for row in results
                ]

        except Exception as e:
            logger.error(
                "get_history_failed",
                start_date=start_date,
                end_date=end_date,
                error=str(e),
            )
            return []

    def get_components(self, target_date: date) -> dict[str, Any] | None:
        """Get component percentiles for a specific date.

        Args:
            target_date: Date to retrieve

        Returns:
            Component data, or None if not found
        """
        try:
            with self.storage.connection() as conn:
                result = conn.execute(
                    """
                SELECT as_of_date, vix_pct, momentum_pct, rsi_pct, pcr_pct, credit_pct, window_days
                FROM fear_greed_components
                WHERE as_of_date = %s
                """,
                    (target_date,),
                )
                result = result.fetchone()

                if result:
                    return {
                        "date": result[0],
                        "vix_pct": result[1],
                        "momentum_pct": result[2],
                        "rsi_pct": result[3],
                        "pcr_pct": result[4],
                        "credit_pct": result[5],
                        "window_days": result[6],
                    }
                return None

        except Exception as e:
            logger.error("get_components_failed", date=target_date, error=str(e))
            return None
