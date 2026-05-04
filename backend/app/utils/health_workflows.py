"""Workflow health checks for autonomous trading workflows."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)

SCHEDULED_MAINTENANCE_WORKFLOW_TASKS = (
    "check_all_data_freshness",
    "maintain_data_freshness",
)


class WorkflowHealthInfo(BaseModel):
    """Workflow health status information."""

    status: Literal["healthy", "warning", "critical"]
    total_workflows_24h: int
    successful_workflows: int
    failed_workflows: int
    blocked_workflows: int
    success_rate: float
    avg_duration_s: int | None = None
    last_successful_workflow: datetime | None = None
    last_successful_type: str | None = None
    failures_by_type: dict[str, int]
    blocked_by_type: dict[str, int]


def _query_workflow_health_data(storage: PortfolioStorage) -> tuple[object, object, object, object]:
    """Run all DB queries needed for workflow health and return raw results."""
    with storage.connection() as conn:
        result = conn.execute(
            """
            WITH workflow_rows AS (
                SELECT workflow_type, status
                FROM agent_workflows
                WHERE created_at > NOW() - INTERVAL '24 hours'
                  AND status IN ('complete', 'failed', 'blocked')
                UNION ALL
                SELECT
                    task_name AS workflow_type,
                    CASE status
                        WHEN 'success' THEN 'complete'
                        WHEN 'error' THEN 'failed'
                        ELSE status
                    END AS status
                FROM maintenance_log
                WHERE started_at > NOW() - INTERVAL '24 hours'
                  AND task_name IN ('check_all_data_freshness', 'maintain_data_freshness')
                  AND status IN ('success', 'error', 'blocked')
            )
            SELECT workflow_type, status, COUNT(*) as count
            FROM workflow_rows
            GROUP BY workflow_type, status
            """
        ).pl()

        total_result = conn.execute(
            """
            SELECT SUM(count) AS total
            FROM (
                SELECT COUNT(*) AS count
                FROM agent_workflows
                WHERE created_at > NOW() - INTERVAL '24 hours'
                UNION ALL
                SELECT COUNT(*) AS count
                FROM maintenance_log
                WHERE started_at > NOW() - INTERVAL '24 hours'
                  AND task_name IN ('check_all_data_freshness', 'maintain_data_freshness')
            ) totals
            """
        ).pl()

        last_success = conn.execute(
            """
            SELECT id, workflow_type, completed_at
            FROM (
                SELECT id::text AS id, workflow_type, completed_at
                FROM agent_workflows
                WHERE status = 'complete' AND completed_at IS NOT NULL
                UNION ALL
                SELECT id::text AS id, task_name AS workflow_type, completed_at
                FROM maintenance_log
                WHERE status = 'success'
                  AND completed_at IS NOT NULL
                  AND task_name IN ('check_all_data_freshness', 'maintain_data_freshness')
            ) successful_workflows
            ORDER BY completed_at DESC
            LIMIT 1
            """
        ).pl()

        stale_running = conn.execute(
            """
            WITH stale_rows AS (
                SELECT workflow_type
                FROM agent_workflows
                WHERE created_at > NOW() - INTERVAL '24 hours'
                  AND status = 'running'
                  AND created_at < NOW() - make_interval(secs => COALESCE(max_duration_seconds, 3600))
                UNION ALL
                SELECT task_name AS workflow_type
                FROM maintenance_log
                WHERE started_at > NOW() - INTERVAL '24 hours'
                  AND status = 'running'
                  AND started_at < NOW() - INTERVAL '2 hours'
                  AND task_name IN ('check_all_data_freshness', 'maintain_data_freshness')
            )
            SELECT workflow_type, COUNT(*) as count
            FROM stale_rows
            GROUP BY workflow_type
            """
        ).pl()

    return result, total_result, last_success, stale_running


def _aggregate_workflow_stats(
    result: object,
) -> tuple[dict[str, dict[str, int]], dict[str, int], dict[str, int]]:
    """Aggregate per-type counts from the grouped query result."""
    stats: dict[str, dict[str, int]] = {}
    failures_by_type: dict[str, int] = {}
    blocked_by_type: dict[str, int] = {}

    if result.is_empty():
        return stats, failures_by_type, blocked_by_type

    for row in result.iter_rows(named=True):
        wtype = row["workflow_type"]
        status = row["status"]
        count = row["count"]

        if wtype not in stats:
            stats[wtype] = {"complete": 0, "failed": 0, "blocked": 0}
        stats[wtype][status] = count

        if status == "failed":
            failures_by_type[wtype] = count
        elif status == "blocked":
            blocked_by_type[wtype] = count

    return stats, failures_by_type, blocked_by_type


def _determine_health_status(
    total_failed: int,
    total_blocked: int,
    success_rate: float,
    evaluated_workflows: int,
) -> Literal["healthy", "warning", "critical"]:
    """Derive health status from failure/block counts and success rate."""
    if total_failed > 0 or total_blocked > 0:
        if total_failed >= 2 or total_blocked >= 3:
            return "critical"
        return "warning"
    if evaluated_workflows == 0:
        return "healthy"
    if success_rate < 75:
        return "warning"
    return "healthy"


def _extract_last_success(
    last_success: object,
) -> tuple[datetime | None, str | None]:
    """Pull timestamp and type from last-success query result."""
    if last_success.is_empty():
        return None, None
    row = last_success.row(0)
    return row[2], row[1]


def _aggregate_stale_running_counts(stale_running: object) -> dict[str, int]:
    """Aggregate overdue running workflow counts by type."""
    if stale_running.is_empty():
        return {}
    return {
        row["workflow_type"]: row["count"]
        for row in stale_running.iter_rows(named=True)
    }


def _fallback_workflow_health() -> WorkflowHealthInfo:
    """Return a safe default WorkflowHealthInfo when data is unavailable."""
    return WorkflowHealthInfo(
        status="warning",
        total_workflows_24h=0,
        successful_workflows=0,
        failed_workflows=0,
        blocked_workflows=0,
        success_rate=0,
        avg_duration_s=None,
        last_successful_workflow=None,
        last_successful_type=None,
        failures_by_type={},
        blocked_by_type={},
    )


def get_workflow_health(storage: PortfolioStorage) -> WorkflowHealthInfo:
    """Get workflow health status from agent_workflows table."""
    try:
        result, total_result, last_success, stale_running = _query_workflow_health_data(storage)
    except Exception as e:
        logger.warning("workflow_health_failed", error=str(e), exc_info=True)
        return _fallback_workflow_health()

    total_workflows = total_result.row(0)[0] if not total_result.is_empty() else 0
    stats, failures_by_type, blocked_by_type = _aggregate_workflow_stats(result)
    stale_running_by_type = _aggregate_stale_running_counts(stale_running)

    total_successful = sum(s.get("complete", 0) for s in stats.values())
    total_failed = sum(s.get("failed", 0) for s in stats.values())
    total_blocked = sum(s.get("blocked", 0) for s in stats.values()) + sum(stale_running_by_type.values())
    for workflow_type, count in stale_running_by_type.items():
        blocked_by_type[workflow_type] = blocked_by_type.get(workflow_type, 0) + count

    evaluated_workflows = total_successful + total_failed
    success_rate = (total_successful / evaluated_workflows * 100) if evaluated_workflows > 0 else 0

    health_status = _determine_health_status(
        total_failed,
        total_blocked,
        success_rate,
        evaluated_workflows,
    )
    last_successful_time, last_successful_type = _extract_last_success(last_success)

    return WorkflowHealthInfo(
        status=health_status,
        total_workflows_24h=total_workflows,
        successful_workflows=total_successful,
        failed_workflows=total_failed,
        blocked_workflows=total_blocked,
        success_rate=round(success_rate, 1),
        avg_duration_s=None,
        last_successful_workflow=last_successful_time,
        last_successful_type=last_successful_type,
        failures_by_type=failures_by_type,
        blocked_by_type=blocked_by_type,
    )


def _query_workflow_metrics_data(storage: PortfolioStorage) -> tuple[object, object]:
    """Run DB queries needed for workflow metrics and return raw results."""
    with storage.connection() as conn:
        workflows = conn.execute(
            """
            SELECT id, workflow_type, status, created_at
            FROM agent_workflows
            WHERE created_at > NOW() - INTERVAL '7 days'
            ORDER BY created_at DESC
            LIMIT 50
            """
        ).pl()

        summary = conn.execute(
            """
            SELECT workflow_type, status, COUNT(*) as count
            FROM agent_workflows
            WHERE created_at > NOW() - INTERVAL '7 days'
            GROUP BY workflow_type, status
            """
        ).pl()

    return workflows, summary


def _build_recent_workflows(workflows: object) -> list[dict[str, object]]:
    """Convert workflow rows to serialisable dicts."""
    if workflows.is_empty():
        return []
    return [
        {
            "id": row["id"],
            "type": row["workflow_type"],
            "status": row["status"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in workflows.iter_rows(named=True)
    ]


def _aggregate_summary(
    summary: object,
) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    """Aggregate summary counts by type and overall status."""
    summary_by_type: dict[str, dict[str, int]] = {}
    total_by_status: dict[str, int] = {"complete": 0, "failed": 0, "blocked": 0}

    if summary.is_empty():
        return summary_by_type, total_by_status

    for row in summary.iter_rows(named=True):
        wtype = row["workflow_type"]
        status = row["status"]
        count = row["count"]

        if wtype not in summary_by_type:
            summary_by_type[wtype] = {"complete": 0, "failed": 0, "blocked": 0}
        summary_by_type[wtype][status] = count
        total_by_status[status] = total_by_status.get(status, 0) + count

    return summary_by_type, total_by_status


def get_workflow_metrics(storage: PortfolioStorage) -> dict[str, object]:
    """Get detailed workflow metrics for Status page (last 7 days)."""
    try:
        workflows, summary = _query_workflow_metrics_data(storage)
    except Exception as e:
        logger.warning("workflow_metrics_failed", error=str(e), exc_info=True)
        return {
            "recent_workflows": [],
            "summary_by_type": {},
            "total_by_status": {},
            "total_workflows_7d": 0,
            "success_rate": 0,
        }

    recent_workflows = _build_recent_workflows(workflows)
    summary_by_type, total_by_status = _aggregate_summary(summary)
    total_workflows = sum(total_by_status.values())

    return {
        "recent_workflows": recent_workflows,
        "summary_by_type": summary_by_type,
        "total_by_status": total_by_status,
        "total_workflows_7d": total_workflows,
        "success_rate": (total_by_status.get("complete", 0) / max(1, total_workflows) * 100),
    }
