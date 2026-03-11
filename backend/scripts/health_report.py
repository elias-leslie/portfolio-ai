#!/usr/bin/env python3
"""Health report generator for capabilities and maintenance surfaces.

Runs after capabilities scan (03:15 UTC) to generate health summary.
Outputs to logs and JSON file for monitoring.

Usage:
    python backend/scripts/health_report.py

Scheduled:
    Runs daily at 03:15 UTC via Hatchet (after capability scan)
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.logging_config import get_logger
from app.storage.connection import ConnectionManager

logger = get_logger(__name__)


def generate_health_report() -> dict[str, Any]:
    """Generate health report from latest capability scan.

    Returns:
        Dict with health summary, orphaned/legacy capability lists

    Output structure:
        {
            "generated_at": "2025-11-13T15:30:00Z",
            "total_capabilities": 71,
            "by_type": {
                "database": {"active": 35, "orphaned": 3, "legacy": 2, "suspect": 2},
                "celery": {"active": 11, "orphaned": 1, "legacy": 0, "suspect": 1},
                "api": {"active": 14, "orphaned": 1, "legacy": 0, "suspect": 1}
            },
            "by_status": {
                "active": 60,
                "orphaned": 5,
                "legacy": 2,
                "suspect": 4
            },
            "orphaned": [
                {"type": "database", "name": "unused_table", "row_count": 12},
                {"type": "celery", "name": "experimental_task", "schedule": null},
                ...
            ],
            "maintenance": {
                "stale_running": 1,
                "recent_failures": 2
            },
            "stale_maintenance_runs": [
                {"task_name": "cleanup_debug_captures", "started_at": "..."}
            ],
            "recent_maintenance_failures": [
                {"task_name": "vacuum_database_task", "started_at": "...", "status": "error"}
            ],
            "legacy": [
                {"type": "database", "name": "old_cache", "last_update": "2024-10-01"},
                ...
            ],
            "suspect": [
                {"type": "celery", "name": "flaky_task", "success_rate": 45},
                ...
            ]
        }
    """
    conn_mgr = ConnectionManager()

    try:
        with conn_mgr.connection() as conn:
            # Initialize summary structure
            summary = {
                "generated_at": datetime.now(UTC).isoformat(),
                "total_capabilities": 0,
                "by_type": {
                    "database": {"active": 0, "orphaned": 0, "legacy": 0, "suspect": 0},
                    "celery": {"active": 0, "orphaned": 0, "legacy": 0, "suspect": 0},
                    "api": {"active": 0, "orphaned": 0, "legacy": 0, "suspect": 0},
                },
                "by_status": {"active": 0, "orphaned": 0, "legacy": 0, "suspect": 0},
                "maintenance": {"stale_running": 0, "recent_failures": 0},
                "stale_maintenance_runs": [],
                "recent_maintenance_failures": [],
                "orphaned": [],
                "legacy": [],
                "suspect": [],
            }

            # Query db_capabilities
            db_query = """
                SELECT health_status, COUNT(*) as count
                FROM db_capabilities
                WHERE health_status IS NOT NULL
                GROUP BY health_status
            """
            result = conn.execute(db_query)
            for row in result.fetchall():
                health_status_val = str(row[0])
                count_val = int(row[1]) if row[1] is not None else 0
                summary["by_type"]["database"][health_status_val] = count_val  # type: ignore[index]
                summary["by_status"][health_status_val] += count_val  # type: ignore[index]
                summary["total_capabilities"] += count_val  # type: ignore[operator]

            # Get orphaned/legacy/suspect database tables
            db_detail_query = """
                SELECT table_name, health_status, row_count, days_since_update, freshness_status
                FROM db_capabilities
                WHERE health_status IN ('orphaned', 'legacy', 'suspect')
                ORDER BY health_status, table_name
            """
            result = conn.execute(db_detail_query)
            for row in result.fetchall():
                table_name_val = str(row[0])
                health_status_val = str(row[1])
                row_count_val = int(row[2]) if row[2] is not None else 0
                days_since_val = int(row[3]) if row[3] is not None else None
                freshness_val = str(row[4])
                detail = {
                    "type": "database",
                    "name": table_name_val,
                    "row_count": row_count_val,
                    "days_since_update": days_since_val,
                    "freshness_status": freshness_val,
                }
                summary[health_status_val].append(detail)  # type: ignore[attr-defined]

            # Query celery_capabilities
            celery_query = """
                SELECT health_status, COUNT(*) as count
                FROM celery_capabilities
                WHERE health_status IS NOT NULL
                GROUP BY health_status
            """
            result = conn.execute(celery_query)
            for row in result.fetchall():
                health_status_val = str(row[0])
                count_val = int(row[1]) if row[1] is not None else 0
                summary["by_type"]["celery"][health_status_val] = count_val  # type: ignore[index]
                summary["by_status"][health_status_val] += count_val  # type: ignore[index]
                summary["total_capabilities"] += count_val  # type: ignore[operator]

            # Get orphaned/legacy/suspect celery tasks
            celery_detail_query = """
                SELECT task_name, health_status, schedule_description, success_rate_pct, last_run_at
                FROM celery_capabilities
                WHERE health_status IN ('orphaned', 'legacy', 'suspect')
                ORDER BY health_status, task_name
            """
            result = conn.execute(celery_detail_query)
            for row in result.fetchall():
                task_name_val = str(row[0])
                health_status_val = str(row[1])
                schedule_val = row[2]
                success_rate_val = row[3]
                last_run_raw = row[4]
                last_run_iso: str | None = None
                if last_run_raw is not None and hasattr(last_run_raw, "isoformat"):
                    last_run_iso = last_run_raw.isoformat()
                detail = {
                    "type": "celery",
                    "name": task_name_val,
                    "schedule": schedule_val,
                    "success_rate_pct": success_rate_val,
                    "last_run_at": last_run_iso,
                }
                summary[health_status_val].append(detail)  # type: ignore[attr-defined]

            # Query api_capabilities
            api_query = """
                SELECT health_status, COUNT(*) as count
                FROM api_capabilities
                WHERE health_status IS NOT NULL
                GROUP BY health_status
            """
            result = conn.execute(api_query)
            for row in result.fetchall():
                health_status_val = str(row[0])
                count_val = int(row[1]) if row[1] is not None else 0
                summary["by_type"]["api"][health_status_val] = count_val  # type: ignore[index]
                summary["by_status"][health_status_val] += count_val  # type: ignore[index]
                summary["total_capabilities"] += count_val  # type: ignore[operator]

            # Get orphaned/legacy/suspect API endpoints
            api_detail_query = """
                SELECT endpoint_path, http_method, health_status, function_name
                FROM api_capabilities
                WHERE health_status IN ('orphaned', 'legacy', 'suspect')
                ORDER BY health_status, endpoint_path
            """
            result = conn.execute(api_detail_query)
            for row in result.fetchall():
                endpoint_val = str(row[0])
                method_val = str(row[1])
                health_status_val = str(row[2])
                function_val = str(row[3])
                detail = {
                    "type": "api",
                    "name": f"{method_val} {endpoint_val}",
                    "function_name": function_val,
                }
                summary[health_status_val].append(detail)  # type: ignore[attr-defined]

            stale_runs_query = """
                SELECT task_name, started_at
                FROM maintenance_log
                WHERE status = 'running'
                  AND started_at < NOW() - INTERVAL '2 hours'
                ORDER BY started_at ASC
                LIMIT 10
            """
            result = conn.execute(stale_runs_query)
            stale_runs = [
                {
                    "task_name": str(row[0]),
                    "started_at": row[1].isoformat() if row[1] is not None else None,
                }
                for row in result.fetchall()
            ]
            summary["stale_maintenance_runs"] = stale_runs
            summary["maintenance"]["stale_running"] = len(stale_runs)  # type: ignore[index]

            recent_failures_query = """
                SELECT task_name, started_at, status
                FROM maintenance_log
                WHERE status IN ('error', 'failed')
                  AND started_at > NOW() - INTERVAL '24 hours'
                ORDER BY started_at DESC
                LIMIT 10
            """
            result = conn.execute(recent_failures_query)
            recent_failures = [
                {
                    "task_name": str(row[0]),
                    "started_at": row[1].isoformat() if row[1] is not None else None,
                    "status": str(row[2]),
                }
                for row in result.fetchall()
            ]
            summary["recent_maintenance_failures"] = recent_failures
            summary["maintenance"]["recent_failures"] = len(recent_failures)  # type: ignore[index]

            logger.info(
                "health_report_generated",
                total=summary["total_capabilities"],
                active=summary["by_status"]["active"],  # type: ignore[index]
                orphaned=summary["by_status"]["orphaned"],  # type: ignore[index]
                legacy=summary["by_status"]["legacy"],  # type: ignore[index]
                suspect=summary["by_status"]["suspect"],  # type: ignore[index]
                stale_maintenance_runs=summary["maintenance"]["stale_running"],  # type: ignore[index]
                recent_maintenance_failures=summary["maintenance"]["recent_failures"],  # type: ignore[index]
            )

            return summary

    except Exception as e:
        logger.error("health_report_generation_failed", error=str(e))
        raise


def save_health_report(report: dict[str, Any], output_path: Path | None = None) -> None:
    """Save health report to JSON file.

    Args:
        report: Health report dict from generate_health_report()
        output_path: Optional custom output path (default: /var/log/portfolio-ai/health-report.json)
    """
    if output_path is None:
        output_path = Path("/var/log/portfolio-ai/health-report.json")

    try:
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write JSON with pretty formatting
        output_path.write_text(json.dumps(report, indent=2))

        logger.info(
            "health_report_saved", path=str(output_path), size_bytes=output_path.stat().st_size
        )

    except Exception as e:
        logger.error("health_report_save_failed", error=str(e), path=str(output_path))
        raise


def print_health_summary(report: dict[str, Any]) -> None:
    """Print human-readable health summary to stdout.

    Args:
        report: Health report dict from generate_health_report()
    """
    print(f"\n{'=' * 80}")
    print(f"System Capabilities Health Report - {report['generated_at']}")
    print(f"{'=' * 80}\n")

    print(f"Total Capabilities: {report['total_capabilities']}\n")

    print("By Type:")
    for cap_type, counts in report["by_type"].items():
        total = sum(counts.values())
        label = "Scheduled" if cap_type == "celery" else cap_type.capitalize()
        print(f"  {label}: {total}")
        for status, count in counts.items():
            if count > 0:
                print(f"    - {status}: {count}")
    print()

    print("By Status:")
    for status, count in report["by_status"].items():
        if count > 0:
            print(f"  {status}: {count}")
    print()

    maintenance = report.get("maintenance", {})
    if maintenance:
        print("Maintenance:")
        print(f"  stale running: {maintenance.get('stale_running', 0)}")
        print(f"  recent failures: {maintenance.get('recent_failures', 0)}")
        print()

    # Show problematic capabilities
    if report["orphaned"]:
        print(f"\nOrphaned Capabilities ({len(report['orphaned'])}):")
        for item in report["orphaned"][:10]:  # Show first 10
            print(f"  - [{item['type']}] {item['name']}")
        if len(report["orphaned"]) > 10:
            print(f"  ... and {len(report['orphaned']) - 10} more")

    if report["legacy"]:
        print(f"\nLegacy Capabilities ({len(report['legacy'])}):")
        for item in report["legacy"][:10]:  # Show first 10
            print(f"  - [{item['type']}] {item['name']}")
        if len(report["legacy"]) > 10:
            print(f"  ... and {len(report['legacy']) - 10} more")

    if report["suspect"]:
        print(f"\nSuspect Capabilities ({len(report['suspect'])}):")
        for item in report["suspect"][:10]:  # Show first 10
            print(f"  - [{item['type']}] {item['name']}")
        if len(report["suspect"]) > 10:
            print(f"  ... and {len(report['suspect']) - 10} more")

    stale_runs = report.get("stale_maintenance_runs", [])
    if stale_runs:
        print(f"\nStale Maintenance Runs ({len(stale_runs)}):")
        for item in stale_runs[:10]:
            print(f"  - {item['task_name']} since {item['started_at']}")

    recent_failures = report.get("recent_maintenance_failures", [])
    if recent_failures:
        print(f"\nRecent Maintenance Failures ({len(recent_failures)}):")
        for item in recent_failures[:10]:
            print(f"  - {item['task_name']} ({item['status']}) at {item['started_at']}")

    print(f"\n{'=' * 80}\n")


def main() -> None:
    """Main entry point for health report script."""
    try:
        # Generate report
        report = generate_health_report()

        # Save to JSON file
        save_health_report(report)

        # Print summary to stdout
        print_health_summary(report)

        # Exit with status based on health
        orphaned_count = report["by_status"]["orphaned"]
        legacy_count = report["by_status"]["legacy"]
        stale_running_count = report.get("maintenance", {}).get("stale_running", 0)

        if legacy_count > 0:
            logger.warning(
                "health_report_legacy_found",
                count=legacy_count,
                message="Legacy capabilities detected - review required",
            )
            sys.exit(1)  # Non-zero exit for monitoring systems

        if orphaned_count > 5:
            logger.warning(
                "health_report_many_orphaned",
                count=orphaned_count,
                message="High number of orphaned capabilities",
            )

        if stale_running_count > 0:
            logger.warning(
                "health_report_stale_maintenance_runs",
                count=stale_running_count,
                message="Maintenance tasks appear stuck in running state",
            )

    except Exception as e:
        logger.error("health_report_failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
