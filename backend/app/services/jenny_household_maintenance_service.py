"""Daily Jenny maintenance for household-money correctness."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.logging_config import get_logger
from app.models.household_finance import (
    HouseholdFinanceDashboard,
)
from app.services._household_document_pipeline_db import update_document_application_summary
from app.services._jenny_review_notifications import (
    resolve_superseded_notifications,
    upsert_notification,
)

logger = get_logger(__name__)

_HOUSEHOLD_NOTIFICATION_PREFIX = "household_inbox:"
_REVIEW_LOOKBACK = timedelta(days=3)
_REVIEW_LIMIT = 24
_SUSPICIOUS_TRANSACTION_REPLAY_SQL = """
                           OR EXISTS (
                                SELECT 1
                                FROM household_transactions tx
                                WHERE tx.document_id = household_documents.id
                                  AND (
                                        (
                                            COALESCE(tx.metadata->>'source', '') = 'receipt_summary'
                                            AND COALESCE(household_documents.source_type, '') <> 'receipt'
                                        )
                                     OR tx.transaction_date::date > CURRENT_DATE
                                     OR (
                                            tx.flow_type = 'expense'
                                            AND (
                                                lower(tx.description) LIKE '%%credit crd epay%%'
                                             OR lower(tx.description) LIKE '%%inst xfer%%'
                                             OR lower(tx.description) LIKE '%%moneyline%%'
                                             OR lower(tx.description) LIKE '%%zelle from%%'
                                             OR lower(tx.description) LIKE '%%zelle to%%'
                                             OR lower(tx.description) LIKE '%%ui benefit%%'
                                             OR lower(tx.description) LIKE '%%payroll%%'
                                             OR lower(tx.description) LIKE '%%payables%%'
                                             OR lower(tx.description) LIKE '%%salary%%'
                                             OR lower(tx.description) LIKE '%%atm withdrawal%%'
                                             OR lower(tx.description) LIKE '%%transfer from%%'
                                             OR lower(tx.description) LIKE '%%transfer to%%'
                                             OR lower(tx.description) LIKE '%%online transfer%%'
                                             OR lower(tx.description) LIKE '%%recurring transfer%%'
                                        )
                                     )
                                  )
                           )
