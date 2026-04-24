"""Portfolio account household-linkage classification tests."""

from __future__ import annotations

from app.models.household_finance import HouseholdAccountSummary
from app.portfolio.account_linkage import classify_account_linkage
from app.portfolio.models import Account


def _portfolio_account(
    *,
    account_id: str = "portfolio-1",
    name: str = "Fidelity IRA",
    account_type: str = "IRA",
    household_account_id: str | None = None,
) -> Account:
    return Account(
        id=account_id,
        name=name,
        account_type=account_type,  # type: ignore[arg-type]
        household_account_id=household_account_id,
    )


def _household_account(
    *,
    account_id: str = "household-1",
    label: str = "Fidelity IRA",
    asset_group: str = "retirement",
    linked_portfolio_account_id: str | None = None,
    freshness_status: str = "fresh",
    freshness_label: str = "Fresh",
    evidence_count: int = 1,
    document_ids: list[str] | None = None,
) -> HouseholdAccountSummary:
    return HouseholdAccountSummary(
        id=account_id,
        household_account_id=account_id,
        label=label,
        asset_group=asset_group,
        account_type="ira",
        source_type="retirement",
        institution_name="Fidelity",
        owner_name="Elias",
        account_mask="1234",
        current_value=1000.0,
        evidence_count=evidence_count,
        document_ids=document_ids or ["doc-1"],
        linked_portfolio_account_id=linked_portfolio_account_id,
        freshness_status=freshness_status,
        freshness_label=freshness_label,
        balance_freshness_status=freshness_status,
        balance_freshness_label=freshness_label,
        match_status="linked" if linked_portfolio_account_id else "tracked",
    )


def test_classifies_linked_household_evidence_by_portfolio_account_id() -> None:
    account = _portfolio_account(account_id="portfolio-1", name="Traditional IRA")
    household_account = _household_account(
        account_id="household-1",
        label="Traditional IRA",
        linked_portfolio_account_id="portfolio-1",
    )

    linkage = classify_account_linkage(account, [household_account])

    assert linkage.state == "linked"
    assert linkage.label == "Linked household account"
    assert linkage.candidate_ids == ["household-1"]
    assert linkage.action_href == "/money?tab=accounts&account=household-1&intent=review"


def test_classifies_standalone_by_design_for_paper_accounts() -> None:
    account = _portfolio_account(account_type="paper")

    linkage = classify_account_linkage(account, [])

    assert linkage.state == "standalone_by_design"
    assert linkage.label == "Standalone by design"


def test_classifies_unmapped_investment_account_without_household_evidence() -> None:
    account = _portfolio_account(name="Taxable Brokerage", account_type="Taxable")

    linkage = classify_account_linkage(account, [])

    assert linkage.state == "unmapped"
    assert linkage.label == "Unmapped investment account"
    assert "Included in holdings totals" in (linkage.detail or "")
    assert linkage.action_href == "/money?tab=accounts&focus=account-coverage"


def test_classifies_duplicate_candidate_from_matching_money_account() -> None:
    account = _portfolio_account(name="Fidelity IRA")
    household_account = _household_account(
        account_id="household-candidate",
        label="Fidelity IRA",
        linked_portfolio_account_id=None,
    )

    linkage = classify_account_linkage(account, [household_account])

    assert linkage.state == "duplicate_candidate"
    assert linkage.label == "Possible household match"
    assert linkage.candidate_count == 1
    assert linkage.candidate_ids == ["household-candidate"]
    assert linkage.action_href == (
        "/money?tab=accounts&account=household-candidate&intent=review"
    )


def test_classifies_linked_account_with_stale_household_evidence() -> None:
    account = _portfolio_account(
        account_id="portfolio-1",
        household_account_id="household-stale",
    )
    household_account = _household_account(
        account_id="household-stale",
        label="Fidelity IRA",
        freshness_status="stale",
        freshness_label="Stale",
    )

    linkage = classify_account_linkage(account, [household_account])

    assert linkage.state == "stale_evidence"
    assert linkage.label == "Linked stale evidence"
    assert "stale" in (linkage.detail or "").lower()
    assert linkage.action_href == "/money?tab=accounts&account=household-stale&intent=evidence"
