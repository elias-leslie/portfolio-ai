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

from app.storage.types import DatabaseConnection

# Add parent directory to path for imports when run as script
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)


def check_orphaned_watchlist_snapshots(
    conn: DatabaseConnection, fix: bool = False
) -> dict[str, Any]:
    """Check for watchlist snapshots without corresponding watchlist items.

    Args:
        conn: Database connection
        fix: If True, delete orphaned records

    Returns:
        Dict with check results
    """
    result = conn.execute(
        """
        SELECT COUNT(*) as orphaned_count
        FROM watchlist_snapshots ws
        WHERE NOT EXISTS (
            SELECT 1 FROM watchlist_items wi
            WHERE wi.id = ws.item_id
        )
        """
    ).fetchone()

    orphaned_count: int = result[0] if result and isinstance(result[0], int) else 0
    fixed_count = 0

    if orphaned_count > 0:
        if fix:
            conn.execute(
                """
                DELETE FROM watchlist_snapshots ws
                WHERE NOT EXISTS (
                    SELECT 1 FROM watchlist_items wi
                    WHERE wi.id = ws.item_id
                )
                """
            )
            fixed_count = conn._cursor.rowcount  # type: ignore[attr-defined]
            conn.commit()
            logger.info("fixed_orphaned_watchlist_snapshots", deleted=fixed_count)
        else:
            logger.warning("orphaned_watchlist_snapshots", count=orphaned_count)

    return {
        "table": "watchlist_snapshots",
        "check": "orphaned_records",
        "issue_count": orphaned_count,
        "fixed_count": fixed_count if fix else None,
        "severity": "warning" if orphaned_count > 0 and not fix else "ok",
        "description": f"Snapshots without corresponding watchlist items: {orphaned_count}"
        + (f" (deleted {fixed_count})" if fix and fixed_count else ""),
    }


def check_orphaned_price_cache(conn: DatabaseConnection, fix: bool = False) -> dict[str, Any]:
    """Check for price cache entries without corresponding positions or watchlist items.

    Args:
        conn: Database connection
        fix: If True, delete orphaned records

    Returns:
        Dict with check results
    """
    result = conn.execute(
        """
        SELECT COUNT(*) as orphaned_count
        FROM price_cache pc
        WHERE NOT EXISTS (
            SELECT 1 FROM portfolio_positions pp WHERE pp.symbol = pc.symbol
        )
        AND NOT EXISTS (
            SELECT 1 FROM watchlist_items wi WHERE wi.symbol = pc.symbol
        )
        """
    ).fetchone()

    orphaned_count: int = result[0] if result and isinstance(result[0], int) else 0
    fixed_count = 0

    if orphaned_count > 0:
        if fix:
            conn.execute(
                """
                DELETE FROM price_cache pc
                WHERE NOT EXISTS (
                    SELECT 1 FROM portfolio_positions pp WHERE pp.symbol = pc.symbol
                )
                AND NOT EXISTS (
                    SELECT 1 FROM watchlist_items wi WHERE wi.symbol = pc.symbol
                )
                """
            )
            fixed_count = conn._cursor.rowcount  # type: ignore[attr-defined]
            conn.commit()
            logger.info("fixed_orphaned_price_cache", deleted=fixed_count)
        else:
            logger.warning("orphaned_price_cache", count=orphaned_count)

    return {
        "table": "price_cache",
        "check": "orphaned_records",
        "issue_count": orphaned_count,
        "fixed_count": fixed_count if fix else None,
        "severity": "warning" if orphaned_count > 0 and not fix else "ok",
        "description": f"Price cache entries without portfolio or watchlist reference: {orphaned_count}"
        + (f" (deleted {fixed_count})" if fix and fixed_count else ""),
    }


def check_missing_reference_cache(conn: DatabaseConnection, fix: bool = False) -> dict[str, Any]:
    """Check for watchlist items without reference cache entries.

    Note: This is informational only - missing cache requires data fetch, not deletion.

    Args:
        conn: Database connection
        fix: Not applicable for this check (requires external data fetch)

    Returns:
        Dict with check results
    """
    result = conn.execute(
        """
        SELECT wi.symbol
        FROM watchlist_items wi
        WHERE NOT EXISTS (
            SELECT 1 FROM reference_cache rc
            WHERE rc.symbol = wi.symbol
        )
        """
    ).fetchall()

    missing_symbols = [row[0] for row in result]
    missing_count = len(missing_symbols)

    if missing_count > 0:
        logger.info("missing_reference_cache", count=missing_count, symbols=missing_symbols[:10])

    return {
        "table": "watchlist_items",
        "check": "missing_reference_cache",
        "issue_count": missing_count,
        "fixed_count": None,  # Cannot fix - requires external data fetch
        "severity": "info" if missing_count > 0 else "ok",
        "description": f"Watchlist items without reference cache: {missing_count}"
        + (" (run reference data ingestion to fix)" if missing_count > 0 else ""),
        "details": missing_symbols[:10] if missing_symbols else [],
    }


