"""Previewable, fingerprint-bound repair of machine-derived merchant data."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from typing import Any

from app.services._household_merchants import _canonical_merchant_name, _classification_for_flow
from app.services._household_report_builder import _merchant_aliases
from app.services.household_transaction_service import HouseholdTransactionService

_REPAIR_VERSION = "2026-09-11-source-identity"
_PROTECTED = {"manual", "manual_rule", "merchant_rule", "transaction_audit_agent"}


def _snapshot(conn: Any) -> dict[str, Any]:
    merchants = conn.execute(
        "SELECT id::text, canonical_name, display_name, normalized_key, metadata FROM household_merchants ORDER BY id"
    ).fetchall()
    transactions = conn.execute(
        """SELECT id::text, merchant_id::text, raw_merchant, description,
                  category, essentiality, categorization_source, amount,
                  to_char(transaction_date, 'YYYY-MM'), flow_type,
                  transaction_rule_id::text, metadata, category_updated_by
           FROM household_transactions ORDER BY id"""
    ).fetchall()
    return {
        "merchants": {str(row[0]): list(row[1:]) for row in merchants},
        "transactions": {str(row[0]): list(row[1:]) for row in transactions},
    }


def _changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for kind in ("merchants", "transactions"):
        changes[kind] = [
            {"id": key, "before": before[kind].get(key), "after": after[kind].get(key)}
            for key in sorted(before[kind].keys() | after[kind].keys())
            if before[kind].get(key) != after[kind].get(key)
        ]
    for item in changes["transactions"]:
        old, new = item["before"], item["after"]
        if old[3] != new[3]:
            # Raw category movement, not deduplicated budget totals. The normal
            # spending service recomputes the actual review after repair.
            amount, month = float(old[6] or 0), str(old[7])
            totals[month][str(old[3])] -= amount
            totals[month][str(new[3])] += amount
    changes["raw_category_movements"] = {
        month: {category: round(amount, 2) for category, amount in categories.items()}
        for month, categories in sorted(totals.items())
    }
    return changes


def _restore_bridge_evidence(conn: Any, before: dict[str, Any]) -> None:
    """Undo the bridge's replacement of raw evidence with a derived name.

    Only identifiable card purchases/cash advances are repaired here. A source
    description is preserved and a deterministic audit may be corrected; a
    person's classification, agent-reviewed rule, or merchant rule is retained.
    """
    targets: dict[str, str] = {}
    touched: set[str] = set()
    for transaction_id, row in before["transactions"].items():
        old_id, raw, description = row[:3]
        metadata = row[10] if isinstance(row[10], dict) else {}
        if metadata.get("source") != "snaptrade_activity_bridge":
            continue
        if not str(description).lower().startswith(("debit card purchase ", "cash advance ")):
            continue
        name = _canonical_merchant_name(str(description))
        key = name.casefold()
        merchant = before["merchants"].get(old_id, ["", "", "", {}])
        merchant_metadata = merchant[3] if isinstance(merchant[3], dict) else {}
        protected = row[5] in _PROTECTED or bool(row[9]) or bool(merchant_metadata.get("manual_rule"))
        category, essentiality = (row[3], row[4]) if protected else _classification_for_flow(
            raw_merchant=name, description=str(description), amount=float(row[6]), flow_type=str(row[8])
        )
        if key not in targets:
            # Retain an existing correctly named merchant (and its real rules).
            candidates = sorted(
                mid for mid, value in before["merchants"].items()
                if _canonical_merchant_name(str(value[0])).casefold() == key
            )
            targets[key] = candidates[0] if candidates else str(uuid.uuid5(uuid.NAMESPACE_URL, f"portfolio-ai/merchant/{key}"))
        target = targets[key]
        conn.execute(
            """INSERT INTO household_merchants
               (id, canonical_name, display_name, normalized_key, primary_category, essentiality, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, '{}'::jsonb)
               ON CONFLICT (id) DO NOTHING""",
            [target, name, name, f"identity:{target}", category, essentiality],
        )
        touched.update(mid for mid in (old_id, target) if mid)
        if (old_id, raw, row[3], row[4]) == (target, description, category, essentiality):
            continue
        repair_metadata = {
            "merchant_repair": {
                "version": _REPAIR_VERSION,
                "original_raw_merchant": raw,
                "original_merchant_id": old_id,
                "original_category": row[3],
                "original_categorization_source": row[5],
                "source": "preserved_vendor_description",
                "manual_classification_preserved": bool(protected),
            }
        }
        conn.execute(
            """UPDATE household_transactions SET merchant_id=%s, raw_merchant=%s,
               category=%s, essentiality=%s, categorization_source=%s,
               original_category=COALESCE(original_category, category),
               category_updated_by=%s, categorization_version=%s,
               metadata=metadata || %s::jsonb, updated_at=NOW()
               WHERE id=%s""",
            [target, description, category, essentiality,
             row[5] if protected else "evidence_repair",
             row[11] if protected else "source_identity_repair", _REPAIR_VERSION,
             json.dumps(repair_metadata), transaction_id],
        )
    for merchant_id in sorted(touched):
        rows = conn.execute(
            "SELECT raw_merchant FROM household_transactions WHERE merchant_id=%s AND raw_merchant IS NOT NULL ORDER BY raw_merchant",
            [merchant_id],
        ).fetchall()
        aliases = sorted({alias for (raw,) in rows for alias in _merchant_aliases(str(raw))})
        names = [_canonical_merchant_name(str(raw)) for (raw,) in rows]
        name = max(names, key=lambda value: (len(value), value)) if names else None
        conn.execute(
            """UPDATE household_merchants SET normalized_key=%s,
               canonical_name=COALESCE(%s, canonical_name), display_name=COALESCE(%s, display_name),
               metadata=metadata || %s::jsonb, updated_at=NOW() WHERE id=%s""",
            [f"identity:{merchant_id}", name, name, json.dumps({"alias_keys": aliases}), merchant_id],
        )


def repair_household_merchants(
    service: HouseholdTransactionService,
    *,
    expected_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Rollback a preview; apply only the exact previously reviewed snapshot.

    Both paths lock the two affected tables briefly to prevent an import from
    changing the meaning of a merchant while its categories are derived. No
    purchase linking, account linking, or manual-rule backfill runs here.
    """
    with service.storage.connection() as conn:
        try:
            conn.execute(
                "LOCK TABLE household_merchants, household_transactions IN SHARE ROW EXCLUSIVE MODE"
            )
            before = _snapshot(conn)
            _restore_bridge_evidence(conn, before)
            after = _snapshot(conn)
            changes = _changes(before, after)
            fingerprint = hashlib.sha256(
                json.dumps({"before": before, "changes": changes}, sort_keys=True, default=str).encode()
            ).hexdigest()
            if expected_fingerprint is not None and expected_fingerprint != fingerprint:
                raise ValueError("Financial evidence changed since the preview; generate and review a new preview.")
            if expected_fingerprint is None:
                conn.rollback()
            else:
                conn.commit()
            return {"fingerprint": fingerprint, "applied": expected_fingerprint is not None, **changes}
        except Exception:
            conn.rollback()
            raise
