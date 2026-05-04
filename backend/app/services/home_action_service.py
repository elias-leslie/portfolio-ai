"""Aggregate prioritized product actions for the home page."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Lock

from app.services._home_action_ranking import (
    PRIORITY_RANK,
    internal_rank_score,
    public_action,
)
from app.services._home_action_sources import (
    build_household_actions_from_service,
    build_jenny_actions_from_service,
    build_portfolio_health_actions,
    build_recommendation_actions,
    build_workflow_actions_from_service,
)
from app.services.household_finance_service import HouseholdFinanceService
from app.services.jenny_operator_service import JennyOperatorService
from app.services.symbol_workflow_service import SymbolWorkflowService
from app.storage import get_storage

_ACTION_QUEUE_CACHE_SECONDS = 60


def _normalized_action_title(action: dict[str, object]) -> str:
    return " ".join(str(action.get("title", "") or "").lower().split())


def _action_specificity_score(action: dict[str, object]) -> float:
    source = str(action.get("source", "") or "")
    href = str(action.get("href", "") or "")
    detail = str(action.get("detail", "") or "")

    score = {
        "household": 40.0,
        "portfolio": 30.0,
        "recommendations": 25.0,
        "workflow": 20.0,
        "jenny": 10.0,
    }.get(source, 0.0)

    if href.startswith("/money?"):
        score += 12.0
    elif href.startswith("/portfolio?"):
        score += 10.0
    elif href.startswith("/symbols/"):
        score += 8.0
    elif href.startswith("/money"):
        score += 6.0

    if detail:
        score += min(len(detail) / 80.0, 3.0)

    if action.get("execution"):
        score -= 2.0

    return score


class HomeActionService:
    """Build a ranked cross-product action queue for the home dashboard."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self.household_service: HouseholdFinanceService | None = None
        self.jenny_service: JennyOperatorService | None = None
        self.workflow_service: SymbolWorkflowService | None = None
        self._cache_lock = Lock()
        self._queue_cache: dict[str, object] | None = None
        self._queue_cached_at: datetime | None = None

    def _household_service(self) -> HouseholdFinanceService:
        service = getattr(self, "household_service", None)
        if service is None:
            service = HouseholdFinanceService()
            self.household_service = service
        return service

    def _jenny_service(self) -> JennyOperatorService:
        service = getattr(self, "jenny_service", None)
        if service is None:
            service = JennyOperatorService()
            self.jenny_service = service
        return service

    def _workflow_service(self) -> SymbolWorkflowService:
        service = getattr(self, "workflow_service", None)
        if service is None:
            service = SymbolWorkflowService()
            self.workflow_service = service
        return service

    def _ensure_cache_state(self) -> None:
        if not hasattr(self, "_cache_lock"):
            self._cache_lock = Lock()
        if not hasattr(self, "_queue_cache"):
            self._queue_cache = None
        if not hasattr(self, "_queue_cached_at"):
            self._queue_cached_at = None

    def get_action_queue(self) -> dict[str, object]:
        self._ensure_cache_state()
        with self._cache_lock:
            if self._queue_cache is not None and self._queue_cached_at is not None:
                age = (datetime.now(UTC) - self._queue_cached_at).total_seconds()
                if age <= _ACTION_QUEUE_CACHE_SECONDS:
                    return self._queue_cache

        # Warm shared services before parallel read-only calls.
        self._household_service()
        self._jenny_service()
        self._workflow_service()

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(
                    getattr(
                        self,
                        "_recommendation_actions",
                        lambda: build_recommendation_actions(self.storage),
                    )
                ),
                executor.submit(
                    getattr(self, "_portfolio_health_actions", build_portfolio_health_actions)
                ),
                executor.submit(
                    getattr(
                        self,
                        "_jenny_actions",
                        lambda: build_jenny_actions_from_service(
                            self._jenny_service(),
                            getattr(self, "storage", None),
                        ),
                    )
                ),
                executor.submit(
                    getattr(
                        self,
                        "_workflow_actions",
                        lambda: build_workflow_actions_from_service(self._workflow_service()),
                    )
                ),
                executor.submit(
                    getattr(
                        self,
                        "_household_actions",
                        lambda: build_household_actions_from_service(self._household_service()),
                    )
                ),
            ]

        actions: list[dict[str, object]] = []
        for future in futures:
            actions.extend(future.result())

        if not actions:
            actions.append(
                {
                    "id": "calm-default",
                    "source": "system",
                    "category": "overview",
                    "priority": "low",
                    "title": "No urgent actions",
                    "detail": "The app does not see any high-priority investing or household follow-ups right now.",
                    "action_label": "Open dashboard",
                    "href": "/",
                    "symbol": None,
                    "badge": "Calm",
                }
            )

        deduped_by_key: dict[tuple[str, str | None], dict[str, object]] = {}
        for action in actions:
            key = (
                _normalized_action_title(action),
                str(action.get("symbol") or "").upper() or None,
            )
            existing = deduped_by_key.get(key)
            if existing is None:
                deduped_by_key[key] = action
                continue

            existing_score = (
                _action_specificity_score(existing),
                internal_rank_score(existing),
            )
            candidate_score = (
                _action_specificity_score(action),
                internal_rank_score(action),
            )
            if candidate_score > existing_score:
                deduped_by_key[key] = action

        deduped = list(deduped_by_key.values())

        deduped.sort(
            key=lambda action: (
                -internal_rank_score(action),
                PRIORITY_RANK.get(str(action.get("priority", "low")), 99),
                str(action.get("title", "")),
            )
        )
        queue = [public_action(action) for action in deduped[:8]]
        summary = (
            "Nothing urgent is queued."
            if not queue
            else f"{len(queue)} prioritized action{'s' if len(queue) != 1 else ''} ready."
        )
        response: dict[str, object] = {
            "generated_at": datetime.now(UTC).isoformat(),
            "actions": queue,
            "summary": summary,
        }
        with self._cache_lock:
            self._queue_cache = response
            self._queue_cached_at = datetime.now(UTC)
        return response
