"""Database migration management for portfolio-ai.

This module handles database schema migrations, tracking applied migrations,
and ensuring idempotent execution.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ..logging_config import get_logger

if TYPE_CHECKING:
    from .connection import ConnectionManager

logger = get_logger(__name__)


class MigrationManager:
    """Manages database schema migrations.

    Tracks applied migrations in schema_migrations table and executes
    pending migrations in version order.
    """

    def __init__(self, connection_mgr: ConnectionManager) -> None:
        """Initialize migration manager.

        Args:
            connection_mgr: ConnectionManager instance for database access
        """
        self.connection_mgr = connection_mgr
        self.migrations_dir = Path(__file__).parent.parent.parent / "migrations"

    def _ensure_migrations_table(self) -> None:
        """Ensure schema_migrations table exists."""
        with self.connection_mgr.connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version         INTEGER PRIMARY KEY,
                    description     TEXT NOT NULL,
                    applied_at      TIMESTAMP NOT NULL,
                    checksum        TEXT NOT NULL
                )
            """)
            logger.info("schema_migrations_table_ready")

    def _get_migration_files(self) -> list[tuple[int, str, str, str]]:
        """Get all migration files from migrations directory.

        Returns:
            List of tuples: (version, filename, description, SQL content)
        """
        if not self.migrations_dir.exists():
            logger.info(
                "migrations_dir_not_found",
                path=str(self.migrations_dir),
            )
            return []

        migrations = []

        for filepath in sorted(self.migrations_dir.glob("*.sql")):
            # Parse version from filename: 001_description.sql -> 1
            filename = filepath.name
            try:
                version_str = filename.split("_")[0]
                version = int(version_str)
            except (ValueError, IndexError):
                logger.warning(
                    "invalid_migration_filename",
                    filename=filename,
                    message="Filename must start with numeric version (e.g., 001_description.sql)",
                )
                continue

            # Extract description from filename
            description = "_".join(filename.split("_")[1:]).replace(".sql", "")

            # Read SQL content
            sql_content = filepath.read_text()

            migrations.append((version, filename, description, sql_content))

        logger.info(
            "migration_files_found",
            num_migrations=len(migrations),
            versions=[m[0] for m in migrations],
        )

        return migrations

    def _get_applied_migrations(self) -> set[int]:
        """Get set of already-applied migration versions.

        Returns:
            Set of applied migration version numbers
        """
        try:
            with self.connection_mgr.connection() as conn:
                df = conn.execute("SELECT version FROM schema_migrations ORDER BY version").pl()

            if df.is_empty():
                return set()

            versions = {row["version"] for row in df.iter_rows(named=True)}
            logger.info(
                "applied_migrations_loaded",
                num_applied=len(versions),
                versions=sorted(versions),
            )
            return versions

        except Exception as e:
            # Table might not exist yet
            logger.warning(
                "failed_to_load_applied_migrations",
                error=str(e),
            )
            return set()

    def _calculate_checksum(self, sql_content: str) -> str:
        """Calculate SHA256 checksum of SQL content.

        Args:
            sql_content: SQL migration content

        Returns:
            Hex string of SHA256 hash
        """
        return hashlib.sha256(sql_content.encode()).hexdigest()

    def apply_migrations(self) -> None:
        """Apply all pending migrations in version order.

        Migrations are executed in a transaction per migration file.
        Each successful migration is recorded in schema_migrations table.
        """
        # Ensure migrations table exists
        self._ensure_migrations_table()

        # Get all migration files
        all_migrations = self._get_migration_files()

        if not all_migrations:
            logger.info("no_migrations_found")
            return

        # Get already-applied migrations
        applied_versions = self._get_applied_migrations()

        # Filter to pending migrations
        pending_migrations = [m for m in all_migrations if m[0] not in applied_versions]

        if not pending_migrations:
            logger.info(
                "no_pending_migrations",
                total_migrations=len(all_migrations),
            )
            return

        logger.info(
            "applying_pending_migrations",
            num_pending=len(pending_migrations),
            versions=[m[0] for m in pending_migrations],
        )

        # Apply each pending migration
        for version, filename, description, sql_content in pending_migrations:
            self._apply_single_migration(version, filename, description, sql_content)

        logger.info(
            "all_migrations_applied",
            num_applied=len(pending_migrations),
        )

    def _apply_single_migration(
        self,
        version: int,
        filename: str,
        description: str,
        sql_content: str,
    ) -> None:
        """Apply a single migration.

        Args:
            version: Migration version number
            filename: Migration filename
            description: Migration description
            sql_content: SQL statements to execute
        """
        checksum = self._calculate_checksum(sql_content)

        logger.info(
            "applying_migration",
            version=version,
            filename=filename,
            description=description,
        )

        try:
            with self.connection_mgr.connection() as conn:
                # Execute migration SQL
                conn.execute(sql_content)

                # Record migration in schema_migrations table
                conn.execute(
                    """
                    INSERT INTO schema_migrations (version, description, applied_at, checksum)
                    VALUES (?, ?, ?, ?)
                    """,
                    [version, description, datetime.now(), checksum],
                )

                # Commit the transaction
                conn.commit()

            logger.info(
                "migration_applied_successfully",
                version=version,
                filename=filename,
            )

        except Exception as e:
            logger.error(
                "migration_failed",
                version=version,
                filename=filename,
                error=str(e),
            )
            raise
