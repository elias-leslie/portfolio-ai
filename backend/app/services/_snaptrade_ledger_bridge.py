"""Bridge SnapTrade cash-management activities into the household ledger.

The Fidelity Cash Management account is the household's checking
replacement: payroll direct deposits, bill-pay debits, and money-market
dividends all land there. SnapTrade syncs those events into
``snaptrade_activities`` (raw vendor table); this module mirrors the cash
ones into ``household_transactions`` so Money reports and the retirement
income card stay current without manual CSV exports.

Scope and safeguards:
- Cash Management accounts only (``name ILIKE 'cash management%'``) with a
  household account mapping — IRA/TOD internal activity is investment
  churn, not household cash flow.
- ``CONTRIBUTION``/``WITHDRAWAL``/``DIVIDEND`` activity types only; buys,
  sells, and reinvestments stay out of the spending ledger.
- Activities from 2026-01 onward (the ledger's existing coverage start);
  bridging earlier history would silently rewrite audited Money baselines.
- The same underlying account synced under two SnapTrade connections
  yields duplicate activity rows with distinct activity ids. Real
  multiplicity within a natural-key group is the per-connection maximum,
  not the total (two connections x two real PayPal micro-deposits = four
  raw rows = two ledger rows).
- Rows the ledger already carries from another source (statement CSV /
  bank statement) are twins, not new events: same household account, same
  absolute amount, within 3 days. Each existing foreign row absorbs one
  activity instance. The bridge defers to foreign rows present at insert
  time; rows it already wrote are never re-inserted (stable natural-key
  row_hash), so user audits and removals stick.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.logging_config import get_logger
from app.services._household_merchants import _classify_merchant
from app.services._household_transaction_parsers import _classify_statement_csv_flow
from app.services.household_transaction_service import HouseholdTransactionService
from app.storage import PortfolioStorage, get_storage

logger = get_logger(__name__)

_BRIDGED_ACTIVITY_TYPES = ["CONTRIBUTION", "WITHDRAWAL", "DIVIDEND"]
_BRIDGE_START = datetime(2026, 1, 1, tzinfo=UTC)
_TWIN_SKEW_DAYS = 3


def _normalize_description(description: str) -> str:
    return re.sub(r"\s+", " ", description or "").strip()


def _row_hash(
    *,
    household_account_id: str,
    trade_date: str,
    amount: str,
    activity_type: str,
    description: str,
    occurrence: int,
) -> str:
    key = "|".join(
        [
            "snaptrade",
            household_account_id,
            trade_date,
            amount,
            activity_type,
            description,
            str(occurrence),
        ]
    )
    return hashlib.sha256(key.encode()).hexdigest()


def _ensure_bridge_document(conn: Any) -> str:
    now = datetime.now(UTC)
    metadata = {"source": "snaptrade", "surface": "activity_bridge"}
    existing = conn.execute(
        """
        SELECT id
        FROM household_documents
        WHERE source_type = 'snaptrade'
          AND document_type = 'api_sync'
        ORDER BY uploaded_at DESC
        LIMIT 1
        """
    ).fetchone()
    if existing is not None:
        document_id = str(existing[0])
        conn.execute(
            """
            UPDATE household_documents
            SET status = 'parsed',
                review_status = 'complete',
                parsed_at = %s
            WHERE id = %s
            """,
            [now, document_id],
        )
        return document_id
    document_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO household_documents (
            id, filename, stored_path, source_type, document_type, status,
            account_label, content_type, file_size_bytes,
            classification_confidence, uploaded_at, parsed_at, metadata,
            review_status, review_summary, review_confidence
        ) VALUES (
            %s, %s, %s, 'snaptrade', 'api_sync', 'parsed',
            %s, 'application/json', 0,
            1.0, %s, %s, %s::jsonb,
            'complete', %s, 1.0
        )
        """,
        [
            document_id,
            "SnapTrade - cash activity sync",
            "snaptrade://activities",
            "Cash Management",
            now,
            now,
            json.dumps(metadata),
            "SnapTrade cash-management activity bridge.",
        ],
    )
    return document_id


