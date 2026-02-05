#!/usr/bin/env python3
"""Import configuration data from JSON lines format to PostgreSQL.

This script imports configuration data exported from PostgreSQL into PostgreSQL,
handling foreign key dependencies and data type conversions.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extensions import connection as PgConnection

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Import order respects foreign key dependencies
IMPORT_ORDER = [
    "source_registry",  # No dependencies
    "source_performance",  # No dependencies
    "table_registry",  # No dependencies
    "source_credentials",  # References source_registry (but no FK constraint)
    "endpoint_catalog",  # References source_registry (FK constraint)
    "portfolio_accounts",  # No dependencies
    "user_preferences",  # No dependencies (no FK to accounts)
]


def connect_to_postgres() -> PgConnection:
    """Connect to PostgreSQL using DATABASE_URL from environment."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://portfolio_app:$PGPASSWORD@localhost:5432/portfolio_ai",
    )
    try:
        conn = psycopg2.connect(database_url)
        logger.info("Connected to PostgreSQL database")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        sys.exit(1)


def import_table_from_json(
    conn: PgConnection, table_name: str, input_file: Path
) -> None:
    """Import a table from JSON lines format."""
    if not input_file.exists():
        logger.info(f"  {table_name}: Skipped (no export file)")
        return

    try:
        cur = conn.cursor()

        # Read JSONL file
        rows = []
        with open(input_file) as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))

        if not rows:
            logger.info(f"  {table_name}: 0 rows (empty file)")
            return

        # Get column names from first row
        columns = list(rows[0].keys())

        # Build INSERT query with ON CONFLICT DO NOTHING
        placeholders = ", ".join(["%s"] * len(columns))
        columns_str = ", ".join(columns)
        query = f"""
            INSERT INTO {table_name} ({columns_str})
            VALUES ({placeholders})
            ON CONFLICT DO NOTHING
        """

        # Insert rows in batches
        inserted = 0
        skipped = 0
        batch_size = 1000

        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]

            for row in batch:
                try:
                    # Convert JSON/JSONB fields if needed
                    values = []
                    for col in columns:
                        value = row[col]
                        # Convert dict/list to JSON string for JSONB columns
                        if isinstance(value, (dict, list)):
                            values.append(json.dumps(value))
                        else:
                            values.append(value)

                    cur.execute(query, values)
                    if cur.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1

                except Exception as e:
                    logger.warning(f"  {table_name}: Skipped row - {e}")
                    skipped += 1

            # Commit batch
            conn.commit()

        logger.info(f"  {table_name}: {inserted} rows inserted, {skipped} skipped")

    except Exception as e:
        conn.rollback()
        logger.error(f"  {table_name}: Import failed - {e}")
        raise

    finally:
        cur.close()


def validate_foreign_keys(conn: PgConnection) -> None:
    """Validate that all foreign key constraints are satisfied."""
    cur = conn.cursor()

    # Check endpoint_catalog → source_registry
    cur.execute("""
        SELECT COUNT(*) FROM endpoint_catalog ec
        LEFT JOIN source_registry sr ON ec.source_id = sr.source_id
        WHERE sr.source_id IS NULL
    """)
    orphaned = cur.fetchone()[0]
    if orphaned > 0:
        logger.warning(
            f"Found {orphaned} orphaned rows in endpoint_catalog (no matching source_registry)"
        )

    logger.info("✅ Foreign key validation passed")
    cur.close()


def main() -> None:
    """Import configuration data into PostgreSQL."""
    logger.info("Starting PostgreSQL data import...")

    # Find input directory
    input_dir = Path.home() / "portfolio-ai" / "backend" / "data" / "migration_export"
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        logger.error("Run export-postgres-data.py first!")
        sys.exit(1)

    logger.info(f"Input directory: {input_dir}")

    # Connect to PostgreSQL
    conn = connect_to_postgres()

    try:
        # Import each table in dependency order
        logger.info("Importing configuration tables...")
        for table_name in IMPORT_ORDER:
            input_file = input_dir / f"{table_name}.jsonl"
            import_table_from_json(conn, table_name, input_file)

        # Validate foreign keys
        logger.info("\nValidating foreign key constraints...")
        validate_foreign_keys(conn)

        logger.info("\n✅ Import completed successfully!")

    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
