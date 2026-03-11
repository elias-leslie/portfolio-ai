"""Conversational Jenny service for portfolio-wide Q&A and household reconciliation."""

from __future__ import annotations

import json
import re
from typing import Any

from app.agents.clients.agent_hub_client import AgentHubAPIClient
from app.api.portfolio.analytics_routes import _get_analytics_payload
from app.api.symbols.router import _build_response as build_symbol_intelligence_response
from app.logging_config import get_logger
from app.models.household_finance import HouseholdQuestion, HouseholdQuestionAnswer
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.services.household_finance_service import HouseholdFinanceService
from app.storage import get_storage

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


class JennyConversationService:
    """Portfolio-wide Jenny chat with household question reconciliation."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self.household_service = HouseholdFinanceService()
        self.portfolio_mgr = PortfolioManager(self.storage)
        self.price_fetcher = PriceDataFetcher(self.storage)

    def chat(self, message: str, session_id: str | None = None) -> dict[str, Any]:
        cleaned_message = message.strip()
        open_questions = [
            question
            for question in self.household_service.list_questions().items
            if question.status == "open"
            and (question.direction is None or question.direction == "jenny_to_user")
        ]
        context = self._build_context(cleaned_message, open_questions)
        completion = self._complete_conversation(
            message=cleaned_message,
            session_id=session_id,
            context=context,
            open_questions=open_questions,
        )
        reconciled_answers = self._reconcile_message(
            message=cleaned_message,
            open_questions=open_questions,
            context=context,
        )
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

        return {
            "reply": reply,
            "session_id": str(getattr(completion, "session_id", None) or session_id or ""),
            "resolved_questions": resolved_questions,
            "updated_fields": updated_fields,
            "referenced_symbols": context["symbols"]["detected"],
        }

    def _client(self) -> AgentHubAPIClient:
        return AgentHubAPIClient(agent_slug="persona", use_memory=True, timeout=120.0)

    def _build_context(self, message: str, open_questions: list[HouseholdQuestion]) -> dict[str, Any]:
        household_dashboard = self.household_service.get_dashboard()
        accounts = self.portfolio_mgr.get_accounts()
        positions = self.portfolio_mgr.get_positions()
        live_symbols = sorted({position.symbol.upper() for position in positions if position.symbol})
        detected_symbols = self._detect_symbols(message, live_symbols)
        symbol_contexts = [
            self._summarize_symbol(symbol)
            for symbol in detected_symbols[:MAX_CONTEXT_SYMBOLS]
        ]
        analytics = _get_analytics_payload(include_paper=True)
        position_summaries = self._summarize_positions(positions)

        return {
            "household": {
                "overview": household_dashboard.overview.model_dump(),
                "profile": household_dashboard.profile.model_dump(),
                "resolved_values": [value.model_dump() for value in household_dashboard.resolved_values],
                "budget_readiness": household_dashboard.budget_readiness.model_dump(),
                "budget_snapshot": household_dashboard.budget_snapshot.model_dump(),
                "retirement_preparedness": household_dashboard.retirement_preparedness.model_dump(),
                "jenny_needs": [need.model_dump() for need in household_dashboard.jenny_needs],
                "open_questions": [self._question_summary(question) for question in open_questions],
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
        system_prompt = (
            "You are Jenny inside Portfolio-AI. Help with household planning, retirement, "
            "portfolio accounts, held positions, symbol questions, and any Portfolio-AI workflow context. "
            "Use the supplied context as your live source of truth. If the user asks for data that is not "
            "present in the supplied context, say what is missing instead of inventing it. "
            "If the user appears to have answered one of Jenny's open household questions, acknowledge it naturally."
        )
        prompt = (
            f"Portfolio-AI context:\n{json.dumps(context, indent=2)}\n\n"
            f"Open household questions:\n{json.dumps([self._question_summary(q) for q in open_questions], indent=2)}\n\n"
            f"User message:\n{message}"
        )
        client = self._client()
        try:
            return client.complete_messages(
                messages=[{"role": "user", "content": prompt}],
                purpose="portfolio_jenny_chat",
                session_id=session_id,
                thinking_level="low",
                system_prompt=system_prompt,
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
            f"Open questions:\n{json.dumps([self._question_summary(q) for q in open_questions], indent=2)}\n\n"
            f"Relevant portfolio-ai context:\n{json.dumps(context, indent=2)}\n\n"
            f"User message:\n{message}"
        )
        client = self._client()
        try:
            response = client.complete_messages(
                messages=[{"role": "user", "content": prompt}],
                purpose="portfolio_jenny_reconcile",
                thinking_level="minimal",
                system_prompt=(
                    "Return JSON only. Extract only confident answers that the user's message directly supports."
                ),
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
        cleaned_answers: list[dict[str, str]] = []
        for answer in answers:
            if not isinstance(answer, dict):
                continue
            question_id = str(answer.get("question_id") or "").strip()
            answer_text = str(answer.get("answer_text") or "").strip()
            if question_id and answer_text:
                cleaned_answers.append({"question_id": question_id, "answer_text": answer_text})
        return cleaned_answers

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
        combined = sorted(validated | (candidates & live_symbol_set))
        return combined

    def _lookup_symbols(self, candidates: list[str]) -> set[str]:
        if not candidates:
            return set()
        with self.storage.connection() as conn:
            rows = conn.execute(
                "SELECT symbol FROM symbols WHERE UPPER(symbol) = ANY(%s)",
                [candidates],
            ).fetchall()
        return {str(row[0]).upper() for row in rows if row and row[0]}

    def _summarize_symbol(self, symbol: str) -> dict[str, Any]:
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

    def _summarize_positions(self, positions: list[Any]) -> list[dict[str, Any]]:
        if not positions:
            return []
        price_data = self.price_fetcher.fetch_price_data(list({position.symbol for position in positions if position.symbol}))
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

    def _question_summary(self, question: HouseholdQuestion) -> dict[str, Any]:
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
