"""Repository layer for market-prediction committee persistence."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from app.models.market_prediction import (
    CommitteeSeatVote,
    MarketPredictionCall,
    MarketPredictionCommitteeResponse,
    MarketPredictionEvaluation,
    MarketPredictionEvaluationCandidate,
    MarketPredictionRun,
    MarketPredictionScorecard,
)

if TYPE_CHECKING:
    from app.storage import PortfolioStorage


class MarketPredictionRepository:
    """Database access layer for prediction runs, calls, votes, and evaluations."""

    def __init__(self, storage: PortfolioStorage):
        self.storage = storage

    @staticmethod
    def _dump(value: Any) -> str:
        return json.dumps(value, default=str)

    @staticmethod
    def _load(value: Any, fallback: Any) -> Any:
        if value in (None, ""):
            return fallback
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return fallback
        return fallback

    def persist_snapshot(
        self,
        *,
        run: MarketPredictionRun,
        calls: list[MarketPredictionCall],
        votes: list[CommitteeSeatVote],
    ) -> None:
        with self.storage.connection() as conn:
            self._create_run_with_connection(conn, run)
            for call in calls:
                self._upsert_call_with_connection(conn, run.id, call)
            self._replace_votes_for_run_with_connection(conn, run.id, votes)
            conn.commit()

    def create_run(self, run: MarketPredictionRun) -> None:
        with self.storage.connection() as conn:
            self._create_run_with_connection(conn, run)
            conn.commit()

    def _create_run_with_connection(self, conn: Any, run: MarketPredictionRun) -> None:
        conn.execute(
            """
            INSERT INTO market_prediction_runs (
                id,
                generated_at,
                as_of_ts,
                window_days,
                base_date,
                target_date,
                target_universe,
                lead_symbol,
                lead_direction,
                lead_prob_up,
                lead_expected_move_pct,
                source_snapshot,
                committee_summary,
                metadata
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb
            )
            """,
            [
                run.id,
                run.generated_at,
                run.as_of_ts,
                run.window_days,
                run.base_date,
                run.target_date,
                self._dump(run.target_universe),
                run.lead_symbol,
                run.lead_direction,
                run.lead_prob_up,
                run.lead_expected_move_pct,
                self._dump(run.source_snapshot),
                self._dump(run.committee_summary),
                self._dump(run.metadata),
            ],
        )

    def upsert_call(self, run_id: str, call: MarketPredictionCall) -> None:
        with self.storage.connection() as conn:
            self._upsert_call_with_connection(conn, run_id, call)
            conn.commit()

    def _upsert_call_with_connection(self, conn: Any, run_id: str, call: MarketPredictionCall) -> None:
        call_id = call.id or str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO market_prediction_calls (
                id,
                run_id,
                symbol,
                window_days,
                direction_label,
                prob_up,
                expected_move_pct,
                confidence_band_low_pct,
                confidence_band_high_pct,
                confidence_score,
                committee_disagreement_score,
                rationale_summary,
                top_source_clusters,
                metadata
            ) VALUES (
                %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb
            )
            ON CONFLICT (run_id, symbol)
            DO UPDATE SET
                direction_label = EXCLUDED.direction_label,
                prob_up = EXCLUDED.prob_up,
                expected_move_pct = EXCLUDED.expected_move_pct,
                confidence_band_low_pct = EXCLUDED.confidence_band_low_pct,
                confidence_band_high_pct = EXCLUDED.confidence_band_high_pct,
                confidence_score = EXCLUDED.confidence_score,
                committee_disagreement_score = EXCLUDED.committee_disagreement_score,
                rationale_summary = EXCLUDED.rationale_summary,
                top_source_clusters = EXCLUDED.top_source_clusters,
                metadata = EXCLUDED.metadata
            """,
            [
                call_id,
                run_id,
                call.symbol,
                call.window_days,
                call.direction_label,
                call.prob_up,
                call.expected_move_pct,
                call.confidence_band_low_pct,
                call.confidence_band_high_pct,
                call.confidence_score,
                call.committee_disagreement_score,
                call.rationale_summary,
                self._dump([cluster.model_dump() for cluster in call.top_source_clusters]),
                self._dump(call.metadata),
            ],
        )

    def replace_votes_for_run(self, run_id: str, votes: list[CommitteeSeatVote]) -> None:
        with self.storage.connection() as conn:
            self._replace_votes_for_run_with_connection(conn, run_id, votes)
            conn.commit()

    def _replace_votes_for_run_with_connection(
        self,
        conn: Any,
        run_id: str,
        votes: list[CommitteeSeatVote],
    ) -> None:
        conn.execute("DELETE FROM market_prediction_votes WHERE run_id = %s", [run_id])
        for vote in votes:
            conn.execute(
                """
                INSERT INTO market_prediction_votes (
                    run_id,
                    symbol,
                    window_days,
                    seat_key,
                    agent_slug,
                    model_id,
                    provider,
                    direction_label,
                    prob_up,
                    expected_move_pct,
                    confidence_score,
                    rationale_summary,
                    source_clusters,
                    metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb
                )
                """,
                [
                    run_id,
                    vote.symbol,
                    vote.window_days,
                    vote.seat_key,
                    vote.agent_slug,
                    vote.model_id,
                    vote.provider,
                    vote.direction_label,
                    vote.prob_up,
                    vote.expected_move_pct,
                    vote.confidence_score,
                    vote.rationale_summary,
                    self._dump([cluster.model_dump() for cluster in vote.source_clusters]),
                    self._dump(vote.metadata),
                ],
            )

    def upsert_evaluation(self, evaluation: MarketPredictionEvaluation) -> None:
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO market_prediction_evaluations (
                    call_id,
                    evaluated_at,
                    base_close,
                    target_close,
                    realized_move_pct,
                    direction_hit,
                    move_abs_error_pct,
                    brier_score,
                    metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
                )
                ON CONFLICT (call_id)
                DO UPDATE SET
                    evaluated_at = EXCLUDED.evaluated_at,
                    base_close = EXCLUDED.base_close,
                    target_close = EXCLUDED.target_close,
                    realized_move_pct = EXCLUDED.realized_move_pct,
                    direction_hit = EXCLUDED.direction_hit,
                    move_abs_error_pct = EXCLUDED.move_abs_error_pct,
                    brier_score = EXCLUDED.brier_score,
                    metadata = EXCLUDED.metadata
                """,
                [
                    evaluation.call_id,
                    evaluation.evaluated_at,
                    evaluation.base_close,
                    evaluation.target_close,
                    evaluation.realized_move_pct,
                    evaluation.direction_hit,
                    evaluation.move_abs_error_pct,
                    evaluation.brier_score,
                    self._dump(evaluation.metadata),
                ],
            )
            conn.commit()

    def upsert_vote_evaluation(self, evaluation: MarketPredictionVoteEvaluation) -> None:
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO market_prediction_vote_evaluations (
                    vote_id,
                    evaluated_at,
                    seat_key,
                    symbol,
                    window_days,
                    base_close,
                    target_close,
                    realized_move_pct,
                    direction_hit,
                    move_abs_error_pct,
                    brier_score,
                    metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
                )
                ON CONFLICT (vote_id)
                DO UPDATE SET
                    evaluated_at = EXCLUDED.evaluated_at,
                    seat_key = EXCLUDED.seat_key,
                    symbol = EXCLUDED.symbol,
                    window_days = EXCLUDED.window_days,
                    base_close = EXCLUDED.base_close,
                    target_close = EXCLUDED.target_close,
                    realized_move_pct = EXCLUDED.realized_move_pct,
                    direction_hit = EXCLUDED.direction_hit,
                    move_abs_error_pct = EXCLUDED.move_abs_error_pct,
                    brier_score = EXCLUDED.brier_score,
                    metadata = EXCLUDED.metadata
                """,
                [
                    evaluation.vote_id,
                    evaluation.evaluated_at,
                    evaluation.seat_key,
                    evaluation.symbol,
                    evaluation.window_days,
                    evaluation.base_close,
                    evaluation.target_close,
                    evaluation.realized_move_pct,
                    evaluation.direction_hit,
                    evaluation.move_abs_error_pct,
                    evaluation.brier_score,
                    self._dump(evaluation.metadata),
                ],
            )
            conn.commit()

    def list_vote_evaluation_backfill_candidates(
        self,
        *,
        window_days: int,
        effective_market_date: date,
        run_limit: int = 120,
        max_age_days: int = 180,
    ) -> list[MarketPredictionVoteEvaluationCandidate]:
        min_base_date = effective_market_date - timedelta(days=max_age_days)
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                WITH eligible_runs AS (
                    SELECT id, base_date, target_date, as_of_ts
                    FROM market_prediction_runs
                    WHERE window_days = %s
                      AND target_date <= %s
                      AND base_date >= %s
                    ORDER BY as_of_ts DESC
                    LIMIT %s
                )
                SELECT
                    v.id,
                    v.run_id,
                    v.symbol,
                    v.window_days,
                    v.seat_key,
                    v.direction_label,
                    v.prob_up,
                    v.expected_move_pct,
                    r.base_date,
                    r.target_date,
                    v.confidence_score
                FROM eligible_runs r
                JOIN market_prediction_votes v ON v.run_id = r.id
                WHERE v.window_days = %s
                ORDER BY r.as_of_ts DESC, v.symbol ASC, v.id ASC
                """,
                [window_days, effective_market_date, min_base_date, run_limit, window_days],
            ).fetchall()
        return [
            MarketPredictionVoteEvaluationCandidate(
                vote_id=int(row[0]),
                run_id=str(row[1]),
                symbol=str(row[2]),
                window_days=int(row[3]),
                seat_key=str(row[4]) if row[4] is not None else None,
                direction_label=str(row[5]),
                prob_up=float(row[6]),
                expected_move_pct=float(row[7]),
                base_date=self._coerce_date(row[8]),
                target_date=self._coerce_date(row[9]),
                confidence_score=float(row[10]) if row[10] is not None else None,
            )
            for row in rows
        ]

    def list_vote_evaluations_for_weighting(
        self,
        *,
        window_days: int,
        effective_market_date: date,
    ) -> list[MarketPredictionVoteEvaluation]:
        del effective_market_date
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    vote_id,
                    evaluated_at,
                    seat_key,
                    symbol,
                    window_days,
                    base_close,
                    target_close,
                    realized_move_pct,
                    direction_hit,
                    move_abs_error_pct,
                    brier_score,
                    metadata
                FROM market_prediction_vote_evaluations
                WHERE window_days = %s
                ORDER BY evaluated_at DESC, vote_id DESC
                """,
                [window_days],
            ).fetchall()
        return [self._row_to_vote_evaluation(row) for row in rows]

    def upsert_seat_review(self, review: MarketPredictionSeatReview) -> MarketPredictionSeatReview:
        with self.storage.connection() as conn:
            existing = conn.execute(
                """
                SELECT
                    id,
                    generated_at,
                    as_of_ts,
                    window_days,
                    review_state,
                    seat_scorecards,
                    review_summary,
                    metadata
                FROM market_prediction_seat_reviews
                WHERE window_days = %s AND as_of_ts = %s
                LIMIT 1
                """,
                [review.window_days, review.as_of_ts],
            ).fetchone()
            if existing is not None:
                existing_review = self._row_to_seat_review(existing)
                incoming_rank = self._review_state_rank(review.review_state)
                existing_rank = self._review_state_rank(existing_review.review_state)
                if incoming_rank < existing_rank:
                    return existing_review
                if incoming_rank == existing_rank:
                    if review.generated_at < existing_review.generated_at:
                        return existing_review
                    if review.generated_at == existing_review.generated_at:
                        return existing_review
                conn.execute(
                    """
                    UPDATE market_prediction_seat_reviews
                    SET generated_at = %s,
                        review_state = %s,
                        seat_scorecards = %s::jsonb,
                        review_summary = %s::jsonb,
                        metadata = %s::jsonb
                    WHERE id = %s
                    """,
                    [
                        review.generated_at,
                        review.review_state,
                        self._dump([row.model_dump() if hasattr(row, "model_dump") else row for row in review.seat_scorecards]),
                        self._dump(review.review_summary),
                        self._dump(review.metadata),
                        existing_review.id,
                    ],
                )
                conn.commit()
                return review.model_copy(update={"id": existing_review.id})
            conn.execute(
                """
                INSERT INTO market_prediction_seat_reviews (
                    id,
                    generated_at,
                    as_of_ts,
                    window_days,
                    review_state,
                    seat_scorecards,
                    review_summary,
                    metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb
                )
                """,
                [
                    review.id,
                    review.generated_at,
                    review.as_of_ts,
                    review.window_days,
                    review.review_state,
                    self._dump([row.model_dump() if hasattr(row, "model_dump") else row for row in review.seat_scorecards]),
                    self._dump(review.review_summary),
                    self._dump(review.metadata),
                ],
            )
            conn.commit()
        return review

    def list_latest_seat_reviews(self, *, window_days: int, limit: int = 5) -> list[MarketPredictionSeatReview]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    generated_at,
                    as_of_ts,
                    window_days,
                    review_state,
                    seat_scorecards,
                    review_summary,
                    metadata
                FROM market_prediction_seat_reviews
                WHERE window_days = %s
                ORDER BY as_of_ts DESC, generated_at DESC, id ASC
                LIMIT %s
                """,
                [window_days, limit],
            ).fetchall()
        return [self._row_to_seat_review(row) for row in rows]

    def get_latest_committee_snapshot(
        self,
        window_days: int,
    ) -> MarketPredictionCommitteeResponse | None:
        with self.storage.connection() as conn:
            run_row = conn.execute(
                """
                SELECT
                    id,
                    generated_at,
                    as_of_ts,
                    window_days,
                    base_date,
                    target_date,
                    target_universe,
                    lead_symbol,
                    lead_direction,
                    lead_prob_up,
                    lead_expected_move_pct,
                    source_snapshot,
                    committee_summary,
                    metadata
                FROM market_prediction_runs
                WHERE window_days = %s
                ORDER BY as_of_ts DESC, generated_at DESC
                LIMIT 1
                """,
                [window_days],
            ).fetchone()
            if not run_row:
                return None

            run = MarketPredictionRun.model_construct(
                id=str(run_row[0]),
                generated_at=run_row[1],
                as_of_ts=run_row[2],
                window_days=int(run_row[3]),
                base_date=run_row[4],
                target_date=run_row[5],
                target_universe=self._load(run_row[6], []),
                lead_symbol=str(run_row[7]),
                lead_direction=str(run_row[8]),
                lead_prob_up=float(run_row[9]) if run_row[9] is not None else None,
                lead_expected_move_pct=float(run_row[10]) if run_row[10] is not None else None,
                source_snapshot=self._load(run_row[11], {}),
                committee_summary=self._load(run_row[12], {}),
                metadata=self._load(run_row[13], {}),
            )

            call_rows = conn.execute(
                """
                SELECT
                    id,
                    symbol,
                    window_days,
                    direction_label,
                    prob_up,
                    expected_move_pct,
                    confidence_band_low_pct,
                    confidence_band_high_pct,
                    confidence_score,
                    committee_disagreement_score,
                    rationale_summary,
                    top_source_clusters,
                    metadata
                FROM market_prediction_calls
                WHERE run_id = %s
                ORDER BY CASE WHEN symbol = 'SPY' THEN 0 ELSE 1 END, symbol ASC
                """,
                [run.id],
            ).fetchall()

            vote_rows = conn.execute(
                """
                SELECT
                    seat_key,
                    agent_slug,
                    model_id,
                    provider,
                    symbol,
                    window_days,
                    direction_label,
                    prob_up,
                    expected_move_pct,
                    confidence_score,
                    rationale_summary,
                    source_clusters,
                    metadata
                FROM market_prediction_votes
                WHERE run_id = %s
                ORDER BY seat_key ASC, symbol ASC
                """,
                [run.id],
            ).fetchall()

        calls = [self._row_to_call(row) for row in call_rows]
        votes = [self._row_to_vote(row) for row in vote_rows]
        lead_call = next((call for call in calls if call.symbol == run.lead_symbol), calls[0]) if calls else MarketPredictionCall(
            symbol=run.lead_symbol,
            window_days=run.window_days,
            direction_label=run.lead_direction,
            prob_up=run.lead_prob_up or 0.5,
            expected_move_pct=run.lead_expected_move_pct or 0.0,
        )

        response = MarketPredictionCommitteeResponse.model_construct(
            as_of_ts=run.as_of_ts,
            generated_at=run.generated_at,
            window_days=run.window_days,
            base_date=run.base_date,
            target_date=run.target_date,
            target_universe=run.target_universe,
            lead_call=lead_call,
            calls=calls,
            votes=votes,
            scorecard=self.get_scorecard(window_days),
            committee_summary=run.committee_summary,
            source_snapshot=run.source_snapshot,
            last_evaluated_at=self.get_last_evaluated_at(window_days),
        )
        response._storage_metadata = run.metadata
        return response

    def list_history(self, symbol: str, window_days: int, limit: int = 30) -> list[MarketPredictionCall]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    c.id,
                    c.symbol,
                    c.window_days,
                    c.direction_label,
                    c.prob_up,
                    c.expected_move_pct,
                    c.confidence_band_low_pct,
                    c.confidence_band_high_pct,
                    c.confidence_score,
                    c.committee_disagreement_score,
                    c.rationale_summary,
                    c.top_source_clusters,
                    c.metadata
                FROM market_prediction_calls c
                JOIN market_prediction_runs r ON r.id = c.run_id
                WHERE c.symbol = %s AND c.window_days = %s
                ORDER BY r.as_of_ts DESC
                LIMIT %s
                """,
                [symbol.upper(), window_days, limit],
            ).fetchall()
        return [self._row_to_call(row) for row in rows]

    def list_due_for_evaluation(self, as_of_date: date, limit: int = 200) -> list[tuple[str, str, date, int]]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.symbol, r.target_date, c.window_days
                FROM market_prediction_calls c
                JOIN market_prediction_runs r ON r.id = c.run_id
                LEFT JOIN market_prediction_evaluations e ON e.call_id = c.id
                WHERE e.call_id IS NULL
                  AND r.target_date <= %s
                ORDER BY r.target_date ASC, c.symbol ASC
                LIMIT %s
                """,
                [as_of_date, limit],
            ).fetchall()
        return [
            (
                str(row[0]),
                str(row[1]),
                self._coerce_date(row[2]),
                int(row[3]),
            )
            for row in rows
        ]

    def list_due_evaluation_candidates(
        self,
        as_of_date: date,
        limit: int = 200,
    ) -> list[MarketPredictionEvaluationCandidate]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    c.id,
                    c.symbol,
                    c.window_days,
                    c.direction_label,
                    c.prob_up,
                    c.expected_move_pct,
                    c.confidence_band_low_pct,
                    c.confidence_band_high_pct,
                    c.confidence_score,
                    c.committee_disagreement_score,
                    c.rationale_summary,
                    c.top_source_clusters,
                    c.metadata,
                    r.base_date,
                    r.target_date
                FROM market_prediction_calls c
                JOIN market_prediction_runs r ON r.id = c.run_id
                LEFT JOIN market_prediction_evaluations e ON e.call_id = c.id
                WHERE e.call_id IS NULL
                  AND r.target_date <= %s
                ORDER BY r.target_date ASC, c.symbol ASC
                LIMIT %s
                """,
                [as_of_date, limit],
            ).fetchall()
        return [
            MarketPredictionEvaluationCandidate(
                call=self._row_to_call(row[:13]),
                base_date=row[13],
                target_date=row[14],
            )
            for row in rows
        ]

    def get_scorecard(self, window_days: int, sample_limit: int = 500) -> MarketPredictionScorecard | None:
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT
                    AVG(CASE WHEN e.direction_hit THEN 1.0 ELSE 0.0 END),
                    AVG(e.move_abs_error_pct),
                    AVG(e.brier_score),
                    COUNT(*)
                FROM market_prediction_evaluations e
                JOIN market_prediction_calls c ON c.id = e.call_id
                WHERE c.window_days = %s
                """,
                [window_days],
            ).fetchone()
        if not row or int(row[3] or 0) == 0:
            return None
        return MarketPredictionScorecard(
            direction_hit_rate=float(row[0]) if row[0] is not None else None,
            move_mae_pct=float(row[1]) if row[1] is not None else None,
            brier_score=float(row[2]) if row[2] is not None else None,
            sample_size=int(row[3] or 0),
        )

    def get_last_evaluated_at(self, window_days: int) -> datetime | None:
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT MAX(e.evaluated_at)
                FROM market_prediction_evaluations e
                JOIN market_prediction_calls c ON c.id = e.call_id
                WHERE c.window_days = %s
                """,
                [window_days],
            ).fetchone()
        return self._coerce_datetime(row[0]) if row and row[0] is not None else None

    @staticmethod
    def _coerce_date(value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

    @staticmethod
    def _coerce_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        parsed = datetime.fromisoformat(str(value))
        return parsed

    def _row_to_call(self, row: tuple[Any, ...]) -> MarketPredictionCall:
        return MarketPredictionCall.model_construct(
            id=str(row[0]),
            symbol=str(row[1]),
            window_days=int(row[2]),
            direction_label=str(row[3]),
            prob_up=float(row[4]),
            expected_move_pct=float(row[5]),
            confidence_band_low_pct=float(row[6]) if row[6] is not None else None,
            confidence_band_high_pct=float(row[7]) if row[7] is not None else None,
            confidence_score=float(row[8]) if row[8] is not None else None,
            committee_disagreement_score=float(row[9]) if row[9] is not None else None,
            rationale_summary=str(row[10]) if row[10] is not None else None,
            top_source_clusters=self._load(row[11], []),
            metadata=self._load(row[12], {}),
        )

    def _row_to_vote(self, row: tuple[Any, ...]) -> CommitteeSeatVote:
        return CommitteeSeatVote.model_construct(
            seat_key=str(row[0]),
            agent_slug=str(row[1]),
            model_id=str(row[2]) if row[2] is not None else None,
            provider=str(row[3]) if row[3] is not None else None,
            symbol=str(row[4]),
            window_days=int(row[5]),
            direction_label=str(row[6]),
            prob_up=float(row[7]),
            expected_move_pct=float(row[8]),
            confidence_score=float(row[9]) if row[9] is not None else None,
            rationale_summary=str(row[10]) if row[10] is not None else None,
            source_clusters=self._load(row[11], []),
            metadata=self._load(row[12], {}),
        )

    def _row_to_vote_evaluation(self, row: tuple[Any, ...]) -> MarketPredictionVoteEvaluation:
        return MarketPredictionVoteEvaluation.model_construct(
            vote_id=int(row[0]),
            evaluated_at=self._coerce_datetime(row[1]),
            seat_key=str(row[2]),
            symbol=str(row[3]),
            window_days=int(row[4]),
            base_close=float(row[5]),
            target_close=float(row[6]),
            realized_move_pct=float(row[7]),
            direction_hit=bool(row[8]),
            move_abs_error_pct=float(row[9]),
            brier_score=float(row[10]),
            metadata=self._load(row[11], {}),
        )

    def _row_to_seat_review(self, row: tuple[Any, ...]) -> MarketPredictionSeatReview:
        return MarketPredictionSeatReview.model_construct(
            id=str(row[0]),
            generated_at=self._coerce_datetime(row[1]),
            as_of_ts=self._coerce_datetime(row[2]),
            window_days=int(row[3]),
            review_state=str(row[4]),
            seat_scorecards=self._load(row[5], []),
            review_summary=self._load(row[6], {}),
            metadata=self._load(row[7], {}),
        )

    @staticmethod
    def _review_state_rank(review_state: str) -> int:
        if review_state == "live":
            return 3
        if review_state == "warmup":
            return 2
        return 1