def bridge_cash_activities(
    storage: PortfolioStorage | None = None,
    transaction_service: HouseholdTransactionService | None = None,
) -> dict[str, int]:
    """Mirror cash-management activities into household_transactions."""

    storage = storage or get_storage()
    transaction_service = transaction_service or HouseholdTransactionService()
    counts = {
        "bridged": 0,
        "already_bridged": 0,
        "twin_skipped": 0,
        "duplicate_collapsed": 0,
    }
    with storage.connection() as conn:
        rows = conn.execute(
            """
            SELECT act.account_id, act.activity_id, act.activity_type,
                   act.trade_date, act.settlement_date, act.amount,
                   act.currency, act.description,
                   sa.household_account_id, sa.name
            FROM snaptrade_activities act
            JOIN snaptrade_accounts sa ON sa.account_id = act.account_id
            WHERE LOWER(sa.name) LIKE 'cash management%%'
              AND sa.household_account_id IS NOT NULL
              AND act.activity_type = ANY(%s)
              AND act.trade_date >= %s
              AND act.amount IS NOT NULL
              AND act.amount <> 0
            ORDER BY act.trade_date, act.activity_id
            """,
            [_BRIDGED_ACTIVITY_TYPES, _BRIDGE_START],
        ).fetchall()
        if not rows:
            return counts

        groups: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
        for row in rows:
            (
                vendor_account_id,
                activity_id,
                activity_type,
                trade_date,
                settlement_date,
                amount,
                currency,
                description,
                household_account_id,
                account_name,
            ) = row
            normalized = _normalize_description(str(description or ""))
            signed_amount = Decimal(str(amount))
            key = (
                str(household_account_id),
                trade_date.date().isoformat(),
                str(signed_amount),
                str(activity_type),
                normalized,
            )
            group = groups.setdefault(
                key,
                {
                    "trade_date": trade_date,
                    "settlement_date": settlement_date,
                    "signed_amount": signed_amount,
                    "currency": str(currency or "USD"),
                    "description": normalized,
                    "activity_type": str(activity_type),
                    "household_account_id": str(household_account_id),
                    "account_name": str(account_name),
                    "per_account": {},
                    "activity_ids": [],
                },
            )
            group["per_account"].setdefault(str(vendor_account_id), 0)
            group["per_account"][str(vendor_account_id)] += 1
            group["activity_ids"].append(str(activity_id))

        document_id: str | None = None
        now = datetime.now(UTC)
        for key, group in sorted(groups.items()):
            raw_row_count = sum(group["per_account"].values())
            real_count = max(group["per_account"].values())
            counts["duplicate_collapsed"] += raw_row_count - real_count

            signed_amount = group["signed_amount"]
            abs_amount = abs(signed_amount)
            description = group["description"]
            household_account_id = group["household_account_id"]
            trade_date = group["trade_date"]
            day_start = datetime.combine(trade_date.date(), datetime.min.time(), tzinfo=UTC)
            twin_row = conn.execute(
                """
                SELECT COUNT(*)
                FROM household_transactions
                WHERE household_account_id = %s
                  AND removed IS NOT TRUE
                  AND source_system <> 'snaptrade'
                  AND amount = %s
                  AND transaction_date BETWEEN %s AND %s
                """,
                [
                    household_account_id,
                    abs_amount,
                    day_start - timedelta(days=_TWIN_SKEW_DAYS),
                    day_start + timedelta(days=_TWIN_SKEW_DAYS),
                ],
            ).fetchone()
            twin_count = int(twin_row[0]) if twin_row else 0

            classified = False
            for occurrence in range(real_count):
                row_hash = _row_hash(
                    household_account_id=key[0],
                    trade_date=key[1],
                    amount=key[2],
                    activity_type=key[3],
                    description=key[4],
                    occurrence=occurrence,
                )
                exists = conn.execute(
                    "SELECT 1 FROM household_transactions WHERE row_hash = %s",
                    [row_hash],
                ).fetchone()
                if exists is not None:
                    counts["already_bridged"] += 1
                    continue
                if occurrence < twin_count:
                    counts["twin_skipped"] += 1
                    continue

                if not classified:
                    category, essentiality = _classify_merchant(
                        raw_merchant=description,
                        description=description,
                        amount=float(abs_amount),
                    )
                    flow_type, category, essentiality = _classify_statement_csv_flow(
                        description=description,
                        source_type="brokerage",
                        signed_amount=signed_amount,
                        category=category,
                        essentiality=essentiality,
                    )
                    (
                        merchant_id,
                        canonical_name,
                        category,
                        essentiality,
                        has_manual_rule,
                        rule_id,
                    ) = transaction_service._resolve_merchant(
                        conn=conn,
                        raw_merchant=description,
                        category=category,
                        essentiality=essentiality,
                    )
                    categorization_source = "merchant_rule" if has_manual_rule else "snaptrade"
                    classified = True
                if document_id is None:
                    document_id = _ensure_bridge_document(conn)

                settlement = group["settlement_date"]
                conn.execute(
                    """
                    INSERT INTO household_transactions (
                        id, document_id, household_account_id, merchant_id, row_hash,
                        transaction_date, posted_date, description, raw_merchant,
                        account_label, amount, currency, flow_type, category,
                        essentiality, confidence, metadata, source_system,
                        external_transaction_id, original_category,
                        categorization_source, categorization_version,
                        category_updated_at, category_updated_by,
                        transaction_rule_id, pending, removed, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        1.0, %s::jsonb, 'snaptrade', %s, %s, %s, %s, %s, %s, %s,
                        FALSE, FALSE, %s, %s
                    )
                    ON CONFLICT (row_hash) DO NOTHING
                    """,
                    [
                        str(uuid.uuid4()),
                        document_id,
                        household_account_id,
                        merchant_id,
                        row_hash,
                        day_start,
                        settlement,
                        description,
                        canonical_name,
                        group["account_name"],
                        abs_amount,
                        group["currency"],
                        flow_type,
                        category,
                        essentiality,
                        json.dumps(
                            {
                                "snaptrade_activity_ids": sorted(group["activity_ids"]),
                                "occurrence": occurrence,
                                "source": "snaptrade_activity_bridge",
                            }
                        ),
                        sorted(group["activity_ids"])[0],
                        group["activity_type"],
                        categorization_source,
                        "2026-05-canonical",
                        now,
                        categorization_source,
                        rule_id,
                        now,
                        now,
                    ],
                )
                counts["bridged"] += 1
        conn.commit()
    if counts["bridged"]:
        logger.info("snaptrade_ledger_bridge", **counts)
    return counts
