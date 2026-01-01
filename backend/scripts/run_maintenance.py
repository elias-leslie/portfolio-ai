#!/usr/bin/env python3
"""Manual maintenance task runner with dry-run support.

This script allows you to manually run maintenance tasks for testing,
dry-run previews, or custom retention periods.

Usage:
    # Preview what would be cleaned (no changes made)
    python scripts/run_maintenance.py --task cleanup_old_news --dry-run

    # Run specific task with custom retention
    python scripts/run_maintenance.py --task cleanup_old_news --days 60

    # Run all tasks (full maintenance cycle)
    python scripts/run_maintenance.py --all

    # Run with verbose output
    python scripts/run_maintenance.py --task vacuum_database --verbose

Available tasks:
    - vacuum_database: VACUUM ANALYZE all tables
    - cleanup_old_news: Delete news older than N days
    - cleanup_old_agent_runs: Delete agent runs older than N days
    - cleanup_old_logs: Delete log files older than N days
    - cleanup_temp_files: Delete temp files older than N hours
    - cleanup_orphaned_data: Remove orphaned records
    - check_disk_space: Check disk usage
    - get_database_size: Get database and table sizes
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Any

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.logging_config import get_logger  # noqa: E402
from app.storage.connection import get_connection_manager  # noqa: E402
from app.tasks.cleanup import (  # noqa: E402
    check_disk_space_task,
    cleanup_old_logs_task,
    cleanup_temp_files_task,
)
from app.tasks.maintenance_tasks import (  # noqa: E402
    cleanup_old_agent_runs_task,
    cleanup_old_news_task,
    cleanup_orphaned_data_task,
    get_database_size_task,
    vacuum_database_task,
)

logger = get_logger(__name__)

# Task registry: Maps task names to functions and their default args
TASK_REGISTRY = {
    "vacuum_database": {
        "function": vacuum_database_task,
        "args": [],
        "description": "VACUUM ANALYZE all database tables",
    },
    "cleanup_old_news": {
        "function": cleanup_old_news_task,
        "args": [90],  # days
        "description": "Delete news articles older than N days (default: 90)",
    },
    "cleanup_old_agent_runs": {
        "function": cleanup_old_agent_runs_task,
        "args": [30],  # days
        "description": "Delete agent runs older than N days (default: 30)",
    },
    "cleanup_old_logs": {
        "function": cleanup_old_logs_task,
        "args": [7],  # days
        "description": "Delete log files older than N days (default: 7)",
    },
    "cleanup_temp_files": {
        "function": cleanup_temp_files_task,
        "args": [24],  # hours
        "description": "Delete temp files older than N hours (default: 24)",
    },
    "cleanup_orphaned_data": {
        "function": cleanup_orphaned_data_task,
        "args": [],
        "description": "Remove orphaned records (referential integrity cleanup)",
    },
    "check_disk_space": {
        "function": check_disk_space_task,
        "args": [],
        "description": "Check disk usage for /, /tmp, /var/log",
    },
    "get_database_size": {
        "function": get_database_size_task,
        "args": [],
        "description": "Get database size and top 10 largest tables",
    },
}


class MockCeleryRequest:
    """Mock Celery request for manual task execution."""

    def __init__(self) -> None:
        self.id = f"manual-{dt.datetime.now(dt.UTC).strftime('%Y%m%d%H%M%S')}"


def run_task(
    task_name: str, dry_run: bool = False, verbose: bool = False, **kwargs: Any
) -> dict[str, Any]:
    """Run a single maintenance task.

    Args:
        task_name: Name of the task to run
        dry_run: If True, preview what would be done without making changes
        verbose: If True, print detailed output
        **kwargs: Task-specific arguments (e.g., days, hours)

    Returns:
        Result dictionary from task execution
    """
    if task_name not in TASK_REGISTRY:
        raise ValueError(f"Unknown task: {task_name}. Available: {', '.join(TASK_REGISTRY.keys())}")

    task_config = TASK_REGISTRY[task_name]
    task_func = task_config["function"]
    default_args = task_config["args"].copy()

    # Override default args with provided kwargs
    if "days" in kwargs and kwargs["days"] is not None:
        default_args = [kwargs["days"]]
    elif "hours" in kwargs and kwargs["hours"] is not None:
        default_args = [kwargs["hours"]]

    print(f"\n{'=' * 70}")
    print(f"Task: {task_name}")
    print(f"Description: {task_config['description']}")
    print(f"Args: {default_args}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (changes will be made)'}")
    print(f"{'=' * 70}\n")

    if dry_run:
        # For dry run, we'll query what WOULD be affected
        result = _dry_run_preview(task_name, default_args, verbose)
    else:
        # Create mock request object for Celery task
        mock_request = MockCeleryRequest()

        # Execute task (need to pass self/request for bind=True tasks)
        # Most tasks use self.request.id, so we pass mock request as self
        class TaskContext:
            request = mock_request

        result = task_func(TaskContext(), *default_args)

    if verbose:
        print(f"\n{'-' * 70}")
        print("Result:")
        for key, value in result.items():
            print(f"  {key}: {value}")
        print(f"{'-' * 70}\n")

    return result


def _dry_run_preview(task_name: str, args: list[Any], verbose: bool) -> dict[str, Any]:
    """Preview what would be affected by a task (dry run).

    Args:
        task_name: Name of the task
        args: Task arguments
        verbose: If True, print detailed information

    Returns:
        Dictionary with preview information
    """
    storage = get_connection_manager()

    if task_name == "cleanup_old_news":
        days = args[0]
        cutoff_date = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)

        with storage.connection() as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM news_cache WHERE fetched_at < %s",
                [cutoff_date],
            ).fetchone()
            count = result[0] if result else 0

            if verbose:
                # Show sample of articles that would be deleted
                sample = conn.execute(
                    """
                    SELECT symbol, headline, fetched_at
                    FROM news_cache
                    WHERE fetched_at < %s
                    ORDER BY fetched_at
                    LIMIT 5
                    """,
                    [cutoff_date],
                ).fetchall()

                print(f"\nWould delete {count} news articles older than {cutoff_date.date()}")
                if sample:
                    print("\nSample (first 5):")
                    for symbol, headline, fetched_at in sample:
                        print(f"  - {symbol}: {headline[:60]}... ({fetched_at.date()})")

        return {
            "task": task_name,
            "dry_run": True,
            "would_delete": count,
            "cutoff_date": cutoff_date.isoformat(),
            "retention_days": days,
        }

    if task_name == "cleanup_old_agent_runs":
        days = args[0]
        cutoff_date = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)

        with storage.connection() as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM agent_runs WHERE created_at < %s",
                [cutoff_date],
            ).fetchone()
            count = result[0] if result else 0

            if verbose:
                # Show sample of runs that would be deleted
                sample = conn.execute(
                    """
                    SELECT agent_name, status, created_at
                    FROM agent_runs
                    WHERE created_at < %s
                    ORDER BY created_at
                    LIMIT 5
                    """,
                    [cutoff_date],
                ).fetchall()

                print(f"\nWould delete {count} agent runs older than {cutoff_date.date()}")
                if sample:
                    print("\nSample (first 5):")
                    for agent_name, status, created_at in sample:
                        print(f"  - {agent_name} ({status}): {created_at.date()}")

        return {
            "task": task_name,
            "dry_run": True,
            "would_delete": count,
            "cutoff_date": cutoff_date.isoformat(),
            "retention_days": days,
        }

    if task_name == "vacuum_database":
        with storage.connection() as conn:
            # Get table stats
            result = conn.execute(
                """
                SELECT
                    schemaname,
                    tablename,
                    n_dead_tup,
                    n_live_tup,
                    last_vacuum,
                    last_autovacuum
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                ORDER BY n_dead_tup DESC
                LIMIT 10
                """
            ).fetchall()

            if verbose:
                print("\nTop 10 tables by dead tuples (candidates for VACUUM):")
                print(f"{'Table':<30} {'Dead':>10} {'Live':>10} {'Last Vacuum':<20}")
                print("-" * 72)
                for _schema, table, dead, live, vac, autovac in result:
                    last_vac = vac or autovac or "Never"
                    if isinstance(last_vac, dt.datetime):
                        last_vac = last_vac.strftime("%Y-%m-%d %H:%M")
                    print(f"{table:<30} {dead:>10,} {live:>10,} {last_vac!s:<20}")

        return {
            "task": task_name,
            "dry_run": True,
            "tables_to_vacuum": len(result),
            "note": "VACUUM will reclaim space and update statistics",
        }

    return {
        "task": task_name,
        "dry_run": True,
        "note": f"Dry run not implemented for {task_name} (would execute normally)",
    }


def run_all_tasks(dry_run: bool = False, verbose: bool = False) -> dict[str, Any]:
    """Run all maintenance tasks in sequence.

    Args:
        dry_run: If True, preview what would be done
        verbose: If True, print detailed output

    Returns:
        Dictionary with results for each task
    """
    print(f"\n{'=' * 70}")
    print("Running ALL Maintenance Tasks")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"{'=' * 70}\n")

    results = {}
    for task_name in TASK_REGISTRY:
        try:
            result = run_task(task_name, dry_run=dry_run, verbose=verbose)
            results[task_name] = result
        except Exception as e:
            logger.error(f"Task {task_name} failed", error=str(e))
            results[task_name] = {"error": str(e), "success": False}

    print(f"\n{'=' * 70}")
    print(
        f"Summary: {len([r for r in results.values() if r.get('success', True)])} / {len(results)} tasks succeeded"
    )
    print(f"{'=' * 70}\n")

    return results


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manual maintenance task runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--task",
        choices=list(TASK_REGISTRY.keys()),
        help="Task to run (use --all to run all tasks)",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all maintenance tasks in sequence",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be done without making changes",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed output",
    )

    parser.add_argument(
        "--days",
        type=int,
        help="Custom retention period in days (for cleanup tasks)",
    )

    parser.add_argument(
        "--hours",
        type=int,
        help="Custom retention period in hours (for temp file cleanup)",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List available tasks and exit",
    )

    args = parser.parse_args()

    # List tasks and exit
    if args.list:
        print("\nAvailable maintenance tasks:\n")
        for task_name, config in TASK_REGISTRY.items():
            print(f"  {task_name}")
            print(f"    {config['description']}")
            print()
        return 0

    # Validate args
    if not args.task and not args.all:
        parser.error("Must specify --task or --all")

    if args.task and args.all:
        parser.error("Cannot specify both --task and --all")

    # Run tasks
    try:
        if args.all:
            run_all_tasks(dry_run=args.dry_run, verbose=args.verbose)
        else:
            run_task(
                args.task,
                dry_run=args.dry_run,
                verbose=args.verbose,
                days=args.days,
                hours=args.hours,
            )

        return 0

    except Exception as e:
        logger.error("Maintenance script failed", error=str(e))
        print(f"\nERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
