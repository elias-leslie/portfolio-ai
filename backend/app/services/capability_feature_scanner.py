"""Feature capability scanner for long-running agent patterns.

Validates features in feature_capabilities table:
- Calculates completion from feature_tasks table (all-in-DB approach)
- Verification status calculated dynamically from tasks + acceptance criteria

Agent permissions (corruption protection):
- Scanner can only modify: last_verified_at, acceptance_criteria
- Other fields (name, description) are read-only
- Features can only be added via /task_it, deleted manually
- Subtasks can be added/toggled via API

All-in-DB architecture:
- feature_capabilities: Features with acceptance_criteria
- feature_tasks: Subtasks with completion status
- Progress = COUNT(completed=true) / COUNT(*) from feature_tasks
- Verified = tasks=0 AND all acceptance_criteria.passed=true (dynamic)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..storage.connection import ConnectionManager

logger = get_logger(__name__)


class FeatureScanner:
    """Scans and validates features in feature_capabilities table.

    Unlike other scanners that discover capabilities, this scanner validates
    existing features by checking their linked task files and completion status.

    Implements Anthropic's long-running agent patterns:
    - Restricted field modification (last_verified_at, acceptance_criteria only)
    - Verification status calculated dynamically
    - Section completion parsing from markdown
    """

    def __init__(self, connection_mgr: ConnectionManager) -> None:
        """Initialize feature scanner.

        Args:
            connection_mgr: ConnectionManager instance for database access
        """
        self.conn_mgr = connection_mgr

    def scan(self) -> list[dict[str, Any]]:
        """Scan all features and validate their completion status.

        Uses all-in-DB approach: calculates completion from feature_tasks table.
        Falls back to markdown parsing if no DB tasks exist (migration path).

        Returns:
            List of feature dicts with validation results:
                - feature_id: str
                - name: str
                - category: str
                - total_tasks: int (from DB)
                - completed_tasks: int (from DB)
                - completion_pct: int
                - health_status: str
                - tasks: list[dict] (subtasks from DB)
                - acceptance_criteria: list[dict] (with passed status)
        """
        logger.info("scanning_features")

        features = []

        with self.conn_mgr.connection() as conn:
            # Get all features with task counts from database
            rows = conn.execute(
                """
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
            ).fetchall()

            # Batch load ALL tasks in one query to avoid N+1 (optimization)
            all_tasks_rows = conn.execute(
                """
                SELECT
                    ft.feature_id, ft.task_id, ft.description, ft.completed,
                    ft.order_num, ft.completed_at, ft.completed_by,
                    ft.files, ft.notes, ft.status, ft.effort, ft.task_type
                FROM feature_tasks ft
                ORDER BY ft.feature_id, ft.order_num, ft.task_id
                """
            ).fetchall()

            # Index tasks by feature DB id for O(1) lookup
            tasks_by_feature: dict[int, list[dict[str, Any]]] = {}
            for task_row in all_tasks_rows:
                feature_db_id = task_row[0]
                task_dict = {
                    "task_id": task_row[1],
                    "description": task_row[2],
                    "completed": task_row[3],
                    "order_num": task_row[4],
                    "completed_at": task_row[5],
                    "completed_by": task_row[6],
                    "files": task_row[7] if task_row[7] else [],
                    "notes": task_row[8],
                    "status": task_row[9] or "pending",
                    "effort": task_row[10],
                    "task_type": task_row[11] or "implementation",
                }
                if feature_db_id not in tasks_by_feature:
                    tasks_by_feature[feature_db_id] = []
                tasks_by_feature[feature_db_id].append(task_dict)

            for row in rows:
                feature = self._validate_feature(row, tasks_by_feature)
                features.append(feature)

        logger.info("feature_scan_complete", features_scanned=len(features))

        return features

    def _validate_feature(
        self, row: tuple[Any, ...], tasks_by_feature: dict[int, list[dict[str, Any]]]
    ) -> dict[str, Any]:
        """Validate a single feature's completion status.

        Args:
            row: Database row tuple with task counts
            tasks_by_feature: Pre-fetched tasks indexed by feature DB id

        Returns:
            Feature dict with validation results
        """
        (
            db_id,
            feature_id,
            name,
            category,
            description,
            last_verified_at,
            created_at,
            updated_at,
            db_total_tasks,
            db_completed_tasks,
            layers,
            layer_results,
            priority,
            acceptance_criteria,
            vision_goals,
        ) = row

        # Use DB tasks (all-in-DB approach)
        total_tasks = db_total_tasks
        completed_tasks = db_completed_tasks

        # Get subtasks from pre-fetched dict (O(1) lookup, no N+1 query)
        tasks = tasks_by_feature.get(db_id, [])

        # Calculate completion percentage
        completion_pct = 0
        if total_tasks > 0:
            completion_pct = int((completed_tasks / total_tasks) * 100)

        # Calculate health status (based on tasks only now)
        calculated_health = self._calculate_health_status(
            has_tasks=db_total_tasks > 0,
            completion_pct=completion_pct,
        )

        # Calculate effective priority (based on layer progress)
        effective_priority = self._calculate_effective_priority(
            priority=priority,
            layers=layers,
            layer_results=layer_results,
            acceptance_criteria=acceptance_criteria,
        )

        return {
            "id": db_id,
            "feature_id": feature_id,
            "name": name,
            "category": category,
            "description": description,
            "layers": layers if layers else ["Frontend", "Backend", "UI"],
            "layer_results": layer_results if layer_results else {},
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "completion_pct": completion_pct,
            "health_status": calculated_health,
            "last_verified_at": last_verified_at,
            "created_at": created_at,
            "updated_at": updated_at,
            "tasks": tasks,
            "priority": priority,
            "effective_priority": effective_priority,
            "acceptance_criteria": acceptance_criteria if acceptance_criteria else [],
            "vision_goals": vision_goals if vision_goals else [],
        }

    def _calculate_health_status(
        self,
        has_tasks: bool,
        completion_pct: int,
    ) -> str:
        """Calculate health status based on task state.

        Args:
            has_tasks: Whether has DB tasks
            completion_pct: Completion percentage of tasks

        Returns:
            Health status: 'active', 'orphaned'
        """
        # No tasks defined - orphaned (needs setup)
        if not has_tasks:
            return "orphaned"

        # Has tasks - active
        return "active"

    def _calculate_effective_priority(  # noqa: PLR0911
        self,
        priority: int | None,
        layers: list[str] | None,
        layer_results: dict | None,
        acceptance_criteria: list[dict[str, Any]] | None,
    ) -> int:
        """Calculate effective priority based on verification state.

        Priority is auto-calculated from layer verification progress and
        acceptance criteria status unless a user override is set.

        Args:
            priority: User override priority (1-5), or None for auto
            layers: List of verification layers
            layer_results: Dict of layer verification results
            acceptance_criteria: List of acceptance criteria dicts

        Returns:
            Effective priority 1-5:
                1 = Critical (failing criteria)
                2 = High (almost verified)
                3 = Medium (partially verified)
                4 = Low (started)
                5 = Backlog (not started)
        """
        # User override takes precedence
        if priority is not None:
            return priority

        # Check if any criteria are failing - highest priority
        criteria = acceptance_criteria if acceptance_criteria else []
        if criteria and any(c.get("passed") is False for c in criteria):
            return 1

        # Calculate layer verification progress
        layers_list = layers if layers else []
        results = layer_results if layer_results else {}
        total_layers = len(layers_list)
        verified_layers = len(results)

        if total_layers == 0:
            return 5  # No layers defined

        verification_pct = (verified_layers / total_layers) * 100

        if verification_pct >= 80:
            return 2  # Almost verified
        if verification_pct >= 50:
            return 3  # Partially verified
        if verification_pct > 0:
            return 4  # Started
        return 5  # Not started

    def update_last_verified(self, feature_id: str) -> bool:
        """Update last_verified_at timestamp.

        Use this when verification runs to record when the feature was last checked.
        This ensures the "Checked" column in UI reflects when verification last ran.

        Args:
            feature_id: Feature ID (e.g., "FEAT-001")

        Returns:
            True if update succeeded, False otherwise
        """
        logger.info(
            "updating_last_verified",
            feature_id=feature_id,
        )

        with self.conn_mgr.connection() as conn:
            result = conn.execute(
                """
                UPDATE feature_capabilities
                SET last_verified_at = %s,
                    updated_at = NOW()
                WHERE feature_id = %s
                """,
                (datetime.now(UTC), feature_id),
            )
            conn.commit()

            return result.rowcount > 0 if hasattr(result, "rowcount") else True

    def add_feature(
        self,
        feature_id: str,
        name: str,
        category: str,
        description: str | None = None,
    ) -> bool:
        """Add a new feature to the registry.

        Only allowed by the initializer agent (/task_it).
        New features start with no tasks (needs setup).

        Args:
            feature_id: Feature ID (e.g., "FEAT-001")
            name: Feature name
            category: Category (Dashboard, Watchlist, etc.)
            description: Optional description

        Returns:
            True if insert succeeded, False otherwise
        """
        logger.info(
            "adding_feature",
            feature_id=feature_id,
            name=name,
            category=category,
        )

        with self.conn_mgr.connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO feature_capabilities (
                        feature_id, name, category, description,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, NOW(), NOW()
                    )
                    """,
                    (
                        feature_id,
                        name,
                        category,
                        description,
                    ),
                )
                conn.commit()
                return True
            except Exception as e:
                logger.error("add_feature_failed", feature_id=feature_id, error=str(e))
                return False

    def get_next_feature_id(self) -> str:
        """Get the next available feature ID.

        Returns:
            Next feature ID in format FEAT-XXX
        """
        with self.conn_mgr.connection() as conn:
            row = conn.execute(
                """
                SELECT MAX(
                    CAST(SUBSTRING(feature_id FROM 'FEAT-([0-9]+)') AS INTEGER)
                )
                FROM feature_capabilities
                WHERE feature_id LIKE 'FEAT-%'
                """
            ).fetchone()

            max_num = row[0] if row and row[0] else 0
            return f"FEAT-{max_num + 1:03d}"

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics for features.

        Returns:
            Summary dict with counts and breakdowns
        """
        with self.conn_mgr.connection() as conn:
            # Total count
            total_row = conn.execute("SELECT COUNT(*) FROM feature_capabilities").fetchone()
            total = total_row[0] if total_row else 0

            # By category
            category_rows = conn.execute(
                """
                SELECT category, COUNT(*)
                FROM feature_capabilities
                GROUP BY category
                ORDER BY COUNT(*) DESC
                """
            ).fetchall()
            category_breakdown = {row[0] or "Uncategorized": row[1] for row in category_rows}

            # By health status (based on tasks)
            health_rows = conn.execute(
                """
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
            ).fetchall()
            health_breakdown = {row[0] or "unknown": row[1] for row in health_rows}

            return {
                "total": total,
                "category_breakdown": category_breakdown,
                "health_breakdown": health_breakdown,
            }

    # =========================================================================
    # Subtask Management (feature_tasks table)
    # =========================================================================

    def get_tasks(self, feature_id: str) -> list[dict[str, Any]]:
        """Get all subtasks for a feature.

        Args:
            feature_id: Feature ID (e.g., "FEAT-001")

        Returns:
            List of task dicts
        """
        with self.conn_mgr.connection() as conn:
            # Get feature DB id first
            row = conn.execute(
                "SELECT id FROM feature_capabilities WHERE feature_id = %s",
                (feature_id,),
            ).fetchone()
            if not row:
                return []

            db_id = row[0]
            task_rows = conn.execute(
                """
                SELECT id, task_id, description, completed, order_num,
                       completed_at, completed_by, created_at, updated_at,
                       files, notes, status, effort, task_type
                FROM feature_tasks
                WHERE feature_id = %s
                ORDER BY order_num, task_id
                """,
                (db_id,),
            ).fetchall()

            return [
                {
                    "id": r[0],
                    "task_id": r[1],
                    "description": r[2],
                    "completed": r[3],
                    "order_num": r[4],
                    "completed_at": r[5],
                    "completed_by": r[6],
                    "created_at": r[7],
                    "updated_at": r[8],
                    "files": r[9] if r[9] else [],
                    "notes": r[10],
                    "status": r[11] or "pending",
                    "effort": r[12],
                    "task_type": r[13] or "implementation",
                }
                for r in task_rows
            ]

    def add_task(
        self,
        feature_id: str,
        task_id: str,
        description: str,
        order_num: int | None = None,
        files: list[str] | None = None,
        notes: str | None = None,
        effort: str | None = None,
        task_type: str = "implementation",
    ) -> bool:
        """Add a subtask to a feature.

        Args:
            feature_id: Feature ID (e.g., "FEAT-001")
            task_id: Task ID within feature (e.g., "1.1", "2.0")
            description: What needs to be done
            order_num: Display order (auto-calculated if None)
            files: List of files this subtask modifies
            notes: Implementation notes
            effort: Effort estimate (trivial, low, medium, high)
            task_type: Task type (implementation, fix, task_file, discovery)

        Returns:
            True if insert succeeded, False otherwise
        """
        logger.info("adding_task", feature_id=feature_id, task_id=task_id)

        with self.conn_mgr.connection() as conn:
            # Get feature DB id
            row = conn.execute(
                "SELECT id FROM feature_capabilities WHERE feature_id = %s",
                (feature_id,),
            ).fetchone()
            if not row:
                logger.error("feature_not_found", feature_id=feature_id)
                return False

            db_id = row[0]

            # Auto-calculate order_num if not provided
            if order_num is None:
                max_row = conn.execute(
                    "SELECT MAX(order_num) FROM feature_tasks WHERE feature_id = %s",
                    (db_id,),
                ).fetchone()
                order_num = (max_row[0] or -1) + 1

            try:
                conn.execute(
                    """
                    INSERT INTO feature_tasks (
                        feature_id, task_id, description, order_num,
                        completed, files, notes, status, effort, task_type,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, false, %s, %s, 'pending', %s, %s, NOW(), NOW())
                    """,
                    (db_id, task_id, description, order_num, files or [], notes, effort, task_type),
                )
                conn.commit()
                return True
            except Exception as e:
                logger.error(
                    "add_task_failed",
                    feature_id=feature_id,
                    task_id=task_id,
                    error=str(e),
                )
                return False

    def toggle_task(
        self,
        feature_id: str,
        task_id: str,
        completed: bool,
        completed_by: str = "manual",
    ) -> bool:
        """Toggle completion status of a subtask.

        Args:
            feature_id: Feature ID (e.g., "FEAT-001")
            task_id: Task ID within feature (e.g., "1.1")
            completed: New completion status
            completed_by: Who completed it (default "manual")

        Returns:
            True if update succeeded, False otherwise
        """
        logger.info(
            "toggling_task",
            feature_id=feature_id,
            task_id=task_id,
            completed=completed,
            completed_by=completed_by,
        )

        with self.conn_mgr.connection() as conn:
            # Get feature DB id
            row = conn.execute(
                "SELECT id FROM feature_capabilities WHERE feature_id = %s",
                (feature_id,),
            ).fetchone()
            if not row:
                logger.error("feature_not_found", feature_id=feature_id)
                return False

            db_id = row[0]

            # Update task
            completed_at = datetime.now(UTC) if completed else None
            result = conn.execute(
                """
                UPDATE feature_tasks
                SET completed = %s,
                    completed_at = %s,
                    completed_by = %s,
                    updated_at = NOW()
                WHERE feature_id = %s AND task_id = %s
                """,
                (completed, completed_at, completed_by if completed else None, db_id, task_id),
            )
            conn.commit()

            return result.rowcount > 0 if hasattr(result, "rowcount") else True

    def delete_task(self, feature_id: str, task_id: str) -> bool:
        """Delete a subtask from a feature.

        Args:
            feature_id: Feature ID (e.g., "FEAT-001")
            task_id: Task ID within feature (e.g., "1.1")

        Returns:
            True if delete succeeded, False otherwise
        """
        logger.info("deleting_task", feature_id=feature_id, task_id=task_id)

        with self.conn_mgr.connection() as conn:
            # Get feature DB id
            row = conn.execute(
                "SELECT id FROM feature_capabilities WHERE feature_id = %s",
                (feature_id,),
            ).fetchone()
            if not row:
                return False

            db_id = row[0]

            result = conn.execute(
                "DELETE FROM feature_tasks WHERE feature_id = %s AND task_id = %s",
                (db_id, task_id),
            )
            conn.commit()

            return result.rowcount > 0 if hasattr(result, "rowcount") else True