"""


def _priority_to_severity(priority: str) -> str:
    normalized = priority.strip().lower()
    if normalized == "high":
        return "critical"
    if normalized == "medium":
        return "warning"
    return "info"


class JennyHouseholdMaintenanceService:
    """Replay weak money evidence and sync the money inbox into Jenny."""

    def run_daily_maintenance_pass(self, service: Any, *, routine_id: str) -> dict[str, Any]:
        registry_summary = service.household_service.account_registry_service.sync_registry(
            service.household_service,
            limit=1000,
        )
        replay_stats = self._replay_candidate_documents(service)
        audit_summary = service.household_service.transaction_audit_service.audit_transactions(
            service.household_service,
            limit=240,
        )
        dashboard = service.household_service.get_dashboard()
        notification_count = self._sync_household_notifications(
            service,
            routine_id=routine_id,
            dashboard=dashboard,
        )
        summary = self._build_summary(
            dashboard,
            replay_stats,
            notification_count,
            registry_summary,
            audit_summary,
        )
        return {
            "summary": summary,
            "linked_accounts_synced": int(registry_summary.get("tracked_linked", 0)),
            "canonical_accounts_created": int(registry_summary.get("accounts_created", 0)),
            "canonical_accounts_merged": int(registry_summary.get("accounts_merged", 0)),
            "evidence_accounts_linked": int(registry_summary.get("evidence_linked", 0)),
            "transactions_linked": int(registry_summary.get("transaction_linked", 0)),
            "documents_reviewed": replay_stats["attempted"],
            "documents_recovered": replay_stats["recovered"],
            "missing_sources": replay_stats["missing_source"],
            "transactions_audited": int(audit_summary.get("reviewed") or 0),
            "transactions_auto_fixed": int(audit_summary.get("auto_fixed") or 0),
            "transactions_agent_fixed": int(audit_summary.get("agent_fixed") or 0),
            "transactions_flagged": int(audit_summary.get("flagged") or 0),
            "notifications_created": notification_count,
            "money_inbox_items": len(dashboard.inbox),
        }

    def _replay_candidate_documents(self, service: Any) -> dict[str, int]:
        cutoff = (datetime.now(UTC) - _REVIEW_LOOKBACK).isoformat()
        with service.storage.connection() as conn:
            rows = conn.execute(
                f"""
                SELECT id, metadata->>'stored_path' AS stored_path, status, review_status
                FROM household_documents
                WHERE status IN ('staged', 'needs_review')
                   OR COALESCE(review_status, '') IN ('needs_review', 'failed')
                   OR (
                        source_type IN ('bank', 'credit_card', 'brokerage', 'retirement')
                        AND (
                            review_confidence IS NULL
                           OR review_confidence < 0.95
                           OR source_type = 'other'
                           OR document_type = 'other'
                           OR (
                                metadata->'structured_data'->'financial_accounts' IS NULL
                                OR jsonb_typeof(metadata->'structured_data'->'financial_accounts') <> 'array'
                                OR jsonb_array_length(
                                    CASE
                                        WHEN jsonb_typeof(metadata->'structured_data'->'financial_accounts') = 'array'
                                        THEN metadata->'structured_data'->'financial_accounts'
                                        ELSE '[]'::jsonb
                                    END
                                ) = 0
                           )
                           OR COALESCE(metadata->'application_summary'->>'status', '') <> 'applied'
                           OR COALESCE((metadata->'application_summary'->>'needs_follow_up')::boolean, false)
                           OR COALESCE(metadata->'reconciliation_summary'->>'status', '') = ''
                           OR COALESCE(metadata->'reconciliation_summary'->>'status', '') = 'needs_retry'
                           {_SUSPICIOUS_TRANSACTION_REPLAY_SQL}
                        )
                   )
                   OR (
                        uploaded_at >= %s
                        AND (
                            review_confidence IS NULL
                           OR review_confidence < 0.95
                           OR source_type = 'other'
                           OR document_type = 'other'
                           OR (
                                source_type IN ('bank', 'credit_card', 'brokerage', 'retirement')
                                AND (
                                    metadata->'structured_data'->'financial_accounts' IS NULL
                                    OR jsonb_typeof(metadata->'structured_data'->'financial_accounts') <> 'array'
                                    OR jsonb_array_length(
                                        CASE
                                            WHEN jsonb_typeof(metadata->'structured_data'->'financial_accounts') = 'array'
                                            THEN metadata->'structured_data'->'financial_accounts'
                                            ELSE '[]'::jsonb
                                        END
                                    ) = 0
                                )
                           )
                           OR COALESCE(metadata->'application_summary'->>'status', '') <> 'applied'
                           OR COALESCE((metadata->'application_summary'->>'needs_follow_up')::boolean, false)
                           OR COALESCE(metadata->'reconciliation_summary'->>'status', '') = ''
                           OR COALESCE(metadata->'reconciliation_summary'->>'status', '') = 'needs_retry'
                           {_SUSPICIOUS_TRANSACTION_REPLAY_SQL}
                        )
                   )
                ORDER BY uploaded_at DESC
                LIMIT %s
                """,
                [cutoff, _REVIEW_LIMIT],
            ).fetchall()

        attempted = 0
        recovered = 0
        missing_source = 0
        unresolved = 0

        for document_id, stored_path, prior_status, prior_review_status in rows:
            path = Path(str(stored_path)) if stored_path else None
            if path is None or not path.exists():
                if self._recover_document_without_source(service, str(document_id)):
                    recovered += 1
                    continue
                missing_source += 1
                continue
            attempted += 1
            service.household_service.review_document(str(document_id))
            reviewed = service.household_service.get_document(str(document_id))
            if reviewed is None:
                unresolved += 1
                continue
            if reviewed.status == "parsed" and reviewed.review_status == "complete":
                if prior_status != "parsed" or prior_review_status != "complete":
                    recovered += 1
                continue
            unresolved += 1

        return {
            "attempted": attempted,
            "recovered": recovered,
            "missing_source": missing_source,
            "unresolved": unresolved,
        }

    def _recover_document_without_source(self, service: Any, document_id: str) -> bool:
        service.household_service.review_document(document_id)
        document = service.household_service.get_document(document_id)
        if document is None:
            return False
        summary = service.household_service.document_pipeline.describe_application_state(
            service.household_service,
            document=document,
        )
        if str(summary.get("status") or "") != "applied":
            return False
        with service.storage.connection() as conn:
            update_document_application_summary(
                conn,
                document_id=document_id,
                application_summary=summary,
                reconciliation_summary={
                    "status": "clear",
                    "retry_recommended": False,
                    "review_strategy": "recovered_without_source",
                    "expected_account_count": 0,
                    "evidence_account_count": int(summary.get("evidence_accounts") or 0),
                    "transaction_changes": int(
                        (
                            summary.get("transactions")
                            if isinstance(summary.get("transactions"), dict)
                            else {}
                        ).get("inserted")
                        or 0
                    ) + int(
                        (
                            summary.get("transactions")
                            if isinstance(summary.get("transactions"), dict)
                            else {}
                        ).get("updated")
                        or 0
                    ),
                    "import_changes": int(
                        (
                            summary.get("imports")
                            if isinstance(summary.get("imports"), dict)
                            else {}
                        ).get("inserted")
                        or 0
                    ),
                    "ambiguity_remaining": False,
                    "issues": [],
                },
            )
            conn.commit()
        return True

    def _sync_household_notifications(
        self,
        service: Any,
        *,
        routine_id: str,
        dashboard: HouseholdFinanceDashboard,
    ) -> int:
        active_categories: set[str] = set()
        count = 0
        for item in dashboard.inbox[:10]:
            if item.priority not in {"high", "medium"}:
                continue
            category = f"{_HOUSEHOLD_NOTIFICATION_PREFIX}{item.id}"
            active_categories.add(category)
            upsert_notification(
                service,
                routine_id,
                None,
                category=category,
                severity=_priority_to_severity(item.priority),
                title=item.title,
                detail=item.detail,
                recommendation=item.action_label,
            )
            count += 1
        resolve_superseded_notifications(service, None, active_categories=active_categories)
        return count

    @staticmethod
    def _build_summary(
        dashboard: HouseholdFinanceDashboard,
        replay_stats: dict[str, int],
        notification_count: int,
        registry_summary: dict[str, int],
        audit_summary: dict[str, int],
    ) -> str:
        overview = dashboard.overview
        return (
            f"Registry created {registry_summary.get('accounts_created', 0)} account(s), "
            f"merged {registry_summary.get('accounts_merged', 0)}, "
            f"linked {registry_summary.get('evidence_linked', 0)} evidence row(s), "
            f"{registry_summary.get('transaction_linked', 0)} transaction row(s), "
            f"and {registry_summary.get('tracked_linked', 0)} tracked customization row(s). "
            f"Replayed {replay_stats['attempted']} household documents "
            f"({replay_stats['recovered']} recovered, {replay_stats['missing_source']} missing source). "
            f"Audited {audit_summary.get('reviewed', 0)} transaction row(s) "
            f"({audit_summary.get('auto_fixed', 0)} deterministic, {audit_summary.get('agent_fixed', 0)} agent fixed, "
            f"{audit_summary.get('flagged', 0)} flagged). "
            f"Net worth is {overview.net_worth_status}; monthly spend is {overview.monthly_spend_status}; "
            f"{len(dashboard.inbox)} money blockers on file and {notification_count} open Jenny household alerts."
        )
