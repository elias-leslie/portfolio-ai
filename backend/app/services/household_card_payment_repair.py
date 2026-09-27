"""Preview and repair machine-classified card payments already in the ledger."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.services.plaid_service import _CARD_PAYMENT_DESCRIPTION
from app.storage import PortfolioStorage, get_storage

_REPAIR_VERSION = "2026-09-27-card-payment-flow"
_MACHINE_SOURCES = {"plaid", "snaptrade", "transaction_audit"}
_CAUTOPAY_DESCRIPTION = "direct debit chase credit cautopay (cash)"


def _payment_rows(conn: Any) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT t.id::text, t.transaction_date, t.description, t.amount,
               t.flow_type, t.category, t.essentiality, t.source_system,
               t.categorization_source, t.transaction_rule_id::text,
               t.spend_override, t.original_category, t.metadata, t.updated_at,
               pa.type AS plaid_account_type, pt.amount AS plaid_signed_amount,
               m.metadata AS merchant_metadata,
               EXISTS (
                   SELECT 1 FROM household_transaction_rules r
                   WHERE r.merchant_id = t.merchant_id AND r.enabled IS TRUE
               ) AS active_merchant_rule
        FROM household_transactions t
        LEFT JOIN household_merchants m ON m.id = t.merchant_id
        LEFT JOIN plaid_transactions pt
          ON t.source_system = 'plaid'
         AND pt.transaction_id = t.external_transaction_id
        LEFT JOIN plaid_accounts pa ON pa.account_id = pt.account_id
        WHERE t.removed IS NOT TRUE
          AND (
            (t.source_system = 'plaid' AND t.description ILIKE '%payment%thank%')
            OR (t.source_system = 'snaptrade' AND t.description ILIKE '%credit cautopay%')
          )
        ORDER BY t.id
        FOR UPDATE OF t
        """
    ).fetchall()
    return [
        {
            "id": str(row[0]),
            "date": row[1].date().isoformat() if isinstance(row[1], datetime) else str(row[1]),
            "description": str(row[2] or ""),
            "amount": Decimal(str(row[3])),
            "flow_type": str(row[4] or ""),
            "category": str(row[5] or ""),
            "essentiality": str(row[6] or ""),
            "source_system": str(row[7] or ""),
            "categorization_source": str(row[8] or ""),
            "transaction_rule_id": row[9],
            "spend_override": row[10],
            "original_category": str(row[11] or ""),
            "metadata": row[12] if isinstance(row[12], dict) else {},
            "updated_at": row[13].isoformat() if isinstance(row[13], datetime) else str(row[13]),
            "plaid_account_type": str(row[14] or ""),
            "plaid_signed_amount": Decimal(str(row[15])) if row[15] is not None else None,
            "merchant_metadata": row[16] if isinstance(row[16], dict) else {},
            "active_merchant_rule": bool(row[17]),
        }
        for row in rows
    ]


def _is_card_credit(row: dict[str, Any]) -> bool:
    return (
        row["source_system"] == "plaid"
        and row["plaid_account_type"].lower() == "credit"
        and row["plaid_signed_amount"] == -row["amount"]
        and _CARD_PAYMENT_DESCRIPTION.search(row["description"]) is not None
    )


def _target(row: dict[str, Any], card_credits: list[dict[str, Any]]) -> tuple[str, str, str] | None:
    if (
        row["categorization_source"] not in _MACHINE_SOURCES
        or row["transaction_rule_id"] is not None
        or row["spend_override"] not in (None, "")
        or row["active_merchant_rule"]
        or bool(row["merchant_metadata"].get("manual_rule"))
    ):
        return None
    if _is_card_credit(row):
        return "payment", "Transfers", "mixed"
    if (
        row["source_system"] == "snaptrade"
        and row["description"].strip().lower() == _CAUTOPAY_DESCRIPTION
        and row["original_category"].upper() == "WITHDRAWAL"
        and row["metadata"].get("source") == "snaptrade_activity_bridge"
        and row["flow_type"] == "expense"
        and row["category"] == "Bills"
        and any(
            credit["amount"] == row["amount"]
            and abs((datetime.fromisoformat(credit["date"]) - datetime.fromisoformat(row["date"])).days) <= 3
            for credit in card_credits
        )
    ):
        return "transfer_out", "Transfers", "mixed"
    return None


def repair_card_payments(
    storage: PortfolioStorage | None = None,
    *,
    expected_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Preview a rollback, or apply only the exact previewed ledger changes.

    Source descriptions, provider categories, transaction identities, merchant
    links, and a person's rules or overrides are left intact. A repeat call is
    empty because the target flow and category are already stored.
    """
    storage = storage or get_storage()
    with storage.connection() as conn:
        try:
            rows = _payment_rows(conn)
            card_credits = [row for row in rows if _is_card_credit(row)]
            changes: list[dict[str, Any]] = []
            for row in rows:
                target = _target(row, card_credits)
                if target is None:
                    continue
                before = (row["flow_type"], row["category"], row["essentiality"])
                if before == target:
                    continue
                changes.append(
                    {
                        "id": row["id"],
                        "date": row["date"],
                        "description": row["description"],
                        "amount": str(row["amount"]),
                        "source_system": row["source_system"],
                        "before": before,
                        "after": target,
                        "updated_at": row["updated_at"],
                    }
                )
            fingerprint = hashlib.sha256(
                json.dumps(changes, sort_keys=True).encode()
            ).hexdigest()
            if expected_fingerprint is not None and expected_fingerprint != fingerprint:
                raise ValueError("Card-payment evidence changed since preview; generate a new preview.")
            if expected_fingerprint is None:
                conn.rollback()
                return {"applied": False, "fingerprint": fingerprint, "changes": changes}
            for change in changes:
                before = change["before"]
                after = change["after"]
                provenance = {
                    "card_payment_repair": {
                        "version": _REPAIR_VERSION,
                        "previous_flow_type": before[0],
                        "previous_category": before[1],
                        "previous_essentiality": before[2],
                        "evidence": "explicit card-payment description and account/source evidence",
                    }
                }
                result = conn.execute(
                    """
                    UPDATE household_transactions
                    SET flow_type = %s, category = %s, essentiality = %s,
                        metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s AND flow_type = %s AND category = %s
                    RETURNING id
                    """,
                    [*after, json.dumps(provenance), change["id"], before[0], before[1]],
                ).fetchone()
                if result is None:
                    raise ValueError("Card-payment evidence changed during repair.")
            conn.commit()
            return {"applied": True, "fingerprint": fingerprint, "changes": changes}
        except Exception:
            conn.rollback()
            raise
