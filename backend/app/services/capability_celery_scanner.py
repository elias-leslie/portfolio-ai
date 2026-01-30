"""Celery task capability scanner."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..logging_config import get_logger
from .capability_celery_scanner_detection import (
    detect_populates_tables,
    detect_reads_from_tables,
    detect_task_callers,
    detect_task_dependencies,
)
from .capability_celery_scanner_health import calculate_celery_health_status
from .capability_celery_scanner_metadata import get_task_metadata
from .capability_celery_scanner_persistence import save_capabilities
from .capability_celery_scanner_schedule import parse_schedule
from .config_loader import categorize_by_name, load_capabilities_config

if TYPE_CHECKING:
    from ..storage.connection import ConnectionManager

logger = get_logger(__name__)


class CeleryScanner:
    """Scans Celery beat schedule to auto-discover scheduled tasks.

    Detects task metadata including schedules, success rates, dependencies.
    """

    def __init__(
        self,
        connection_mgr: ConnectionManager,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize Celery scanner.

        Args:
            connection_mgr: ConnectionManager instance for database access
            config: Optional config dict (loads from file if not provided)
        """
        self.conn_mgr = connection_mgr
        self.config = config or load_capabilities_config()
        self.celery_config = self.config["scan_config"]["targets"]["celery"]

    def scan(self) -> list[dict[str, Any]]:
        """Scan Celery beat schedule and return task metadata.

        Returns:
            List of dicts with task metadata:
                - task_name: str
                - category: str
                - task_path: str
                - function_name: str
                - schedule_description: str
                - schedule_crontab: str | None
                - schedule_interval_seconds: int | None
                - last_run_at: datetime | None
                - next_run_at: datetime | None
                - success_count_7d: int
                - failure_count_7d: int
                - success_rate_pct: int | None
                - avg_duration_ms: int | None
                - max_duration_ms: int | None
                - populates_tables: list[str]
                - depends_on_tasks: list[str]
        """
        if not self.celery_config["enabled"]:
            logger.info("celery_scan_disabled")
            return []

        logger.info("scanning_celery_tasks")

        # Import celery_app to access beat_schedule
        from ..celery_app import celery_app  # noqa: PLC0415

        capabilities = []
        beat_schedule = celery_app.conf.beat_schedule

        for task_name, task_config in beat_schedule.items():
            try:
                capability = self._scan_single_task(task_name, task_config)
                capabilities.append(capability)
            except Exception as e:
                logger.error(
                    "task_scan_failed",
                    task=task_name,
                    error=str(e),
                )

        logger.info(
            "celery_scan_complete",
            tasks_scanned=len(capabilities),
        )

        return capabilities

    def _scan_single_task(
        self,
        task_name: str,
        task_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Scan a single Celery task for metadata.

        Args:
            task_name: Name of task (beat_schedule key)
            task_config: Task configuration dict from beat_schedule

        Returns:
            Dict with task metadata
        """
        task_path = task_config["task"]
        function_name = task_path.split(".")[-1] if "." in task_path else task_path

        # Parse schedule
        schedule_obj = task_config["schedule"]
        schedule_description, schedule_crontab, schedule_interval_seconds = parse_schedule(
            schedule_obj
        )

        # Get task execution metadata (if celery_taskmeta table available)
        (
            last_run_at,
            next_run_at,
            success_count,
            failure_count,
            success_rate,
            avg_duration,
            max_duration,
        ) = get_task_metadata(
            self.conn_mgr,
            task_path,
            self.celery_config["track_success_rate"],
            self.celery_config["lookback_days"],
        )

        # Detect populated tables (basic regex scan of task file)
        populates_tables = detect_populates_tables(task_path)

        # Detect tables this task reads from (for dependency inference)
        reads_from_tables = detect_reads_from_tables(task_path)

        # Categorize task
        category = categorize_by_name(task_name)

        # Detect task callers (who calls this task via .delay() or send_task())
        called_by = detect_task_callers(task_name, task_path)

        # Detect dependencies (tasks this task calls)
        depends_on_tasks = detect_task_dependencies(task_path)

        # Calculate health status
        health_status = calculate_celery_health_status(
            populates_tables=populates_tables,
            depends_on_tasks=depends_on_tasks,
            called_by=called_by,
            last_run_at=last_run_at,
            success_rate_pct=success_rate,
            schedule_interval_seconds=schedule_interval_seconds,
        )

        return {
            "task_name": task_name,
            "category": category,
            "task_path": task_path,
            "function_name": function_name,
            "schedule_description": schedule_description,
            "schedule_crontab": schedule_crontab,
            "schedule_interval_seconds": schedule_interval_seconds,
            "last_run_at": last_run_at,
            "next_run_at": next_run_at,
            "success_count_7d": success_count,
            "failure_count_7d": failure_count,
            "success_rate_pct": success_rate,
            "avg_duration_ms": avg_duration,
            "max_duration_ms": max_duration,
            "populates_tables": populates_tables,
            "reads_from_tables": reads_from_tables,  # Phase 1.5: tables task reads from
            "depends_on_tasks": depends_on_tasks,
            "called_by": called_by,  # files/tasks that call this task
            "health_status": health_status,
        }

    def save_capabilities(self, capabilities: list[dict[str, Any]]) -> int:
        """Save scanned Celery capabilities to celery_capabilities table.

        Uses UPSERT logic (INSERT ... ON CONFLICT DO UPDATE) to update existing records.

        Args:
            capabilities: List of capability dicts from scan()

        Returns:
            Number of rows inserted/updated
        """
        return save_capabilities(self.conn_mgr, capabilities)
