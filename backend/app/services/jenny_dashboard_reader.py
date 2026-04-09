"""Read-model helpers for Jenny dashboard data."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.models.jenny import (
    JennyAgentEvaluation,
    JennyAgentScorecard,
    JennyNotification,
    JennyRoutine,
    JennySymbolReview,
    JennyTradeReview,
)
from app.services.jenny_row_parsers import (
    row_to_evaluation,
    row_to_notification,
    row_to_routine,
    row_to_scorecard,
    row_to_trade_review,
)


class JennyDashboardReader:
    """Load persisted Jenny state and aggregate symbol reviews."""

    def get_recent_routines(self, service: Any, limit: int = 6) -> list[JennyRoutine]:
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, routine_type, status, triggered_by, summary, agents_used, symbols_scanned,
                       notifications_created, started_at, completed_at, metadata
                FROM jenny_routines
                ORDER BY started_at DESC
                LIMIT %s
                """,
                [limit],
            ).fetchall()
        return [row_to_routine(row) for row in rows]

    def get_routine(self, service: Any, routine_id: str) -> JennyRoutine:
        with service.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT id, routine_type, status, triggered_by, summary, agents_used, symbols_scanned,
                       notifications_created, started_at, completed_at, metadata
                FROM jenny_routines
                WHERE id = %s
                """,
                [routine_id],
            ).fetchone()
        if row is None:
            raise RuntimeError(f"Jenny routine {routine_id} not found")
        return row_to_routine(row)

    def get_open_notifications(self, service: Any, limit: int = 12) -> list[JennyNotification]:
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, routine_id, symbol, category, severity, status, title, detail,
                       recommendation, created_at, acknowledged_at, metadata
                FROM jenny_notifications
                WHERE status = 'open'
                  AND created_at >= NOW() - INTERVAL '7 days'
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 0
                        WHEN 'warning' THEN 1
                        ELSE 2
                    END,
                    created_at DESC
                LIMIT %s
                """,
                [limit],
            ).fetchall()
        return [row_to_notification(row) for row in rows]

    def get_open_notifications_for_symbol(
        self,
        service: Any,
        symbol: str,
        limit: int = 5,
    ) -> list[JennyNotification]:
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, routine_id, symbol, category, severity, status, title, detail,
                       recommendation, created_at, acknowledged_at, metadata
                FROM jenny_notifications
                WHERE status = 'open'
                  AND created_at >= NOW() - INTERVAL '7 days'
                  AND symbol = %s
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 0
                        WHEN 'warning' THEN 1
                        ELSE 2
                    END,
                    created_at DESC
                LIMIT %s
                """,
                [symbol, limit],
            ).fetchall()
        return [row_to_notification(row) for row in rows]

    def get_notification(self, service: Any, notification_id: str) -> JennyNotification | None:
        with service.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT id, routine_id, symbol, category, severity, status, title, detail,
                       recommendation, created_at, acknowledged_at, metadata
                FROM jenny_notifications
                WHERE id = %s
                """,
                [notification_id],
            ).fetchone()
        return row_to_notification(row) if row else None

    def get_latest_symbol_reviews(self, service: Any, limit: int = 8) -> list[JennySymbolReview]:
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                WITH latest_symbol_routines AS (
                    SELECT DISTINCT ON (symbol)
                        symbol,
                        routine_id,
                        created_at
                    FROM jenny_agent_evaluations
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                    ORDER BY symbol, created_at DESC
                )
                SELECT e.id, e.routine_id, e.symbol, e.agent_name, e.provider, e.model, e.verdict, e.confidence,
                       e.rationale, e.recommendation, e.strengths, e.weaknesses, e.metadata, e.thesis_id,
                       e.agent_run_id, e.created_at
                FROM jenny_agent_evaluations e
                JOIN latest_symbol_routines lsr
                  ON lsr.symbol = e.symbol
                 AND lsr.routine_id = e.routine_id
                ORDER BY lsr.created_at DESC, e.created_at DESC
                LIMIT %s
                """,
                [limit * len(service.AGENT_SPECS) * 2],
            ).fetchall()
        evaluations = [row_to_evaluation(row) for row in rows]
        latest_routine_by_symbol: dict[str, str] = {}
        for evaluation in evaluations:
            latest_routine_by_symbol.setdefault(evaluation.symbol, evaluation.routine_id)

        grouped: dict[str, list[JennyAgentEvaluation]] = defaultdict(list)
        for evaluation in evaluations:
            if latest_routine_by_symbol.get(evaluation.symbol) != evaluation.routine_id:
                continue
            grouped[evaluation.symbol].append(evaluation)
        reviews = [
            service._aggregate_symbol_review(
                symbol,
                symbol_evaluations,
                service.thesis_service.get_thesis(symbol),
            )
            for symbol, symbol_evaluations in grouped.items()
        ]
        action_map = service._build_position_action_map({review.symbol: review for review in reviews})
        for review in reviews:
            action = action_map.get(review.symbol)
            if action:
                review.management_action = action["action"]
                review.management_detail = action["detail"]
                review.position_gain_pct = action.get("gain_pct")
                review.position_weight_pct = action.get("weight_pct")
        return reviews[:limit]

    def get_latest_symbol_review(
        self,
        service: Any,
        symbol: str,
    ) -> JennySymbolReview | None:
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                WITH latest_symbol_routine AS (
                    SELECT routine_id
                    FROM jenny_agent_evaluations
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                      AND symbol = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                SELECT e.id, e.routine_id, e.symbol, e.agent_name, e.provider, e.model, e.verdict, e.confidence,
                       e.rationale, e.recommendation, e.strengths, e.weaknesses, e.metadata, e.thesis_id,
                       e.agent_run_id, e.created_at
                FROM jenny_agent_evaluations e
                JOIN latest_symbol_routine lsr
                  ON lsr.routine_id = e.routine_id
                WHERE e.symbol = %s
                ORDER BY e.created_at DESC
                """,
                [symbol, symbol],
            ).fetchall()
        evaluations = [row_to_evaluation(row) for row in rows]
        if not evaluations:
            return None

        review = service._aggregate_symbol_review(
            symbol,
            evaluations,
            service.thesis_service.get_thesis(symbol),
        )
        action_map = service._build_position_action_map({review.symbol: review})
        action = action_map.get(review.symbol)
        if action:
            review.management_action = action["action"]
            review.management_detail = action["detail"]
            review.position_gain_pct = action.get("gain_pct")
            review.position_weight_pct = action.get("weight_pct")
        return review

    def build_review_consensus(self, service: Any, symbol: str) -> dict[str, Any]:
        latest_review = next(
            (
                review
                for review in self.get_latest_symbol_reviews(service, limit=20)
                if review.symbol == symbol
            ),
            None,
        )
        if latest_review is None:
            return {}
        return {
            "final_verdict": latest_review.final_verdict,
            "average_confidence": latest_review.average_confidence,
            "agents": [evaluation.agent_name for evaluation in latest_review.evaluations],
            "agent_verdicts": {
                evaluation.agent_name: evaluation.verdict
                for evaluation in latest_review.evaluations
            },
            "agent_confidences": {
                evaluation.agent_name: evaluation.confidence
                for evaluation in latest_review.evaluations
                if evaluation.confidence is not None
            },
        }

    def get_recent_trade_reviews(self, service: Any, limit: int = 12) -> list[JennyTradeReview]:
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, symbol, thesis_id, idea_id, review_source, outcome_label,
                       return_pct, lesson, what_worked, what_failed, next_time,
                       created_at, updated_at, agent_consensus, metadata
                FROM jenny_trade_reviews
                ORDER BY created_at DESC
                LIMIT %s
                """,
                [limit],
            ).fetchall()
        return [row_to_trade_review(row) for row in rows]

    def get_scorecards(self, service: Any) -> list[JennyAgentScorecard]:
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT agent_name, total_evaluations, completed_reviews, positive_verdicts,
                       win_rate, avg_return_pct, agreement_rate, calibration_score,
                       entry_quality_score, risk_judgment_score, exit_timing_score, alert_discipline_score,
                       strengths, weaknesses, last_evaluation_at, updated_at
                FROM jenny_agent_scorecards
                ORDER BY
                    COALESCE(entry_quality_score, win_rate * 100, 0) DESC,
                    COALESCE(avg_return_pct, 0) DESC
                """
            ).fetchall()
        return [row_to_scorecard(row) for row in rows]

    def fetch_all_evaluations(self, service: Any) -> list[JennyAgentEvaluation]:
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, routine_id, symbol, agent_name, provider, model, verdict, confidence,
                       rationale, recommendation, strengths, weaknesses, metadata, thesis_id,
                       agent_run_id, created_at
                FROM jenny_agent_evaluations
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [row_to_evaluation(row) for row in rows]
