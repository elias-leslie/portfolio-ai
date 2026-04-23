"""Jenny operator service.

Runs AI-assisted portfolio routines, stores multi-agent evaluations,
and surfaces plain-language notifications for the solo investor workflow.
"""

from __future__ import annotations

import functools
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from app.agents.clients.agent_hub_client import AgentHubAPIClient
from app.agents.workflow_orchestrator import WorkflowOrchestrator
from app.logging_config import get_logger
from app.models.jenny import (
    JennyAgentEvaluation,
    JennyDashboard,
    JennyNotification,
    JennyRunResponse,
    JennySymbolReview,
)
from app.models.thesis import Thesis
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.portfolio.sector_labels import FUND_CATEGORY_LABELS
from app.repositories.agent_repository import AgentRunRepository
from app.services._jenny_agent_specs import AGENT_SPECS, JennyAgentSpec  # noqa: F401 - re-exported
from app.services._jenny_evaluation_store import save_agent_evaluation
from app.services._jenny_scoring import aggregate_symbol_review
from app.services.household_finance_service import HouseholdFinanceService
from app.services.jenny_dashboard_reader import JennyDashboardReader
from app.services.jenny_household_maintenance_service import JennyHouseholdMaintenanceService
from app.services.jenny_learning_service import JennyLearningService
from app.services.jenny_review_engine import JennyReviewEngine
from app.services.jenny_routine_coordinator import JennyRoutineCoordinator
from app.services.jenny_symbol_profile_service import JennySymbolProfileService
from app.services.thesis_service import ThesisService
from app.storage import get_storage
from app.watchlist.trading_style import INDEX_ETFS
from app.watchlist.watchlist_service import WatchlistService

logger = get_logger(__name__)

FINAL_VERDICT_PRIORITY = {"exit": 5, "trim": 4, "review": 3, "buy": 2, "avoid": 1, "hold": 0}
POSITIVE_VERDICTS = {"buy", "hold"}
MIN_AGENT_REVIEW_DATA_QUALITY_PCT = 55.0
PASSIVE_FUND_SYMBOLS = frozenset(INDEX_ETFS) | frozenset(FUND_CATEGORY_LABELS)
ACTIVE_ROUTINE_WINDOW = timedelta(hours=1)
ROUTINE_ACTIVITY_STALE_WINDOW = timedelta(minutes=15)

# Routing tables for __getattr__ delegation
_DelegateMode = Literal["positional", "keyword", "none"]

_ROUTINE_COORDINATOR_METHODS: dict[str, str] = {
    "_create_routine": "create_routine",
    "_get_active_routine": "get_active_routine",
    "_fail_stale_routines": "fail_stale_routines",
    "_complete_routine": "complete_routine",
}
_SYMBOL_PROFILE_METHODS: dict[str, str] = {
    "_default_symbol_profile": "default_symbol_profile",
    "_build_symbol_profiles": "build_symbol_profiles",
    "_ensure_thesis": "ensure_thesis",
}
_DASHBOARD_READER_METHODS: dict[str, str] = {
    "_get_recent_routines": "get_recent_routines",
    "_get_routine": "get_routine",
    "_get_open_notifications": "get_open_notifications",
    "_get_open_notifications_for_symbol": "get_open_notifications_for_symbol",
    "_get_notification": "get_notification",
    "_get_latest_symbol_reviews": "get_latest_symbol_reviews",
    "_get_latest_symbol_review": "get_latest_symbol_review",
    "_get_recent_trade_reviews": "get_recent_trade_reviews",
    "_get_scorecards": "get_scorecards",
    "_get_latest_prediction_review_summary": "get_latest_prediction_review_summary",
    "_fetch_all_evaluations": "fetch_all_evaluations",
    "_build_review_consensus": "build_review_consensus",
}
_LEARNING_SERVICE_METHODS: dict[str, str] = {
    "_refresh_trade_reviews": "refresh_trade_reviews",
    "_refresh_scorecards": "refresh_scorecards",
    "_build_scorecard": "build_scorecard",
}
_HOUSEHOLD_MAINTENANCE_METHODS: dict[str, str] = {
    "_run_household_maintenance_pass": "run_daily_maintenance_pass",
}

