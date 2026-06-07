"""Unit tests for canonical household-account registry matching rules."""

from __future__ import annotations

from typing import Any, cast
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
    _evidence_mask_rank,
    _mask_identity_candidates,
    _registry_identity_candidates,
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
        owner_name="Alex Demo",
        account_mask=None,
        match_key="identity::frs|alex-demo",
    )
    tracked.household_account_id = "household-frs"
    canonical = _canonical(
        account_id="household-frs",
        label="Florida Retirement System (FRS) · FRS Investment Plan",
        asset_group="retirement",
        account_type="401k",
        source_type="retirement",
        institution_name="Florida Retirement System (FRS)",
        owner_name="Jordan Demo",
        account_mask="8891",
    )
    conn = _ConnectionRecorder()

    service._sync_tracked_identity_snapshot(
        conn,
        tracked=tracked,
        canonical_account=canonical,
    )

    assert conn.calls
    _, params = conn.calls[0]
    assert params is not None
    assert params[5] == "Alex Demo"


def test_account_identity_candidates_do_not_emit_owner_level_education_keys() -> None:
    candidates = account_identity_candidates(
        source_type="education",
        asset_group="education",
        account_type="529",
        institution_name="CollegeAmerica / VCSP",
        account_name="529 - Demo Child Two",
        owner_name="Jordan Demo",
        account_mask="00022222",
        explicit_match_key="evidence|00022222|529",
    )

    assert "institution-owner-asset::collegeamerica / vcsp|jordan-demo|education" not in candidates
    assert "institution-owner::collegeamerica / vcsp|jordan demo|education|529" not in candidates
    assert "institution-mask::collegeamerica / vcsp|00022222" in candidates
    assert "match::evidence|00022222|529" in candidates


def test_account_identity_candidates_emit_credit_lineage_before_mask() -> None:
    candidates = account_identity_candidates(
        source_type="credit_card",
        asset_group="credit",
        account_type="credit_card",
        institution_name="Chase",
        account_name="Prime Visa",
        owner_name="Alex Demo",
        account_mask="5313",
    )

    assert candidates[0] == "credit-lineage|chase|prime visa|alex demo|credit_card"
    assert "institution-mask::chase|5313" in candidates


def test_registry_matching_uses_only_mask_identity_candidates() -> None:
    candidates = account_identity_candidates(
        source_type="credit_card",
        asset_group="credit",
        account_type="credit_card",
        institution_name="Chase",
        account_name="Prime Visa",
        owner_name="Alex Demo",
        account_mask="5313",
    )

    filtered = _mask_identity_candidates(candidates)

    assert "credit-lineage|chase|prime visa|alex demo|credit_card" not in filtered
    assert "institution-mask::chase|5313" in filtered


def test_registry_matching_allows_explicit_review_match_key_without_mask() -> None:
    explicit_key = (
        "institution-name-owner::florida retirement system (frs)|frs investment plan|"
        "alex-demo b. leslie|retirement|retirement"
    )
    candidates = account_identity_candidates(
        source_type="retirement",
        asset_group="retirement",
        account_type="retirement",
        institution_name="Florida Retirement System (FRS)",
        account_name="FRS Investment Plan",
        owner_name="Alex Demo",
        account_mask=None,
        explicit_match_key=explicit_key,
    )

    filtered = _registry_identity_candidates(candidates, explicit_match_key=explicit_key)

    assert explicit_key in filtered
    assert f"match::{explicit_key}" in filtered
    assert "name-owner::frs investment plan|alex-demo b. leslie|retirement|retirement" not in filtered


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


def test_evidence_mask_rank_prefers_extracted_mask_over_filename_id() -> None:
    score, _, mask = _evidence_mask_rank(
        {
            "account_name": "Chase Prime Visa / Amazon card",
            "account_mask": "1000020649",
            "balance": 92.58,
            "holdings_value": None,
            "cash_balance": None,
            "source_type": "credit_card",
            "confidence": 0.93,
            "metadata": {
                "document_filename": "1000020649.jpg",
                "extracted_account_mask": "9728",
            },
        }
    )

    assert mask == "9728"
    assert score > 100


