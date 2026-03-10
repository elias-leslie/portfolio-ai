"""Transaction categorization command helpers for household finance."""

from __future__ import annotations

import json
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
                SELECT id, merchant_id
                FROM household_transactions
                WHERE id = %s
                """,
                [transaction_id],
            ).fetchone()
            if target is None:
                return False

            merchant_id = str(target[1]) if target[1] is not None else None
            updated_at = datetime.now(UTC)
            row = conn.execute(
                """
                UPDATE household_transactions
                SET category = %s,
                    essentiality = %s,
                    confidence = GREATEST(COALESCE(confidence, 0), 0.97),
                    updated_at = %s
                WHERE id = %s
                RETURNING id
                """,
                [
                    payload.category,
                    payload.essentiality,
                    updated_at,
                    transaction_id,
                ],
            ).fetchone()
            if payload.apply_to_merchant and merchant_id is not None:
                conn.execute(
                    """
                    UPDATE household_transactions
                    SET category = %s,
                        essentiality = %s,
                        confidence = GREATEST(COALESCE(confidence, 0), 0.97),
                        updated_at = %s
                    WHERE merchant_id = %s
                    """,
                    [
                        payload.category,
                        payload.essentiality,
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