def check_null_timestamps(conn: DatabaseConnection, fix: bool = False) -> dict[str, Any]:
    """Check for records with NULL timestamps that should have values.

    Args:
        conn: Database connection
        fix: If True, delete records with NULL timestamps

    Returns:
        Dict with check results
    """
    issues: list[dict[str, str | int | None]] = []
    total_fixed = 0

    # Check watchlist_snapshots.fetched_at
    result = conn.execute(
        """
        SELECT COUNT(*) FROM watchlist_snapshots
        WHERE fetched_at IS NULL
        """
    ).fetchone()

    if result and isinstance(result[0], int) and result[0] > 0:
        null_count = result[0]
        fixed = 0
        if fix:
            conn.execute("DELETE FROM watchlist_snapshots WHERE fetched_at IS NULL")
            fixed = conn._cursor.rowcount  # type: ignore[attr-defined]
            conn.commit()
            total_fixed += fixed
        issues.append(
            {
                "table": "watchlist_snapshots",
                "column": "fetched_at",
                "null_count": null_count,
                "fixed": fixed if fix else None,
            }
        )

    # Check news_cache.published_at
    result = conn.execute(
        """
        SELECT COUNT(*) FROM news_cache
        WHERE published_at IS NULL
        """
    ).fetchone()

    if result and isinstance(result[0], int) and result[0] > 0:
        null_count = result[0]
        fixed = 0
        if fix:
            conn.execute("DELETE FROM news_cache WHERE published_at IS NULL")
            fixed = conn._cursor.rowcount  # type: ignore[attr-defined]
            conn.commit()
            total_fixed += fixed
        issues.append(
            {
                "table": "news_cache",
                "column": "published_at",
                "null_count": null_count,
                "fixed": fixed if fix else None,
            }
        )

    total_issues: int = sum(
        issue["null_count"] for issue in issues if isinstance(issue["null_count"], int)
    )

    if total_issues > 0:
        if fix:
            logger.info("fixed_null_timestamps", deleted=total_fixed)
        else:
            logger.warning("null_timestamp_issues", issues=issues)

    return {
        "check": "null_timestamps",
        "issue_count": total_issues,
        "fixed_count": total_fixed if fix else None,
        "severity": "error" if total_issues > 0 and not fix else "ok",
        "description": f"Records with NULL timestamps: {total_issues}"
        + (f" (deleted {total_fixed})" if fix and total_fixed else ""),
        "details": issues,
    }


def check_duplicate_watchlist_items(conn: DatabaseConnection, fix: bool = False) -> dict[str, Any]:
    """Check for duplicate watchlist entries (same symbol).

    Args:
        conn: Database connection
        fix: If True, delete duplicates keeping the most recent entry

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
    fixed_count = 0

    if duplicates and fix:
        # Delete duplicates, keeping the one with highest ID (most recent)
        conn.execute(
            """
            DELETE FROM watchlist_items
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM watchlist_items
                GROUP BY symbol
            )
            AND symbol IN (
                SELECT symbol
                FROM watchlist_items
                GROUP BY symbol
                HAVING COUNT(*) > 1
            )
            """
        )
        fixed_count = conn._cursor.rowcount  # type: ignore[attr-defined]
        conn.commit()
        logger.info("fixed_duplicate_watchlist_items", deleted=fixed_count)
    elif duplicates:
        logger.warning("duplicate_watchlist_items", duplicates=duplicates)

    return {
        "table": "watchlist_items",
        "check": "duplicate_records",
        "issue_count": len(duplicates),
        "fixed_count": fixed_count if fix else None,
        "severity": "error" if duplicates and not fix else "ok",
        "description": f"Duplicate watchlist entries: {len(duplicates)} symbols"
        + (f" (deleted {fixed_count} duplicates)" if fix and fixed_count else ""),
        "details": duplicates[:10],
    }


def validate_data_integrity(dry_run: bool = True) -> dict[str, Any]:
    """Run all data integrity checks and optionally fix issues.

    Args:
        dry_run: If True, only report issues without fixing. If False, fix issues.

    Returns:
        Dict with summary of all checks
    """
    fix = not dry_run
    logger.info("validate_data_integrity_started", dry_run=dry_run, fix=fix)

    conn_mgr = get_connection_manager()
    checks = []

    try:
        with conn_mgr.connection() as conn:
            # Run all integrity checks (with fix=True if not dry_run)
            checks.append(check_orphaned_watchlist_snapshots(conn, fix=fix))
            checks.append(check_orphaned_price_cache(conn, fix=fix))
            checks.append(check_missing_reference_cache(conn, fix=fix))
            checks.append(check_null_timestamps(conn, fix=fix))
            checks.append(check_duplicate_watchlist_items(conn, fix=fix))

            # Count issues by severity
            total_errors = sum(1 for c in checks if c["severity"] == "error")
            total_warnings = sum(1 for c in checks if c["severity"] == "warning")
            total_info = sum(1 for c in checks if c["severity"] == "info")
            total_fixed = sum(c.get("fixed_count", 0) or 0 for c in checks)

            summary = {
                "checks_run": len(checks),
                "total_errors": total_errors,
                "total_warnings": total_warnings,
                "total_info": total_info,
                "total_fixed": total_fixed if fix else None,
                "dry_run": dry_run,
                "checks": checks,
            }

            if fix and total_fixed > 0:
                logger.info(
                    "data_integrity_issues_fixed",
                    fixed=total_fixed,
                    remaining_errors=total_errors,
                    remaining_warnings=total_warnings,
                )
            elif total_errors > 0:
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
