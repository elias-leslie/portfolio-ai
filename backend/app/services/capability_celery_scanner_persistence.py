"""Database persistence for Celery scanner."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ..logging_config import get_logger
from .capability_utils import _to_json_string

if TYPE_CHECKING:
    from ..storage.connection import ConnectionManager

logger = get_logger(__name__)


def save_capabilities(
    conn_mgr: ConnectionManager,
    capabilities: list[dict[str, Any]],
) -> int:
    """Save scanned Celery capabilities to celery_capabilities table.

    Uses UPSERT logic (INSERT ... ON CONFLICT DO UPDATE) to update existing records.

    Args:
        conn_mgr: ConnectionManager instance for database access
        capabilities: List of capability dicts from scan()

    Returns:
        Number of rows inserted/updated
    """
    if not capabilities:
        logger.info("no_celery_capabilities_to_save")
        return 0

    logger.info("saving_celery_capabilities", count=len(capabilities))

    with conn_mgr.connection() as conn:
        for cap in capabilities:
            # Convert lists to JSON strings for JSONB columns
            populates_tables_json = _to_json_string(cap["populates_tables"])
            reads_from_tables_json = _to_json_string(cap["reads_from_tables"])
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
                    populates_tables, reads_from_tables, depends_on_tasks, health_status,
                    last_scanned_at, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
                    reads_from_tables = EXCLUDED.reads_from_tables,
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
                    reads_from_tables_json,
                    depends_on_tasks_json,
                    cap["health_status"],
                    datetime.now(UTC),  # last_scanned_at
                    datetime.now(UTC),  # created_at
                    datetime.now(UTC),  # updated_at
                ],
            )
            conn.commit()

        # Clean up removed tasks (inside the with block)
        removed_count = cleanup_removed_capabilities(
            conn, [cap["task_name"] for cap in capabilities]
        )
        if removed_count > 0:
            logger.info("celery_capabilities_removed", count=removed_count)

    logger.info("celery_capabilities_saved", count=len(capabilities))
    return len(capabilities)


def cleanup_removed_capabilities(
    conn: Any,
    current_task_names: list[str],
) -> int:
    """Remove capabilities for tasks no longer in beat schedule.

    Args:
        conn: Database connection
        current_task_names: List of task names currently in beat schedule

    Returns:
        Number of rows deleted
    """
    if not current_task_names:
        return 0

    # Find and delete tasks that are in DB but not in current schedule
    result = conn.execute(
        """
        DELETE FROM celery_capabilities
        WHERE task_name NOT IN %s
        RETURNING task_name
        """,
        [tuple(current_task_names)],
    )
    deleted = result.fetchall()
    conn.commit()

    for row in deleted:
        logger.info("celery_capability_removed", task_name=row[0])

    return len(deleted)
