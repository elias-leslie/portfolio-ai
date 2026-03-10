"""Jenny operator service.

Runs AI-assisted portfolio routines, stores multi-agent evaluations,
and surfaces plain-language notifications for the solo investor workflow.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.agents.clients.agent_hub_client import AgentHubAPIClient
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
from app.services._jenny_scoring import aggregate_symbol_review
from app.services.jenny_dashboard_reader import JennyDashboardReader
from app.services.jenny_learning_service import JennyLearningService
from app.services.jenny_review_engine import JennyReviewEngine
from app.services.jenny_routine_coordinator import JennyRoutineCoordinator
from app.services.jenny_symbol_profile_service import JennySymbolProfileService
from app.services.thesis_service import ThesisService
from app.storage import get_storage
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
    FINAL_VERDICT_PRIORITY = FINAL_VERDICT_PRIORITY
    POSITIVE_VERDICTS = POSITIVE_VERDICTS

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
        self.symbol_profile_service = JennySymbolProfileService()
        self.dashboard_reader = JennyDashboardReader()
        self.learning_service = JennyLearningService()

    def _review_engine(self) -> JennyReviewEngine:
        engine = getattr(self, "review_engine", None)
        if engine is None:
            engine = JennyReviewEngine()
            self.review_engine = engine
        return engine

    def _routine_coordinator(self) -> JennyRoutineCoordinator:
        coordinator = getattr(self, "routine_coordinator", None)
        if coordinator is None:
            coordinator = JennyRoutineCoordinator()
            self.routine_coordinator = coordinator
        return coordinator

    def _symbol_profile_service(self) -> JennySymbolProfileService:
        helper = getattr(self, "symbol_profile_service", None)
        if helper is None:
            helper = JennySymbolProfileService()
            self.symbol_profile_service = helper
        return helper

    def _dashboard_reader(self) -> JennyDashboardReader:
        reader = getattr(self, "dashboard_reader", None)
        if reader is None:
            reader = JennyDashboardReader()
            self.dashboard_reader = reader
        return reader

    def _learning_service(self) -> JennyLearningService:
        helper = getattr(self, "learning_service", None)
        if helper is None:
            helper = JennyLearningService()
            self.learning_service = helper
        return helper

    def _agent_hub_client_class(self):
        return AgentHubAPIClient

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
        return self._routine_coordinator().run_daily_operator(self, triggered_by)

    def run_weekly_learning(self, triggered_by: str = "system") -> JennyRunResponse:
        """Run Jenny's weekly trade review and scorecard update."""
        return self._routine_coordinator().run_weekly_learning(self, triggered_by)

    def _create_routine(self, routine_type: str, triggered_by: str) -> tuple[str, str]:
        return self._routine_coordinator().create_routine(self, routine_type, triggered_by)

    def _get_active_routine(self, routine_type: str) -> JennyRoutine | None:
        return self._routine_coordinator().get_active_routine(self, routine_type)

    def _fail_stale_routines(self, routine_type: str | None = None) -> int:
        return self._routine_coordinator().fail_stale_routines(self, routine_type)

    def _complete_routine(
        self,
        routine_id: str,
        status: str,
        summary: str,
        symbols_scanned: int,
        notifications_created: int,
    ) -> None:
        self._routine_coordinator().complete_routine(
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
        return self._symbol_profile_service().default_symbol_profile(self, symbol)

    def _normalize_security_type(self, symbol: str, stored_security_type: str | None) -> str:
        return self._symbol_profile_service().normalize_security_type(
            self,
            symbol,
            stored_security_type,
        )

    def _build_symbol_profiles(
        self,
        symbols: list[str],
        live_symbols: set[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        return self._symbol_profile_service().build_symbol_profiles(
            self,
            symbols,
            live_symbols,
        )

    def _ensure_thesis(self, symbol: str, symbol_profile: dict[str, Any]) -> Thesis | None:
        return self._symbol_profile_service().ensure_thesis(self, symbol, symbol_profile)

    def _evaluate_symbol(
        self,
        symbol: str,
        thesis: Thesis | None,
        price_data: Any,
        routine_id: str,
        workflow_id: str,
        symbol_profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self._review_engine().evaluate_symbol(
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
        return self._review_engine().should_use_insufficient_evidence_fallback(
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
        return self._review_engine().build_symbol_context(
            self,
            symbol,
            thesis,
            price_data,
            symbol_profile,
        )

    def _run_agent_review(self, spec: JennyAgentSpec, payload: dict[str, Any]) -> dict[str, Any]:
        return self._review_engine().run_agent_review(self, spec, payload)

    def _build_agent_prompt(self, mode: str, payload: dict[str, Any]) -> str:
        return self._review_engine().build_agent_prompt(mode, payload)

    def _normalize_confidence(self, raw_confidence: Any) -> float | None:
        return self._review_engine().normalize_confidence(raw_confidence)

    def _normalize_verdict(self, raw_verdict: Any) -> str:
        return self._review_engine().normalize_verdict(raw_verdict)

    def _parse_agent_response(self, content: str, agent_name: str) -> dict[str, Any]:
        return self._review_engine().parse_agent_response(content, agent_name)

    def _fallback_evaluation(
        self,
        symbol: str,
        thesis: Thesis | None,
        agent_name: str = "fallback_operator",
        symbol_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._review_engine().fallback_evaluation(
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
        return self._review_engine().create_notifications(
            self,
            routine_id=routine_id,
            live_symbols=live_symbols,
            evaluations_by_symbol=evaluations_by_symbol,
        )

    def _extract_symbol_profile(self, evaluations: list[dict[str, Any]]) -> dict[str, Any]:
        return self._review_engine().extract_symbol_profile(evaluations)

    def _extract_invalidation_triggers(self, evaluations: list[dict[str, Any]]) -> list[str]:
        return self._review_engine().extract_invalidation_triggers(evaluations)

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
        self._review_engine().upsert_notification(
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
        return self._learning_service().refresh_trade_reviews(self)

    def _refresh_scorecards(self) -> int:
        return self._learning_service().refresh_scorecards(self)

    def _build_trade_lesson(self, return_pct: float | None, exit_reason: str | None) -> str:
        return self._learning_service().build_trade_lesson(return_pct, exit_reason)

    def _build_trade_review_details(
        self,
        return_pct: float | None,
        exit_reason: str | None,
    ) -> tuple[str, str, str]:
        return self._learning_service().build_trade_review_details(return_pct, exit_reason)

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
        self._learning_service().save_trade_review(
            self,
            symbol=symbol,
            thesis_id=thesis_id,
            idea_id=idea_id,
            outcome_label=outcome_label,
            return_pct=return_pct,
            lesson=lesson,
            what_worked=what_worked,
            what_failed=what_failed,
            next_time=next_time,
            agent_consensus=agent_consensus,
        )

    def _build_review_consensus(self, symbol: str) -> dict[str, Any]:
        return self._dashboard_reader().build_review_consensus(self, symbol)

    def _build_scorecard(
        self,
        agent_name: str,
        evaluations: list[JennyAgentEvaluation],
        reviews_by_symbol: dict[str, list[JennyTradeReview]],
    ) -> JennyAgentScorecard:
        return self._learning_service().build_scorecard(self, agent_name, evaluations, reviews_by_symbol)

    def _save_scorecard(self, scorecard: JennyAgentScorecard) -> None:
        self._learning_service().save_scorecard(self, scorecard)

    def _get_recent_routines(self, limit: int = 6) -> list[JennyRoutine]:
        return self._dashboard_reader().get_recent_routines(self, limit)

    def _get_routine(self, routine_id: str) -> JennyRoutine:
        return self._dashboard_reader().get_routine(self, routine_id)

    def _get_open_notifications(self, limit: int = 12) -> list[JennyNotification]:
        return self._dashboard_reader().get_open_notifications(self, limit)

    def _get_notification(self, notification_id: str) -> JennyNotification | None:
        return self._dashboard_reader().get_notification(self, notification_id)

    def _get_latest_symbol_reviews(self, limit: int = 8) -> list[JennySymbolReview]:
        return self._dashboard_reader().get_latest_symbol_reviews(self, limit)

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
        return self._dashboard_reader().get_recent_trade_reviews(self, limit)

    def _get_scorecards(self) -> list[JennyAgentScorecard]:
        return self._dashboard_reader().get_scorecards(self)

    def _fetch_all_evaluations(self) -> list[JennyAgentEvaluation]:
        return self._dashboard_reader().fetch_all_evaluations(self)

    def _build_position_action_map(
        self,
        review_map: dict[str, JennySymbolReview],
    ) -> dict[str, dict[str, Any]]:
        return self._review_engine().build_position_action_map(self, review_map)

    def _get_position_action(
        self,
        symbol: str,
        gain_pct: float,
        weight_pct: float,
        thesis: Thesis | None,
        invalidation_triggers: list[str],
        aggregated_review: Any,
    ) -> dict[str, Any]:
        return self._review_engine().get_position_action(
            self,
            symbol=symbol,
            gain_pct=gain_pct,
            weight_pct=weight_pct,
            thesis=thesis,
            invalidation_triggers=invalidation_triggers,
            aggregated_review=aggregated_review,
        )
