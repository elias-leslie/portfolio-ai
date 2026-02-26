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

from typing import TYPE_CHECKING

from ..logging_config import get_logger
from ._feature_scanner_helpers import (
    build_feature_dict,
    calculate_completion_pct,
    calculate_effective_priority,
    calculate_health_status,
    index_tasks_by_feature,
)
from ._feature_scanner_queries import (
    fetch_features_with_counts,
    fetch_next_feature_id,
    fetch_summary_data,
    insert_feature,
    update_verified_timestamp,
)

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

    def scan(self) -> list[dict]:
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

        feature_rows, task_rows = fetch_features_with_counts(self.conn_mgr)
        tasks_by_feature = index_tasks_by_feature(task_rows)

        features = [
            self._validate_feature(row, tasks_by_feature) for row in feature_rows
        ]

        logger.info("feature_scan_complete", features_scanned=len(features))
        return features

    def _validate_feature(self, row: tuple, tasks_by_feature: dict[int, list[dict]]) -> dict:
        """Validate a single feature's completion status.

        Args:
            row: Database row tuple with task counts
            tasks_by_feature: Pre-fetched tasks indexed by feature DB id

        Returns:
            Feature dict with validation results
        """
        db_id = row[0]
        db_total_tasks = row[8]
        db_completed_tasks = row[9]
        layers = row[10]
        layer_results = row[11]
        priority = row[12]
        acceptance_criteria = row[13]

        tasks = tasks_by_feature.get(db_id, [])
        completion_pct = calculate_completion_pct(db_total_tasks, db_completed_tasks)
        health_status = calculate_health_status(has_tasks=db_total_tasks > 0)
        effective_priority = calculate_effective_priority(
            priority=priority,
            layers=layers,
            layer_results=layer_results,
            acceptance_criteria=acceptance_criteria,
        )

        return build_feature_dict(
            row=row,
            tasks=tasks,
            completion_pct=completion_pct,
            health_status=health_status,
            effective_priority=effective_priority,
        )

    def update_last_verified(self, feature_id: str) -> bool:
        """Update last_verified_at timestamp.

        Use this when verification runs to record when the feature was last checked.
        This ensures the "Checked" column in UI reflects when verification last ran.

        Args:
            feature_id: Feature ID (e.g., "FEAT-001")

        Returns:
            True if update succeeded, False otherwise
        """
        logger.info("updating_last_verified", feature_id=feature_id)
        return update_verified_timestamp(self.conn_mgr, feature_id)

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
        logger.info("adding_feature", feature_id=feature_id, name=name, category=category)
        try:
            insert_feature(self.conn_mgr, feature_id, name, category, description)
            return True
        except Exception as e:
            logger.error("add_feature_failed", feature_id=feature_id, error=str(e))
            return False

    def get_next_feature_id(self) -> str:
        """Get the next available feature ID.

        Returns:
            Next feature ID in format FEAT-XXX
        """
        return fetch_next_feature_id(self.conn_mgr)

    def get_summary(self) -> dict:
        """Get summary statistics for features.

        Returns:
            Summary dict with counts and breakdowns
        """
        total, category_rows, health_rows = fetch_summary_data(self.conn_mgr)
        return {
            "total": total,
            "category_breakdown": {row[0] or "Uncategorized": row[1] for row in category_rows},
            "health_breakdown": {row[0] or "unknown": row[1] for row in health_rows},
        }

    # Subtask Management REMOVED - Use Beads CLI: bd ready, bd create, bd update, bd close
