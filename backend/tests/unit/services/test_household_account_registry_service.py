"""Unit tests for canonical household-account registry matching rules."""

from __future__ import annotations

from unittest.mock import Mock

from app.models.household_finance import HouseholdEvidenceAccount, HouseholdTrackedAccount
from app.portfolio.models import Account
from app.services.household_account_identity import (
    account_identity_candidates,
    derive_account_mask,
)
from app.services.household_account_registry_service import (
    HouseholdAccountRegistryService,
    HouseholdCanonicalAccount,
)


def _canonical(
    *,
    account_id: str,
    label: str,
    asset_group: str,
    account_type: str,
    source_type: str,
    institution_name: str | None = None,
    owner_name: str | None = None,
    account_mask: str | None = None,
) -> HouseholdCanonicalAccount:
    return HouseholdCanonicalAccount(
        id=account_id,
        primary_identity_key=None,
        canonical_label=label,
        asset_group=asset_group,
        account_type=account_type,
        source_type=source_type,
        institution_name=institution_name,
        owner_name=owner_name,
        account_mask=account_mask,
        metadata={},
    )


def _tracked(
    *,
    account_id: str,
    label: str,
    asset_group: str,
    account_type: str,
    source_type: str,
    institution_name: str | None = None,
    owner_name: str | None = None,
    account_mask: str | None = None,
    match_key: str | None = None,
) -> HouseholdTrackedAccount:
    return HouseholdTrackedAccount(
        id=account_id,
        household_account_id=None,
        label=label,
        asset_group=asset_group,
        account_type=account_type,
        source_type=source_type,
        match_key=match_key,
        institution_name=institution_name,
        owner_name=owner_name,
        account_mask=account_mask,
        notes=None,
        created_at="2026-04-14T00:00:00Z",
        updated_at="2026-04-14T00:00:00Z",
    )


class _ConnectionRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[object] | None]] = []

    def execute(self, sql: str, params: list[object] | None = None) -> None:
        self.calls.append((sql, params))


def _evidence(
    *,
    evidence_id: str,
    document_id: str,
    institution_name: str | None,
    account_name: str | None,
    owner_name: str | None,
    account_mask: str | None,
    asset_group: str,
    account_type: str,
    source_type: str,
) -> HouseholdEvidenceAccount:
    return HouseholdEvidenceAccount(
        id=evidence_id,
        document_id=document_id,
        household_account_id=None,
        source_type=source_type,
        asset_group=asset_group,
        account_type=account_type,
        institution_name=institution_name,
        account_name=account_name,
        account_mask=account_mask,
        owner_name=owner_name,
        currency="USD",
        balance=100.0,
        holdings_value=None,
        cash_balance=None,
        as_of_date="2026-04-14T00:00:00Z",
        confidence=0.99,
        metadata={},
    )


def test_sync_tracked_identity_snapshot_preserves_display_owner_for_linked_account() -> None:
    service = HouseholdAccountRegistryService()
    tracked = _tracked(
        account_id="tracked-frs",
        label="FRS",
        asset_group="retirement",
        account_type="401k",
        source_type="retirement",
        institution_name="Florida Retirement System (FRS)",
        owner_name="Elias",
        account_mask=None,
        match_key="identity::frs|elias",
    )
    tracked.household_account_id = "household-frs"
    canonical = _canonical(
        account_id="household-frs",
        label="Florida Retirement System (FRS) · FRS Investment Plan",
        asset_group="retirement",
        account_type="401k",
        source_type="retirement",
        institution_name="Florida Retirement System (FRS)",
        owner_name="Mariana Leslie",
        account_mask="8891",
    )
    conn = _ConnectionRecorder()

    service._sync_tracked_identity_snapshot(  # type: ignore[attr-defined]
        conn,
        tracked=tracked,
        canonical_account=canonical,
    )

    assert conn.calls
    _, params = conn.calls[0]
    assert params is not None
    assert params[5] == "Elias"


def test_account_identity_candidates_do_not_emit_owner_level_education_keys() -> None:
    candidates = account_identity_candidates(
        source_type="education",
        asset_group="education",
        account_type="529",
        institution_name="CollegeAmerica / VCSP",
        account_name="529 - Nadia R Leslie",
        owner_name="Mariana Leslie",
        account_mask="87595982",
        explicit_match_key="evidence|87595982|529",
    )

    assert "institution-owner-asset::collegeamerica / vcsp|mariana|education" not in candidates
    assert "institution-owner::collegeamerica / vcsp|mariana leslie|education|529" not in candidates
    assert "institution-mask::collegeamerica / vcsp|87595982" in candidates
    assert "match::evidence|87595982|529" in candidates


