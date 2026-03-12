"""Conversational Jenny service for portfolio-wide Q&A and household reconciliation."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

from app.agents.clients.agent_hub_client import AgentHubAPIClient
from app.api.portfolio.analytics_routes import _get_analytics_payload
from app.api.symbols.router import _build_response as build_symbol_intelligence_response
from app.logging_config import get_logger
from app.models.household_finance import (
    HouseholdProfileUpdate,
    HouseholdQuestion,
    HouseholdQuestionAnswer,
)
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.services.household_finance_service import HouseholdFinanceService
from app.services.jenny_dashboard_reader import JennyDashboardReader
from app.storage import get_storage
from app.utils._market_status import get_market_status
from app.utils.health_service import HealthCheckService

logger = get_logger(__name__)

SYMBOL_TOKEN_PATTERN = re.compile(r"\b[A-Za-z]{1,5}\b")
SYMBOL_STOPWORDS = frozenset(
    {
        "A",
        "AN",
        "AND",
        "ARE",
        "AT",
        "FOR",
        "FROM",
        "HOW",
        "IRA",
        "HSA",
        "IN",
        "IS",
        "IT",
        "MY",
        "OF",
        "ON",
        "OR",
        "OUR",
        "ROTH",
        "THE",
        "TO",
        "WE",
        "WHAT",
        "WITH",
    }
)
MAX_CONTEXT_SYMBOLS = 3
MAX_PORTFOLIO_POSITIONS = 12
MAX_RECENT_DOCUMENTS = 6
MAX_RECENT_ROUTINES = 3
MAX_OPEN_NOTIFICATIONS = 5
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROJECT_INDEX_PATH = PROJECT_ROOT / ".index.yaml"

# ── Behavioral identifiers ────────────────────────────────────────────────────
_STATUS_OPEN = "open"
_DIRECTION_JENNY_TO_USER = "jenny_to_user"
_PROVENANCE_JENNY_CHAT = "jenny_chat"
_PURPOSE_CHAT = "portfolio_jenny_chat"
_PURPOSE_RECONCILE = "portfolio_jenny_reconcile"
_PURPOSE_PLANNING_EXTRACT = "portfolio_jenny_planning_extract"

# ── System prompts ─────────────────────────────────────────────────────────────
_SYSTEM_CHAT = (
    "You are Jenny inside Portfolio-AI. Help with household planning, retirement, "
    "portfolio accounts, held positions, symbol questions, uploads, routines, status, and any "
    "Portfolio-AI workflow or product context. "
    "Use the supplied context as your live source of truth. If the user asks for data that is not "
    "present in the supplied context, say what is missing instead of inventing it. "
    "If the user appears to have answered one of Jenny's open household questions, acknowledge it naturally. "
    "Be proactive about diagnosis and the next best corrective step, but do not claim a mutation, ingest, "
    "or workflow side effect unless the supplied context proves it."
)
_SYSTEM_RECONCILE = (
    "Return JSON only. Extract only confident answers that the user's message directly supports."
)
_SYSTEM_PLANNING_EXTRACT = (
    "Return JSON only. Extract only information the user clearly stated and that should update"
    " the household planning record."
)

# ── Response schemas ──────────────────────────────────────────────────────────
RECONCILIATION_RESPONSE_FORMAT = {
    "type": "json_object",
    "schema": {
        "type": "object",
        "properties": {
            "answers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question_id": {"type": "string"},
                        "answer_text": {"type": "string"},
                    },
                    "required": ["question_id", "answer_text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["answers"],
        "additionalProperties": False,
    },
}
PLANNING_UPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "profile_updates": {
            "type": "object",
            "properties": {
                "adult_count": {"type": ["integer", "null"]},
                "dependent_count": {"type": ["integer", "null"]},
                "monthly_net_income_target": {"type": ["number", "null"]},
                "monthly_essential_target": {"type": ["number", "null"]},
                "monthly_discretionary_target": {"type": ["number", "null"]},
                "monthly_savings_target": {"type": ["number", "null"]},
                "target_retirement_age": {"type": ["integer", "null"]},
                "target_retirement_spend": {"type": ["number", "null"]},
                "filing_status": {"type": ["string", "null"]},
                "state_of_residence": {"type": ["string", "null"]},
                "effective_tax_rate": {"type": ["number", "null"]},
                "marginal_federal_tax_rate": {"type": ["number", "null"]},
                "marginal_state_tax_rate": {"type": ["number", "null"]},
                "emergency_fund_target_months": {"type": ["number", "null"]},
                "emergency_fund_target_amount": {"type": ["number", "null"]},
            },
            "additionalProperties": False,
        },
        "planning_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "label": {"type": "string"},
                    "role": {"type": ["string", "null"]},
                    "relationship": {"type": ["string", "null"]},
                    "owner_name": {"type": ["string", "null"]},
                    "source_type": {"type": ["string", "null"]},
                    "pay_frequency": {"type": ["string", "null"]},
                    "employer_or_source": {"type": ["string", "null"]},
                    "debt_type": {"type": ["string", "null"]},
                    "lender": {"type": ["string", "null"]},
                    "housing_type": {"type": ["string", "null"]},
                    "occupancy_role": {"type": ["string", "null"]},
                    "coverage_type": {"type": ["string", "null"]},
                    "carrier": {"type": ["string", "null"]},
                    "expense_kind": {"type": ["string", "null"]},
                    "category": {"type": ["string", "null"]},
                    "monthly_amount": {"type": ["number", "null"]},
                    "annual_amount": {"type": ["number", "null"]},
                    "gross_amount": {"type": ["number", "null"]},
                    "net_amount": {"type": ["number", "null"]},
                    "monthly_payment": {"type": ["number", "null"]},
                    "balance": {"type": ["number", "null"]},
                    "interest_rate": {"type": ["number", "null"]},
                    "premium_monthly": {"type": ["number", "null"]},
                    "coverage_amount": {"type": ["number", "null"]},
                    "deductible": {"type": ["number", "null"]},
                    "target_amount": {"type": ["number", "null"]},
                    "target_date": {"type": ["string", "null"]},
                    "monthly_saving_target": {"type": ["number", "null"]},
                    "start_age": {"type": ["integer", "null"]},
                    "birth_year": {"type": ["integer", "null"]},
                    "is_dependent": {"type": ["boolean", "null"]},
                    "inflation_adjusted": {"type": ["boolean", "null"]},
                    "survivor_benefit": {"type": ["boolean", "null"]},
                    "notes": {"type": ["string", "null"]},
                    "rationale": {"type": ["string", "null"]},
                },
                "required": ["section", "label"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["profile_updates", "planning_items"],
    "additionalProperties": False,
}


# ── Module-level pure helpers ─────────────────────────────────────────────────

def _question_summary(question: HouseholdQuestion) -> dict[str, Any]:
    return {
        "id": question.id,
        "field_name": question.field_name,
        "question": question.question,
        "priority": question.priority,
        "question_format": question.question_format,
        "options": question.options,
        "rationale": question.rationale,
        "recommendation": question.recommendation,
    }


def _summarize_symbol(symbol: str) -> dict[str, Any]:
    intelligence = build_symbol_intelligence_response(symbol, include_market=True, include_strategies=False)
    payload = intelligence.model_dump(mode="json")
    return {
        "symbol": payload.get("symbol"),
        "recommendation": payload.get("recommendation"),
        "signal": payload.get("signal"),
        "scores": payload.get("scores"),
        "portfolio": payload.get("portfolio"),
        "alerts": payload.get("alerts"),
        "news": payload.get("news"),
        "error": payload.get("error"),
    }


# ── Service ───────────────────────────────────────────────────────────────────

class JennyConversationService:
    """Portfolio-wide Jenny chat with household question reconciliation."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self.household_service = HouseholdFinanceService()
        self.portfolio_mgr = PortfolioManager(self.storage)
        self.price_fetcher = PriceDataFetcher(self.storage)
        self.health_service = HealthCheckService()
        self.jenny_dashboard_reader = JennyDashboardReader()

    def chat(self, message: str, session_id: str | None = None) -> dict[str, Any]:
        cleaned_message = message.strip()
        open_questions = [
            q for q in self.household_service.list_questions().items
            if q.status == _STATUS_OPEN
            and (q.direction is None or q.direction == _DIRECTION_JENNY_TO_USER)
        ]
        context = self._build_context(cleaned_message, open_questions)
        try:
            completion = self._complete_conversation(
                message=cleaned_message,
                session_id=session_id,
                context=context,
                open_questions=open_questions,
            )
        except Exception as exc:
            logger.exception("jenny_chat_completion_failed", error=str(exc))
            completion = SimpleNamespace(
                content=self._fallback_reply(cleaned_message, context),
                session_id=session_id or "",
            )

        try:
            reconciled_answers = self._reconcile_message(
                message=cleaned_message,
                open_questions=open_questions,
                context=context,
            )
        except Exception as exc:
            logger.exception("jenny_chat_reconciliation_failed", error=str(exc))
            reconciled_answers = []
        resolved_questions: list[dict[str, Any]] = []
        updated_fields: list[str] = []
        for answer in reconciled_answers:
            question_id = str(answer.get("question_id") or "").strip()
            answer_text = str(answer.get("answer_text") or "").strip()
            if not question_id or not answer_text:
                continue
            answered = self.household_service.answer_question(
                question_id,
                HouseholdQuestionAnswer(answer_text=answer_text),
            )
            if answered is None:
                continue
            resolved_questions.append(
                {
                    "id": answered.id,
                    "field_name": answered.field_name,
                    "question": answered.question,
                    "answer_text": answered.answer_text,
                }
            )
            if answered.field_name and answered.field_name not in updated_fields:
                updated_fields.append(answered.field_name)

        try:
            planning_updates = self._extract_planning_updates(
                message=cleaned_message,
                context=context,
                open_questions=open_questions,
            )
        except Exception as exc:
            logger.exception("jenny_chat_planning_updates_failed", error=str(exc))
            planning_updates = {"profile_updates": {}, "planning_items": []}
        profile_updates = planning_updates.get("profile_updates") if isinstance(planning_updates, dict) else None
        if isinstance(profile_updates, dict):
            cleaned_profile_updates = {k: v for k, v in profile_updates.items() if v is not None}
            if cleaned_profile_updates:
                self.household_service.update_profile(HouseholdProfileUpdate.model_validate(cleaned_profile_updates))
                updated_fields.extend(k for k in cleaned_profile_updates if k not in updated_fields)

        planning_items = planning_updates.get("planning_items") if isinstance(planning_updates, dict) else None
        if isinstance(planning_items, list) and planning_items:
            dict_items = [item for item in planning_items if isinstance(item, dict)]
            self.household_service.merge_planning_items(items=dict_items, provenance=_PROVENANCE_JENNY_CHAT)
            for section in (str(i.get("section") or "").strip() for i in dict_items):
                if section and section not in updated_fields:
                    updated_fields.append(section)

        reply = str(getattr(completion, "content", "") or "").strip()
        if resolved_questions:
            field_labels = getattr(self.household_service, "FIELD_LABELS", {})
            if not isinstance(field_labels, dict):
                field_labels = {}
            labels = [
                field_labels.get(field_name, field_name.replace("_", " "))
                for field_name in updated_fields
            ]
            if labels:
                reply = (
                    f"{reply}\n\n"
                    f"I also used your message to update the household plan: {', '.join(labels)}."
                ).strip()
        elif isinstance(planning_items, list) and planning_items:
            reply = f"{reply}\n\nI also added those planning details to your household plan.".strip()

        return {
            "reply": reply,
            "session_id": str(getattr(completion, "session_id", None) or session_id or ""),
            "resolved_questions": resolved_questions,
            "updated_fields": updated_fields,
            "referenced_symbols": context["symbols"]["detected"],
        }

    def _fallback_reply(self, message: str, context: dict[str, Any]) -> str:
        household = context.get("household", {})
        lower_message = message.lower()
        raw_documents = household.get("documents")
        documents = raw_documents if isinstance(raw_documents, list) else []
        if (
            any(token in lower_message for token in ("upload", "uploaded", "image", "document", "screenshot"))
            and documents
        ):
            latest = documents[0]
            if isinstance(latest, dict):
                summary = str(latest.get("review_summary") or latest.get("filename") or "latest upload").strip()
                document_type = str(latest.get("document_type") or "document").replace("_", " ")
                status = str(latest.get("status") or "unknown")
                return (
                    "Jenny hit an upstream model issue, but I can still confirm the latest intake state. "
                    f"I do see your latest upload: {summary} "
                    f"(type: {document_type}, status: {status}). "
                    "Household uploads do not auto-create portfolio accounts from screenshots, "
                    "so this should appear in intake context first rather than immediately as a new account."
                )

        raw_needs = household.get("jenny_needs")
        needs = raw_needs if isinstance(raw_needs, list) else []
        top_titles = [
            str(need.get("title"))
            for need in needs[:3]
            if isinstance(need, dict) and need.get("title")
        ]
        if top_titles:
            return (
                "Jenny hit an upstream model issue, but your workspace is still available. "
                f"Top priorities right now: {', '.join(top_titles)}."
            )
        return (
            "Jenny hit an upstream model issue, but your household and portfolio "
            "workspace is still available. Try again in a moment."
        )

    def _client(self) -> AgentHubAPIClient:
        return AgentHubAPIClient(agent_slug="persona", use_memory=True, timeout=120.0)

    def _load_project_index(self) -> dict[str, Any]:
        try:
            loaded = yaml.safe_load(PROJECT_INDEX_PATH.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            logger.warning("jenny_project_index_load_failed", error=str(exc))
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def _build_document_context(self, documents: list[Any]) -> list[dict[str, Any]]:
        return [
            {
                "id": document.id,
                "filename": document.filename,
                "source_type": document.source_type,
                "document_type": document.document_type,
                "status": document.status,
                "review_status": document.review_status,
                "review_summary": document.review_summary,
                "uploaded_at": document.uploaded_at,
                "parsed_at": document.parsed_at,
            }
            for document in documents
        ]

    def _build_runtime_context(self) -> dict[str, Any]:
        index = self._load_project_index()
        try:
            health = self.health_service.perform_health_check()
        except Exception as exc:
            logger.warning("jenny_runtime_health_failed", error=str(exc))
            health = {}

        try:
            recent_routines = self.jenny_dashboard_reader.get_recent_routines(
                self,
                limit=MAX_RECENT_ROUTINES,
            )
        except Exception as exc:
            logger.warning("jenny_runtime_routines_failed", error=str(exc))
            recent_routines = []

        try:
            open_notifications = self.jenny_dashboard_reader.get_open_notifications(
                self,
                limit=MAX_OPEN_NOTIFICATIONS,
            )
        except Exception as exc:
            logger.warning("jenny_runtime_notifications_failed", error=str(exc))
            open_notifications = []

        workflow_health = health.get("workflow_health")
        workflow_summary = (
            workflow_health.model_dump()
            if hasattr(workflow_health, "model_dump")
            else workflow_health
            if isinstance(workflow_health, dict)
            else {}
        )
        services = health.get("services")
        services_summary = (
            {
                name: str((payload or {}).get("status") or "unknown")
                for name, payload in services.items()
            }
            if isinstance(services, dict)
            else {}
        )
        pages = index.get("pages")
        tasks = index.get("tasks")
        endpoints = index.get("endpoints")
        services_index = index.get("services")

        return {
            "project": index.get("project") or "portfolio-ai",
            "generated_at": index.get("generated_at"),
            "ports": (
                {
                    "backend": (services_index or {}).get("backend_port", 8000),
                    "frontend": (services_index or {}).get("frontend_port", 3000),
                }
                if isinstance(services_index, dict)
                else {"backend": 8000, "frontend": 3000}
            ),
            "pages": pages if isinstance(pages, list) else [],
            "api_endpoints": endpoints if isinstance(endpoints, list) else [],
            "workflow_schedules": tasks if isinstance(tasks, list) else [],
            "current_status": {
                "system": health.get("status", "unknown"),
                "market": str(get_market_status(datetime.now(UTC))),
                "workflow_health": workflow_summary,
                "services": services_summary,
            },
            "jenny_operations": {
                "recent_routines": [
                    {
                        "routine_type": routine.routine_type,
                        "status": routine.status,
                        "summary": routine.summary,
                        "started_at": routine.started_at,
                        "completed_at": routine.completed_at,
                    }
                    for routine in recent_routines
                ],
                "open_notifications": [
                    {
                        "symbol": notification.symbol,
                        "category": notification.category,
                        "severity": notification.severity,
                        "title": notification.title,
                        "status": notification.status,
                    }
                    for notification in open_notifications
                ],
            },
            "document_pipeline": {
                "intake_route": "/money?tab=intake",
                "behavior": (
                    "Uploads create household document records and can update document reviews, "
                    "household transactions, and planning items. They do not auto-create "
                    "portfolio_accounts from screenshots."
                ),
            },
        }

    def _build_context(self, message: str, open_questions: list[HouseholdQuestion]) -> dict[str, Any]:
        household_dashboard = self.household_service.get_dashboard()
        recent_documents = self.household_service.list_documents(limit=MAX_RECENT_DOCUMENTS).items
        accounts = self.portfolio_mgr.get_accounts()
        positions = self.portfolio_mgr.get_positions()
        live_symbols = sorted({position.symbol.upper() for position in positions if position.symbol})
        detected_symbols = self._detect_symbols(message, live_symbols)
        symbol_contexts = [_summarize_symbol(sym) for sym in detected_symbols[:MAX_CONTEXT_SYMBOLS]]
        analytics = _get_analytics_payload(include_paper=True)
        position_summaries = self._summarize_positions(positions)

        return {
            "household": {
                "overview": household_dashboard.overview.model_dump(),
                "profile": household_dashboard.profile.model_dump(),
                "resolved_values": [v.model_dump() for v in household_dashboard.resolved_values],
                "budget_readiness": household_dashboard.budget_readiness.model_dump(),
                "budget_snapshot": household_dashboard.budget_snapshot.model_dump(),
                "retirement_preparedness": household_dashboard.retirement_preparedness.model_dump(),
                "import_center": household_dashboard.import_center.model_dump(),
                "jenny_needs": [need.model_dump() for need in household_dashboard.jenny_needs],
                "open_questions": [_question_summary(q) for q in open_questions],
                "documents": self._build_document_context(recent_documents),
                "planning": household_dashboard.planning.model_dump(),
            },
            "portfolio": {
                "accounts": [
                    {
                        "id": account.id,
                        "name": account.name,
                        "account_type": account.account_type,
                        "cash_balance": account.cash_balance,
                    }
                    for account in accounts
                ],
                "positions": position_summaries,
                "analytics": analytics.model_dump(),
            },
            "portfolio_ai": self._build_runtime_context(),
            "symbols": {
                "detected": detected_symbols[:MAX_CONTEXT_SYMBOLS],
                "details": symbol_contexts,
            },
        }

    def _complete_conversation(
        self,
        *,
        message: str,
        session_id: str | None,
        context: dict[str, Any],
        open_questions: list[HouseholdQuestion],
    ) -> Any:
        prompt = (
            f"Portfolio-AI context:\n{json.dumps(context, indent=2)}\n\n"
            f"Open household questions:\n{json.dumps([_question_summary(q) for q in open_questions], indent=2)}\n\n"
            f"User message:\n{message}"
        )
        client = self._client()
        try:
            return client.complete_messages(
                messages=[{"role": "user", "content": prompt}],
                purpose=_PURPOSE_CHAT,
                session_id=session_id,
                thinking_level="low",
                system_prompt=_SYSTEM_CHAT,
            )
        finally:
            client.close()

    def _reconcile_message(
        self,
        *,
        message: str,
        open_questions: list[HouseholdQuestion],
        context: dict[str, Any],
    ) -> list[dict[str, str]]:
        if not open_questions:
            return []
        prompt = (
            "Decide which open household questions are directly answered by the user's latest message. "
            "Return only answers that are clearly supported.\n\n"
            f"Open questions:\n{json.dumps([_question_summary(q) for q in open_questions], indent=2)}\n\n"
            f"Relevant portfolio-ai context:\n{json.dumps(context, indent=2)}\n\n"
            f"User message:\n{message}"
        )
        client = self._client()
        try:
            response = client.complete_messages(
                messages=[{"role": "user", "content": prompt}],
                purpose=_PURPOSE_RECONCILE,
                thinking_level="minimal",
                system_prompt=_SYSTEM_RECONCILE,
                response_format=RECONCILIATION_RESPONSE_FORMAT,
                use_memory=False,
            )
        finally:
            client.close()
        try:
            payload = json.loads(str(getattr(response, "content", "") or "{}"))
        except json.JSONDecodeError:
            logger.warning("jenny_chat_reconciliation_parse_failed", content=getattr(response, "content", ""))
            return []
        answers = payload.get("answers")
        if not isinstance(answers, list):
            return []
        return [
            {"question_id": str(a.get("question_id") or "").strip(), "answer_text": str(a.get("answer_text") or "").strip()}
            for a in answers
            if isinstance(a, dict)
            and str(a.get("question_id") or "").strip()
            and str(a.get("answer_text") or "").strip()
        ]

    def _extract_planning_updates(
        self,
        *,
        message: str,
        context: dict[str, Any],
        open_questions: list[HouseholdQuestion],
    ) -> dict[str, Any]:
        prompt = (
            "Extract only durable household planning changes that the user directly stated. "
            "Use profile_updates for scalar assumptions and planning_items for typed section rows.\n\n"
            f"Current context:\n{json.dumps(context, indent=2)}\n\n"
            f"Open questions:\n{json.dumps([_question_summary(q) for q in open_questions], indent=2)}\n\n"
            f"User message:\n{message}"
        )
        client = self._client()
        try:
            response = client.complete_messages(
                messages=[{"role": "user", "content": prompt}],
                purpose=_PURPOSE_PLANNING_EXTRACT,
                thinking_level="minimal",
                system_prompt=_SYSTEM_PLANNING_EXTRACT,
                response_format={"type": "json_object", "schema": PLANNING_UPDATE_SCHEMA},
                use_memory=False,
            )
        finally:
            client.close()
        try:
            payload = json.loads(str(getattr(response, "content", "") or "{}"))
        except json.JSONDecodeError:
            logger.warning("jenny_chat_planning_parse_failed", content=getattr(response, "content", ""))
            return {"profile_updates": {}, "planning_items": []}
        if not isinstance(payload, dict):
            return {"profile_updates": {}, "planning_items": []}
        profile_updates = payload.get("profile_updates")
        planning_items = payload.get("planning_items")
        return {
            "profile_updates": profile_updates if isinstance(profile_updates, dict) else {},
            "planning_items": planning_items if isinstance(planning_items, list) else [],
        }

    def _detect_symbols(self, message: str, live_symbols: list[str]) -> list[str]:
        live_symbol_set = {symbol.upper() for symbol in live_symbols}
        candidates = {
            token.upper()
            for token in SYMBOL_TOKEN_PATTERN.findall(message.upper())
            if token.upper() not in SYMBOL_STOPWORDS
        }
        if not candidates:
            return []
        validated = self._lookup_symbols(sorted(candidates))
        return sorted(validated | (candidates & live_symbol_set))

    def _lookup_symbols(self, candidates: list[str]) -> set[str]:
        if not candidates:
            return set()
        with self.storage.connection() as conn:
            rows = conn.execute(
                "SELECT symbol FROM symbols WHERE UPPER(symbol) = ANY(%s)",
                [candidates],
            ).fetchall()
        return {str(row[0]).upper() for row in rows if row and row[0]}

    def _summarize_positions(self, positions: list[Any]) -> list[dict[str, Any]]:
        if not positions:
            return []
        price_data = self.price_fetcher.fetch_price_data(
            list({position.symbol for position in positions if position.symbol})
        )
        summaries: list[dict[str, Any]] = []
        for position in positions[:MAX_PORTFOLIO_POSITIONS]:
            price_info = price_data.get(position.symbol)
            current_price = getattr(price_info, "price", None) if price_info is not None else None
            current_value = position.shares * current_price if current_price is not None else None
            gain_pct = None
            if current_price is not None and position.cost_basis:
                gain_pct = ((current_price - position.cost_basis) / position.cost_basis) * 100
            summaries.append(
                {
                    "symbol": position.symbol,
                    "account_id": position.account_id,
                    "shares": position.shares,
                    "cost_basis": position.cost_basis,
                    "position_type": position.position_type,
                    "current_price": current_price,
                    "current_value": current_value,
                    "gain_pct": gain_pct,
                }
            )
        return summaries
