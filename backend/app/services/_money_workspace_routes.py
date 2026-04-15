"""Canonical routes for the Money workspace."""

from urllib.parse import urlencode

MONEY_ROUTE = "/money"
MONEY_ACCOUNT_COVERAGE_ROUTE = "/money?tab=accounts&focus=account-coverage"
MONEY_DISCOVERED_ACCOUNTS_ROUTE = "/money?tab=accounts&focus=discovered-accounts"
MONEY_ACCOUNTS_ROUTE = "/money?tab=accounts"
MONEY_SPENDING_ROUTE = "/money?tab=spending"
MONEY_REVIEW_ROUTE = "/money?tab=review"
MONEY_CLARIFICATIONS_ROUTE = "/money?tab=review&focus=clarifications#money-clarifications"
MONEY_DATE_QUALITY_ROUTE = "/money?tab=intake&focus=date-quality"
MONEY_EVIDENCE_ROUTE = "/money?tab=intake"
MONEY_PLANNING_ROUTE = "/money?utility=planning"


def money_planning_focus_route(section: str) -> str:
    return f"{MONEY_PLANNING_ROUTE}&focus={section}"


def money_account_focus_route(account_id: str, *, intent: str | None = None) -> str:
    params: dict[str, str] = {
        "tab": "accounts",
        "account": account_id,
    }
    if intent:
        params["intent"] = intent
    return f"{MONEY_ROUTE}?{urlencode(params)}"


def money_question_focus_route(question_id: str) -> str:
    return f"{MONEY_ROUTE}?{urlencode({'tab': 'review', 'focus': 'clarifications', 'question': question_id})}#money-clarifications"
