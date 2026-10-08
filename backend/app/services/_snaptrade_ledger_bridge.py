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
- Foreign statement twins require the same account, amount, currency and
  compatible cash direction within 3 days; each absorbs one instance.
- Stable account/activity linkage keeps provider corrections on the same
  ledger row, preserving user classifications, audit metadata and removals.
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
    currency: str = "USD",
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
    # Preserve existing USD hashes while distinguishing foreign currencies.
    if currency != "USD":
        key += "|" + currency
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
                   sa.household_account_id, sa.name, act.last_synced_at
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

        groups: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
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
                last_synced_at,
            ) = row
            normalized = _normalize_description(str(description or ""))
            signed_amount = Decimal(str(amount))
            currency = str(currency or "USD").upper()
            key = (
                str(household_account_id),
                trade_date.date().isoformat(),
                str(signed_amount),
                str(activity_type),
                normalized,
                currency,
            )
            group = groups.setdefault(
                key,
                {
                    "trade_date": trade_date,
                    "settlement_date": settlement_date,
                    "signed_amount": signed_amount,
                    "currency": currency,
                    "description": normalized,
                    "activity_type": str(activity_type),
                    "household_account_id": str(household_account_id),
                    "account_name": str(account_name),
                    "last_synced_at": last_synced_at or _BRIDGE_START,
                    "per_account": {},
                    "activity_ids": [],
                },
            )
            group["per_account"].setdefault(str(vendor_account_id), [])
            group["per_account"][str(vendor_account_id)].append(str(activity_id))
            group["activity_ids"].append(str(activity_id))
            group["last_synced_at"] = max(group["last_synced_at"], last_synced_at or _BRIDGE_START)

        document_id: str | None = None
        now = datetime.now(UTC)
        allocated_foreign_ids: set[str] = set()
        allocated_bridge_ids: set[str] = set()
        # When connections disagree after a correction, the freshest observed
        # provider facts own the linked row; older aliases cannot revert them.
        for key, group in sorted(groups.items(), key=lambda item: (-item[1]["last_synced_at"].timestamp(), item[0])):
            per_account = {account: sorted(ids) for account, ids in group["per_account"].items()}
            raw_row_count = sum(len(ids) for ids in per_account.values())
            real_count = max(len(ids) for ids in per_account.values())
            counts["duplicate_collapsed"] += raw_row_count - real_count

            signed_amount = group["signed_amount"]
            abs_amount = abs(signed_amount)
            description = group["description"]
            household_account_id = group["household_account_id"]
            trade_date = group["trade_date"]
            day_start = datetime.combine(trade_date.date(), datetime.min.time(), tzinfo=UTC)
            category, essentiality = _classify_merchant(
                raw_merchant=description, description=description, amount=float(abs_amount)
            )
            flow_type, category, essentiality = _classify_statement_csv_flow(
                description=description, source_type="brokerage", signed_amount=signed_amount,
                category=category, essentiality=essentiality,
            )
            # Investment rows store absolute values with no cash direction.
            # They cannot prove a foreign twin, so do not suppress on that alone.
            compatible_flows = (
                ["income", "refund", "transfer_in"] if signed_amount > 0
                else ["expense", "payment", "transfer_out"]
            )
            twin_rows = conn.execute(
                """
                SELECT id
                FROM household_transactions
                WHERE household_account_id = %s
                  AND removed IS NOT TRUE
                  AND source_system <> 'snaptrade'
                  AND amount = %s
                  AND UPPER(COALESCE(currency, 'USD')) = %s
                  AND flow_type = ANY(%s)
                  AND transaction_date BETWEEN %s AND %s
                ORDER BY transaction_date, id
                """,
                [
                    household_account_id,
                    abs_amount,
                    group["currency"],
                    compatible_flows,
                    day_start - timedelta(days=_TWIN_SKEW_DAYS),
                    day_start + timedelta(days=_TWIN_SKEW_DAYS),
                ],
            ).fetchall()
            available_twins = [str(row[0]) for row in twin_rows if str(row[0]) not in allocated_foreign_ids]

            classified = False
            for occurrence in range(real_count):
                row_hash = _row_hash(
                    household_account_id=key[0],
                    trade_date=key[1],
                    amount=key[2],
                    activity_type=key[3],
                    description=key[4],
                    occurrence=occurrence,
                    currency=group["currency"],
                )
                activity_ids = [ids[occurrence] for ids in per_account.values() if occurrence < len(ids)]
                activity_refs = [
                    json.dumps([account, ids[occurrence]])
                    for account, ids in sorted(per_account.items()) if occurrence < len(ids)
                ]
                existing_rows = conn.execute(
                    """
                    SELECT id, row_hash, metadata
                    FROM household_transactions
                    WHERE household_account_id = %s
                      AND source_system = 'snaptrade'
                      AND (row_hash = %s
                           OR jsonb_exists_any(metadata->'snaptrade_activity_refs', %s::text[])
                           OR (NOT jsonb_exists(COALESCE(metadata, '{}'::jsonb), 'snaptrade_activity_refs')
                               AND (jsonb_exists_any(metadata->'snaptrade_activity_ids', %s::text[])
                                    OR external_transaction_id = ANY(%s))))
                    ORDER BY (row_hash = %s) DESC, metadata->>'occurrence', id
                    """,
                    [household_account_id, row_hash, activity_refs, activity_ids, activity_ids, row_hash],
                ).fetchall()
                # A corrected legacy row retains its original natural hash.
                # That hash cannot claim a new event with disjoint stable IDs.
                existing_rows = [
                    row for row in existing_rows
                    if not isinstance(row[2], dict)
                    or (
                        set(row[2]["snaptrade_activity_refs"]) & set(activity_refs)
                        if "snaptrade_activity_refs" in row[2]
                        else "snaptrade_activity_ids" not in row[2]
                        or set(row[2]["snaptrade_activity_ids"]) & set(activity_ids)
                    )
                ]
                # An amount/date correction can collide with another event's
                # natural hash. Prefer proven stable linkage over that hash.
                linked_rows = [
                    row for row in existing_rows
                    if isinstance(row[2], dict)
                    and (
                        set(row[2].get("snaptrade_activity_refs", [])) & set(activity_refs)
                        or ("snaptrade_activity_refs" not in row[2]
                            and set(row[2].get("snaptrade_activity_ids", [])) & set(activity_ids))
                    )
                ]
                candidates = linked_rows or existing_rows
                exists = next((row for row in candidates if str(row[0]) not in allocated_bridge_ids), None)
                if exists is not None:
                    allocated_bridge_ids.add(str(exists[0]))
                    old_metadata = exists[2] if isinstance(exists[2], dict) else {}
                    linkage = {
                        "snaptrade_activity_refs": sorted(set(old_metadata.get("snaptrade_activity_refs", [])) | set(activity_refs)),
                        "snaptrade_activity_ids": sorted(set(old_metadata.get("snaptrade_activity_ids", [])) | set(activity_ids)),
                    }
                    conn.execute(
                        """
                        UPDATE household_transactions
                        SET transaction_date = %s, posted_date = %s,
                            amount = %s, currency = %s, description = %s, raw_merchant = %s,
                            flow_type = CASE
                                WHEN categorization_source IN ('manual', 'manual_rule', 'merchant_rule', 'transaction_audit', 'transaction_audit_agent')
                                  OR jsonb_exists(metadata, 'audit') THEN flow_type ELSE %s END,
                            category = CASE
                                WHEN categorization_source IN ('manual', 'manual_rule', 'merchant_rule', 'transaction_audit', 'transaction_audit_agent')
                                  OR jsonb_exists(metadata, 'audit') THEN category ELSE %s END,
                            essentiality = CASE
                                WHEN categorization_source IN ('manual', 'manual_rule', 'merchant_rule', 'transaction_audit', 'transaction_audit_agent')
                                  OR jsonb_exists(metadata, 'audit') THEN essentiality ELSE %s END,
                            metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                            updated_at = %s
                        WHERE id = %s AND source_system = 'snaptrade'
                        """,
                        [day_start, group["settlement_date"], abs_amount, group["currency"],
                         description, description, flow_type, category, essentiality,
                         json.dumps(linkage), now, str(exists[0])],
                    )
                    counts["already_bridged"] += 1
                    continue
                if existing_rows:
                    # Two connections can report a correction at different
                    # times and split one linked event into two natural groups.
                    counts["duplicate_collapsed"] += 1
                    continue
                if available_twins:
                    allocated_foreign_ids.add(available_twins.pop(0))
                    counts["twin_skipped"] += 1
                    continue

                if not classified:
                    (
                        merchant_id,
                        _canonical_name,
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
                # New rows use provider identity, so another event can safely
                # occupy a corrected row's historical natural key.
                insertion_hash = hashlib.sha256(
                    json.dumps(["snaptrade_activity", household_account_id, min(activity_refs)]).encode()
                ).hexdigest()
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
                        insertion_hash,
                        day_start,
                        settlement,
                        description,
                        description,
                        group["account_name"],
                        abs_amount,
                        group["currency"],
                        flow_type,
                        category,
                        essentiality,
                        json.dumps(
                            {
                                "snaptrade_activity_ids": sorted(activity_ids),
                                "snaptrade_activity_refs": activity_refs,
                                "occurrence": occurrence,
                                "source": "snaptrade_activity_bridge",
                            }
                        ),
                        sorted(activity_ids)[0],
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
