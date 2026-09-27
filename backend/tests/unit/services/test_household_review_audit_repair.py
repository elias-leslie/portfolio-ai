"""Evidence boundaries for the historical Money Review repair."""

from __future__ import annotations

from decimal import Decimal

from app.services.household_review_audit_repair import _duplicates, _target


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "other", "date": "2026-05-08", "amount": Decimal("20"),
        "flow_type": "expense", "category": "Subscriptions",
        "essentiality": "discretionary", "source_system": "plaid",
        "categorization_source": "canonical_backfill", "description": "DEPOP",
        "original_category": "GENERAL_MERCHANDISE_CLOTHING_AND_ACCESSORIES",
        "merchant_id": None, "spend_override": None,
    }
    row.update(overrides)
    return row


def test_repair_restores_clothing_purchase_without_reclassifying_minimax() -> None:
    assert _target(_row()) == ("expense", "Retail", "discretionary", "provider_category")
    assert _target(_row(description="NANONOBLE PTE. LTD.")) is None


def test_repair_separates_spaxx_yield_from_budget_income() -> None:
    row = _row(
        source_system="snaptrade", flow_type="income", category="Income",
        description="DIVIDEND RECEIVED FIDELITY GOVERNMENT MONEY MARKET (SPAXX) (Cash)",
    )
    assert _target(row) == ("investment", "Investments", "mixed", "user_budget_yield_preference")


def test_repair_does_not_merge_distinct_hvac_charges() -> None:
    rows = [
        _row(id="first", amount=Decimal("5801.50"), description="Costco", source_system="plaid"),
        _row(id="second", amount=Decimal("5831.50"), description="Costco", source_system="plaid"),
    ]
    assert _duplicates(rows) == {}


def test_repair_never_changes_unrelated_manual_classification() -> None:
    assert _target(_row(categorization_source="manual")) is None
