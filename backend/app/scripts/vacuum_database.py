#!/usr/bin/env python3
"""Vacuum and optimize PostgreSQL database tables.

This script runs VACUUM ANALYZE on database tables to reclaim space,
update statistics, and optimize query performance.

Usage:
    python -m app.scripts.vacuum_database --dry-run
    python -m app.scripts.vacuum_database
    python -m app.scripts.vacuum_database --tables news_headlines day_bars
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


def get_table_size(conn: Any, table_name: str) -> float:
    """Get table size in MB.

    Args:
        conn: Database connection
        table_name: Name of table

    Returns:
        Size in MB
    """
    result = conn.execute(
        """
        SELECT pg_total_relation_size(?) / (1024.0 * 1024.0) as size_mb
        """,
        [table_name],
    ).fetchone()

    return round(result[0], 2) if result else 0.0


def get_all_tables(conn: Any) -> list[str]:
    """Get list of all user tables in public schema.

    Args:
        conn: Database connection

    Returns:
        List of table names
    """
    result = conn.execute(
        """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
        """
    ).fetchall()

    return [row[0] for row in result]


def validate_table_exists(conn: Any, table_name: str) -> None:
    """Validate that a table exists in pg_tables before vacuum.

    This prevents SQL injection by ensuring the table_name parameter
    matches an actual table in the database before using it in VACUUM.

    Args:
        conn: Database connection
        table_name: Name of table to validate

    Raises:
        ValueError: If table does not exist in public schema
    """
    result = conn.execute(
        """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public' AND tablename = ?
        """,
        [table_name],
    ).fetchone()

    if not result:
        raise ValueError(
            f"Table '{table_name}' does not exist in public schema. "
            "Use --tables to specify valid tables or omit to vacuum all tables."
        )


def vacuum_database(tables: list[str] | None = None, dry_run: bool = False) -> dict[str, Any]:
    """Run VACUUM ANALYZE on database tables.

    Args:
        tables: List of table names to vacuum (None = all tables)
        dry_run: If True, only show what would be done

    Returns:
        Dict with summary: tables processed, space reclaimed
    """
    logger.info("vacuum_database_started", tables=tables, dry_run=dry_run)

    conn_mgr = get_connection_manager()
    results = []
    total_before_mb = 0.0
    total_after_mb = 0.0

    try:
        with conn_mgr.connection() as conn:
            # Get list of tables to vacuum
            if tables is None:
                tables = get_all_tables(conn)
                logger.info("vacuum_all_tables", count=len(tables))
            else:
                logger.info("vacuum_specified_tables", tables=tables)

            # Process each table
            for table_name in tables:
                logger.info("vacuum_table_started", table=table_name)

                # Validate table exists before using in SQL (prevents SQL injection)
                validate_table_exists(conn, table_name)

                # Get size before
                before_mb = get_table_size(conn, table_name)
                total_before_mb += before_mb

                if not dry_run:
                    # Run VACUUM ANALYZE (PostgreSQL specific)
                    # Note: VACUUM cannot run inside a transaction block
                    conn.execute("COMMIT")  # Ensure no active transaction
                    # validated: table from pg_tables
                    conn.execute(f"VACUUM ANALYZE {table_name}")
                    logger.info("vacuum_table_completed", table=table_name)
                else:
                    logger.info("vacuum_table_dry_run", table=table_name)

                # Get size after
                after_mb = get_table_size(conn, table_name)
                total_after_mb += after_mb

                reclaimed_mb = before_mb - after_mb

                results.append(
                    {
                        "table": table_name,
                        "before_mb": before_mb,
                        "after_mb": after_mb,
                        "reclaimed_mb": round(reclaimed_mb, 2),
                    }
                )

                logger.info(
                    "vacuum_table_result",
                    table=table_name,
                    before_mb=before_mb,
                    after_mb=after_mb,
                    reclaimed_mb=reclaimed_mb,
                )

            total_reclaimed_mb = round(total_before_mb - total_after_mb, 2)

            summary = {
                "tables": results,
                "total_before_mb": round(total_before_mb, 2),
                "total_after_mb": round(total_after_mb, 2),
                "total_reclaimed_mb": total_reclaimed_mb,
                "dry_run": dry_run,
                "tables_processed": len(results),
            }

            logger.info("vacuum_database_completed", summary=summary)
            return summary

    except Exception as e:
        logger.error("vacuum_database_error", error=str(e), exc_info=True)
        raise


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Vacuum and optimize PostgreSQL database tables",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview vacuum operation (dry-run mode)
  python -m app.scripts.vacuum_database --dry-run

  # Vacuum all tables
  python -m app.scripts.vacuum_database

  # Vacuum specific tables
  python -m app.scripts.vacuum_database --tables news_headlines day_bars
        """,
    )

    parser.add_argument(
        "--tables",
        nargs="+",
        help="Specific tables to vacuum (default: all tables)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be done without actually vacuuming",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    try:
        result = vacuum_database(tables=args.tables, dry_run=args.dry_run)

        # Print JSON summary to stdout for programmatic use
        print(json.dumps(result, indent=2))

        return 0

    except Exception as e:
        logger.error("vacuum_script_failed", error=str(e), exc_info=True)
        print(json.dumps({"error": str(e)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
