"""Context builders for Jenny conversation service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import yaml

from app.api.portfolio.analytics_routes import get_analytics_payload as _get_analytics_payload
from app.api.symbols.router import build_symbol_intelligence as build_symbol_intelligence_response
from app.config import PORTFOLIO_BACKEND_PORT, PORTFOLIO_FRONTEND_PORT, settings
from app.logging_config import get_logger
from app.models.household_finance import HouseholdQuestion
from app.utils._market_status import get_market_status

from ._jenny_conversation_constants import (
    MAX_CONTEXT_SYMBOLS,
    MAX_OPEN_NOTIFICATIONS,
    MAX_PORTFOLIO_POSITIONS,
    MAX_RECENT_DOCUMENTS,
    MAX_RECENT_ROUTINES,
    PROJECT_INDEX_PATH,
    SYMBOL_STOPWORDS,
    SYMBOL_TOKEN_PATTERN,
)

if TYPE_CHECKING:
    from app.portfolio.manager import PortfolioManager
    from app.portfolio.price_fetcher import PriceDataFetcher
    from app.services.household_finance_service import HouseholdFinanceService
    from app.services.jenny_dashboard_reader import JennyDashboardReader
    from app.utils.health_service import HealthCheckService

logger = get_logger(__name__)

# ── Runtime context magic strings ──────────────────────────────────────────────
_DEFAULT_PROJECT_NAME = "portfolio-ai"
_DEFAULT_SYSTEM_STATUS = "unknown"
_DOCUMENT_INTAKE_ROUTE = "/money?tab=intake"
_DOCUMENT_PIPELINE_BEHAVIOR = (
    "Uploads create household document records and can update document reviews, "
    "household transactions, and planning items. They do not auto-create "
    "portfolio_accounts from screenshots."
)

# ── Log event names ────────────────────────────────────────────────────────────
_LOG_HEALTH_FAILED = "jenny_runtime_health_failed"
_LOG_ROUTINES_FAILED = "jenny_runtime_routines_failed"
_LOG_NOTIFICATIONS_FAILED = "jenny_runtime_notifications_failed"
_LOG_PROJECT_INDEX_FAILED = "jenny_project_index_load_failed"


def question_summary(question: HouseholdQuestion) -> dict[str, Any]:
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


def summarize_symbol(symbol: str) -> dict[str, Any]:
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


def load_project_index() -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(PROJECT_INDEX_PATH.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning(_LOG_PROJECT_INDEX_FAILED, error=str(exc))
        return {}
    return loaded if isinstance(loaded, dict) else {}


def build_document_context(documents: list[Any]) -> list[dict[str, Any]]:
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


def _resolve_ports(services_index: Any, backend_port: int, frontend_port: int) -> dict[str, int]:
    if isinstance(services_index, dict):
        return {
            "backend": services_index.get("backend_port", backend_port),
            "frontend": services_index.get("frontend_port", frontend_port),
        }
    return {"backend": backend_port, "frontend": frontend_port}


def _build_current_status(health: dict[str, Any]) -> dict[str, Any]:
    return {
        "system": health.get("status", _DEFAULT_SYSTEM_STATUS),
        "market": str(get_market_status(datetime.now(UTC))),
        "workflow_health": _summarize_workflow_health(health.get("workflow_health")),
        "services": _summarize_services(health.get("services")),
    }


def _build_jenny_operations(recent_routines: list[Any], open_notifications: list[Any]) -> dict[str, Any]:
    return {
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
    }


def build_runtime_context(
    health_service: HealthCheckService,
    jenny_dashboard_reader: JennyDashboardReader,
    jenny_service: Any,
    project_index: dict[str, Any],
) -> dict[str, Any]:
    try:
        health = health_service.perform_health_check()
    except Exception as exc:
        logger.warning(_LOG_HEALTH_FAILED, error=str(exc))
        health = {}

    recent_routines = _safe_get_routines(jenny_dashboard_reader, jenny_service)
    open_notifications = _safe_get_notifications(jenny_dashboard_reader, jenny_service)

    index = project_index
    services_index = index.get("services")
    backend_port = urlparse(settings.backend_url).port or PORTFOLIO_BACKEND_PORT
    frontend_port = urlparse(settings.frontend_url).port or PORTFOLIO_FRONTEND_PORT

    return {
        "project": index.get("project") or _DEFAULT_PROJECT_NAME,
        "generated_at": index.get("generated_at"),
        "ports": _resolve_ports(services_index, backend_port, frontend_port),
        "pages": index.get("pages") if isinstance(index.get("pages"), list) else [],
        "api_endpoints": index.get("endpoints") if isinstance(index.get("endpoints"), list) else [],
        "workflow_schedules": index.get("tasks") if isinstance(index.get("tasks"), list) else [],
        "current_status": _build_current_status(health),
        "jenny_operations": _build_jenny_operations(recent_routines, open_notifications),
        "document_pipeline": {
            "intake_route": _DOCUMENT_INTAKE_ROUTE,
            "behavior": _DOCUMENT_PIPELINE_BEHAVIOR,
        },
    }


def _summarize_workflow_health(workflow_health: Any) -> dict[str, Any]:
    if hasattr(workflow_health, "model_dump"):
        return workflow_health.model_dump()
    if isinstance(workflow_health, dict):
        return workflow_health
    return {}


def _summarize_services(services: Any) -> dict[str, str]:
    if not isinstance(services, dict):
        return {}
    return {
        name: str((payload or {}).get("status") or _DEFAULT_SYSTEM_STATUS)
        for name, payload in services.items()
    }


def _safe_get_routines(jenny_dashboard_reader: JennyDashboardReader, jenny_service: Any) -> list[Any]:
    try:
        return jenny_dashboard_reader.get_recent_routines(jenny_service, limit=MAX_RECENT_ROUTINES)
    except Exception as exc:
        logger.warning(_LOG_ROUTINES_FAILED, error=str(exc))
        return []


def _safe_get_notifications(jenny_dashboard_reader: JennyDashboardReader, jenny_service: Any) -> list[Any]:
    try:
        return jenny_dashboard_reader.get_open_notifications(jenny_service, limit=MAX_OPEN_NOTIFICATIONS)
    except Exception as exc:
        logger.warning(_LOG_NOTIFICATIONS_FAILED, error=str(exc))
        return []


def detect_symbols(
    message: str,
    live_symbols: list[str],
    lookup_fn: Any,
) -> list[str]:
    live_symbol_set = {symbol.upper() for symbol in live_symbols}
    candidates = {
        token.upper()
        for token in SYMBOL_TOKEN_PATTERN.findall(message.upper())
        if token.upper() not in SYMBOL_STOPWORDS
    }
    if not candidates:
        return []
    validated = lookup_fn(sorted(candidates))
    return sorted(validated | (candidates & live_symbol_set))


def summarize_positions(positions: list[Any], price_fetcher: PriceDataFetcher) -> list[dict[str, Any]]:
    if not positions:
        return []
    price_data = price_fetcher.fetch_price_data(
        list({position.symbol for position in positions if position.symbol})
    )
    summaries: list[dict[str, Any]] = []
    for position in positions[:MAX_PORTFOLIO_POSITIONS]:
        price_info = price_data.get(position.symbol)
        current_price = getattr(price_info, "price", None) if price_info is not None else None
        current_value = position.shares * current_price if current_price is not None else None
        gain_pct = _compute_gain_pct(current_price, position.cost_basis)
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


def _compute_gain_pct(current_price: float | None, cost_basis: float | None) -> float | None:
    if current_price is not None and cost_basis:
        return ((current_price - cost_basis) / cost_basis) * 100
    return None


def _build_household_context(
    household_dashboard: Any,
    open_questions: list[HouseholdQuestion],
    recent_documents: list[Any],
) -> dict[str, Any]:
    return {
        "overview": household_dashboard.overview.model_dump(),
        "profile": household_dashboard.profile.model_dump(),
        "resolved_values": [v.model_dump() for v in household_dashboard.resolved_values],
        "budget_readiness": household_dashboard.budget_readiness.model_dump(),
        "budget_snapshot": household_dashboard.budget_snapshot.model_dump(),
        "retirement_preparedness": household_dashboard.retirement_preparedness.model_dump(),
        "import_center": household_dashboard.import_center.model_dump(),
        "jenny_needs": [need.model_dump() for need in household_dashboard.jenny_needs],
        "open_questions": [question_summary(q) for q in open_questions],
        "documents": build_document_context(recent_documents),
        "planning": household_dashboard.planning.model_dump(),
    }


def _build_portfolio_context(
    accounts: list[Any],
    position_summaries: list[dict[str, Any]],
    analytics: Any,
) -> dict[str, Any]:
    return {
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
    }


def build_full_context(
    message: str,
    open_questions: list[HouseholdQuestion],
    household_service: HouseholdFinanceService,
    portfolio_mgr: PortfolioManager,
    price_fetcher: PriceDataFetcher,
    health_service: HealthCheckService,
    jenny_dashboard_reader: JennyDashboardReader,
    jenny_service: Any,
    lookup_fn: Any,
    analytics_fn: Callable[..., Any] | None = None,
    index_fn: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    _analytics_fn = analytics_fn if analytics_fn is not None else _get_analytics_payload
    _index_fn = index_fn if index_fn is not None else load_project_index
    household_dashboard = household_service.get_dashboard()
    recent_documents = household_service.list_documents(limit=MAX_RECENT_DOCUMENTS).items
    accounts = portfolio_mgr.get_accounts()
    positions = portfolio_mgr.get_positions()
    live_symbols = sorted({position.symbol.upper() for position in positions if position.symbol})
    detected_symbols = detect_symbols(message, live_symbols, lookup_fn)
    symbol_contexts = [summarize_symbol(sym) for sym in detected_symbols[:MAX_CONTEXT_SYMBOLS]]
    analytics = _analytics_fn(include_paper=True)
    position_summaries = summarize_positions(positions, price_fetcher)
    project_index = _index_fn()

    return {
        "household": _build_household_context(household_dashboard, open_questions, recent_documents),
        "portfolio": _build_portfolio_context(accounts, position_summaries, analytics),
        "portfolio_ai": build_runtime_context(
            health_service, jenny_dashboard_reader, jenny_service, project_index
        ),
        "symbols": {
            "detected": detected_symbols[:MAX_CONTEXT_SYMBOLS],
            "details": symbol_contexts,
        },
    }
