#!/usr/bin/env python3
"""Safe database migration runner with dry-run, backup, and rollback support.

Created: 2025-11-10 (Response to Nov 9 deletion incident)
Purpose: Prevent data loss during migrations through comprehensive safety checks

Usage:
    # Dry-run (shows impact, no changes)
    python backend/scripts/migrate.py --dry-run

    # Execute with safety checks
    python backend/scripts/migrate.py --execute

    # Run specific migration
    python backend/scripts/migrate.py --dry-run --migration 018

    # Force (skip confirmations) - USE WITH CAUTION
    python backend/scripts/migrate.py --execute --force
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.logging_config import get_logger
from app.storage.connection import ConnectionManager
from app.storage.migrations import MigrationManager

logger = get_logger(__name__)


class SafeMigrationRunner:
    """Migration runner with safety checks and dry-run support."""

    def __init__(self, connection_mgr: ConnectionManager) -> None:
        """Initialize safe migration runner.

        Args:
            connection_mgr: Database connection manager
        """
        self.conn_mgr = connection_mgr
        self.migration_mgr = MigrationManager(connection_mgr)
        self.migrations_dir = Path(__file__).parent.parent / "migrations"
        self.backup_dir = Path(__file__).parent.parent.parent / "backups"

    def analyze_migration_impact(
        self, sql_content: str
    ) -> dict[str, Any]:
        """Analyze migration SQL for potential impact.

        Args:
            sql_content: SQL migration content

        Returns:
            Dict with impact analysis:
            - is_destructive: bool
            - has_cascade: bool
            - affected_tables: list[str]
            - operations: list[str]
            - estimated_rows: dict[str, int] (if possible)
        """
        analysis = {
            "is_destructive": False,
            "has_cascade": False,
            "affected_tables": [],
            "operations": [],
            "warnings": [],
        }

        # Convert to uppercase for case-insensitive matching
        sql_upper = sql_content.upper()

        # Check for destructive operations
        destructive_ops = ["DROP TABLE", "DELETE FROM", "TRUNCATE", "ALTER TABLE.*DROP"]
        for op in destructive_ops:
            if re.search(op, sql_upper):
                analysis["is_destructive"] = True
                analysis["operations"].append(op.replace(".*", ""))

        # Check for CASCADE
        if "CASCADE" in sql_upper:
            analysis["has_cascade"] = True
            analysis["warnings"].append(
                "⚠️  CASCADE detected - deletions may affect multiple tables"
            )

        # Extract affected tables
        # Pattern: FROM <table> or TABLE <table> or INTO <table>
        table_patterns = [
            r"FROM\s+([a-z_][a-z0-9_]*)",
            r"TABLE\s+IF\s+EXISTS\s+([a-z_][a-z0-9_]*)",
            r"TABLE\s+([a-z_][a-z0-9_]*)",
            r"INTO\s+([a-z_][a-z0-9_]*)",
            r"UPDATE\s+([a-z_][a-z0-9_]*)",
        ]

        for pattern in table_patterns:
            matches = re.findall(pattern, sql_content, re.IGNORECASE)
            analysis["affected_tables"].extend(matches)

        # Deduplicate tables
        analysis["affected_tables"] = sorted(set(analysis["affected_tables"]))

        # Add warnings for specific tables
        critical_tables = ["watchlist_items", "watchlist_snapshots", "portfolio_positions"]
        for table in analysis["affected_tables"]:
            if table in critical_tables and analysis["is_destructive"]:
                analysis["warnings"].append(
                    f"🔴 CRITICAL: Destructive operation on {table}"
                )

        return analysis

    def estimate_row_counts(self, tables: list[str]) -> dict[str, int]:
        """Estimate current row counts for affected tables.

        Args:
            tables: List of table names

        Returns:
            Dict mapping table name to row count
        """
        counts = {}

        with self.conn_mgr.connection() as conn:
            for table in tables:
                try:
                    result = conn.execute(
                        f"SELECT COUNT(*) as count FROM {table}"
                    ).pl()
                    counts[table] = result["count"][0]
                except Exception as e:
                    logger.warning(
                        "failed_to_count_table_rows",
                        table=table,
                        error=str(e),
                    )
                    counts[table] = -1  # Unknown

        return counts

    def create_pre_migration_backup(
        self, version: int, affected_tables: list[str]
    ) -> Path | None:
        """Create pre-migration backup using pg_dump.

        Args:
            version: Migration version number
            affected_tables: List of affected table names

        Returns:
            Path to backup file, or None if backup failed
        """
        # Ensure backup directory exists
        self.backup_dir.mkdir(exist_ok=True)

        # Generate backup filename
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"pre-migration-{version:03d}-{timestamp}.sql"
        backup_path = self.backup_dir / backup_filename

        print(f"\n📦 Creating backup: {backup_path}")

        try:
            # Get database connection parameters
            # Note: This assumes PostgreSQL. Adjust for other databases.
            db_url = os.getenv("DATABASE_URL", "")
            if not db_url:
                print("❌ DATABASE_URL not set, skipping backup")
                return None

            # Parse connection string
            # Format: postgresql://user:pass@host:port/dbname
            match = re.match(
                r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)",
                db_url,
            )
            if not match:
                print(f"❌ Could not parse DATABASE_URL: {db_url}")
                return None

            user, password, host, port, dbname = match.groups()

            # Build pg_dump command
            cmd = [
                "pg_dump",
                "-h", host,
                "-p", port,
                "-U", user,
                "-d", dbname,
                "-f", str(backup_path),
                "--no-owner",
                "--no-acl",
            ]

            # If specific tables affected, backup only those
            if affected_tables:
                for table in affected_tables:
                    cmd.extend(["-t", table])

            # Set password in environment
            env = os.environ.copy()
            env["PGPASSWORD"] = password

            # Run pg_dump
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                print(f"❌ pg_dump failed: {result.stderr}")
                return None

            # Verify backup created
            if not backup_path.exists():
                print("❌ Backup file not created")
                return None

            backup_size = backup_path.stat().st_size
            print(f"✅ Backup created: {backup_size:,} bytes")

            return backup_path

        except Exception as e:
            print(f"❌ Backup failed: {e}")
            return None

    def dry_run_migration(self, version: int | None = None) -> None:
        """Run migration analysis without executing.

        Args:
            version: Specific migration version to analyze, or None for all pending
        """
        print("\n" + "=" * 80)
        print("MIGRATION DRY-RUN (No changes will be made)")
        print("=" * 80)

        # Get pending migrations
        self.migration_mgr._ensure_migrations_table()
        all_migrations = self.migration_mgr._get_migration_files()
        applied_versions = self.migration_mgr._get_applied_migrations()

        pending_migrations = [
            m for m in all_migrations if m[0] not in applied_versions
        ]

        if version is not None:
            pending_migrations = [m for m in pending_migrations if m[0] == version]

        if not pending_migrations:
            print("\n✅ No pending migrations")
            return

        print(f"\n📋 Found {len(pending_migrations)} pending migration(s):\n")

        for version_num, filename, description, sql_content in pending_migrations:
            print(f"{'─' * 80}")
            print(f"Migration {version_num:03d}: {description}")
            print(f"File: {filename}")
            print(f"{'─' * 80}")

            # Analyze impact
            impact = self.analyze_migration_impact(sql_content)

            # Show analysis
            print("\n🔍 Impact Analysis:")
            print(f"  Destructive: {'YES ⚠️' if impact['is_destructive'] else 'No'}")
            print(f"  Has CASCADE: {'YES ⚠️' if impact['has_cascade'] else 'No'}")
            print(f"  Operations: {', '.join(impact['operations']) if impact['operations'] else 'DDL only'}")

            if impact["affected_tables"]:
                print(f"  Affected tables: {', '.join(impact['affected_tables'])}")

                # Get row counts
                row_counts = self.estimate_row_counts(impact["affected_tables"])
                print("\n📊 Current Row Counts:")
                for table, count in row_counts.items():
                    if count >= 0:
                        print(f"    {table}: {count:,} rows")
                    else:
                        print(f"    {table}: (unknown)")

            # Show warnings
            if impact["warnings"]:
                print("\n⚠️  WARNINGS:")
                for warning in impact["warnings"]:
                    print(f"    {warning}")

            # Show SQL preview
            print("\n📝 SQL Preview (first 20 lines):")
            lines = sql_content.strip().split("\n")[:20]
            for line in lines:
                if line.strip():
                    print(f"    {line}")
            if len(sql_content.strip().split("\n")) > 20:
                print("    ...")

            print()

        print("\n" + "=" * 80)
        print("DRY-RUN COMPLETE")
        print("=" * 80)
        print("\nTo execute migrations, run:")
        print("  python backend/scripts/migrate.py --execute")
        print()

    def execute_migrations(
        self,
        force: bool = False,
        version: int | None = None,
    ) -> None:
        """Execute pending migrations with safety checks.

        Args:
            force: Skip confirmation prompts
            version: Specific migration version, or None for all pending
        """
        print("\n" + "=" * 80)
        print("MIGRATION EXECUTION (Changes WILL be made)")
        print("=" * 80)

        # Run dry-run first
        self.dry_run_migration(version=version)

        # Get pending migrations
        self.migration_mgr._ensure_migrations_table()
        all_migrations = self.migration_mgr._get_migration_files()
        applied_versions = self.migration_mgr._get_applied_migrations()

        pending_migrations = [
            m for m in all_migrations if m[0] not in applied_versions
        ]

        if version is not None:
            pending_migrations = [m for m in pending_migrations if m[0] == version]

        if not pending_migrations:
            return

        # Confirm execution
        if not force:
            print("\n⚠️  WARNING: You are about to execute migrations that will modify the database")
            response = input("\nType 'yes' to proceed: ")
            if response.lower() != "yes":
                print("❌ Aborted")
                return

        # Execute each migration
        for version_num, filename, description, sql_content in pending_migrations:
            print(f"\n{'=' * 80}")
            print(f"Executing Migration {version_num:03d}: {description}")
            print(f"{'=' * 80}")

            # Analyze impact
            impact = self.analyze_migration_impact(sql_content)

            # Create backup if destructive
            if impact["is_destructive"]:
                backup_path = self.create_pre_migration_backup(
                    version_num,
                    impact["affected_tables"],
                )
                if backup_path:
                    print(f"✅ Pre-migration backup: {backup_path}")
                else:
                    if not force:
                        print("\n⚠️  Backup failed. Continue anyway?")
                        response = input("Type 'yes' to continue without backup: ")
                        if response.lower() != "yes":
                            print("❌ Aborted")
                            return

            # Execute migration
            try:
                self.migration_mgr._apply_single_migration(
                    version_num,
                    filename,
                    description,
                    sql_content,
                )
                print(f"✅ Migration {version_num:03d} applied successfully")

            except Exception as e:
                print(f"❌ Migration {version_num:03d} FAILED: {e}")
                print("\n🔄 To rollback, restore from backup:")
                if impact["is_destructive"]:
                    print(f"  psql -d portfolio_ai -f {backup_path}")
                raise

        print("\n" + "=" * 80)
        print("✅ ALL MIGRATIONS COMPLETED SUCCESSFULLY")
        print("=" * 80)


def main() -> None:
    """Main entry point for migration runner."""
    parser = argparse.ArgumentParser(
        description="Safe database migration runner with dry-run and backup support"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze migration impact without executing",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute pending migrations",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompts (use with caution)",
    )
    parser.add_argument(
        "--migration",
        type=int,
        metavar="VERSION",
        help="Run specific migration version only",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.dry_run and not args.execute:
        parser.print_help()
        print("\n❌ Error: Must specify --dry-run or --execute")
        sys.exit(1)

    if args.dry_run and args.execute:
        print("❌ Error: Cannot specify both --dry-run and --execute")
        sys.exit(1)

    # Initialize connection manager
    conn_mgr = ConnectionManager.from_env()

    # Create safe migration runner
    runner = SafeMigrationRunner(conn_mgr)

    # Execute requested action
    try:
        if args.dry_run:
            runner.dry_run_migration(version=args.migration)
        else:
            runner.execute_migrations(force=args.force, version=args.migration)

    except Exception as e:
        logger.error("migration_runner_failed", error=str(e))
        print(f"\n❌ FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