def test_account_identity_candidates_emit_credit_lineage_before_mask() -> None:
    candidates = account_identity_candidates(
        source_type="credit_card",
        asset_group="credit",
        account_type="credit_card",
        institution_name="Chase",
        account_name="Prime Visa",
        owner_name="Elias B Leslie",
        account_mask="5313",
    )

    assert candidates[0] == "credit-lineage|chase|prime visa|elias b leslie|credit_card"
    assert "institution-mask::chase|5313" in candidates


def test_derive_account_mask_ignores_year_like_export_tokens() -> None:
    assert (
        derive_account_mask(
            "2026",
            "Credit card activity export",
            "Chase credit card activity export dated 2026-04-14",
        )
        is None
    )
    assert (
        derive_account_mask(
            None,
            "Credit card activity export",
            "Chasenull_Activity20260101_20260414_20260414.CSV",
        )
        is None
    )
    assert derive_account_mask("Shares", "529 college savings account", None) is None
    assert derive_account_mask("5313", "Prime Visa", None) == "5313"


def test_should_not_merge_same_owner_sibling_evidence_accounts() -> None:
    registry = HouseholdAccountRegistryService()
    left = _canonical(
        account_id="left",
        label="Pinellas County Schools 403(b) Plan",
        asset_group="retirement",
        account_type="retirement",
        source_type="retirement",
        institution_name="Pinellas County Schools",
        owner_name="Mariana Leslie",
    )
    right = _canonical(
        account_id="right",
        label="Pinellas County Schools 457(b) Deferred Compensation Plan",
        asset_group="retirement",
        account_type="retirement",
        source_type="retirement",
        institution_name="Pinellas County Schools",
        owner_name="Mariana Leslie",
    )

    assert not registry._should_merge_accounts(
        left,
        right,
        metrics={
            "left": {"evidence": 1, "tracked": 0, "transactions": 0},
            "right": {"evidence": 1, "tracked": 0, "transactions": 0},
        },
    )


def test_should_merge_shadow_alias_into_evidence_account() -> None:
    registry = HouseholdAccountRegistryService()
    evidence = _canonical(
        account_id="evidence",
        label="FRS Investment Plan",
        asset_group="retirement",
        account_type="retirement",
        source_type="retirement",
        institution_name="Florida Retirement System (FRS)",
        owner_name="Elias B. Leslie",
    )
    shadow = _canonical(
        account_id="shadow",
        label="FRS",
        asset_group="retirement",
        account_type="401k",
        source_type="retirement",
        institution_name="Florida Retirement System (FRS)",
        owner_name="Elias",
    )

    assert registry._should_merge_accounts(
        evidence,
        shadow,
        metrics={
            "evidence": {"evidence": 1, "tracked": 0, "transactions": 0},
            "shadow": {"evidence": 0, "tracked": 1, "transactions": 0},
        },
    )


def test_should_merge_weaker_evidence_alias_into_stronger_canonical_account() -> None:
    registry = HouseholdAccountRegistryService()
    legacy = _canonical(
        account_id="legacy",
        label="Chase Amazon card",
        asset_group="credit",
        account_type="credit_card",
        source_type="credit_card",
        institution_name=None,
        owner_name=None,
        account_mask="5313",
    )
    legacy.primary_identity_key = "mask::5313|credit|credit_card"
    current = _canonical(
        account_id="current",
        label="Chase Prime Visa / Amazon card",
        asset_group="credit",
        account_type="credit_card",
        source_type="credit_card",
        institution_name="Chase",
        owner_name="Elias B Leslie",
        account_mask="9728",
    )
    current.primary_identity_key = "credit-lineage|chase|chase prime visa / amazon card|elias b leslie|credit_card"

    assert registry._should_merge_accounts(
        legacy,
        current,
        metrics={
            "legacy": {"evidence": 4, "tracked": 0, "transactions": 120},
            "current": {"evidence": 3, "tracked": 1, "transactions": 331},
        },
    )


