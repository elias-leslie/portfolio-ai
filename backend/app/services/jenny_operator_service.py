"""Jenny operator service.

Runs AI-assisted portfolio routines, stores multi-agent evaluations,
and surfaces plain-language notifications for the solo investor workflow.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.agents.clients.agent_hub_client import AGENT_HUB_ENABLED
from app.agents.workflow_orchestrator import WorkflowOrchestrator
from app.logging_config import get_logger
from app.models.jenny import (
    JennyAgentEvaluation,
    JennyAgentScorecard,
    JennyDashboard,
    JennyNotification,
    JennyRoutine,
    JennyRunResponse,
    JennySymbolReview,
    JennyTradeReview,
)
from app.models.thesis import Thesis
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.portfolio.sector_labels import FUND_CATEGORY_LABELS
from app.repositories.agent_repository import AgentRunRepository
from app.services._jenny_scoring import aggregate_symbol_review, build_scorecard
from app.services.jenny_review_engine import JennyReviewEngine
from app.services.jenny_routine_coordinator import JennyRoutineCoordinator
from app.services.jenny_row_parsers import (
    row_to_evaluation,
    row_to_notification,
    row_to_routine,
    row_to_scorecard,
    row_to_trade_review,
)
from app.services.thesis_service import ThesisService
from app.storage import get_storage
from app.watchlist.data_quality import calculate_data_quality, get_security_type
from app.watchlist.trading_style import INDEX_ETFS
from app.watchlist.watchlist_service import WatchlistService

logger = get_logger(__name__)

FINAL_VERDICT_PRIORITY = {
    "exit": 5,
    "trim": 4,
    "review": 3,
    "buy": 2,
    "avoid": 1,
    "hold": 0,
}
POSITIVE_VERDICTS = {"buy", "hold"}
JENNY_AGENT_TIMEOUT_SECONDS = 90.0
MIN_AGENT_REVIEW_DATA_QUALITY_PCT = 55.0
PASSIVE_FUND_SYMBOLS = frozenset(INDEX_ETFS) | frozenset(FUND_CATEGORY_LABELS)
ACTIVE_ROUTINE_WINDOW = timedelta(minutes=15)
ROUTINE_ACTIVITY_STALE_WINDOW = timedelta(minutes=2)


@dataclass(frozen=True)
class JennyAgentSpec:
    agent_slug: str
    system_prompt: str
    prompt_mode: str


AGENT_SPECS: tuple[JennyAgentSpec, ...] = (
    JennyAgentSpec(
        agent_slug="equity-analyst",
        prompt_mode="thesis",
        system_prompt=(
            "You are Jenny's thesis guardian. Return strict JSON only. "
            "Focus on whether the thesis still holds for a solo long-only investor."
        ),
    ),
    JennyAgentSpec(
        agent_slug="risk-manager",
        prompt_mode="risk",
        system_prompt=(
            "You are Jenny's risk manager. Return strict JSON only. "
            "Focus on concentration, downside, and position-sizing discipline."
        ),
    ),
    JennyAgentSpec(
        agent_slug="trade-manager",
        prompt_mode="exit",
        system_prompt=(
            "You are Jenny. Return strict JSON only. "
            "Focus on whether to hold, trim, review, or exit based on the current facts."
        ),
    ),
    JennyAgentSpec(
        agent_slug="investment-committee",
        prompt_mode="synthesis",
        system_prompt=(
            "You are Jenny's decision synthesizer. Return strict JSON only. "
            "Weigh the thesis, risks, and catalysts to produce the clearest next action."
        ),
    ),
)


class JennyOperatorService:
    """Portfolio operator service for Jenny routines."""

    AGENT_SPECS = AGENT_SPECS
    JENNY_AGENT_TIMEOUT_SECONDS = JENNY_AGENT_TIMEOUT_SECONDS
    MIN_AGENT_REVIEW_DATA_QUALITY_PCT = MIN_AGENT_REVIEW_DATA_QUALITY_PCT
    PASSIVE_FUND_SYMBOLS = PASSIVE_FUND_SYMBOLS
    ACTIVE_ROUTINE_WINDOW = ACTIVE_ROUTINE_WINDOW
    ROUTINE_ACTIVITY_STALE_WINDOW = ROUTINE_ACTIVITY_STALE_WINDOW
    JennyRunResponse = JennyRunResponse

    def __init__(self) -> None:
        self.storage = get_storage()
        self.portfolio_mgr = PortfolioManager(self.storage)
        self.price_fetcher = PriceDataFetcher(self.storage)
        self.watchlist_service = WatchlistService(self.storage)
        self.thesis_service = ThesisService()
        self.agent_run_repo = AgentRunRepository(self.storage)
        self.workflow_orchestrator = WorkflowOrchestrator(self.storage)
        self.review_engine = JennyReviewEngine()
        self.routine_coordinator = JennyRoutineCoordinator()

    def get_dashboard(self) -> JennyDashboard:
        """Return Jenny dashboard data."""
        self._fail_stale_routines()
        return JennyDashboard(
            routines=self._get_recent_routines(),
            notifications=self._get_open_notifications(),
            symbol_reviews=self._get_latest_symbol_reviews(),
            trade_reviews=self._get_recent_trade_reviews(),
            scorecards=self._get_scorecards(),
        )

    def acknowledge_notification(self, notification_id: str) -> JennyNotification | None:
        now = datetime.now(UTC).isoformat()
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE jenny_notifications
                SET status = %s, acknowledged_at = %s
                WHERE id = %s
                """,
                ["acknowledged", now, notification_id],
            )
            conn.commit()

        return self._get_notification(notification_id)

    def run_daily_operator(self, triggered_by: str = "manual") -> JennyRunResponse:
        """Run the daily Jenny operator routine."""
        return self.routine_coordinator.run_daily_operator(self, triggered_by)

    def run_weekly_learning(self, triggered_by: str = "system") -> JennyRunResponse:
        """Run Jenny's weekly trade review and scorecard update."""
        return self.routine_coordinator.run_weekly_learning(self, triggered_by)

    def _create_routine(self, routine_type: str, triggered_by: str) -> tuple[str, str]:
        return self.routine_coordinator.create_routine(self, routine_type, triggered_by)

    def _get_active_routine(self, routine_type: str) -> JennyRoutine | None:
        return self.routine_coordinator.get_active_routine(self, routine_type)

    def _fail_stale_routines(self, routine_type: str | None = None) -> int:
        return self.routine_coordinator.fail_stale_routines(self, routine_type)

    def _complete_routine(
        self,
        routine_id: str,
        status: str,
        summary: str,
        symbols_scanned: int,
        notifications_created: int,
    ) -> None:
        self.routine_coordinator.complete_routine(
            self,
            routine_id,
            status,
            summary,
            symbols_scanned,
            notifications_created,
        )

    def _select_symbols(self, live_positions: list[Any]) -> list[str]:
        symbols = [position.symbol for position in live_positions]
        candidates = self.watchlist_service.get_items_with_scores()
        candidate_symbols = [
            item["symbol"]
            for item in sorted(
                candidates,
                key=lambda item: float((item.get("current_score") or {}).get("overall") or 0.0),
                reverse=True,
            )
            if item["symbol"] not in symbols
        ][:3]
        return list(dict.fromkeys(symbols + candidate_symbols))

    def _default_symbol_profile(self, symbol: str) -> dict[str, Any]:
        security_type = self._normalize_security_type(symbol, None)
        return {
            "security_type": security_type,
            "is_passive_fund": security_type == "etf",
            "is_live_position": False,
            "data_quality_pct": None,
        }

    def _normalize_security_type(self, symbol: str, stored_security_type: str | None) -> str:
        normalized_symbol = symbol.upper()
        normalized_type = (stored_security_type or "").strip().lower()
        if normalized_type == "etf" or normalized_symbol in PASSIVE_FUND_SYMBOLS:
            return "etf"
        if normalized_type in {"equity", "index", "other"}:
            return normalized_type
        return "equity"

    def _build_symbol_profiles(
        self,
        symbols: list[str],
        live_symbols: set[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        if not symbols:
            return {}
        live_symbols = live_symbols or set()
        quality_map = calculate_data_quality(self.storage, symbols)
        profiles: dict[str, dict[str, Any]] = {}
        for symbol in symbols:
            security_type = self._normalize_security_type(symbol, get_security_type(self.storage, symbol))
            quality = quality_map.get(symbol)
            profiles[symbol] = {
                "security_type": security_type,
                "is_passive_fund": security_type == "etf",
                "is_live_position": symbol in live_symbols,
                "data_quality_pct": quality.overall_pct if quality else None,
            }
        return profiles

    def _ensure_thesis(self, symbol: str, symbol_profile: dict[str, Any]) -> Thesis | None:
        thesis = self.thesis_service.get_thesis(symbol)
        if thesis is not None:
            return thesis
        if symbol_profile.get("is_passive_fund"):
            return None
        data_quality_pct = symbol_profile.get("data_quality_pct")
        if data_quality_pct is not None and data_quality_pct < MIN_AGENT_REVIEW_DATA_QUALITY_PCT:
            return None
        if not AGENT_HUB_ENABLED:
            return None
        try:
            return self.thesis_service.generate_thesis(symbol, force=False)
        except Exception as exc:
            logger.warning("jenny_thesis_generation_skipped", symbol=symbol, error=str(exc))
            return None

    def _evaluate_symbol(
        self,
        symbol: str,
        thesis: Thesis | None,
        price_data: Any,
        routine_id: str,
        workflow_id: str,
        symbol_profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self.review_engine.evaluate_symbol(
            self,
            symbol=symbol,
            thesis=thesis,
            price_data=price_data,
            routine_id=routine_id,
            workflow_id=workflow_id,
            symbol_profile=symbol_profile,
        )

    def _should_use_insufficient_evidence_fallback(
        self,
        thesis: Thesis | None,
        symbol_profile: dict[str, Any],
    ) -> bool:
        return self.review_engine.should_use_insufficient_evidence_fallback(
            thesis,
            symbol_profile,
            self,
        )

    def _build_symbol_context(
        self,
        symbol: str,
        thesis: Thesis | None,
        price_data: Any,
        symbol_profile: dict[str, Any],
    ) -> dict[str, Any]:
        return self.review_engine.build_symbol_context(
            self,
            symbol,
            thesis,
            price_data,
            symbol_profile,
        )

    def _run_agent_review(self, spec: JennyAgentSpec, payload: dict[str, Any]) -> dict[str, Any]:
        return self.review_engine.run_agent_review(self, spec, payload)

    def _build_agent_prompt(self, mode: str, payload: dict[str, Any]) -> str:
        return self.review_engine.build_agent_prompt(mode, payload)

    def _normalize_confidence(self, raw_confidence: Any) -> float | None:
        return self.review_engine.normalize_confidence(raw_confidence)

    def _normalize_verdict(self, raw_verdict: Any) -> str:
        return self.review_engine.normalize_verdict(raw_verdict)

    def _parse_agent_response(self, content: str, agent_name: str) -> dict[str, Any]:
        return self.review_engine.parse_agent_response(content, agent_name)

    def _fallback_evaluation(
        self,
        symbol: str,
        thesis: Thesis | None,
        agent_name: str = "fallback_operator",
        symbol_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.review_engine.fallback_evaluation(
            symbol,
            thesis,
            service=self,
            agent_name=agent_name,
            symbol_profile=symbol_profile,
        )

    def _save_agent_evaluation(
        self,
        routine_id: str,
        symbol: str,
        thesis: Thesis | None,
        evaluation: dict[str, Any],
    ) -> None:
        evaluation_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO jenny_agent_evaluations (
                    id, routine_id, symbol, agent_name, provider, model, verdict, confidence,
                    rationale, recommendation, strengths, weaknesses, metadata, thesis_id, agent_run_id, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s
                )
                """,
                [
                    evaluation_id,
                    routine_id,
                    symbol,
                    evaluation["agent_name"],
                    evaluation.get("provider"),
                    evaluation.get("model"),
                    evaluation["verdict"],
                    evaluation.get("confidence"),
                    evaluation["rationale"],
                    evaluation.get("recommendation"),
                    json.dumps(evaluation.get("strengths", [])),
                    json.dumps(evaluation.get("weaknesses", [])),
                    json.dumps(evaluation.get("metadata", {})),
                    thesis.id if thesis else None,
                    evaluation.get("agent_run_id"),
                    now,
                ],
            )
            conn.commit()

    def _create_notifications(
        self,
        routine_id: str,
        live_symbols: set[str],
        evaluations_by_symbol: dict[str, list[dict[str, Any]]],
    ) -> int:
        return self.review_engine.create_notifications(
            self,
            routine_id=routine_id,
            live_symbols=live_symbols,
            evaluations_by_symbol=evaluations_by_symbol,
        )

    def _extract_symbol_profile(self, evaluations: list[dict[str, Any]]) -> dict[str, Any]:
        return self.review_engine.extract_symbol_profile(evaluations)

    def _extract_invalidation_triggers(self, evaluations: list[dict[str, Any]]) -> list[str]:
        return self.review_engine.extract_invalidation_triggers(evaluations)

    def _upsert_notification(
        self,
        routine_id: str,
        symbol: str | None,
        category: str,
        severity: str,
        title: str,
        detail: str,
        recommendation: str | None,
    ) -> None:
        self.review_engine.upsert_notification(
            self,
            routine_id,
            symbol,
            category=category,
            severity=severity,
            title=title,
            detail=detail,
            recommendation=recommendation,
        )

    def _build_routine_summary(
        self,
        symbol_count: int,
        notification_count: int,
        evaluations_by_symbol: dict[str, list[dict[str, Any]]],
    ) -> str:
        opportunities = sum(
            1
            for symbol, evaluations in evaluations_by_symbol.items()
            if self._aggregate_symbol_review(symbol, evaluations, self.thesis_service.get_thesis(symbol)).final_verdict == "buy"
        )
        return (
            f"Jenny reviewed {symbol_count} symbols, found {opportunities} buy-ready setups, "
            f"and opened {notification_count} alerts."
        )

    def _refresh_trade_reviews(self) -> int:
        with self.storage.connection() as conn:
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
            lesson = self._build_trade_lesson(return_pct, str(exit_reason) if exit_reason else None)
            what_worked, what_failed, next_time = self._build_trade_review_details(return_pct, exit_reason)
            self._save_trade_review(
                symbol=str(symbol),
                thesis_id=str(thesis_id) if thesis_id else None,
                idea_id=str(idea_id),
                outcome_label=outcome_label,
                return_pct=return_pct,
                lesson=lesson,
                what_worked=what_worked,
                what_failed=what_failed,
                next_time=next_time,
                agent_consensus=self._build_review_consensus(str(symbol)),
            )
            count += 1
        return count

    def _refresh_scorecards(self) -> int:
        evaluations = self._fetch_all_evaluations()
        reviews = self._get_recent_trade_reviews(limit=200)
        reviews_by_symbol = defaultdict(list)
        for review in reviews:
            reviews_by_symbol[review.symbol].append(review)

        grouped: dict[str, list[JennyAgentEvaluation]] = defaultdict(list)
        for evaluation in evaluations:
            grouped[evaluation.agent_name].append(evaluation)

        updated = 0
        for agent_name, agent_evaluations in grouped.items():
            scorecard = self._build_scorecard(agent_name, agent_evaluations, reviews_by_symbol)
            self._save_scorecard(scorecard)
            updated += 1
        return updated

    def _build_trade_lesson(self, return_pct: float | None, exit_reason: str | None) -> str:
        if return_pct is None:
            return "The trade closed without a usable return record, so Jenny could not learn much from it."
        if return_pct >= 10:
            return "Winning trades tend to come from theses that stayed intact long enough for the move to play out."
        if return_pct > 0:
            return "The trade worked, but the edge was modest. Sizing and timing mattered more than raw conviction."
        if return_pct <= -10:
            return "Large losses usually mean the thesis broke faster than expected or the position stayed too large after weakness appeared."
        return "Small losses are acceptable when they confirm the invalidation process is working early."

    def _build_trade_review_details(
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

    def _save_trade_review(
        self,
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
        with self.storage.connection() as conn:
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

    def _build_review_consensus(self, symbol: str) -> dict[str, Any]:
        latest_review = next(
            (
                review
                for review in self._get_latest_symbol_reviews(limit=20)
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

    def _build_scorecard(
        self,
        agent_name: str,
        evaluations: list[JennyAgentEvaluation],
        reviews_by_symbol: dict[str, list[JennyTradeReview]],
    ) -> JennyAgentScorecard:
        return build_scorecard(
            agent_name=agent_name,
            evaluations=evaluations,
            reviews_by_symbol=reviews_by_symbol,
            final_verdict_priority=FINAL_VERDICT_PRIORITY,
            positive_verdicts=POSITIVE_VERDICTS,
            now_iso=datetime.now(UTC).isoformat(),
        )

    def _save_scorecard(self, scorecard: JennyAgentScorecard) -> None:
        with self.storage.connection() as conn:
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

    def _get_recent_routines(self, limit: int = 6) -> list[JennyRoutine]:
        with self.storage.connection() as conn:
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

    def _get_routine(self, routine_id: str) -> JennyRoutine:
        with self.storage.connection() as conn:
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

    def _get_open_notifications(self, limit: int = 12) -> list[JennyNotification]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, routine_id, symbol, category, severity, status, title, detail,
                       recommendation, created_at, acknowledged_at, metadata
                FROM jenny_notifications
                WHERE status = 'open'
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

    def _get_notification(self, notification_id: str) -> JennyNotification | None:
        with self.storage.connection() as conn:
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

    def _get_latest_symbol_reviews(self, limit: int = 8) -> list[JennySymbolReview]:
        with self.storage.connection() as conn:
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
                [limit * len(AGENT_SPECS) * 2],
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
            self._aggregate_symbol_review(symbol, symbol_evaluations, self.thesis_service.get_thesis(symbol))
            for symbol, symbol_evaluations in grouped.items()
        ]
        action_map = self._build_position_action_map({review.symbol: review for review in reviews})
        for review in reviews:
            action = action_map.get(review.symbol)
            if action:
                review.management_action = action["action"]
                review.management_detail = action["detail"]
                review.position_gain_pct = action.get("gain_pct")
                review.position_weight_pct = action.get("weight_pct")
        return reviews[:limit]

    def _aggregate_symbol_review(
        self,
        symbol: str,
        evaluations: list[dict[str, Any]] | list[JennyAgentEvaluation],
        thesis: Thesis | None,
    ) -> JennySymbolReview:
        return aggregate_symbol_review(
            symbol=symbol,
            evaluations=evaluations,
            thesis=thesis,
            final_verdict_priority=FINAL_VERDICT_PRIORITY,
            now_iso=datetime.now(UTC).isoformat(),
        )

    def _get_recent_trade_reviews(self, limit: int = 12) -> list[JennyTradeReview]:
        with self.storage.connection() as conn:
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

    def _get_scorecards(self) -> list[JennyAgentScorecard]:
        with self.storage.connection() as conn:
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

    def _fetch_all_evaluations(self) -> list[JennyAgentEvaluation]:
        with self.storage.connection() as conn:
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

    def _build_position_action_map(
        self,
        review_map: dict[str, JennySymbolReview],
    ) -> dict[str, dict[str, Any]]:
        return self.review_engine.build_position_action_map(self, review_map)

    def _get_position_action(
        self,
        symbol: str,
        gain_pct: float,
        weight_pct: float,
        thesis: Thesis | None,
        invalidation_triggers: list[str],
        aggregated_review: Any,
    ) -> dict[str, Any]:
        return self.review_engine.get_position_action(
            self,
            symbol=symbol,
            gain_pct=gain_pct,
            weight_pct=weight_pct,
            thesis=thesis,
            invalidation_triggers=invalidation_triggers,
            aggregated_review=aggregated_review,
        )
