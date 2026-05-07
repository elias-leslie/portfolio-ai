"""Read-model helpers for Jenny dashboard data."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from app.models.jenny import (
    JennyAgentEvaluation,
    JennyAgentScorecard,
    JennyNotification,
    JennyPredictionReviewChange,
    JennyPredictionReviewClusterWeight,
    JennyPredictionReviewSeatWeight,
    JennyPredictionReviewSummary,
    JennyRoutine,
    JennySymbolReview,
    JennyTradeReview,
)
from app.models.market_prediction import (
    SUPPORTED_ADAPTIVE_CLUSTER_KEYS,
    SUPPORTED_ADAPTIVE_SEAT_KEYS,
    MarketPredictionClusterReview,
    MarketPredictionSeatReview,
    normalize_market_prediction_cluster_key,
    normalize_market_prediction_seat_key,
)
from app.repositories.market_prediction_repository import MarketPredictionRepository
from app.services.jenny_row_parsers import (
    row_to_evaluation,
    row_to_notification,
    row_to_routine,
    row_to_scorecard,
    row_to_trade_review,
)
from app.services.market_prediction_cluster_weighting_service import (
    MarketPredictionClusterWeightingService,
)
from app.services.market_prediction_committee_service import SUPPORTED_PREDICTION_WINDOWS


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

    def get_latest_prediction_review_summary(
        self,
        service: Any,
    ) -> JennyPredictionReviewSummary | None:
        repository = MarketPredictionRepository(service.storage)
        latest_review: MarketPredictionSeatReview | None = None
        for window_days in SUPPORTED_PREDICTION_WINDOWS:
            persisted = repository.list_latest_seat_reviews(window_days=window_days, limit=1)
            if not persisted:
                continue
            candidate = persisted[0]
            if latest_review is None or self._review_sort_key(candidate) > self._review_sort_key(latest_review):
                latest_review = candidate

        if latest_review is None:
            return None

        latest_cluster_review = self._latest_cluster_review_for_window(
            repository,
            window_days=latest_review.window_days,
            as_of_ts=latest_review.as_of_ts,
            storage=service.storage,
        )
        raw_summary = latest_review.review_summary if isinstance(latest_review.review_summary, dict) else {}
        raw_cluster_summary = (
            latest_cluster_review.review_summary
            if latest_cluster_review is not None and isinstance(latest_cluster_review.review_summary, dict)
            else {}
        )
        return JennyPredictionReviewSummary(
            window_days=latest_review.window_days,
            review_state=latest_review.review_state,
            generated_at=str(raw_summary.get("generated_at") or latest_review.generated_at.isoformat()),
            as_of_ts=latest_review.as_of_ts.isoformat(),
            seat_weights=[
                normalized
                for row in latest_review.seat_scorecards
                if (normalized := self._normalize_prediction_review_seat_weight(row)) is not None
            ],
            cluster_weights=[
                normalized
                for row in (latest_cluster_review.cluster_scorecards if latest_cluster_review is not None else [])
                if (normalized := self._normalize_prediction_review_cluster_weight(row)) is not None
            ],
            drift_callouts=self._merge_string_lists(raw_summary.get("drift_callouts"), raw_cluster_summary.get("drift_callouts")),
            gap_callouts=self._merge_string_lists(raw_summary.get("gap_callouts"), raw_cluster_summary.get("gap_callouts")),
            agent_actions=self._merge_string_lists(raw_summary.get("agent_actions"), raw_cluster_summary.get("agent_actions")),
            top_upweighted=[
                change
                for item in self._merge_raw_lists(raw_summary.get("top_upweighted"), raw_cluster_summary.get("top_upweighted"))
                if (change := self._normalize_prediction_review_change(item)) is not None
            ],
            top_downweighted=[
                change
                for item in self._merge_raw_lists(raw_summary.get("top_downweighted"), raw_cluster_summary.get("top_downweighted"))
                if (change := self._normalize_prediction_review_change(item)) is not None
            ],
        )

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

    def _normalize_prediction_review_change(
        self,
        raw_item: Any,
    ) -> JennyPredictionReviewChange | None:
        if not isinstance(raw_item, dict):
            return None
        kind = str(raw_item.get("kind") or "")
        if kind == "cluster":
            key = normalize_market_prediction_cluster_key(raw_item.get("key"))
            if key not in SUPPORTED_ADAPTIVE_CLUSTER_KEYS:
                return None
        else:
            key = normalize_market_prediction_seat_key(raw_item.get("key"))
            kind = "seat"
            if key not in SUPPORTED_ADAPTIVE_SEAT_KEYS:
                return None
        if key is None:
            return None
        try:
            return JennyPredictionReviewChange(
                kind=kind,
                key=key,
                prior_weight=float(raw_item.get("prior_weight") or 0.0),
                effective_weight=float(raw_item.get("effective_weight") or 0.0),
            )
        except (TypeError, ValueError):
            return None

    def _normalize_prediction_review_seat_weight(
        self,
        raw_row: Any,
    ) -> JennyPredictionReviewSeatWeight | None:
        if isinstance(raw_row, dict):
            seat_key = raw_row.get("seat_key")
            prior_weight = raw_row.get("prior_weight")
            effective_weight = raw_row.get("effective_weight")
            sample_size = raw_row.get("sample_size")
            recommended_action = raw_row.get("recommended_action")
        else:
            seat_key = getattr(raw_row, "seat_key", None)
            prior_weight = getattr(raw_row, "prior_weight", None)
            effective_weight = getattr(raw_row, "effective_weight", None)
            sample_size = getattr(raw_row, "sample_size", None)
            recommended_action = getattr(raw_row, "recommended_action", None)

        normalized_key = normalize_market_prediction_seat_key(seat_key)
        if normalized_key not in SUPPORTED_ADAPTIVE_SEAT_KEYS:
            return None
        try:
            return JennyPredictionReviewSeatWeight(
                seat_key=normalized_key,
                prior_weight=float(prior_weight),
                effective_weight=float(effective_weight),
                sample_size=int(sample_size or 0),
                recommended_action=str(recommended_action or "hold"),
            )
        except (TypeError, ValueError):
            return None

    def _normalize_prediction_review_cluster_weight(
        self,
        raw_row: Any,
    ) -> JennyPredictionReviewClusterWeight | None:
        if isinstance(raw_row, dict):
            cluster = raw_row.get("cluster")
            prior_weight = raw_row.get("prior_weight")
            effective_weight = raw_row.get("effective_weight")
            sample_size = raw_row.get("sample_size")
            freshness = raw_row.get("freshness")
            gate_state = raw_row.get("gate_state")
            recommended_action = raw_row.get("recommended_action")
        else:
            cluster = getattr(raw_row, "cluster", None)
            prior_weight = getattr(raw_row, "prior_weight", None)
            effective_weight = getattr(raw_row, "effective_weight", None)
            sample_size = getattr(raw_row, "sample_size", None)
            freshness = getattr(raw_row, "freshness", None)
            gate_state = getattr(raw_row, "gate_state", None)
            recommended_action = getattr(raw_row, "recommended_action", None)

        normalized_cluster = normalize_market_prediction_cluster_key(cluster)
        if normalized_cluster not in SUPPORTED_ADAPTIVE_CLUSTER_KEYS:
            return None
        try:
            return JennyPredictionReviewClusterWeight(
                cluster=normalized_cluster,
                prior_weight=float(prior_weight),
                effective_weight=float(effective_weight),
                sample_size=int(sample_size or 0),
                freshness=str(freshness or "unknown"),
                gate_state=str(gate_state or "off"),
                recommended_action=str(recommended_action or "hold"),
            )
        except (TypeError, ValueError):
            return None

    def _latest_cluster_review_for_window(
        self,
        repository: MarketPredictionRepository,
        *,
        window_days: int,
        as_of_ts: datetime,
        storage: Any,
    ) -> MarketPredictionClusterReview | None:
        return MarketPredictionClusterWeightingService(
            repository=repository,
            storage=storage,
        ).get_review(window_days=window_days, as_of_ts=as_of_ts)

    def _merge_string_lists(self, *values: Any) -> list[str]:
        merged: list[str] = []
        for value in values:
            if not isinstance(value, list):
                continue
            for item in value:
                text = str(item).strip()
                if text and text not in merged:
                    merged.append(text)
        return merged

    def _merge_raw_lists(self, *values: Any) -> list[Any]:
        merged: list[Any] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, list):
                continue
            for item in value:
                key = str(item)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(item)
        return merged

    def _review_sort_key(self, review: MarketPredictionSeatReview) -> tuple[datetime, datetime, str]:
        return (review.as_of_ts, review.generated_at, review.id)
