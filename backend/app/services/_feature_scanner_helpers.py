"""Pure helper functions for feature capability scanner.

Provides row-to-dict conversion and business logic calculations
used by FeatureScanner, with no database dependencies.
"""

from __future__ import annotations

from ..logging_config import get_logger

logger = get_logger(__name__)


def build_task_dict(task_row: tuple) -> dict:
    """Convert a task database row to a typed dict.

    Args:
        task_row: Row from feature_tasks query

    Returns:
        Task dict with normalized fields
    """
    return {
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


def index_tasks_by_feature(task_rows: list[tuple]) -> dict[int, list[dict]]:
    """Index task rows by feature DB id for O(1) lookup.

    Args:
        task_rows: All rows from feature_tasks query

    Returns:
        Dict mapping feature DB id to list of task dicts
    """
    tasks_by_feature: dict[int, list[dict]] = {}
    for task_row in task_rows:
        feature_db_id_raw = task_row[0]
        if not isinstance(feature_db_id_raw, int):
            logger.warning("unexpected_feature_id_type", value=feature_db_id_raw)
            continue
        feature_db_id: int = feature_db_id_raw
        tasks_by_feature.setdefault(feature_db_id, []).append(build_task_dict(task_row))
    return tasks_by_feature


def calculate_completion_pct(total_tasks: int, completed_tasks: int) -> int:
    """Calculate integer completion percentage.

    Args:
        total_tasks: Total number of tasks
        completed_tasks: Number of completed tasks

    Returns:
        Completion percentage 0-100
    """
    if total_tasks <= 0:
        return 0
    return int((completed_tasks / total_tasks) * 100)


def calculate_health_status(has_tasks: bool) -> str:
    """Calculate health status based on task presence.

    Args:
        has_tasks: Whether the feature has any DB tasks

    Returns:
        'active' if has tasks, 'orphaned' otherwise
    """
    return "active" if has_tasks else "orphaned"


def calculate_effective_priority(  # noqa: PLR0911
    priority: int | None,
    layers: list[str] | None,
    layer_results: dict | None,
    acceptance_criteria: list[dict] | None,
) -> int:
    """Calculate effective priority based on verification state.

    Auto-calculates from layer progress and acceptance criteria unless
    a user override priority is set.

    Args:
        priority: User override priority (1-5), or None for auto
        layers: List of verification layers
        layer_results: Dict of layer verification results
        acceptance_criteria: List of acceptance criteria dicts

    Returns:
        Effective priority 1-5 (1=Critical, 5=Backlog)
    """
    if priority is not None:
        return priority

    criteria = acceptance_criteria or []
    if criteria and any(c.get("passed") is False for c in criteria):
        return 1

    layers_list = layers or []
    results = layer_results or {}
    total_layers = len(layers_list)

    if total_layers == 0:
        return 5

    verification_pct = (len(results) / total_layers) * 100

    if verification_pct >= 80:
        return 2
    if verification_pct >= 50:
        return 3
    if verification_pct > 0:
        return 4
    return 5


def build_feature_dict(
    row: tuple,
    tasks: list[dict],
    completion_pct: int,
    health_status: str,
    effective_priority: int,
) -> dict:
    """Build the feature result dict from a database row and computed values.

    Args:
        row: Feature database row (15 fields)
        tasks: Pre-fetched task dicts for this feature
        completion_pct: Calculated completion percentage
        health_status: Calculated health status string
        effective_priority: Calculated effective priority integer

    Returns:
        Feature dict with all validation results
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
        total_tasks,
        completed_tasks,
        layers,
        layer_results,
        priority,
        acceptance_criteria,
        vision_goals,
    ) = row

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
        "health_status": health_status,
        "last_verified_at": last_verified_at,
        "created_at": created_at,
        "updated_at": updated_at,
        "tasks": tasks,
        "priority": priority,
        "effective_priority": effective_priority,
        "acceptance_criteria": acceptance_criteria if acceptance_criteria else [],
        "vision_goals": vision_goals if vision_goals else [],
    }
