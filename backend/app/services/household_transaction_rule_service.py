"""Transaction categorization command helpers for household finance."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import HouseholdTransactionCategoryUpdate


class HouseholdTransactionRuleService:
    """Persist transaction category overrides and merchant rules."""

    def update_transaction_category(
        self,
        service: Any,
        transaction_id: str,
        payload: HouseholdTransactionCategoryUpdate,
    ) -> bool:
        with service.storage.connection() as conn:
            target = conn.execute(
                """
                SELECT t.id, t.merchant_id, m.normalized_key
                FROM household_transactions t
                LEFT JOIN household_merchants m ON m.id = t.merchant_id
                WHERE t.id = %s
                """,
                [transaction_id],
            ).fetchone()
            if target is None:
                return False

            merchant_id = str(target[1]) if target[1] is not None else None
            normalized_merchant_key = str(target[2]) if len(target) > 2 and target[2] is not None else None
            updated_at = datetime.now(UTC)
            row = conn.execute(
                """
                UPDATE household_transactions
                SET category = %s,
                    essentiality = %s,
                    confidence = GREATEST(COALESCE(confidence, 0), 0.97),
                    original_category = COALESCE(original_category, category),
                    categorization_source = %s,
                    categorization_version = %s,
                    category_updated_at = %s,
                    category_updated_by = %s,
                    transaction_rule_id = NULL,
                    updated_at = %s
                WHERE id = %s
                RETURNING id
                """,
                [
                    payload.category,
                    payload.essentiality,
                    "manual",
                    "2026-05-canonical",
                    updated_at,
                    "user",
                    updated_at,
                    transaction_id,
                ],
            ).fetchone()
            if payload.apply_to_merchant and merchant_id is not None:
                existing_rule = conn.execute(
                    """
                    SELECT id
                    FROM household_transaction_rules
                    WHERE merchant_id = %s
                      AND enabled IS TRUE
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    [merchant_id],
                ).fetchone()
                applied_count_row = conn.execute(
                    "SELECT COUNT(*) FROM household_transactions WHERE merchant_id = %s",
                    [merchant_id],
                ).fetchone()
                applied_count = int(applied_count_row[0] or 0) if applied_count_row is not None else 0
                rule_id = str(existing_rule[0]) if existing_rule is not None else str(uuid.uuid4())
                rule_metadata = json.dumps(
                    {
                        "created_from_transaction_id": transaction_id,
                        "updated_at": updated_at.isoformat(),
                    }
                )
                if existing_rule is None:
                    conn.execute(
                        """
                        INSERT INTO household_transaction_rules (
                            id, rule_type, merchant_id, normalized_merchant_key,
                            category, essentiality, enabled, source, applied_count,
                            metadata, created_at, updated_at
                        ) VALUES (
                            %s, 'merchant', %s, %s, %s, %s, TRUE, 'manual',
                            %s, %s::jsonb, %s, %s
                        )
                        """,
                        [
                            rule_id,
                            merchant_id,
                            normalized_merchant_key,
                            payload.category,
                            payload.essentiality,
                            applied_count,
                            rule_metadata,
                            updated_at,
                            updated_at,
                        ],
                    )
                else:
                    conn.execute(
                        """
                        UPDATE household_transaction_rules
                        SET normalized_merchant_key = COALESCE(%s, normalized_merchant_key),
                            category = %s,
                            essentiality = %s,
                            enabled = TRUE,
                            source = 'manual',
                            applied_count = %s,
                            metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                            updated_at = %s
                        WHERE id = %s
                        """,
                        [
                            normalized_merchant_key,
                            payload.category,
                            payload.essentiality,
                            applied_count,
                            rule_metadata,
                            updated_at,
                            rule_id,
                        ],
                    )
                conn.execute(
                    """
                    UPDATE household_transactions
                    SET category = %s,
                        essentiality = %s,
                        confidence = GREATEST(COALESCE(confidence, 0), 0.97),
                        original_category = COALESCE(original_category, category),
                        categorization_source = %s,
                        categorization_version = %s,
                        category_updated_at = %s,
                        category_updated_by = %s,
                        transaction_rule_id = %s,
                        updated_at = %s
                    WHERE merchant_id = %s
                    """,
                    [
                        payload.category,
                        payload.essentiality,
                        "merchant_rule",
                        "2026-05-canonical",
                        updated_at,
                        "user",
                        rule_id,
                        updated_at,
                        merchant_id,
                    ],
                )
                conn.execute(
                    """
                    UPDATE household_merchants
                    SET primary_category = %s,
                        essentiality = %s,
                        metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    [
                        payload.category,
                        payload.essentiality,
                        json.dumps(
                            {
                                "manual_rule": {
                                    "rule_id": rule_id,
                                    "category": payload.category,
                                    "essentiality": payload.essentiality,
                                    "updated_at": updated_at.isoformat(),
                                }
                            }
                        ),
                        updated_at,
                        merchant_id,
                    ],
                )
            conn.commit()
        return row is not None
