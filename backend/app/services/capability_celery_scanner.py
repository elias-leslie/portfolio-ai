"""Celery task capability scanner."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..logging_config import get_logger
from .capability_utils import _to_json_string
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
        schedule_description, schedule_crontab, schedule_interval_seconds = self._parse_schedule(
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
        ) = self._get_task_metadata(task_path)

        # Detect populated tables (basic regex scan of task file)
        populates_tables = self._detect_populates_tables(task_path)

        # Categorize task
        category = categorize_by_name(task_name)

        # Detect task callers (who calls this task via .delay() or send_task())
        called_by = self._detect_task_callers(task_name, task_path)

        # Detect dependencies (tasks this task calls)
        depends_on_tasks = self._detect_task_dependencies(task_path)

        # Calculate health status
        health_status = self._calculate_celery_health_status(
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
            "depends_on_tasks": depends_on_tasks,
            "called_by": called_by,  # NEW: files/tasks that call this task
            "health_status": health_status,
        }

    def _parse_schedule(
        self,
        schedule_obj: Any,
    ) -> tuple[str, str | None, int | None]:
        """Parse Celery schedule object into human-readable format.

        Args:
            schedule_obj: Celery schedule object (crontab or interval)

        Returns:
            Tuple of (description, crontab_string, interval_seconds)
        """
        from celery.schedules import crontab  # type: ignore[import-untyped]  # noqa: PLC0415

        schedule_str = str(schedule_obj)

        # Try to parse crontab
        if isinstance(schedule_obj, crontab):
            # Human-readable description
            hour = schedule_obj._orig_hour if hasattr(schedule_obj, "_orig_hour") else "*"
            minute = schedule_obj._orig_minute if hasattr(schedule_obj, "_orig_minute") else "*"

            if hour != "*" and minute != "*":
                description = f"Daily at {hour:02d}:{minute:02d} UTC"
                crontab_str = f"{minute} {hour} * * *"
            else:
                description = f"Crontab: {schedule_str}"
                crontab_str = schedule_str

            # Estimate interval in seconds for daily tasks
            interval_seconds = 86400 if hour != "*" else None

        elif isinstance(schedule_obj, (int, float)):
            # Interval in seconds
            interval_seconds = int(schedule_obj)

            if interval_seconds < 60:
                description = f"Every {interval_seconds} seconds"
            elif interval_seconds < 3600:
                description = f"Every {interval_seconds // 60} minutes"
            elif interval_seconds < 86400:
                description = f"Every {interval_seconds // 3600} hours"
            else:
                description = f"Every {interval_seconds // 86400} days"

            crontab_str = None

        else:
            # Unknown schedule type
            description = f"Schedule: {schedule_str}"
            crontab_str = None
            interval_seconds = None

        return description, crontab_str, interval_seconds

    def _get_task_metadata(
        self,
        task_path: str,
    ) -> tuple[Any | None, Any | None, int, int, int | None, int | None, int | None]:
        """Get task execution metadata from celery_taskmeta table.

        Args:
            task_path: Task import path

        Returns:
            Tuple of (last_run_at, next_run_at, success_count_7d, failure_count_7d,
                     success_rate_pct, avg_duration_ms, max_duration_ms)
        """
        if not self.celery_config["track_success_rate"]:
            return None, None, 0, 0, None, None, None

        try:
            with self.conn_mgr.connection() as conn:
                # Check if celery_taskmeta table exists
                check_table = conn.execute(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'celery_taskmeta'
                    )
                    """
                )
                row = check_table.fetchone()
                table_exists = row[0] if row else False

                if not table_exists:
                    return None, None, 0, 0, None, None, None

                # Query last 7 days of task execution
                lookback_days = self.celery_config["lookback_days"]

                result = conn.execute(
                    f"""
                    SELECT
                        MAX(date_done) as last_run,
                        COUNT(*) FILTER (WHERE status = 'SUCCESS') as success_count,
                        COUNT(*) FILTER (WHERE status = 'FAILURE') as failure_count
                    FROM celery_taskmeta
                    WHERE name = %s
                    AND date_done >= NOW() - INTERVAL '{lookback_days} days'
                    """,
                    [task_path],
                )

                row = result.fetchone()

                if row:
                    last_run = row[0]
                    success_count = int(row[1] or 0)
                    failure_count = int(row[2] or 0)

                    # Calculate success rate
                    total = success_count + failure_count
                    success_rate = int((success_count / total) * 100) if total > 0 else None

                    # TODO: Calculate duration metrics (requires parsing result JSONB)
                    avg_duration = None
                    max_duration = None

                    return (
                        last_run,
                        None,  # next_run_at (requires celerybeat schedule tracking)
                        success_count,
                        failure_count,
                        success_rate,
                        avg_duration,
                        max_duration,
                    )

        except Exception as e:
            logger.warning("failed_to_query_task_metadata", task=task_path, error=str(e))

        return None, None, 0, 0, None, None, None

    def _calculate_celery_health_status(
        self,
        populates_tables: list[str],
        depends_on_tasks: list[str],
        called_by: list[str],
        last_run_at: Any | None,
        success_rate_pct: int | None,
        schedule_interval_seconds: int | None,
    ) -> str:
        """Calculate health status for Celery task.

        Args:
            populates_tables: Tables this task populates
            depends_on_tasks: Tasks this task depends on
            called_by: Files/tasks that call this task
            last_run_at: Last execution timestamp
            success_rate_pct: Success rate over last 7 days
            schedule_interval_seconds: Schedule interval in seconds

        Returns:
            Health status: "active", "orphaned", "legacy", or "suspect"

        Celery health logic:
        - active: Has callers (other code calls this task) OR healthy execution
        - orphaned: Not in schedule AND no populates AND no depends_on AND no callers
        - legacy: Never run (last_run_at=None) OR success_rate=0% consistently
        - suspect: Low success rate (<50%) OR irregular execution
        """
        has_zero_success = success_rate_pct is not None and success_rate_pct == 0

        # If other code calls this task, it's active (suspect if failing)
        if called_by:
            return "suspect" if has_zero_success else "active"

        # Orphaned: Not scheduled and no dependencies and no callers
        is_isolated = schedule_interval_seconds is None and not populates_tables and not depends_on_tasks
        if is_isolated:
            return "orphaned"

        # Legacy: Never executed OR complete failure (0% success rate)
        if last_run_at is None or has_zero_success:
            return "legacy"

        # Suspect: Low success rate (<50%)
        has_low_success = success_rate_pct is not None and success_rate_pct < 50
        return "suspect" if has_low_success else "active"

    def _detect_populates_tables(self, task_path: str) -> list[str]:
        """Detect which tables a task populates by scanning task file.

        Uses basic regex to find INSERT INTO and UPDATE statements.

        Args:
            task_path: Task import path (e.g., app.tasks.market_data_tasks.fetch_prices)

        Returns:
            List of table names this task writes to
        """
        try:
            # Convert import path to file path
            # app.tasks.market_data_tasks.fetch_prices -> backend/app/tasks/market_data_tasks.py
            path_parts = task_path.split(".")
            if len(path_parts) < 2:
                return []

            # Remove function name
            module_parts = path_parts[:-1]

            # Build file path
            file_path = Path(__file__).parent.parent / "/".join(module_parts[1:])
            file_path = file_path.with_suffix(".py")

            if not file_path.exists():
                return []

            # Read file and search for SQL statements
            content = file_path.read_text()

            # Regex patterns for INSERT/UPDATE
            patterns = [
                r"INSERT\s+INTO\s+([a-z_][a-z0-9_]*)",
                r"UPDATE\s+([a-z_][a-z0-9_]*)",
            ]

            tables = set()
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                tables.update(matches)

            return sorted(tables)

        except Exception as e:
            logger.debug("failed_to_detect_populated_tables", task=task_path, error=str(e))
            return []

    def _detect_task_callers(self, task_name: str, task_path: str) -> list[str]:
        """Detect files/tasks that call this task.

        Searches for patterns like:
        - task_name.delay()
        - task_name.apply_async()
        - send_task('task_path')
        - celery_app.send_task('task_path')

        Args:
            task_name: Beat schedule name (e.g., "fetch-market-data-hourly")
            task_path: Task import path (e.g., "app.tasks.market_data_tasks.fetch_prices")

        Returns:
            List of file paths that call this task
        """
        try:
            callers = set()
            function_name = task_path.split(".")[-1] if "." in task_path else task_path

            # Search patterns
            patterns = [
                rf"{function_name}\.delay\s*\(",
                rf"{function_name}\.apply_async\s*\(",
                rf"send_task\s*\(\s*['\"].*{function_name}['\"]",
                rf"send_task\s*\(\s*['\"].*{task_path}['\"]",
            ]

            # Search in backend app directory
            app_dir = Path(__file__).parent.parent
            for py_file in app_dir.glob("**/*.py"):
                # Skip the task's own file
                if function_name in py_file.name:
                    continue

                try:
                    content = py_file.read_text()
                    for pattern in patterns:
                        if re.search(pattern, content):
                            # Get relative path from app/
                            rel_path = str(py_file.relative_to(app_dir))
                            callers.add(rel_path)
                            break
                except Exception:
                    continue

            return sorted(callers)

        except Exception as e:
            logger.debug("failed_to_detect_task_callers", task=task_name, error=str(e))
            return []

    def _detect_task_dependencies(self, task_path: str) -> list[str]:
        """Detect tasks that this task calls (dependencies).

        Searches for patterns like:
        - other_task.delay()
        - send_task('other_task')

        Args:
            task_path: Task import path

        Returns:
            List of task names this task depends on
        """
        try:
            dependencies = set()

            # Convert import path to file path
            path_parts = task_path.split(".")
            if len(path_parts) < 2:
                return []

            module_parts = path_parts[:-1]
            file_path = Path(__file__).parent.parent / "/".join(module_parts[1:])
            file_path = file_path.with_suffix(".py")

            if not file_path.exists():
                return []

            content = file_path.read_text()

            # Find all .delay() and .apply_async() calls
            delay_pattern = r"(\w+)\.delay\s*\("
            async_pattern = r"(\w+)\.apply_async\s*\("
            send_pattern = r"send_task\s*\(\s*['\"]([^'\"]+)['\"]"

            for match in re.finditer(delay_pattern, content):
                task_var = match.group(1)
                # Filter out common non-task variables
                if task_var not in ["self", "cls", "result", "response", "data"]:
                    dependencies.add(task_var)

            for match in re.finditer(async_pattern, content):
                task_var = match.group(1)
                if task_var not in ["self", "cls", "result", "response", "data"]:
                    dependencies.add(task_var)

            for match in re.finditer(send_pattern, content):
                dependencies.add(match.group(1))

            return sorted(dependencies)

        except Exception as e:
            logger.debug("failed_to_detect_task_dependencies", task=task_path, error=str(e))
            return []

    def save_capabilities(self, capabilities: list[dict[str, Any]]) -> int:
        """Save scanned Celery capabilities to celery_capabilities table.

        Uses UPSERT logic (INSERT ... ON CONFLICT DO UPDATE) to update existing records.

        Args:
            capabilities: List of capability dicts from scan()

        Returns:
            Number of rows inserted/updated
        """
        if not capabilities:
            logger.info("no_celery_capabilities_to_save")
            return 0

        logger.info("saving_celery_capabilities", count=len(capabilities))

        with self.conn_mgr.connection() as conn:
            for cap in capabilities:
                # Convert lists to JSON strings for JSONB columns
                populates_tables_json = _to_json_string(cap["populates_tables"])
                depends_on_tasks_json = _to_json_string(cap["depends_on_tasks"])

                # UPSERT query
                conn.execute(
                    """
                    INSERT INTO celery_capabilities (
                        task_name, category, task_path, function_name,
                        schedule_description, schedule_crontab, schedule_interval_seconds,
                        last_run_at, next_run_at,
                        success_count_7d, failure_count_7d, success_rate_pct,
                        avg_duration_ms, max_duration_ms,
                        populates_tables, depends_on_tasks, health_status,
                        last_scanned_at, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (task_name) DO UPDATE SET
                        category = EXCLUDED.category,
                        task_path = EXCLUDED.task_path,
                        function_name = EXCLUDED.function_name,
                        schedule_description = EXCLUDED.schedule_description,
                        schedule_crontab = EXCLUDED.schedule_crontab,
                        schedule_interval_seconds = EXCLUDED.schedule_interval_seconds,
                        last_run_at = EXCLUDED.last_run_at,
                        next_run_at = EXCLUDED.next_run_at,
                        success_count_7d = EXCLUDED.success_count_7d,
                        failure_count_7d = EXCLUDED.failure_count_7d,
                        success_rate_pct = EXCLUDED.success_rate_pct,
                        avg_duration_ms = EXCLUDED.avg_duration_ms,
                        max_duration_ms = EXCLUDED.max_duration_ms,
                        populates_tables = EXCLUDED.populates_tables,
                        depends_on_tasks = EXCLUDED.depends_on_tasks,
                        health_status = EXCLUDED.health_status,
                        last_scanned_at = EXCLUDED.last_scanned_at,
                        updated_at = EXCLUDED.updated_at
                    """,
                    [
                        cap["task_name"],
                        cap["category"],
                        cap["task_path"],
                        cap["function_name"],
                        cap["schedule_description"],
                        cap["schedule_crontab"],
                        cap["schedule_interval_seconds"],
                        cap["last_run_at"],
                        cap["next_run_at"],
                        cap["success_count_7d"],
                        cap["failure_count_7d"],
                        cap["success_rate_pct"],
                        cap["avg_duration_ms"],
                        cap["max_duration_ms"],
                        populates_tables_json,
                        depends_on_tasks_json,
                        cap["health_status"],
                        datetime.now(UTC),  # last_scanned_at
                        datetime.now(UTC),  # created_at
                        datetime.now(UTC),  # updated_at
                    ],
                )
                conn.commit()

        logger.info("celery_capabilities_saved", count=len(capabilities))
        return len(capabilities)
