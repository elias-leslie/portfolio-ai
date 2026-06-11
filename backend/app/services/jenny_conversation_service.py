"""Conversational Jenny service for portfolio-wide Q&A and household reconciliation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.api.portfolio.analytics_routes import get_analytics_payload
from app.logging_config import get_logger
from app.models.household_finance import HouseholdQuestion
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.services.household_finance_service import HouseholdFinanceService
from app.services.jenny_dashboard_reader import JennyDashboardReader
from app.storage import get_storage
from app.utils.health_service import HealthCheckService

from ._jenny_conversation_chat import (
    apply_planning_items,
    apply_profile_updates,
    apply_reconciled_answers,
    build_fallback_reply,
    compose_reply,
)
from ._jenny_conversation_constants import DIRECTION_JENNY_TO_USER, STATUS_OPEN
from ._jenny_conversation_context import (
    build_compact_context,
    build_full_context,
    load_project_index,
)
from ._jenny_conversation_llm import (
    complete_conversation,
    extract_planning_updates,
    reconcile_message,
)

logger = get_logger(__name__)


class JennyConversationService:
    """Portfolio-wide Jenny chat with household question reconciliation."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self.household_service = HouseholdFinanceService()
        self.portfolio_mgr = PortfolioManager(self.storage)
        self.price_fetcher = PriceDataFetcher(self.storage)
        self.health_service = HealthCheckService()
        self.jenny_dashboard_reader = JennyDashboardReader()

    def chat(
        self,
        message: str,
        session_id: str | None = None,
        page_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cleaned = message.strip()
        open_questions = [
            q for q in self.household_service.list_questions().items
            if q.status == STATUS_OPEN
            and (q.direction is None or q.direction == DIRECTION_JENNY_TO_USER)
        ]
        context = self._build_context(cleaned, open_questions)

        chat_message = cleaned
        if page_context and page_context.get("pathname"):
            title = page_context.get("title") or page_context["pathname"]
            location = f"{page_context['pathname']}{page_context.get('search') or ''}"
            chat_message = f"[User is viewing: {title} ({location})]\n{cleaned}"

        try:
            completion = self._complete_conversation(
                message=chat_message,
                session_id=session_id,
                context=build_compact_context(context),
                open_questions=open_questions,
            )
        except Exception as exc:
            logger.exception("jenny_chat_completion_failed", error=str(exc))
            completion = SimpleNamespace(content=build_fallback_reply(cleaned, context), session_id=session_id or "")

        try:
            reconciled_answers = self._reconcile_message(
                message=cleaned, open_questions=open_questions, context=context
            )
        except Exception as exc:
            logger.exception("jenny_chat_reconciliation_failed", error=str(exc))
            reconciled_answers = []

        try:
            planning_updates = self._extract_planning_updates(
                message=cleaned, context=context, open_questions=open_questions
            )
        except Exception as exc:
            logger.exception("jenny_chat_planning_updates_failed", error=str(exc))
            planning_updates = {"profile_updates": {}, "planning_items": []}

        resolved_questions, updated_fields = apply_reconciled_answers(reconciled_answers, self.household_service)
        updated_fields = apply_profile_updates(planning_updates, updated_fields, self.household_service)
        updated_fields = apply_planning_items(planning_updates, updated_fields, self.household_service)

        raw_labels = getattr(self.household_service, "FIELD_LABELS", {})
        field_labels: dict[str, str] = raw_labels if isinstance(raw_labels, dict) else {}
        reply = compose_reply(completion, resolved_questions, planning_updates, updated_fields, field_labels)
        return {
            "reply": reply,
            "session_id": str(getattr(completion, "session_id", None) or session_id or ""),
            "resolved_questions": resolved_questions,
            "updated_fields": updated_fields,
            "referenced_symbols": context["symbols"]["detected"],
        }

    def _build_context(self, message: str, open_questions: list[HouseholdQuestion]) -> dict[str, Any]:
        return build_full_context(
            message=message,
            open_questions=open_questions,
            household_service=self.household_service,
            portfolio_mgr=self.portfolio_mgr,
            price_fetcher=self.price_fetcher,
            health_service=self.health_service,
            jenny_dashboard_reader=self.jenny_dashboard_reader,
            jenny_service=self,
            lookup_fn=self._lookup_symbols,
            analytics_fn=get_analytics_payload,
            index_fn=self._load_project_index,
        )

    def _load_project_index(self) -> dict[str, Any]:
        return load_project_index()

    def _complete_conversation(
        self,
        *,
        message: str,
        session_id: str | None,
        context: dict[str, Any],
        open_questions: list[HouseholdQuestion],
    ) -> Any:
        return complete_conversation(
            message=message, session_id=session_id, context=context, open_questions=open_questions
        )

    def _reconcile_message(
        self,
        *,
        message: str,
        open_questions: list[HouseholdQuestion],
        context: dict[str, Any],
    ) -> list[dict[str, str]]:
        return reconcile_message(message=message, open_questions=open_questions, context=context)

    def _extract_planning_updates(
        self,
        *,
        message: str,
        context: dict[str, Any],
        open_questions: list[HouseholdQuestion],
    ) -> dict[str, Any]:
        return extract_planning_updates(message=message, context=context, open_questions=open_questions)

    def _lookup_symbols(self, candidates: list[str]) -> set[str]:
        if not candidates:
            return set()
        with self.storage.connection() as conn:
            rows = conn.execute(
                "SELECT symbol FROM symbols WHERE UPPER(symbol) = ANY(%s)",
                [candidates],
            ).fetchall()
        return {str(row[0]).upper() for row in rows if row and row[0]}
