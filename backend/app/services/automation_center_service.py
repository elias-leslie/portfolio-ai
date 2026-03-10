"""Automation guardrails and recent run summaries for the home page."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.automation_center import AutomationCenter, AutomationGuardrail, AutomationRecentRun
from app.rules.loader import get_rules
from app.storage import get_storage


class AutomationCenterService:
    """Expose current automation guardrails and recent runs."""

    def __init__(self) -> None:
        self.storage = get_storage()

    def get_center(self) -> dict[str, object]:
        rules = get_rules()
        recent_runs = self._recent_runs()
        warnings = self._warnings()
        center = AutomationCenter(
            generated_at=datetime.now(UTC).isoformat(),
            guardrails=[
                AutomationGuardrail(
                    key="thesis_generation_enabled",
                    label="Thesis generation",
                    value="Enabled" if rules.thesis_management.thesis_generation_enabled else "Disabled",
                    detail="Controls whether Jenny can auto-generate missing theses.",
                ),
                AutomationGuardrail(
                    key="auto_remove_on_invalidation",
                    label="Auto-remove invalidated theses",
                    value="Enabled" if rules.thesis_management.auto_remove_on_invalidation else "Disabled",
                    detail="Keeps broken theses from lingering in the active loop.",
                ),
                AutomationGuardrail(
                    key="auto_trim_enabled",
                    label="Watchlist auto-trim",
                    value="Enabled" if rules.watchlist_management.auto_trim_enabled else "Disabled",
                    detail="Controls whether weak watchlist names can be trimmed automatically.",
                ),
            ],
            recent_runs=recent_runs,
            warnings=warnings,
        )
        return center.model_dump(mode="json")

    def _recent_runs(self) -> list[AutomationRecentRun]:
        runs: list[AutomationRecentRun] = []
        with self.storage.connection() as conn:
            jenny_rows = conn.execute(
                """
                SELECT id, routine_type, status, triggered_by, started_at, completed_at,
                       symbols_scanned, notifications_created
                FROM jenny_routines
                ORDER BY started_at DESC
                LIMIT 3
                """
            ).fetchall()
            maintenance_rows = conn.execute(
                """
                SELECT id, task_name, status, started_at, completed_at
                FROM maintenance_log
                WHERE task_name IN ('check_all_data_freshness', 'daily_strategy_refresh', 'monitor_thesis_health')
                ORDER BY started_at DESC
                LIMIT 3
                """
            ).fetchall()

        for row in jenny_rows:
            runs.append(
                AutomationRecentRun(
                    id=str(row[0]),
                    label=f"Jenny {str(row[1]).replace('_', ' ')}",
                    status=str(row[2]),
                    triggered_by=str(row[3]),
                    started_at=row[4].isoformat(),
                    completed_at=row[5].isoformat() if row[5] is not None else None,
                    detail=(
                        f"Reviewed {int(row[6] or 0)} symbols and created {int(row[7] or 0)} notifications."
                    ),
                )
            )

        for row in maintenance_rows:
            runs.append(
                AutomationRecentRun(
                    id=f"maintenance-{row[0]}",
                    label=str(row[1]).replace("_", " "),
                    status=str(row[2]),
                    triggered_by="scheduled",
                    started_at=row[3].isoformat(),
                    completed_at=row[4].isoformat() if row[4] is not None else None,
                    detail="System maintenance and freshness checks.",
                )
            )

        runs.sort(key=lambda item: item.started_at, reverse=True)
        return runs[:5]

    def _warnings(self) -> list[str]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT task_name, status
                FROM maintenance_log
                WHERE status IN ('error', 'failed')
                ORDER BY started_at DESC
                LIMIT 3
                """
            ).fetchall()
        return [f"{str(row[0]).replace('_', ' ')} reported {row[1]}." for row in rows]
