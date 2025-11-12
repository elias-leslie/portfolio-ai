#!/usr/bin/env python3
"""Validate database data integrity and consistency.

This script checks for:
- Orphaned records (rows referencing non-existent foreign keys)
- Missing foreign key relationships
- Data consistency violations
- Invalid or inconsistent data states

Usage:
    python -m app.scripts.validate_data_integrity --dry-run
    python -m app.scripts.validate_data_integrity --fix
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path for imports when run as script
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)


def check_orphaned_watchlist_snapshots(conn: Any) -> dict[str, Any]:
    """Check for watchlist snapshots without corresponding watchlist items.

    Args:
        conn: Database connection

    Returns:
        Dict with check results
    """
    result = conn.execute(
        """
        SELECT COUNT(*) as orphaned_count
        FROM watchlist_snapshots ws
        WHERE NOT EXISTS (
            SELECT 1 FROM watchlist_items wi
            WHERE wi.symbol = ws.symbol
        )
        """
    ).fetchone()

    orphaned_count = result[0] if result else 0

    if orphaned_count > 0:
        logger.warning(
            "orphaned_watchlist_snapshots",
            count=orphaned_count,
        )

    return {
        "table": "watchlist_snapshots",
        "check": "orphaned_records",
        "issue_count": orphaned_count,
        "severity": "warning" if orphaned_count > 0 else "ok",
        "description": f"Snapshots without corresponding watchlist items: {orphaned_count}",
    }


def check_orphaned_price_cache(conn: Any) -> dict[str, Any]:
    """Check for price cache entries without corresponding positions or watchlist items.

    Args:
        conn: Database connection

    Returns:
        Dict with check results
    """
    result = conn.execute(
        """
        SELECT COUNT(*) as orphaned_count
        FROM price_cache pc
        WHERE NOT EXISTS (
            SELECT 1 FROM portfolio_positions pp WHERE pp.ticker = pc.ticker
        )
        AND NOT EXISTS (
            SELECT 1 FROM watchlist_items wi WHERE wi.symbol = pc.ticker
        )
        """
    ).fetchone()

    orphaned_count = result[0] if result else 0

    if orphaned_count > 0:
        logger.warning(
            "orphaned_price_cache",
            count=orphaned_count,
        )

    return {
        "table": "price_cache",
        "check": "orphaned_records",
        "issue_count": orphaned_count,
        "severity": "warning" if orphaned_count > 0 else "ok",
        "description": f"Price cache entries without portfolio or watchlist reference: {orphaned_count}",
    }


def check_missing_reference_cache(conn: Any) -> dict[str, Any]:
    """Check for watchlist items without reference cache entries.

    Args:
        conn: Database connection

    Returns:
        Dict with check results
    """
    result = conn.execute(
        """
        SELECT COUNT(*) as missing_count
        FROM watchlist_items wi
        WHERE NOT EXISTS (
            SELECT 1 FROM reference_cache rc
            WHERE rc.ticker = wi.symbol
        )
        """
    ).fetchone()

    missing_count = result[0] if result else 0

    if missing_count > 0:
        logger.warning(
            "missing_reference_cache",
            count=missing_count,
        )

    return {
        "table": "watchlist_items",
        "check": "missing_reference_cache",
        "issue_count": missing_count,
        "severity": "info" if missing_count > 0 else "ok",
        "description": f"Watchlist items without reference cache: {missing_count}",
    }


def check_null_timestamps(conn: Any) -> dict[str, Any]:
    """Check for records with NULL timestamps that should have values.

    Args:
        conn: Database connection

    Returns:
        Dict with check results
    """
    issues = []

    # Check watchlist_snapshots.last_updated_at
    result = conn.execute(
        """
        SELECT COUNT(*) FROM watchlist_snapshots
        WHERE last_updated_at IS NULL
        """
    ).fetchone()

    if result and result[0] > 0:
        issues.append(
            {
                "table": "watchlist_snapshots",
                "column": "last_updated_at",
                "null_count": result[0],
            }
        )

    # Check news_headlines.published_at
    result = conn.execute(
        """
        SELECT COUNT(*) FROM news_headlines
        WHERE published_at IS NULL
        """
    ).fetchone()

    if result and result[0] > 0:
        issues.append(
            {
                "table": "news_headlines",
                "column": "published_at",
                "null_count": result[0],
            }
        )

    total_issues = sum(issue["null_count"] for issue in issues)

    if total_issues > 0:
        logger.warning("null_timestamp_issues", issues=issues)

    return {
        "check": "null_timestamps",
        "issue_count": total_issues,
        "severity": "error" if total_issues > 0 else "ok",
        "description": f"Records with NULL timestamps: {total_issues}",
        "details": issues,
    }


def check_duplicate_watchlist_items(conn: Any) -> dict[str, Any]:
    """Check for duplicate watchlist entries (same symbol).

    Args:
        conn: Database connection

    Returns:
        Dict with check results
    """
    result = conn.execute(
        """
        SELECT symbol, COUNT(*) as count
        FROM watchlist_items
        GROUP BY symbol
        HAVING COUNT(*) > 1
        """
    ).fetchall()

    duplicates = [{"symbol": row[0], "count": row[1]} for row in result]

    if duplicates:
        logger.warning("duplicate_watchlist_items", duplicates=duplicates)

    return {
        "table": "watchlist_items",
        "check": "duplicate_records",
        "issue_count": len(duplicates),
        "severity": "error" if duplicates else "ok",
        "description": f"Duplicate watchlist entries: {len(duplicates)} symbols",
        "details": duplicates[:10],  # Limit to first 10
    }


def validate_data_integrity(dry_run: bool = True) -> dict[str, Any]:
    """Run all data integrity checks.

    Args:
        dry_run: If True, only report issues without fixing

    Returns:
        Dict with summary of all checks
    """
    logger.info("validate_data_integrity_started", dry_run=dry_run)

    conn_mgr = get_connection_manager()
    checks = []

    try:
        with conn_mgr.connection() as conn:
            # Run all integrity checks
            checks.append(check_orphaned_watchlist_snapshots(conn))
            checks.append(check_orphaned_price_cache(conn))
            checks.append(check_missing_reference_cache(conn))
            checks.append(check_null_timestamps(conn))
            checks.append(check_duplicate_watchlist_items(conn))

            # Count issues by severity
            total_errors = sum(1 for c in checks if c["severity"] == "error")
            total_warnings = sum(1 for c in checks if c["severity"] == "warning")
            total_info = sum(1 for c in checks if c["severity"] == "info")

            summary = {
                "checks_run": len(checks),
                "total_errors": total_errors,
                "total_warnings": total_warnings,
                "total_info": total_info,
                "dry_run": dry_run,
                "checks": checks,
            }

            if total_errors > 0:
                logger.error(
                    "data_integrity_errors_found",
                    errors=total_errors,
                    warnings=total_warnings,
                )
            elif total_warnings > 0:
                logger.warning(
                    "data_integrity_warnings_found",
                    warnings=total_warnings,
                    info=total_info,
                )
            else:
                logger.info(
                    "data_integrity_check_passed",
                    checks=len(checks),
                )

            logger.info("validate_data_integrity_completed", summary=summary)
            return summary

    except Exception as e:
        logger.error("validate_data_integrity_error", error=str(e), exc_info=True)
        raise


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate database data integrity and consistency",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run integrity checks (dry-run mode)
  python -m app.scripts.validate_data_integrity --dry-run

  # Run checks and fix issues (if supported)
  python -m app.scripts.validate_data_integrity --fix
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Only report issues without fixing (default: true)",
    )

    parser.add_argument(
        "--fix",
        action="store_true",
        default=False,
        help="Attempt to fix issues (overrides --dry-run)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # If --fix is specified, disable dry-run
    dry_run = not args.fix if args.fix else args.dry_run

    try:
        result = validate_data_integrity(dry_run=dry_run)

        # Print JSON summary to stdout for programmatic use
        print(json.dumps(result, indent=2))

        # Return exit code based on severity
        if result["total_errors"] > 0:
            return 2  # Errors found
        if result["total_warnings"] > 0:
            return 1  # Warnings found
        return 0  # All checks passed

    except Exception as e:
        logger.error("validate_script_failed", error=str(e), exc_info=True)
        print(json.dumps({"error": str(e)}, indent=2), file=sys.stderr)
        return 3  # Script error


if __name__ == "__main__":
    sys.exit(main())
