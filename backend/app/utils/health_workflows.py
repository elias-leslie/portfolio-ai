"""Workflow health checks for autonomous trading workflows."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)


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


def get_workflow_health(storage: PortfolioStorage) -> WorkflowHealthInfo:
    """Get workflow health status from agent_workflows table."""
    try:
        with storage.connection() as conn:
            result = conn.execute(
                """
                SELECT workflow_type, status, COUNT(*) as count
                FROM agent_workflows
                WHERE created_at > NOW() - INTERVAL '24 hours'
                  AND status IN ('complete', 'failed', 'blocked')
                GROUP BY workflow_type, status
                """
            ).pl()

            total_result = conn.execute(
                """
                SELECT COUNT(*) as total
                FROM agent_workflows
                WHERE created_at > NOW() - INTERVAL '24 hours'
                """
            ).pl()

            last_success = conn.execute(
                """
                SELECT id, workflow_type, completed_at
                FROM agent_workflows
                WHERE status = 'complete' AND completed_at IS NOT NULL
                ORDER BY completed_at DESC
                LIMIT 1
                """
            ).pl()

        total_workflows = total_result.row(0)[0] if not total_result.is_empty() else 0

        stats: dict[str, dict[str, int]] = {}
        failures_by_type: dict[str, int] = {}
        blocked_by_type: dict[str, int] = {}

        if not result.is_empty():
            for row in result.iter_rows(named=True):
                workflow_type = row["workflow_type"]
                status = row["status"]
                count = row["count"]

                if workflow_type not in stats:
                    stats[workflow_type] = {"complete": 0, "failed": 0, "blocked": 0}

                stats[workflow_type][status] = count

                if status == "failed":
                    failures_by_type[workflow_type] = count
                elif status == "blocked":
                    blocked_by_type[workflow_type] = count

        total_successful = sum(s.get("complete", 0) for s in stats.values())
        total_failed = sum(s.get("failed", 0) for s in stats.values())
        total_blocked = sum(s.get("blocked", 0) for s in stats.values())

        success_rate = (
            (total_successful / (total_workflows - total_blocked) * 100)
            if total_workflows > total_blocked
            else 0
        )

        health_status: Literal["healthy", "warning", "critical"]
        if total_failed > 0 or total_blocked > 2:
            if total_failed >= 2 or total_blocked >= 3:
                health_status = "critical"
            else:
                health_status = "warning"
        elif success_rate < 75:
            health_status = "warning"
        else:
            health_status = "healthy"

        last_successful_time: datetime | None = None
        last_successful_type: str | None = None
        if not last_success.is_empty():
            success_row = last_success.row(0)  # Returns tuple
            last_successful_time = success_row[2]
            last_successful_type = success_row[1]

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

    except Exception as e:
        logger.warning("workflow_health_failed", error=str(e), exc_info=True)
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


def get_workflow_metrics(storage: PortfolioStorage) -> dict[str, object]:
    """Get detailed workflow metrics for Status page (last 7 days)."""
    try:
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

        recent_workflows = []
        if not workflows.is_empty():
            for row in workflows.iter_rows(named=True):
                recent_workflows.append(
                    {
                        "id": row["id"],
                        "type": row["workflow_type"],
                        "status": row["status"],
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    }
                )

        summary_by_type: dict[str, dict[str, int]] = {}
        total_by_status: dict[str, int] = {"complete": 0, "failed": 0, "blocked": 0}

        if not summary.is_empty():
            for row in summary.iter_rows(named=True):
                workflow_type = row["workflow_type"]
                status = row["status"]
                count = row["count"]

                if workflow_type not in summary_by_type:
                    summary_by_type[workflow_type] = {"complete": 0, "failed": 0, "blocked": 0}

                summary_by_type[workflow_type][status] = count
                total_by_status[status] = total_by_status.get(status, 0) + count

        total_workflows = sum(total_by_status.values())

        return {
            "recent_workflows": recent_workflows,
            "summary_by_type": summary_by_type,
            "total_by_status": total_by_status,
            "total_workflows_7d": total_workflows,
            "success_rate": (total_by_status.get("complete", 0) / max(1, total_workflows) * 100),
        }

    except Exception as e:
        logger.warning("workflow_metrics_failed", error=str(e), exc_info=True)
        return {
            "recent_workflows": [],
            "summary_by_type": {},
            "total_by_status": {},
            "total_workflows_7d": 0,
            "success_rate": 0,
        }
