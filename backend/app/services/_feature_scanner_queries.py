"""SQL query helpers for the feature capability scanner.

Encapsulates all database query logic used by FeatureScanner,
keeping the scanner class focused on orchestration.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.connection import ConnectionManager


FEATURES_WITH_TASK_COUNTS_SQL = """
    SELECT
        f.id, f.feature_id, f.name, f.category, f.description,
        f.last_verified_at, f.created_at, f.updated_at,
        COALESCE(t.total_tasks, 0) as db_total_tasks,
        COALESCE(t.completed_tasks, 0) as db_completed_tasks,
        CASE WHEN f.layers IS NULL OR f.layers = '{}' THEN ARRAY['Frontend', 'Backend', 'UI'] ELSE f.layers END as layers,
        COALESCE(f.layer_results, '{}'::jsonb) as layer_results,
        f.priority,
        COALESCE(f.acceptance_criteria, '[]'::jsonb) as acceptance_criteria,
        COALESCE(f.vision_goals, '{}') as vision_goals
    FROM feature_capabilities f
    LEFT JOIN (
        SELECT
            feature_id,
            COUNT(*) as total_tasks,
            COUNT(*) FILTER (WHERE completed = true) as completed_tasks
        FROM feature_tasks
        GROUP BY feature_id
    ) t ON t.feature_id = f.id
    ORDER BY f.category, f.feature_id
"""

ALL_TASKS_SQL = """
    SELECT
        ft.feature_id, ft.task_id, ft.description, ft.completed,
        ft.order_num, ft.completed_at, ft.completed_by,
        ft.files, ft.notes, ft.status, ft.effort, ft.task_type
    FROM feature_tasks ft
    ORDER BY ft.feature_id, ft.order_num, ft.task_id
"""

HEALTH_BREAKDOWN_SQL = """
    SELECT
        CASE
            WHEN t.total_tasks = 0 OR t.total_tasks IS NULL THEN 'orphaned'
            ELSE 'active'
        END as health_status,
        COUNT(*)
    FROM feature_capabilities f
    LEFT JOIN (
        SELECT feature_id, COUNT(*) as total_tasks
        FROM feature_tasks
        GROUP BY feature_id
    ) t ON t.feature_id = f.id
    GROUP BY 1
"""

CATEGORY_BREAKDOWN_SQL = """
    SELECT category, COUNT(*)
    FROM feature_capabilities
    GROUP BY category
    ORDER BY COUNT(*) DESC
"""

NEXT_FEATURE_ID_SQL = """
    SELECT MAX(
        CAST(SUBSTRING(feature_id FROM 'FEAT-([0-9]+)') AS INTEGER)
    )
    FROM feature_capabilities
    WHERE feature_id LIKE 'FEAT-%'
"""

INSERT_FEATURE_SQL = """
    INSERT INTO feature_capabilities (
        feature_id, name, category, description,
        created_at, updated_at
    ) VALUES (
        %s, %s, %s, %s, NOW(), NOW()
    )
"""

UPDATE_VERIFIED_SQL = """
    UPDATE feature_capabilities
    SET last_verified_at = %s,
        updated_at = NOW()
    WHERE feature_id = %s
"""


def fetch_features_with_counts(conn_mgr: ConnectionManager) -> tuple[list[tuple], list[tuple]]:
    """Fetch all features with task counts and all tasks in two queries.

    Returns:
        Tuple of (feature_rows, task_rows)
    """
    with conn_mgr.connection() as conn:
        feature_rows = conn.execute(FEATURES_WITH_TASK_COUNTS_SQL).fetchall()
        task_rows = conn.execute(ALL_TASKS_SQL).fetchall()
    return feature_rows, task_rows


def fetch_summary_data(
    conn_mgr: ConnectionManager,
) -> tuple[int, list[tuple], list[tuple]]:
    """Fetch total count, category breakdown, and health breakdown.

    Returns:
        Tuple of (total, category_rows, health_rows)
    """
    with conn_mgr.connection() as conn:
        total_row = conn.execute("SELECT COUNT(*) FROM feature_capabilities").fetchone()
        raw_total = total_row[0] if total_row else 0
        total: int = int(raw_total) if raw_total is not None else 0
        category_rows = conn.execute(CATEGORY_BREAKDOWN_SQL).fetchall()
        health_rows = conn.execute(HEALTH_BREAKDOWN_SQL).fetchall()
    return total, category_rows, health_rows


def fetch_next_feature_id(conn_mgr: ConnectionManager) -> str:
    """Fetch the next available feature ID.

    Returns:
        Next feature ID in format FEAT-XXX
    """
    with conn_mgr.connection() as conn:
        row = conn.execute(NEXT_FEATURE_ID_SQL).fetchone()
    max_num = row[0] if row and row[0] else 0
    return f"FEAT-{int(max_num) + 1:03d}"


def insert_feature(
    conn_mgr: ConnectionManager,
    feature_id: str,
    name: str,
    category: str,
    description: str | None,
) -> None:
    """Insert a new feature into the database."""
    with conn_mgr.connection() as conn:
        conn.execute(INSERT_FEATURE_SQL, (feature_id, name, category, description))
        conn.commit()


def update_verified_timestamp(conn_mgr: ConnectionManager, feature_id: str) -> bool:
    """Update last_verified_at timestamp for a feature.

    Returns:
        True if update succeeded (row found), False otherwise
    """
    with conn_mgr.connection() as conn:
        result = conn.execute(UPDATE_VERIFIED_SQL, (datetime.now(UTC), feature_id))
        conn.commit()
    return result.rowcount > 0 if hasattr(result, "rowcount") else True
