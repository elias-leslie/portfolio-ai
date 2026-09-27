"""Evidence-bounded repair of the 2026 household Review ledger.

Preview produces a fingerprint of exact before/after rows. Applying requires that
fingerprint, locks the rows, and retains the previous values in metadata. No
financial transaction is deleted; duplicate source rows are only soft-removed.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.storage import PortfolioStorage, get_storage

_VERSION = "2026-09-27-full-review-audit"
_PROTECTED = {"manual", "manual_rule", "merchant_rule"}

_FIXED: dict[str, tuple[str, str, str, str]] = {
    # Progressive billing activity records a $276.99 refund, not a premium.
    "f231ce04-69bd-4317-a44e-b7c7fed49fb0": ("refund", "Insurance", "essential", "progressive_refund"),
    # Merchant credits on credit cards with source-confirmed matching charges.
    "8d9dd34b-e438-4a9d-a814-329bf31090fb": ("refund", "Retail", "discretionary", "merchant_refund"),
    "e4b56363-dea4-4789-970e-5ce6d28e9a76": ("refund", "Retail", "discretionary", "merchant_refund"),
    "02ede93c-b636-419d-9419-62bc4c749394": ("refund", "Retail", "discretionary", "merchant_refund"),
    "3ff23021-319d-4e52-9c04-8bfc096a8061": ("refund", "Subscriptions", "discretionary", "merchant_refund"),
    "bfc2b9bc-a6fa-4eff-be0c-4faa7c4d0b36": ("refund", "Travel", "discretionary", "merchant_refund"),
    "71e6e0f0-3a41-4e8f-8ef3-713f8b575202": ("refund", "Travel", "discretionary", "merchant_refund"),
    # Brokerage verification deposits/withdrawals, wallet cash-out and broker move.
    "018454cc-3a5b-4add-89ff-2b8b983890f1": ("transfer_in", "Transfers", "mixed", "account_verification"),
    "da6fde43-e11e-4bf7-8be6-b13d715cee23": ("transfer_in", "Transfers", "mixed", "account_verification"),
    "a17d7a12-118c-4c63-b665-648e1e6401c1": ("transfer_out", "Transfers", "mixed", "account_verification"),
    "74bf7291-cd89-4b5b-970e-d30951c3ca4d": ("transfer_in", "Transfers", "mixed", "account_verification"),
    "863fadfd-ed5a-4309-ab81-3222e38a8b36": ("transfer_in", "Transfers", "mixed", "account_verification"),
    "21a8e61e-50cf-4775-b289-15bd5eb0080a": ("transfer_out", "Transfers", "mixed", "account_verification"),
    "dd6dd948-7985-4cf3-98c9-a106f3a143ff": ("transfer_in", "Transfers", "mixed", "broker_transfer"),
    "f2be0c67-c72c-4c14-96e4-a788712b4b4b": ("transfer_in", "Transfers", "mixed", "wallet_cashout"),
    # External property receipts, not movement among the household's accounts.
    # The user says subsequent settlements now run through a brother annually;
    # these historical payments do not establish current monthly run-rate.
    "bca00f4b-d8d3-42dd-989e-dc22d74a3b23": ("income", "Income", "essential", "property_cash_inflow"),
    "2ed75276-9432-42e8-92dc-8fd4e0d0d5dd": ("income", "Income", "essential", "property_cash_inflow"),
    # The user identified these distinct Costco charges as one HVAC installation
    # split across two cards. Neither charge is deduplicated.
    "24d377f7-75a2-4ae7-8172-54a17bd21ee2": ("expense", "Home", "discretionary", "user_confirmed_hvac"),
    "3ff71ffb-76d3-46c8-a97b-5017fea97c14": ("expense", "Home", "discretionary", "user_confirmed_hvac"),
    # Narrow miscategorized merchants outside the canonical-backfill cohort.
    "641f4df3-2f1f-421d-820b-e30ed09fc37e": ("expense", "Entertainment", "discretionary", "merchant_category"),
    "5c81882d-1076-44c5-88ab-660ffbdc37e8": ("expense", "Dining", "discretionary", "merchant_category"),
    "1683fa83-d5ec-4dfc-9576-dbe71c5432ce": ("expense", "Entertainment", "discretionary", "merchant_category"),
    "5be0f6e2-1093-46af-be8a-900be4ca6aa8": ("expense", "Travel", "discretionary", "merchant_category"),
    "cbe7da66-1c3b-446a-bec2-e71969334433": ("expense", "Dining", "discretionary", "merchant_category"),
    "0eda7db1-71fb-4beb-90a4-71a69650edf5": ("expense", "Groceries", "essential", "merchant_category"),
    "7226240f-3dad-4872-a94e-e02a3c7c1f0b": ("expense", "Transportation", "essential", "merchant_category"),
    "7dd91eab-c11e-47ee-a05d-7b5f7df568f9": ("expense", "Girls", "discretionary", "existing_manual_payee_rule"),
    # Clear same-merchant / provider-taxonomy category drift outside Subscriptions.
    "f14fc6f0-9d54-4418-bbc4-69924e9f99cc": ("expense", "Personal Care", "discretionary", "same_merchant_provider"),
    "193cf21e-39b5-494d-871a-02551af7b357": ("expense", "Groceries", "essential", "same_merchant_provider"),
    "6e2f8d61-8ea8-4ed5-947c-81c00597dda3": ("expense", "Retail", "discretionary", "provider_category"),
    "b78012a2-16b5-4d7e-8660-3db76cc7fa33": ("expense", "Retail", "discretionary", "provider_category"),
    "10fbe0c3-4e97-4664-a65d-f1d2ddfe9a1d": ("expense", "Retail", "discretionary", "provider_category"),
    "6a5ec681-6691-405e-b2e7-8c3e90e9f06f": ("expense", "Retail", "discretionary", "provider_category"),
    "9a38483a-6491-4c16-be22-aa0a6458fa20": ("expense", "Dining", "discretionary", "provider_restaurant"),
    "ad89b18e-ff0f-4333-b22e-d07467526077": ("expense", "Dining", "discretionary", "provider_restaurant"),
    "1d7bd037-3755-4ff9-aa55-ee26a8f82f04": ("expense", "Personal Care", "discretionary", "provider_category"),
    "eddcfbf7-0217-4b5d-85a8-971ac85cf923": ("expense", "Personal Care", "discretionary", "provider_category"),
    "c758cbb5-0a5b-4036-be89-35a9809ccfeb": ("expense", "Gas", "essential", "provider_gas"),
    "84a2eb23-38ae-4f3a-a308-0556b426b2f8": ("expense", "Bills", "essential", "user_confirmed_former_llc_filing"),
}

_GIRLS_PAYEE = "vsi*largo rec"
_GIRLS_MERCHANTS = {
    "5158c232-e6b0-467d-9de7-c37afd23b79e",
    "c477408a-7cc0-4e41-bc46-d5da77a3fc70",
}
_REFUND_IDS = {
    "f231ce04-69bd-4317-a44e-b7c7fed49fb0",
    "8d9dd34b-e438-4a9d-a814-329bf31090fb",
    "e4b56363-dea4-4789-970e-5ce6d28e9a76",
    "02ede93c-b636-419d-9419-62bc4c749394",
    "3ff23021-319d-4e52-9c04-8bfc096a8061",
    "bfc2b9bc-a6fa-4eff-be0c-4faa7c4d0b36",
    "71e6e0f0-3a41-4e8f-8ef3-713f8b575202",
}


def _row_dict(row: tuple[Any, ...]) -> dict[str, Any]:
    names = (
        "id", "date", "amount", "flow_type", "category", "essentiality",
        "source_system", "categorization_source", "description", "original_category",
        "merchant_id", "transaction_rule_id", "spend_override", "metadata", "updated_at",
    )
    item = dict(zip(names, row, strict=True))
    item["id"] = str(item["id"])
    item["date"] = item["date"].isoformat()
    item["amount"] = Decimal(str(item["amount"]))
    item["merchant_id"] = str(item["merchant_id"]) if item["merchant_id"] else None
    item["transaction_rule_id"] = str(item["transaction_rule_id"]) if item["transaction_rule_id"] else None
    item["metadata"] = item["metadata"] if isinstance(item["metadata"], dict) else {}
    item["updated_at"] = item["updated_at"].isoformat()
    return item


def _subscription_target(row: dict[str, Any]) -> tuple[str, str, str, str] | None:
    if row["category"] != "Subscriptions" or row["categorization_source"] != "canonical_backfill":
        return None
    description = row["description"].lower()
    if any(x in description for x in ("nanonoble", "google one", "amazon prime", "central pinellas chamber")):
        return None
    if _GIRLS_PAYEE in description:
        return ("expense", "Girls", "discretionary", "existing_manual_payee_rule")
    if "ikea tampa rest" in description:
        return ("expense", "Dining", "discretionary", "restaurant_descriptor")
    key = re.sub(r"[^A-Z0-9]+", "_", str(row["original_category"] or "").upper())
    if key.startswith("FOOD_AND_DRINK_GROCERIES") or key.endswith("CONVENIENCE_STORES"):
        category, essentiality = "Groceries", "essential"
    elif key.startswith("FOOD_AND_DRINK_"):
        category, essentiality = "Dining", "discretionary"
    elif key.startswith("GENERAL_MERCHANDISE_"):
        category, essentiality = "Retail", "discretionary"
    elif key.startswith("MEDICAL_"):
        category, essentiality = "Healthcare", "essential"
    elif key.startswith("HOME_IMPROVEMENT_"):
        category, essentiality = "Home", "discretionary"
    elif key.startswith("PERSONAL_CARE_"):
        category, essentiality = "Personal Care", "discretionary"
    elif key.startswith("ENTERTAINMENT_"):
        category, essentiality = "Entertainment", "discretionary"
    else:
        return None
    return (row["flow_type"], category, essentiality, "provider_category")


def _target(row: dict[str, Any]) -> tuple[str, str, str, str] | None:
    row_id = row["id"]
    if row_id == "2d75c08f-2405-4a7d-87fd-d437aa9174f7":
        return (row["flow_type"], row["category"], row["essentiality"], "remove_false_pdf_premium")
    if row["spend_override"] or (
        row["categorization_source"] in _PROTECTED
        and row_id not in {
            "24d377f7-75a2-4ae7-8172-54a17bd21ee2",
            "3ff71ffb-76d3-46c8-a97b-5017fea97c14",
        }
    ):
        return None
    if row_id in _FIXED:
        return _FIXED[row_id]
    if (
        row["source_system"] in {"snaptrade", "statement_csv"}
        and row["flow_type"] == "income"
        and "dividend received" in row["description"].lower()
        and "spaxx" in row["description"].lower()
    ):
        return ("investment", "Investments", "mixed", "user_budget_yield_preference")
    if row["description"].lower().startswith(_GIRLS_PAYEE) and row["merchant_id"] in _GIRLS_MERCHANTS:
        return ("expense", "Girls", "discretionary", "existing_manual_payee_rule")
    return _subscription_target(row)


def _duplicates(rows: list[dict[str, Any]]) -> dict[str, str]:
    csv: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    pdf: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    for row in rows:
        if row["source_system"] not in {"statement_csv", "bank_statement"}:
            continue
        key = (
            row["date"], str(row["amount"]), row["flow_type"],
            re.sub(r"[^a-z0-9]", "", row["description"].lower()),
        )
        (csv if row["source_system"] == "statement_csv" else pdf)[key].append(row["id"])
    paired: dict[str, str] = {}
    for key, pdf_ids in pdf.items():
        csv_ids = csv.get(key, [])
        if len(pdf_ids) == len(csv_ids) == 1:
            paired[pdf_ids[0]] = csv_ids[0]
        elif csv_ids:
            raise ValueError(f"Ambiguous cross-document duplicate: {key}")
    if paired and len(paired) != 33:
        raise ValueError(f"Expected 33 evidenced PDF/CSV pairs; found {len(paired)}")
    return paired


def _build_changes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {row["id"]: row for row in rows}
    missing = set(_FIXED) - set(by_id)
    if missing:
        # A second preview after an import or audit may encounter legitimately
        # removed rows; never apply a partial repair without new evidence.
        raise ValueError(f"Expected ledger rows missing: {sorted(missing)}")
    if set(_REFUND_IDS) - set(by_id):
        raise ValueError("A source-confirmed refund is missing")
    duplicate_of = _duplicates(rows)
    changes: list[dict[str, Any]] = []
    for row in rows:
        target = _target(row)
        reason = target[3] if target else None
        removed = row["id"] in duplicate_of or reason == "remove_false_pdf_premium"
        if not target and not removed:
            continue
        before = [row["flow_type"], row["category"], row["essentiality"], False]
        after = [*(target[:3] if target else before[:3]), removed]
        if before == after:
            continue
        changes.append({
            "id": row["id"], "date": row["date"], "amount": str(row["amount"]),
            "description": row["description"], "source_system": row["source_system"],
            "before": before, "after": after,
            "before_categorization_source": row["categorization_source"],
            "before_transaction_rule_id": row["transaction_rule_id"],
            "reason": "cross_document_duplicate" if row["id"] in duplicate_of else reason,
            "kept_transaction_id": duplicate_of.get(row["id"]),
            "updated_at": row["updated_at"],
        })
    return sorted(changes, key=lambda change: change["id"])


def _rule_changes(conn: Any) -> list[str]:
    original = conn.execute(
        """SELECT category, essentiality, enabled, source
           FROM household_transaction_rules WHERE id=%s FOR UPDATE""",
        ["7b67988e-5597-448d-8f5d-b75b852f923d"],
    ).fetchone()
    if original != ("Girls", "discretionary", True, "manual"):
        raise ValueError("The user's original Largo Rec rule changed")
    changes: list[str] = []
    for merchant_id in sorted(_GIRLS_MERCHANTS):
        merchant = conn.execute(
            "SELECT canonical_name FROM household_merchants WHERE id=%s FOR UPDATE",
            [merchant_id],
        ).fetchone()
        if merchant is None or str(merchant[0]).lower() != _GIRLS_PAYEE:
            raise ValueError("Largo Rec merchant identity changed")
        rules = conn.execute(
            """SELECT category, essentiality, source FROM household_transaction_rules
               WHERE merchant_id=%s AND enabled IS TRUE FOR UPDATE""",
            [merchant_id],
        ).fetchall()
        if not rules:
            changes.append(merchant_id)
        elif rules != [("Girls", "discretionary", "manual")]:
            raise ValueError("An active Largo Rec rule conflicts with the user's rule")
    return changes


def repair_review_ledger(
    storage: PortfolioStorage | None = None, *, expected_fingerprint: str | None = None
) -> dict[str, Any]:
    """Preview, then atomically apply only the exact source-backed repair."""
    storage = storage or get_storage()
    with storage.connection() as conn:
        try:
            rows = [_row_dict(row) for row in conn.execute(
                """SELECT id, transaction_date::date, amount, flow_type, category,
                          essentiality, source_system, categorization_source,
                          description, original_category, merchant_id,
                          transaction_rule_id, spend_override, metadata, updated_at
                   FROM household_transactions WHERE removed IS NOT TRUE
                   ORDER BY id FOR UPDATE"""
            ).fetchall()]
            changes = _build_changes(rows)
            rule_changes = _rule_changes(conn)
            fingerprint = hashlib.sha256(
                json.dumps({"changes": changes, "rule_changes": rule_changes}, sort_keys=True).encode()
            ).hexdigest()
            if expected_fingerprint is None:
                conn.rollback()
                return {"applied": False, "fingerprint": fingerprint, "changes": changes,
                        "rule_changes": rule_changes}
            if expected_fingerprint != fingerprint:
                raise ValueError("Ledger evidence changed since preview; preview again")
            for change in changes:
                before, after = change["before"], change["after"]
                provenance = {"review_audit_repair": {
                    "version": _VERSION, "reason": change["reason"],
                    "before": before, "kept_transaction_id": change["kept_transaction_id"],
                    "before_categorization_source": change["before_categorization_source"],
                    "before_transaction_rule_id": change["before_transaction_rule_id"],
                }}
                row = conn.execute(
                    """UPDATE household_transactions
                       SET flow_type=%s, category=%s, essentiality=%s, removed=%s,
                           categorization_source=CASE WHEN %s='user_confirmed_hvac'
                               THEN 'manual' ELSE 'transaction_audit' END,
                           category_updated_at=NOW(), category_updated_by='review_audit',
                           metadata=COALESCE(metadata,'{}'::jsonb)||%s::jsonb, updated_at=NOW()
                       WHERE id=%s AND flow_type=%s AND category=%s AND essentiality=%s
                         AND removed IS NOT TRUE AND updated_at=%s
                       RETURNING id""",
                    [*after, change["reason"], json.dumps(provenance), change["id"],
                     *before[:3], datetime.fromisoformat(change["updated_at"])],
                ).fetchone()
                if row is None:
                    raise ValueError(f"Ledger row changed during repair: {change['id']}")
            # The active manual Girls rule was attached to an alias merchant.
            # Link the exact same payee's two actual merchant identities so new
            # imports inherit the user's original choice.
            for merchant_id in rule_changes:
                conn.execute(
                    """INSERT INTO household_transaction_rules
                       (id, rule_type, merchant_id, normalized_merchant_key, category,
                        essentiality, enabled, source, applied_count, metadata,
                        created_at, updated_at)
                       SELECT %s, 'merchant', m.id, m.normalized_key, 'Girls',
                              'discretionary', TRUE, 'manual', 0, %s::jsonb, NOW(), NOW()
                       FROM household_merchants m WHERE m.id=%s
                         AND lower(m.canonical_name)='vsi*largo rec'""",
                    [str(uuid.uuid4()), json.dumps({"derived_from_rule_id":
                     "7b67988e-5597-448d-8f5d-b75b852f923d", "version": _VERSION}),
                     merchant_id],
                )
            conn.commit()
            return {"applied": True, "fingerprint": fingerprint, "changes": changes,
                    "rule_changes": rule_changes}
        except Exception:
            conn.rollback()
            raise
