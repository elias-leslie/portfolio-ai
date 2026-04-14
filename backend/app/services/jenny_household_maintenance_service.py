"""Daily Jenny maintenance for household-money correctness."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.logging_config import get_logger
from app.models.household_finance import (
    HouseholdFinanceDashboard,
)
from app.services._jenny_review_notifications import (
    resolve_superseded_notifications,
    upsert_notification,
)

logger = get_logger(__name__)

_HOUSEHOLD_NOTIFICATION_PREFIX = "household_inbox:"
_REVIEW_LOOKBACK = timedelta(days=3)
_REVIEW_LIMIT = 24


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
        dashboard = service.household_service.get_dashboard()
        notification_count = self._sync_household_notifications(
            service,
            routine_id=routine_id,
            dashboard=dashboard,
        )
        summary = self._build_summary(dashboard, replay_stats, notification_count, registry_summary)
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
            "notifications_created": notification_count,
            "money_inbox_items": len(dashboard.inbox),
        }

    def _replay_candidate_documents(self, service: Any) -> dict[str, int]:
        cutoff = (datetime.now(UTC) - _REVIEW_LOOKBACK).isoformat()
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
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
            f"Net worth is {overview.net_worth_status}; monthly spend is {overview.monthly_spend_status}; "
            f"{len(dashboard.inbox)} money blockers on file and {notification_count} open Jenny household alerts."
        )
