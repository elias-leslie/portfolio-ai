"""Canonical figures and evidence links for the page attached to a chat message."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlencode

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.services.household_finance_service import HouseholdFinanceService

logger = get_logger(__name__)


def current_symbol(page: dict[str, Any] | None) -> str | None:
    path = page.get("pathname") if page else None
    match = re.fullmatch(r"/symbols/([A-Za-z0-9.^=-]{1,32})/?", path) if isinstance(path, str) else None
    return match[1].upper() if match else None


def build_view_context(
    page: dict[str, Any] | None,
    household: HouseholdFinanceService,
) -> dict[str, Any] | None:
    if not page or page.get("pathname") != "/money":
        return None
    raw_search = page.get("search")
    params = parse_qs(raw_search.lstrip("?")[:2000]) if isinstance(raw_search, str) else {}
    tab = params.get("tab", ["spending"])[0]
    if tab == "retirement":
        return {
            "source": "Saved household assumptions; scenario overrides and current browser preview are not supplied.",
            "evidence_links": {
                "retirement": "/money?tab=retirement",
                "accounts": "/money?tab=accounts",
            },
        }
    if tab not in {"spending", "ledger"}:
        return None
    month = params.get("month", [None])[0]
    if month is not None and not re.fullmatch(r"[1-9]\d{3}-(0[1-9]|1[0-2])", month):
        return {"status": "unavailable", "reason": "The selected calendar month is invalid."}
    try:
        spending = household.get_spending(month=month)
        snapshot = spending.model_dump(mode="json")
        month = spending.summary.month
    except Exception as exc:
        logger.warning("jenny_view_context_unavailable", error=type(exc).__name__)
        return {"status": "unavailable", "reason": "The selected review could not be loaded."}
    ledger_params = {
        "tab": "ledger",
        "month": month,
        "ledgerKind": "transactions",
        "ledgerStatus": "all",
        "ledgerInclusion": "included",
    }
    return {
        "status": "available",
        "source": "GET /api/household/spending; same calendar-month review calculation as Money.",
        "generated_at": snapshot["generated_at"],
        "summary": snapshot["summary"],
        "review_plan": snapshot.get("review_plan"),
        "budget_verdict": snapshot.get("budget_verdict"),
        "spend_variance": snapshot.get("spend_variance"),
        "categories": snapshot.get("categories", []),
        "scope": "Entire selected-month spending review, including when opened from a filtered ledger.",
        "evidence_links": {
            "review": f"/money?{urlencode({'tab': 'spending', 'month': month})}",
            "included_transactions": f"/money?{urlencode(ledger_params)}",
            "category_transactions": {
                category[
                    "category"
                ]: f"/money?{urlencode({**ledger_params, 'ledgerCategory': category['category']})}"
                for category in snapshot.get("categories", [])
            },
        },
    }
