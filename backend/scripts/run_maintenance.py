#!/usr/bin/env python3
"""Manual maintenance task runner with dry-run support."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.logging_config import get_logger  # noqa: E402
from app.tasks.artifact_tasks import cleanup_debug_captures  # noqa: E402
from app.tasks.cleanup import (  # noqa: E402
    check_disk_space_task,
    cleanup_cache_directories_task,
    cleanup_old_logs_task,
    cleanup_temp_files_task,
    rotate_logs_task,
)
from app.tasks.maintenance_tasks import (  # noqa: E402
    cleanup_maintenance_tables_task,
    cleanup_old_agent_runs_task,
    cleanup_old_news_task,
    cleanup_old_watchlist_snapshots_task,
    cleanup_orphaned_data_task,
    get_database_size_task,
    refresh_sec_cik_cache,
    vacuum_database_task,
)

logger = get_logger(__name__)


class TaskConfig(TypedDict):
    function: Callable[..., dict[str, Any]]
    args: list[int]
    description: str
    supports_dry_run: bool


TASK_REGISTRY: dict[str, TaskConfig] = {
    "vacuum_database": {
        "function": vacuum_database_task,
        "args": [],
        "description": "VACUUM ANALYZE all database tables",
        "supports_dry_run": True,
    },
    "cleanup_old_news": {
        "function": cleanup_old_news_task,
        "args": [90],
        "description": "Delete news older than N days",
        "supports_dry_run": True,
    },
    "cleanup_old_agent_runs": {
        "function": cleanup_old_agent_runs_task,
        "args": [30],
        "description": "Delete agent runs older than N days",
        "supports_dry_run": True,
    },
    "cleanup_old_watchlist_snapshots": {
        "function": cleanup_old_watchlist_snapshots_task,
        "args": [60],
        "description": "Delete watchlist snapshots older than N days",
        "supports_dry_run": True,
    },
    "cleanup_maintenance_tables": {
        "function": cleanup_maintenance_tables_task,
        "args": [90],
        "description": "Delete old maintenance stats/logs older than N days",
        "supports_dry_run": True,
    },
    "rotate_logs": {
        "function": rotate_logs_task,
        "args": [],
        "description": "Rotate log files over the size threshold",
        "supports_dry_run": True,
    },
    "cleanup_old_logs": {
        "function": cleanup_old_logs_task,
        "args": [7],
        "description": "Delete log files older than N days",
        "supports_dry_run": True,
    },
    "cleanup_temp_files": {
        "function": cleanup_temp_files_task,
        "args": [24],
        "description": "Delete temp files older than N hours",
        "supports_dry_run": True,
    },
    "cleanup_cache_directories": {
        "function": cleanup_cache_directories_task,
        "args": [],
        "description": "Delete regenerable development cache directories",
        "supports_dry_run": True,
    },
    "cleanup_orphaned_data": {
        "function": cleanup_orphaned_data_task,
        "args": [],
        "description": "Mark stale agent runs older than 1 hour as failed",
        "supports_dry_run": True,
    },
    "check_disk_space": {
        "function": check_disk_space_task,
        "args": [],
        "description": "Check disk usage for /, /tmp, /var/log",
        "supports_dry_run": False,
    },
    "get_database_size": {
        "function": get_database_size_task,
        "args": [],
        "description": "Get database size and top tables",
        "supports_dry_run": False,
    },
    "cleanup_debug_captures": {
        "function": cleanup_debug_captures,
        "args": [7],
        "description": "Delete old DBG-* artifact captures older than N days",
        "supports_dry_run": True,
    },
    "refresh_sec_cik_cache": {
        "function": refresh_sec_cik_cache,
        "args": [],
        "description": "Refresh SEC CIK mappings from EDGAR",
        "supports_dry_run": False,
    },
}


def _resolve_args(task_name: str, kwargs: dict[str, Any]) -> list[int]:
    """Resolve task arguments from defaults plus CLI overrides."""
    default_args = TASK_REGISTRY[task_name]["args"].copy()
    if kwargs.get("days") is not None:
        return [int(kwargs["days"])]
    if kwargs.get("hours") is not None:
        return [int(kwargs["hours"])]
    return default_args


def run_task(
    task_name: str, dry_run: bool = False, verbose: bool = False, **kwargs: Any
) -> dict[str, Any]:
    """Run a single maintenance task."""
    if task_name not in TASK_REGISTRY:
        raise ValueError(f"Unknown task: {task_name}. Available: {', '.join(TASK_REGISTRY.keys())}")

    task_config = TASK_REGISTRY[task_name]
    task_func = task_config["function"]
    task_args = _resolve_args(task_name, kwargs)
    effective_dry_run = dry_run and task_config["supports_dry_run"]

    print(f"\n{'=' * 70}")
    print(f"Task: {task_name}")
    print(f"Description: {task_config['description']}")
    print(f"Args: {task_args}")
    print(f"Mode: {'DRY RUN (no changes)' if effective_dry_run else 'LIVE / READ-ONLY'}")
    print(f"{'=' * 70}\n")

    if task_config["supports_dry_run"]:
        result = task_func(*task_args, dry_run=effective_dry_run)
    else:
        result = task_func(*task_args)

    if verbose:
        print(f"\n{'-' * 70}")
        print("Result:")
        for key, value in result.items():
            print(f"  {key}: {value}")
        print(f"{'-' * 70}\n")

    return result


def run_all_tasks(dry_run: bool = False, verbose: bool = False) -> list[dict[str, Any]]:
    """Run all maintenance tasks in sequence."""
    results = []
    for task_name in TASK_REGISTRY:
        try:
            results.append(run_task(task_name, dry_run=dry_run, verbose=verbose))
        except Exception as exc:
            logger.error("manual_maintenance_task_failed", task_name=task_name, error=str(exc))
            results.append({"task": task_name, "success": False, "error": str(exc)})
    return results


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Manual maintenance task runner")
    parser.add_argument("--task", choices=sorted(TASK_REGISTRY.keys()), help="Run one maintenance task")
    parser.add_argument("--all", action="store_true", help="Run all maintenance tasks in sequence")
    parser.add_argument("--dry-run", action="store_true", help="Preview work without making changes")
    parser.add_argument("--verbose", action="store_true", help="Print detailed task output")
    parser.add_argument("--days", type=int, help="Override retention period in days")
    parser.add_argument("--hours", type=int, help="Override retention period in hours")
    args = parser.parse_args()

    if not args.task and not args.all:
        parser.print_help()
        return 1

    if args.task and args.all:
        parser.error("Choose either --task or --all")

    if args.task:
        run_task(
            args.task,
            dry_run=args.dry_run,
            verbose=args.verbose,
            days=args.days,
            hours=args.hours,
        )
        return 0

    run_all_tasks(dry_run=args.dry_run, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