# Combined lookup: method_name → (sub_service_attr, target_method_name, delegate_mode)
_DELEGATE_MAP: dict[str, tuple[str, str, _DelegateMode]] = {
    **{
        "_evaluate_symbol": ("review_engine", "evaluate_symbol", "positional"),
        "_run_agent_review": ("review_engine", "run_agent_review", "positional"),
        "_build_agent_prompt": ("review_engine", "build_agent_prompt", "none"),
        "_parse_agent_response": ("review_engine", "parse_agent_response", "none"),
        "_fallback_evaluation": ("review_engine", "fallback_evaluation", "keyword"),
        "_create_notifications": ("review_engine", "create_notifications", "positional"),
        "_upsert_notification": ("review_engine", "upsert_notification", "positional"),
        "_build_position_action_map": ("review_engine", "build_position_action_map", "positional"),
        "_get_position_action": ("review_engine", "get_position_action", "positional"),
    },
    **{k: ("routine_coordinator", v, "positional") for k, v in _ROUTINE_COORDINATOR_METHODS.items()},
    **{k: ("symbol_profile_service", v, "positional") for k, v in _SYMBOL_PROFILE_METHODS.items()},
    **{k: ("dashboard_reader", v, "positional") for k, v in _DASHBOARD_READER_METHODS.items()},
    **{k: ("learning_service", v, "positional") for k, v in _LEARNING_SERVICE_METHODS.items()},
    **{
        k: ("household_maintenance_service", v, "positional")
        for k, v in _HOUSEHOLD_MAINTENANCE_METHODS.items()
    },
}


class JennyOperatorService:
    """Portfolio operator service for Jenny routines."""

    AGENT_SPECS = AGENT_SPECS
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
        self.household_service = HouseholdFinanceService()
        self.household_maintenance_service = JennyHouseholdMaintenanceService()

    def __getattr__(self, name: str) -> Any:
        """Forward delegation-only methods to the appropriate sub-service."""
        routing = _DELEGATE_MAP.get(name)
        if routing is not None:
            sub_service_attr, target_method, delegate_mode = routing
            sub = object.__getattribute__(self, sub_service_attr)
            method = getattr(sub, target_method)
            if delegate_mode == "positional":
                return functools.partial(method, self)
            if delegate_mode == "keyword":
                return functools.partial(method, service=self)
            return method
        raise AttributeError(f"{type(self).__name__!r} has no attribute {name!r}")

    def _agent_hub_client_class(self) -> type[AgentHubAPIClient]:
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
            prediction_review_summary=self._get_latest_prediction_review_summary(),
        )

    def acknowledge_notification(self, notification_id: str) -> JennyNotification | None:
        now = datetime.now(UTC).isoformat()
        with self.storage.connection() as conn:
            conn.execute(
                "UPDATE jenny_notifications SET status = %s, acknowledged_at = %s WHERE id = %s",
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

    def run_daily_household_maintenance(self, triggered_by: str = "system") -> JennyRunResponse:
        """Run Jenny's daily household-money maintenance pass."""
        return self.routine_coordinator.run_daily_household_maintenance(self, triggered_by)

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

    def _save_agent_evaluation(self, routine_id: str, symbol: str, thesis: Thesis | None, evaluation: dict[str, Any]) -> None:
        save_agent_evaluation(self, routine_id, symbol, thesis, evaluation)

    def _build_routine_summary(self, symbol_count: int, notification_count: int, evaluations_by_symbol: dict[str, list[dict[str, Any]]]) -> str:
        opportunities = sum(
            1
            for symbol, evaluations in evaluations_by_symbol.items()
            if self._aggregate_symbol_review(symbol, evaluations, self.thesis_service.get_thesis(symbol)).final_verdict == "buy"
        )
        return (
            f"Jenny reviewed {symbol_count} symbols, found {opportunities} buy-ready setups, "
            f"and opened {notification_count} alerts."
        )

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
