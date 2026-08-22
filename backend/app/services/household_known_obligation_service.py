"""Seed obligations the household knows about but no feed ever saw.

Every automated feed here has a start date. The oldest begins in December 2025
and the live ones in February 2026, so an annual bill paid before that -- a
property tax due in November, a premium renewed in autumn -- exists for the
household and not for the app.

That gap is not cosmetic. Sinking-fund contributions are derived by averaging a
category's trailing twelve months, so a missing annual obligation does not
merely fail to appear: it drags the fund's monthly target down by a twelfth of
itself, every month, and the shortfall only surfaces when the bill lands.

Seeded rows are ordinary transactions with an explicit ``manual_entry``
provenance, so they count toward history exactly like an ingested row while
remaining distinguishable from one -- and removable by the same means, since a
seeded obligation is a claim about the past that may later be corrected by a
real document.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from typing import Any

from app.logging_config import get_logger

logger = get_logger(__name__)

_SEED_SOURCE_SYSTEM = "manual_entry"
_SEED_DOCUMENT_LABEL = "Known obligations predating the feeds"


def _now() -> datetime:
    return datetime.now(UTC)


class HouseholdKnownObligationService:
    """Record and list obligations seeded by hand rather than ingested."""

    def _seed_document_id(self, conn: Any) -> str:
        """One shared document row for every seeded obligation.

        Transactions require a document, and minting a fake statement per
        obligation would put rows into the intake surfaces that no one can
        review. A single labelled container keeps provenance honest and keeps
        the document list truthful about what was actually uploaded.
        """
        existing = conn.execute(
            """
            SELECT id FROM household_documents
            WHERE source_type = %s AND document_type = 'manual_entry'
            ORDER BY uploaded_at ASC
            LIMIT 1
            """,
            [_SEED_SOURCE_SYSTEM],
        ).fetchone()
        if existing is not None:
            return str(existing[0])

        document_id = str(uuid.uuid4())
        now = _now()
        conn.execute(
            """
            INSERT INTO household_documents (
                id, filename, stored_path, source_type, document_type, status,
                account_label, content_type, file_size_bytes,
                classification_confidence, uploaded_at, parsed_at, metadata,
                review_status, review_summary, review_confidence
            ) VALUES (
                %s, %s, %s, %s, 'manual_entry', 'parsed',
                %s, 'application/json', 0,
                1.0, %s, %s, %s::jsonb,
                'complete', %s, 1.0
            )
            """,
            [
                document_id,
                _SEED_DOCUMENT_LABEL,
                "manual://known-obligations",
                _SEED_SOURCE_SYSTEM,
                "Manual entries",
                now,
                now,
                json.dumps({"source": "known_obligation_seed"}),
                "Obligations recorded by hand because they predate every feed.",
            ],
        )
        return document_id

    def seed_obligation(
        self,
        service: Any,
        *,
        description: str,
        amount: float,
        paid_on: date,
        category: str,
        essentiality: str = "essential",
        household_account_id: str | None = None,
        merchant: str | None = None,
        note: str | None = None,
    ) -> dict[str, object]:
        """Record one known past payment, refusing to record it twice.

        Idempotent on (description, amount, date): re-running a seeding script
        must not quietly double an annual bill, which would inflate the very
        sinking-fund target it exists to correct.
        """
        if amount <= 0:
            raise ValueError("a seeded obligation must have a positive amount")

        moment = datetime.combine(paid_on, datetime.min.time(), tzinfo=UTC)
        with service.storage.connection() as conn:
            duplicate = conn.execute(
                """
                SELECT id FROM household_transactions
                WHERE source_system = %s
                  AND transaction_date = %s
                  AND amount = %s
                  AND description = %s
                LIMIT 1
                """,
                [_SEED_SOURCE_SYSTEM, moment, amount, description],
            ).fetchone()
            if duplicate is not None:
                return {"transaction_id": str(duplicate[0]), "created": False}

            document_id = self._seed_document_id(conn)
            transaction_id = str(uuid.uuid4())
            now = _now()
            conn.execute(
                """
                INSERT INTO household_transactions (
                    id, document_id, household_account_id, row_hash,
                    transaction_date, description, raw_merchant, account_label,
                    amount, currency, flow_type, category, essentiality,
                    confidence, metadata, source_system, categorization_source,
                    pending, removed, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, 'USD', 'expense', %s, %s,
                    1.0, %s::jsonb, %s, 'manual',
                    FALSE, FALSE, %s, %s
                )
                """,
                [
                    transaction_id,
                    document_id,
                    household_account_id,
                    f"manual-obligation:{uuid.uuid4()}",
                    moment,
                    description,
                    merchant or description,
                    "Manual entries",
                    amount,
                    category,
                    essentiality,
                    json.dumps(
                        {
                            "known_obligation": {
                                "seeded_at": now.isoformat(),
                                "note": note,
                            }
                        }
                    ),
                    _SEED_SOURCE_SYSTEM,
                    now,
                    now,
                ],
            )
            conn.commit()
        logger.info(
            "household_known_obligation_seeded",
            amount=amount,
            category=category,
            paid_on=paid_on.isoformat(),
        )
        return {"transaction_id": transaction_id, "created": True}

    def list_obligations(self, service: Any) -> list[dict[str, object]]:
        """Every hand-seeded obligation, so the set stays auditable."""
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, transaction_date::date, description, amount, category,
                       essentiality, removed, metadata->'known_obligation'->>'note'
                FROM household_transactions
                WHERE source_system = %s
                ORDER BY transaction_date
                """,
                [_SEED_SOURCE_SYSTEM],
            ).fetchall()
        return [
            {
                "id": str(row[0]),
                "paid_on": row[1].isoformat(),
                "description": row[2],
                "amount": float(row[3]),
                "category": row[4],
                "essentiality": row[5],
                "removed": bool(row[6]),
                "note": row[7],
            }
            for row in rows
        ]

    def remove_obligation(self, service: Any, *, transaction_id: str) -> dict[str, object]:
        """Retract a seeded obligation, typically once a real document supersedes it."""
        with service.storage.connection() as conn:
            removed = conn.execute(
                """
                UPDATE household_transactions
                SET removed = TRUE, updated_at = %s
                WHERE id = %s AND source_system = %s
                RETURNING id
                """,
                [_now(), transaction_id, _SEED_SOURCE_SYSTEM],
            ).fetchall()
            if not removed:
                raise ValueError(f"no seeded obligation with id {transaction_id!r}")
            conn.commit()
        return {"transaction_id": transaction_id, "removed": True}
