"""Unit tests for dry-run maintenance reporting."""

from __future__ import annotations

from app.services.dry_run_service import DRY_RUN_TASKS, _build_category_report


def test_dry_run_tasks_label_stale_agent_run_cleanup() -> None:
    """The stale-run cleanup task should advertise its current purpose."""
    task = next(
        (task for task in DRY_RUN_TASKS if task[0] == "cleanup_orphaned_data_task"),
        None,
    )
    if task is None:
        raise AssertionError(
            "cleanup_orphaned_data_task not found in DRY_RUN_TASKS"
        )
    task_name, category, retention, _task_fn = task

    assert task_name == "cleanup_orphaned_data_task"
    assert category == "stale_agent_runs"
    assert retention == "Mark stale runs older than 1 hour as failed"


def test_build_category_report_counts_stale_runs() -> None:
    """Zombie-run dry-run results should contribute to the report count."""
    report = _build_category_report(
        {"success": True, "zombie_runs_to_fix": 3},
        "stale_agent_runs",
        "Mark stale runs older than 1 hour as failed",
    )

    assert report["category"] == "stale_agent_runs"
    assert report["would_delete_count"] == 3
    assert report["retention_policy"] == "Mark stale runs older than 1 hour as failed"
