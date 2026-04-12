"""Canonical routes for the Money workspace."""

MONEY_ROUTE = "/money"
MONEY_ACCOUNT_COVERAGE_ROUTE = "/money?tab=accounts&focus=account-coverage"
MONEY_DISCOVERED_ACCOUNTS_ROUTE = "/money?tab=accounts&focus=discovered-accounts"
MONEY_ACCOUNTS_ROUTE = "/money?tab=accounts"
MONEY_CLARIFICATIONS_ROUTE = "/money#money-clarifications"
MONEY_DATE_QUALITY_ROUTE = "/money?utility=evidence&focus=date-quality"
MONEY_EVIDENCE_ROUTE = "/money?utility=evidence"
MONEY_PLANNING_ROUTE = "/money?utility=planning"


def money_planning_focus_route(section: str) -> str:
    return f"{MONEY_PLANNING_ROUTE}&focus={section}"
