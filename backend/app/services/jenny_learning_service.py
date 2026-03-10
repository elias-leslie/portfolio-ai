"""Trade-review and scorecard learning helpers for Jenny."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.jenny import JennyAgentEvaluation, JennyAgentScorecard, JennyTradeReview
from app.services._jenny_scoring import build_scorecard


class JennyLearningService:
    """Persist and summarize Jenny's post-trade learning outputs."""

    def refresh_trade_reviews(self, service: Any) -> int:
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT io.idea_id, io.symbol, io.realized_return_pct, io.exit_reason, wt.id
                FROM idea_outcomes io
                LEFT JOIN watchlist_thesis wt ON wt.symbol = io.symbol
                WHERE io.status IN ('closed', 'target_hit', 'stop_hit', 'expired')
                  AND NOT EXISTS (
                      SELECT 1 FROM jenny_trade_reviews jtr WHERE jtr.idea_id = io.idea_id
                  )
                ORDER BY io.updated_at DESC
                LIMIT 50
                """
            ).fetchall()

        count = 0
        for row in rows:
            idea_id, symbol, realized_return_pct, exit_reason, thesis_id = row
            return_pct = float(realized_return_pct) if realized_return_pct is not None else None
            outcome_label = "win" if (return_pct or 0.0) > 0 else "loss" if (return_pct or 0.0) < 0 else "flat"
            lesson = self.build_trade_lesson(return_pct, str(exit_reason) if exit_reason else None)
            what_worked, what_failed, next_time = self.build_trade_review_details(return_pct, exit_reason)
            self.save_trade_review(
                service,
                symbol=str(symbol),
                thesis_id=str(thesis_id) if thesis_id else None,
                idea_id=str(idea_id),
                outcome_label=outcome_label,
                return_pct=return_pct,
                lesson=lesson,
                what_worked=what_worked,
                what_failed=what_failed,
                next_time=next_time,
                agent_consensus=service._build_review_consensus(str(symbol)),
            )
            count += 1
        return count

    def refresh_scorecards(self, service: Any) -> int:
        evaluations = service._fetch_all_evaluations()
        reviews = service._get_recent_trade_reviews(limit=200)
        reviews_by_symbol: dict[str, list[JennyTradeReview]] = {}
        for review in reviews:
            reviews_by_symbol.setdefault(review.symbol, []).append(review)

        grouped: dict[str, list[JennyAgentEvaluation]] = {}
        for evaluation in evaluations:
            grouped.setdefault(evaluation.agent_name, []).append(evaluation)

        updated = 0
        for agent_name, agent_evaluations in grouped.items():
            scorecard = self.build_scorecard(service, agent_name, agent_evaluations, reviews_by_symbol)
            self.save_scorecard(service, scorecard)
            updated += 1
        return updated

    def build_trade_lesson(self, return_pct: float | None, exit_reason: str | None) -> str:
        if return_pct is None:
            return "The trade closed without a usable return record, so Jenny could not learn much from it."
        if return_pct >= 10:
            return "Winning trades tend to come from theses that stayed intact long enough for the move to play out."
        if return_pct > 0:
            return "The trade worked, but the edge was modest. Sizing and timing mattered more than raw conviction."
        if return_pct <= -10:
            return "Large losses usually mean the thesis broke faster than expected or the position stayed too large after weakness appeared."
        return "Small losses are acceptable when they confirm the invalidation process is working early."

    def build_trade_review_details(
        self,
        return_pct: float | None,
        exit_reason: str | None,
    ) -> tuple[str, str, str]:
        if return_pct is None:
            return (
                "The outcome data was incomplete.",
                "Jenny cannot score the decision quality without a realized return.",
                "Improve fill and exit tracking.",
            )
        what_worked = "The trade respected the thesis and risk plan." if return_pct > 0 else "The invalidation process likely prevented a larger loss."
        what_failed = (
            "The exit was late or the thesis was weaker than expected."
            if return_pct <= 0
            else "Profit capture could still improve if the exit reason was vague."
        )
        next_time = (
            "Favor similar setups when the same catalysts and risk profile show up again."
            if return_pct > 0
            else f"Cut sooner when the same warning signs appear ({exit_reason or 'invalid thesis'})."
        )
        return what_worked, what_failed, next_time

    def save_trade_review(
        self,
        service: Any,
        *,
        symbol: str,
        thesis_id: str | None,
        idea_id: str | None,
        outcome_label: str,
        return_pct: float | None,
        lesson: str,
        what_worked: str,
        what_failed: str,
        next_time: str,
        agent_consensus: dict[str, Any],
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with service.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO jenny_trade_reviews (
                    id, symbol, thesis_id, idea_id, review_source, outcome_label, return_pct,
                    lesson, what_worked, what_failed, next_time, agent_consensus, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                [
                    str(uuid.uuid4()),
                    symbol,
                    thesis_id,
                    idea_id,
                    "paper_trade",
                    outcome_label,
                    return_pct,
                    lesson,
                    what_worked,
                    what_failed,
                    next_time,
                    json.dumps(agent_consensus),
                    now,
                    now,
                ],
            )
            conn.commit()

    def build_scorecard(
        self,
        service: Any,
        agent_name: str,
        evaluations: list[JennyAgentEvaluation],
        reviews_by_symbol: dict[str, list[JennyTradeReview]],
    ) -> JennyAgentScorecard:
        return build_scorecard(
            agent_name=agent_name,
            evaluations=evaluations,
            reviews_by_symbol=reviews_by_symbol,
            final_verdict_priority=service.FINAL_VERDICT_PRIORITY,
            positive_verdicts=service.POSITIVE_VERDICTS,
            now_iso=datetime.now(UTC).isoformat(),
        )

    def save_scorecard(self, service: Any, scorecard: JennyAgentScorecard) -> None:
        with service.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO jenny_agent_scorecards (
                    agent_name, total_evaluations, completed_reviews, positive_verdicts,
                    win_rate, avg_return_pct, agreement_rate, calibration_score,
                    entry_quality_score, risk_judgment_score, exit_timing_score, alert_discipline_score,
                    strengths, weaknesses, last_evaluation_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s
                )
                ON CONFLICT (agent_name) DO UPDATE SET
                    total_evaluations = EXCLUDED.total_evaluations,
                    completed_reviews = EXCLUDED.completed_reviews,
                    positive_verdicts = EXCLUDED.positive_verdicts,
                    win_rate = EXCLUDED.win_rate,
                    avg_return_pct = EXCLUDED.avg_return_pct,
                    agreement_rate = EXCLUDED.agreement_rate,
                    calibration_score = EXCLUDED.calibration_score,
                    entry_quality_score = EXCLUDED.entry_quality_score,
                    risk_judgment_score = EXCLUDED.risk_judgment_score,
                    exit_timing_score = EXCLUDED.exit_timing_score,
                    alert_discipline_score = EXCLUDED.alert_discipline_score,
                    strengths = EXCLUDED.strengths,
                    weaknesses = EXCLUDED.weaknesses,
                    last_evaluation_at = EXCLUDED.last_evaluation_at,
                    updated_at = EXCLUDED.updated_at
                """,
                [
                    scorecard.agent_name,
                    scorecard.total_evaluations,
                    scorecard.completed_reviews,
                    scorecard.positive_verdicts,
                    scorecard.win_rate,
                    scorecard.avg_return_pct,
                    scorecard.agreement_rate,
                    scorecard.calibration_score,
                    scorecard.entry_quality_score,
                    scorecard.risk_judgment_score,
                    scorecard.exit_timing_score,
                    scorecard.alert_discipline_score,
                    json.dumps(scorecard.strengths),
                    json.dumps(scorecard.weaknesses),
                    scorecard.last_evaluation_at,
                    scorecard.updated_at,
                ],
            )
            conn.commit()