def test_resolve_from_tracked_prefers_structural_identity_over_stale_match_key() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    canonical_accounts = {
        "nadia": _canonical(
            account_id="nadia",
            label="529 - Nadia R Leslie",
            asset_group="education",
            account_type="529",
            source_type="education",
            institution_name="CollegeAmerica / VCSP",
            owner_name="Mariana Leslie",
            account_mask="87595982",
        ),
        "sophia": _canonical(
            account_id="sophia",
            label="529 - Sophia O Leslie",
            asset_group="education",
            account_type="529",
            source_type="education",
            institution_name="CollegeAmerica / VCSP",
            owner_name="Mariana Leslie",
            account_mask="87595967",
        ),
    }
    identity_map = {
        "institution-mask::collegeamerica / vcsp|87595982": "nadia",
        "institution-mask::collegeamerica / vcsp|87595967": "sophia",
        "evidence|87595967|529": "sophia",
        "match::evidence|87595967|529": "sophia",
    }

    account_id, created = registry._resolve_from_tracked(
        conn,
        tracked=_tracked(
            account_id="tracked-1",
            label="CollegeAmerica / VCSP · 529 - Nadia R Leslie",
            asset_group="education",
            account_type="529",
            source_type="education",
            institution_name="CollegeAmerica / VCSP",
            owner_name="Mariana Leslie",
            account_mask="87595982",
            match_key="evidence|87595967|529",
        ),
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert created == 0
    assert account_id == "nadia"


def test_resolve_from_tracked_ignores_corrupted_asset_hints_when_label_match_is_clear() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    canonical_accounts = {
        "cash": _canonical(
            account_id="cash",
            label="Cash Management (Joint WROS)",
            asset_group="taxable",
            account_type="brokerage",
            source_type="brokerage",
            institution_name="Fidelity",
            account_mask="Z38367298",
        ),
        "rollover": _canonical(
            account_id="rollover",
            label="Rollover IRA",
            asset_group="retirement",
            account_type="retirement",
            source_type="retirement",
            institution_name="Fidelity",
            account_mask="267328698",
        ),
    }
    identity_map = {
        "institution-mask::fidelity|z38367298": "cash",
        "institution-mask::fidelity|267328698": "rollover",
    }

    account_id, created = registry._resolve_from_tracked(
        conn,
        tracked=_tracked(
            account_id="tracked-2",
            label="Cash Management Account (CMA)",
            asset_group="retirement",
            account_type="retirement",
            source_type="retirement",
            institution_name="Fidelity",
            owner_name=None,
            account_mask="267328698",
        ),
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert created == 0
    assert account_id == "cash"


def test_resolve_from_evidence_merges_credit_card_mask_changes_for_same_lineage() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    canonical_accounts: dict[str, HouseholdCanonicalAccount] = {}
    identity_map: dict[str, str] = {}

    first_id, created_first, merged_first = registry._resolve_from_evidence(
        conn,
        evidence=_evidence(
            evidence_id="evidence-1",
            document_id="doc-1",
            institution_name="Chase",
            account_name="Prime Visa",
            owner_name="Elias B Leslie",
            account_mask="5313",
            asset_group="credit",
            account_type="credit_card",
            source_type="credit_card",
        ),
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )
    second_id, created_second, merged_second = registry._resolve_from_evidence(
        conn,
        evidence=_evidence(
            evidence_id="evidence-2",
            document_id="doc-2",
            institution_name="Chase",
            account_name="Prime Visa",
            owner_name="Elias B Leslie",
            account_mask="9728",
            asset_group="credit",
            account_type="credit_card",
            source_type="credit_card",
        ),
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert created_first == 1
    assert merged_first == 0
    assert created_second == 0
    assert merged_second == 0
    assert second_id == first_id
    assert len(canonical_accounts) == 1


def test_resolve_from_evidence_can_link_weak_statement_rows_by_filename_mask() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    canonical_accounts: dict[str, HouseholdCanonicalAccount] = {}
    identity_map: dict[str, str] = {}

    weak_id, _, _ = registry._resolve_from_evidence(
        conn,
        evidence=HouseholdEvidenceAccount(
            id="weak-evidence",
            document_id="doc-weak",
            household_account_id=None,
            source_type="credit_card",
            asset_group="credit",
            account_type="credit_card",
            institution_name=None,
            account_name="Chase Amazon card",
            account_mask=None,
            owner_name=None,
            currency="USD",
            balance=5192.03,
            holdings_value=None,
            cash_balance=None,
            as_of_date=None,
            confidence=0.8,
            metadata={
                "document_filename": "20260211-statements-5313-.pdf",
                "document_account_label": "Chase Amazon card",
            },
        ),
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    strong_id, _, _ = registry._resolve_from_evidence(
        conn,
        evidence=_evidence(
            evidence_id="strong-evidence",
            document_id="doc-strong",
            institution_name="Chase",
            account_name="Prime Visa",
            owner_name="Elias B Leslie",
            account_mask="5313",
            asset_group="credit",
            account_type="credit_card",
            source_type="credit_card",
        ),
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert strong_id == weak_id
    assert len(canonical_accounts) == 1


def test_prune_orphan_accounts_removes_unlinked_canonical_rows() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    conn.execute.return_value.fetchall.return_value = [("orphan-1",)]
    canonical_accounts = {
        "orphan-1": _canonical(
            account_id="orphan-1",
            label="Ghost",
            asset_group="credit",
            account_type="credit_card",
            source_type="credit_card",
        ),
        "live-1": _canonical(
            account_id="live-1",
            label="Real",
            asset_group="credit",
            account_type="credit_card",
            source_type="credit_card",
        ),
    }
    identity_map = {
        "mask::1234|credit|credit_card": "orphan-1",
        "mask::5678|credit|credit_card": "live-1",
    }

    removed = registry._prune_orphan_accounts(
        conn,
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert removed == 1
    assert "orphan-1" not in canonical_accounts
    assert "mask::1234|credit|credit_card" not in identity_map
    assert "live-1" in canonical_accounts


def test_prune_orphan_accounts_keeps_portfolio_linked_canonical_rows() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    conn.execute.return_value.fetchall.return_value = []
    canonical_accounts = {
        "portfolio-linked": _canonical(
            account_id="portfolio-linked",
            label="Individual - TOD",
            asset_group="taxable",
            account_type="brokerage",
            source_type="brokerage",
            institution_name="Fidelity",
            account_mask="Z35217544",
        )
    }
    identity_map = {"institution-mask::fidelity|z35217544": "portfolio-linked"}

    removed = registry._prune_orphan_accounts(
        conn,
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert removed == 0
    assert "portfolio-linked" in canonical_accounts


def test_sync_portfolio_accounts_links_exact_name_to_canonical_account() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    canonical_accounts = {
        "tod-id": _canonical(
            account_id="tod-id",
            label="Individual - TOD",
            asset_group="taxable",
            account_type="brokerage",
            source_type="brokerage",
            institution_name="Fidelity",
            account_mask="Z35217544",
        )
    }
    tracked_account = _tracked(
        account_id="tracked-tod",
        label="Individual - TOD",
        asset_group="taxable",
        account_type="brokerage",
        source_type="brokerage",
        institution_name="Fidelity",
    )
    tracked_accounts = [
        tracked_account.model_copy(update={"household_account_id": "tod-id"})
    ]
    portfolio_accounts = [
        Account(
            id="portfolio-tod",
            name="Individual - TOD",
            account_type="Taxable",
            household_account_id=None,
            cash_balance=1427.53,
            initial_cash=1427.53,
        )
    ]

    linked = registry._sync_portfolio_accounts(
        conn,
        canonical_accounts=canonical_accounts,
        tracked_accounts=tracked_accounts,
        portfolio_accounts=portfolio_accounts,
    )

    assert linked == 1
    sql, params = conn.execute.call_args.args
    assert "UPDATE portfolio_accounts" in sql
    assert params == ["tod-id", "portfolio-tod"]


def test_sync_portfolio_accounts_skips_duplicate_portfolio_link_target() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    canonical_accounts = {
        "roth-id": _canonical(
            account_id="roth-id",
            label="ROTH IRA",
            asset_group="retirement",
            account_type="roth_ira",
            source_type="retirement",
            institution_name="Fidelity",
        )
    }
    tracked_accounts: list[HouseholdTrackedAccount] = []
    portfolio_accounts = [
        Account(
            id="portfolio-linked",
            name="ROTH IRA",
            account_type="Roth",
            household_account_id="roth-id",
            cash_balance=0.0,
            initial_cash=0.0,
        ),
        Account(
            id="portfolio-duplicate",
            name="ROTH IRA",
            account_type="Roth",
            household_account_id=None,
            cash_balance=0.0,
            initial_cash=0.0,
        ),
    ]

    linked = registry._sync_portfolio_accounts(
        conn,
        canonical_accounts=canonical_accounts,
        tracked_accounts=tracked_accounts,
        portfolio_accounts=portfolio_accounts,
    )

    assert linked == 0
    conn.execute.assert_not_called()


def test_resolve_from_evidence_creates_distinct_sibling_accounts() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    canonical_accounts = {
        "nadia": _canonical(
            account_id="nadia",
            label="529 - Nadia R Leslie",
            asset_group="education",
            account_type="529",
            source_type="education",
            institution_name="CollegeAmerica / VCSP",
            owner_name="Mariana Leslie",
            account_mask="87595982",
        )
    }
    identity_map = {
        "institution-mask::collegeamerica / vcsp|87595982": "nadia",
        "mask::87595982|education|529": "nadia",
    }

    account_id, created, merged = registry._resolve_from_evidence(
        conn,
        evidence=_evidence(
            evidence_id="evidence-2",
            document_id="doc-2",
            institution_name="CollegeAmerica / VCSP",
            account_name="529 - Sophia O Leslie",
            owner_name="Mariana Leslie",
            account_mask="87595967",
            asset_group="education",
            account_type="529",
            source_type="education",
        ),
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert created == 1
    assert merged == 0
    assert account_id != "nadia"