def test_resolve_from_evidence_uses_extracted_mask_for_identity_matching() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    canonical_accounts = {
        "canonical": _canonical(
            account_id="canonical",
            label="Chase Prime Visa / Amazon card",
            asset_group="credit",
            account_type="credit_card",
            source_type="credit_card",
            institution_name="Chase",
            account_mask="9728",
        ),
    }
    identity_map = {"institution-mask::chase|9728": "canonical"}

    account_id, created, merged = registry._resolve_from_evidence(
        conn,
        evidence=HouseholdEvidenceAccount(
            id="image-evidence",
            document_id="doc-image",
            household_account_id=None,
            source_type="credit_card",
            asset_group="credit",
            account_type="credit_card",
            institution_name="Chase",
            account_name="Chase Prime Visa / Amazon card",
            account_mask="1000020670",
            owner_name="Alex Demo",
            currency="USD",
            balance=None,
            holdings_value=None,
            cash_balance=None,
            as_of_date=None,
            confidence=0.8,
            metadata={"extracted_account_mask": "9728"},
        ),
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert account_id == "canonical"
    assert created == 0
    assert merged == 0


def test_resolve_from_evidence_uses_explicit_review_match_key_without_mask() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    match_key = (
        "institution-name-owner::florida retirement system (frs)|frs investment plan|"
        "alex-demo b. leslie|retirement|retirement"
    )
    canonical_accounts = {
        "canonical": _canonical(
            account_id="canonical",
            label="FRS Investment Plan",
            asset_group="retirement",
            account_type="retirement",
            source_type="retirement",
            institution_name="Florida Retirement System (FRS)",
            owner_name="Alex Demo",
            account_mask=None,
        ),
    }
    identity_map = {match_key: "canonical"}

    account_id, created, merged = registry._resolve_from_evidence(
        conn,
        evidence=HouseholdEvidenceAccount(
            id="frs-evidence",
            document_id="doc-frs",
            household_account_id=None,
            source_type="retirement",
            asset_group="retirement",
            account_type="retirement",
            institution_name="Florida Retirement System (FRS)",
            account_name="FRS Investment Plan",
            account_mask=None,
            owner_name="Alex Demo",
            currency="USD",
            balance=44913.86,
            holdings_value=44913.86,
            cash_balance=None,
            as_of_date="2026-05-01T00:00:00Z",
            confidence=0.8,
            metadata={"match_key": match_key},
        ),
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert account_id == "canonical"
    assert created == 0
    assert merged == 0


def test_resolve_from_evidence_uses_preserved_account_id_without_mask() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    canonical_accounts = {
        "canonical": _canonical(
            account_id="canonical",
            label="Cash Management (Joint WROS)",
            asset_group="taxable",
            account_type="brokerage",
            source_type="brokerage",
            institution_name="Fidelity",
            account_mask="Z00000001",
        ),
    }
    identity_map: dict[str, str] = {}

    account_id, created, merged = registry._resolve_from_evidence(
        conn,
        evidence=HouseholdEvidenceAccount(
            id="cash-evidence",
            document_id="doc-cash",
            household_account_id=None,
            source_type="brokerage",
            asset_group="taxable",
            account_type="brokerage",
            institution_name="Fidelity",
            account_name="Cash Management account (CMA)",
            account_mask=None,
            owner_name=None,
            currency="USD",
            balance=42059.44,
            holdings_value=42059.44,
            cash_balance=42059.44,
            as_of_date="2026-04-20T00:00:00Z",
            confidence=0.8,
            metadata={"preserved_household_account_id": "canonical"},
        ),
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert account_id == "canonical"
    assert created == 0
    assert merged == 0


def test_should_not_merge_same_owner_sibling_evidence_accounts() -> None:
    registry = HouseholdAccountRegistryService()
    left = _canonical(
        account_id="left",
        label="Pinellas County Schools 403(b) Plan",
        asset_group="retirement",
        account_type="retirement",
        source_type="retirement",
        institution_name="Pinellas County Schools",
        owner_name="Jordan Demo",
    )
    right = _canonical(
        account_id="right",
        label="Pinellas County Schools 457(b) Deferred Compensation Plan",
        asset_group="retirement",
        account_type="retirement",
        source_type="retirement",
        institution_name="Pinellas County Schools",
        owner_name="Jordan Demo",
    )

    assert not registry._should_merge_accounts(
        left,
        right,
        metrics={
            "left": {"evidence": 1, "tracked": 0, "transactions": 0},
            "right": {"evidence": 1, "tracked": 0, "transactions": 0},
        },
    )


def test_should_not_merge_shadow_alias_without_account_mask() -> None:
    registry = HouseholdAccountRegistryService()
    evidence = _canonical(
        account_id="evidence",
        label="FRS Investment Plan",
        asset_group="retirement",
        account_type="retirement",
        source_type="retirement",
        institution_name="Florida Retirement System (FRS)",
        owner_name="Alex Demo",
    )
    shadow = _canonical(
        account_id="shadow",
        label="FRS",
        asset_group="retirement",
        account_type="401k",
        source_type="retirement",
        institution_name="Florida Retirement System (FRS)",
        owner_name="Alex Demo",
    )

    assert not registry._should_merge_accounts(
        evidence,
        shadow,
        metrics={
            "evidence": {"evidence": 1, "tracked": 0, "transactions": 0},
            "shadow": {"evidence": 0, "tracked": 1, "transactions": 0},
        },
    )


def test_should_not_merge_masked_accounts_when_masks_conflict() -> None:
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
        owner_name="Alex Demo",
        account_mask="9728",
    )
    current.primary_identity_key = (
        "credit-lineage|chase|chase prime visa / amazon card|alex demo|credit_card"
    )

    assert not registry._should_merge_accounts(
        legacy,
        current,
        metrics={
            "legacy": {"evidence": 4, "tracked": 0, "transactions": 120},
            "current": {"evidence": 3, "tracked": 1, "transactions": 331},
        },
    )


def test_should_merge_accounts_when_full_mask_matches_visible_suffix() -> None:
    registry = HouseholdAccountRegistryService()
    evidence = _canonical(
        account_id="evidence",
        label="Rollover IRA",
        asset_group="retirement",
        account_type="ira",
        source_type="retirement",
        institution_name="Fidelity",
        account_mask="267328698",
    )
    source = _canonical(
        account_id="source",
        label="Fidelity - Rollover IRA *8698",
        asset_group="retirement",
        account_type="ira",
        source_type="retirement",
        institution_name="Fidelity",
        account_mask="8698",
    )

    assert registry._should_merge_accounts(
        evidence,
        source,
        metrics={
            "evidence": {"evidence": 2, "tracked": 0, "transactions": 0},
            "source": {"evidence": 0, "tracked": 0, "transactions": 0},
        },
    )


def test_should_not_merge_same_label_accounts_when_masks_differ() -> None:
    registry = HouseholdAccountRegistryService()
    left = _canonical(
        account_id="left",
        label="Rollover IRA",
        asset_group="retirement",
        account_type="ira",
        source_type="retirement",
        institution_name="Fidelity",
        account_mask="2283",
    )
    right = _canonical(
        account_id="right",
        label="Fidelity - Rollover IRA *8698",
        asset_group="retirement",
        account_type="ira",
        source_type="retirement",
        institution_name="Fidelity",
        account_mask="8698",
    )

    assert not registry._should_merge_accounts(
        left,
        right,
        metrics={
            "left": {"evidence": 1, "tracked": 0, "transactions": 0},
            "right": {"evidence": 0, "tracked": 0, "transactions": 0},
        },
    )


def test_resolve_from_tracked_prefers_structural_identity_over_stale_match_key() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    canonical_accounts = {
        "child_two": _canonical(
            account_id="child_two",
            label="529 - Demo Child Two",
            asset_group="education",
            account_type="529",
            source_type="education",
            institution_name="CollegeAmerica / VCSP",
            owner_name="Jordan Demo",
            account_mask="00022222",
        ),
        "child_one": _canonical(
            account_id="child_one",
            label="529 - Demo Child One",
            asset_group="education",
            account_type="529",
            source_type="education",
            institution_name="CollegeAmerica / VCSP",
            owner_name="Jordan Demo",
            account_mask="00011111",
        ),
    }
    identity_map = {
        "institution-mask::collegeamerica / vcsp|00022222": "child_two",
        "institution-mask::collegeamerica / vcsp|00011111": "child_one",
        "evidence|00011111|529": "child_one",
        "match::evidence|00011111|529": "child_one",
    }

    account_id, created = registry._resolve_from_tracked(
        conn,
        tracked=_tracked(
            account_id="tracked-1",
            label="CollegeAmerica / VCSP · 529 - Demo Child Two",
            asset_group="education",
            account_type="529",
            source_type="education",
            institution_name="CollegeAmerica / VCSP",
            owner_name="Jordan Demo",
            account_mask="00022222",
            match_key="evidence|00011111|529",
        ),
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert created == 0
    assert account_id == "child_two"


def test_resolve_from_tracked_prefers_mask_over_label_when_both_are_present() -> None:
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
            account_mask="Z00000001",
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
        "institution-mask::fidelity|z00000001": "cash",
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
    assert account_id == "rollover"


def test_resolve_from_tracked_does_not_merge_shadow_linked_row_without_account_mask() -> (
    None
):
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    canonical_accounts = {
        "shadow": _canonical(
            account_id="shadow",
            label="FRS",
            asset_group="retirement",
            account_type="retirement",
            source_type="retirement",
            institution_name="Florida Retirement System (FRS)",
            owner_name="Jordan Demo",
        ),
        "evidence": _canonical(
            account_id="evidence",
            label="FRS Investment Plan",
            asset_group="retirement",
            account_type="retirement",
            source_type="retirement",
            institution_name="Florida Retirement System (FRS)",
            owner_name="Jordan Demo",
        ),
    }
    identity_map = {
        "institution-name-owner::florida retirement system (frs)|frs investment plan|jordan demo|retirement|retirement": "evidence",
        "match::institution-name-owner::florida retirement system (frs)|frs investment plan|jordan demo|retirement|retirement": "evidence",
    }
    tracked = _tracked(
        account_id="tracked-frs",
        label="FRS",
        asset_group="retirement",
        account_type="retirement",
        source_type="retirement",
        institution_name="Florida Retirement System (FRS)",
        owner_name="Jordan Demo",
        match_key="institution-name-owner::florida retirement system (frs)|frs investment plan|jordan demo|retirement|retirement",
    )
    tracked.household_account_id = "shadow"
    merge_accounts = Mock(return_value="evidence")
    registry._merge_accounts_if_needed = cast(Any, merge_accounts)

    account_id, created = registry._resolve_from_tracked(
        conn,
        tracked=tracked,
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert created == 1
    assert account_id not in {"shadow", "evidence"}
    merge_accounts.assert_not_called()


def test_resolve_from_evidence_does_not_merge_credit_card_mask_changes_by_lineage_only() -> None:
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
            owner_name="Alex Demo",
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
            owner_name="Alex Demo",
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
    assert created_second == 1
    assert merged_second == 0
    assert second_id != first_id
    assert len(canonical_accounts) == 2


def test_resolve_from_evidence_carries_closed_lifecycle_to_created_account() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    canonical_accounts: dict[str, HouseholdCanonicalAccount] = {}
    identity_map: dict[str, str] = {}
    evidence = _evidence(
        evidence_id="closed-evidence",
        document_id="doc-closed",
        institution_name="Test Bank",
        account_name="Closed Checking",
        owner_name="Alex Demo",
        account_mask=None,
        asset_group="cash",
        account_type="checking",
        source_type="bank",
    )
    evidence.metadata = {
        "account_status": "closed",
        "status_confirmed_by": "user",
        "status_confirmed_at": "2026-06-05",
    }

    account_id, created, merged = registry._resolve_from_evidence(
        conn,
        evidence=evidence,
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert created == 1
    assert merged == 0
    assert canonical_accounts[account_id].metadata["account_status"] == "closed"
    assert canonical_accounts[account_id].metadata["status_confirmed_by"] == "user"


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
            owner_name="Alex Demo",
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


def test_resolve_from_evidence_merges_duplicate_accounts_with_shared_mask_identity() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    canonical_accounts = {
        "canonical": _canonical(
            account_id="canonical",
            label="Chase Prime Visa / Amazon card",
            asset_group="credit",
            account_type="credit_card",
            source_type="credit_card",
            institution_name="Chase",
            account_mask="9728",
        ),
        "duplicate": _canonical(
            account_id="duplicate",
            label="Chase Amazon card",
            asset_group="credit",
            account_type="credit_card",
            source_type="credit_card",
            account_mask="5313",
        ),
    }
    identity_map = {
        "institution-mask::chase|5313": "canonical",
        "mask::5313|credit|credit_card": "duplicate",
    }
    merge_accounts = Mock(return_value="canonical")
    registry._merge_accounts_if_needed = cast(Any, merge_accounts)
    evidence = HouseholdEvidenceAccount(
        id="weak-evidence",
        document_id="doc-weak",
        household_account_id="duplicate",
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
            "preserved_household_account_id": "canonical",
        },
    )

    account_id, created, merged = registry._resolve_from_evidence(
        conn,
        evidence=evidence,
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert account_id == "canonical"
    assert created == 0
    assert merged == 1
    merge_args = merge_accounts.call_args.kwargs["account_ids"]
    assert set(merge_args) == {"canonical", "duplicate"}


def test_resolve_from_evidence_rejects_incompatible_existing_household_account_link() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    canonical_accounts = {
        "cash-management": _canonical(
            account_id="cash-management",
            label="Cash Management Account (CMA)",
            asset_group="taxable",
            account_type="brokerage",
            source_type="brokerage",
            institution_name="Fidelity",
            account_mask="Z00000001",
        )
    }
    identity_map: dict[str, str] = {}
    evidence = _evidence(
        evidence_id="rollover",
        document_id="doc-rollover",
        institution_name="Fidelity",
        account_name="Rollover IRA",
        owner_name=None,
        account_mask="267328698",
        asset_group="retirement",
        account_type="ira",
        source_type="retirement",
    )
    evidence.household_account_id = "cash-management"

    account_id, created, merged = registry._resolve_from_evidence(
        conn,
        evidence=evidence,
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert account_id != "cash-management"
    assert created == 1
    assert merged == 0
    assert canonical_accounts[account_id].account_mask == "267328698"
    assert canonical_accounts[account_id].account_type == "ira"


def test_resolve_from_evidence_reassigns_stale_identity_key_to_compatible_account() -> None:
    registry = HouseholdAccountRegistryService()
    conn = Mock()
    canonical_accounts = {
        "wrong": _canonical(
            account_id="wrong",
            label="Rollover IRA",
            asset_group="retirement",
            account_type="ira",
            source_type="retirement",
            institution_name="Fidelity",
            account_mask="267328698",
        )
    }
    identity_map = {"institution-mask::fidelity|z00000001": "wrong"}

    account_id, created, merged = registry._resolve_from_evidence(
        conn,
        evidence=_evidence(
            evidence_id="cma",
            document_id="doc-cma",
            institution_name="Fidelity",
            account_name="Cash Management (Joint WROS)",
            owner_name=None,
            account_mask="Z00000001",
            asset_group="taxable",
            account_type="brokerage",
            source_type="brokerage",
        ),
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert created == 1
    assert merged == 0
    assert account_id != "wrong"
    assert identity_map["institution-mask::fidelity|z00000001"] == account_id
    assert canonical_accounts[account_id].account_type == "brokerage"
    assert canonical_accounts[account_id].asset_group == "taxable"


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
            account_mask="Z00000002",
        )
    }
    identity_map = {"institution-mask::fidelity|z00000002": "portfolio-linked"}

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
            account_mask="Z00000002",
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
    tracked_accounts = [tracked_account.model_copy(update={"household_account_id": "tod-id"})]
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
        "child_two": _canonical(
            account_id="child_two",
            label="529 - Demo Child Two",
            asset_group="education",
            account_type="529",
            source_type="education",
            institution_name="CollegeAmerica / VCSP",
            owner_name="Jordan Demo",
            account_mask="00022222",
        )
    }
    identity_map = {
        "institution-mask::collegeamerica / vcsp|00022222": "child_two",
        "mask::00022222|education|529": "child_two",
    }

    account_id, created, merged = registry._resolve_from_evidence(
        conn,
        evidence=_evidence(
            evidence_id="evidence-2",
            document_id="doc-2",
            institution_name="CollegeAmerica / VCSP",
            account_name="529 - Demo Child One",
            owner_name="Jordan Demo",
            account_mask="00011111",
            asset_group="education",
            account_type="529",
            source_type="education",
        ),
        canonical_accounts=canonical_accounts,
        identity_map=identity_map,
    )

    assert created == 1
    assert merged == 0
    assert account_id != "child_two"
