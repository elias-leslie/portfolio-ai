#!/usr/bin/env python3
"""Export configuration data from legacy database to JSON lines format.

This script exports only configuration data (API keys, preferences, accounts)
for migration to PostgreSQL. Transactional data (price_cache, day_bars) is
intentionally excluded and will be flushed during migration.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import legacy_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Configuration tables to export (preserving data)
TABLES_TO_EXPORT = [
    "source_credentials",  # API keys (critical)
    "user_preferences",  # User settings (critical)
    "portfolio_accounts",  # Accounts (critical)
    "source_performance",  # Source metrics (useful)
    "source_registry",  # Source definitions (critical)
    "endpoint_catalog",  # Endpoint mappings (critical)
    "table_registry",  # Metadata (useful)
]

# Tables to skip (transactional data - will be flushed)
TABLES_TO_SKIP = [
    "price_cache",
    "day_bars",
    "minute_bars",
    "technical_indicators",
    "news_cache",
    "reference_cache",
    "watchlist_snapshots",
    "agent_runs",
    "agent_ideas",
    "agent_tool_calls",
    "validation_results",
    "idea_outcomes",
]


def connect_to_legacy_db() -> legacy_db.legacy databasePyConnection:
    """Connect to legacy database database."""
    db_path = Path.home() / "portfolio-ai" / "backend" / "data" / "portfolio-ai.db"
    if not db_path.exists():
        logger.error(f"legacy database database not found at {db_path}")
        sys.exit(1)

    try:
        conn = legacy_db.connect(str(db_path), read_only=True)
        logger.info(f"Connected to legacy database database: {db_path}")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to legacy database: {e}")
        sys.exit(1)


def export_table_to_json(
    conn: legacy_db.legacy databasePyConnection, table_name: str, output_dir: Path
) -> None:
    """Export a table to JSON lines format."""
    try:
        # Query all rows from the table
        result = conn.execute(f"SELECT * FROM {table_name}").fetchall()
        columns = [desc[0] for desc in conn.description]

        if not result:
            logger.info(f"  {table_name}: 0 rows (empty table)")
            return

        # Write to JSON lines file
        output_file = output_dir / f"{table_name}.jsonl"
        with open(output_file, "w") as f:
            for row in result:
                # Convert row to dictionary
                row_dict = {}
                for col_name, value in zip(columns, row):
                    # Handle special types
                    if hasattr(value, "isoformat"):  # datetime/date
                        row_dict[col_name] = value.isoformat()
                    elif isinstance(value, (dict, list)):  # JSON
                        row_dict[col_name] = value
                    else:
                        row_dict[col_name] = value

                # Write as JSON line
                f.write(json.dumps(row_dict) + "\n")

        logger.info(f"  {table_name}: {len(result)} rows → {output_file.name}")

    except Exception as e:
        logger.error(f"  {table_name}: Export failed - {e}")


def main() -> None:
    """Export configuration data from legacy database."""
    logger.info("Starting legacy database data export...")

    # Create output directory
    output_dir = (
        Path.home() / "portfolio-ai" / "backend" / "data" / "migration_export"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")

    # Connect to legacy database
    conn = connect_to_legacy_db()

    try:
        # Export each table
        logger.info("Exporting configuration tables...")
        for table_name in TABLES_TO_EXPORT:
            export_table_to_json(conn, table_name, output_dir)

        logger.info(
            f"\n✅ Export completed successfully! Files in {output_dir}"
        )
        logger.info(
            f"\nSkipped transactional tables ({len(TABLES_TO_SKIP)} tables):"
        )
        for table in TABLES_TO_SKIP:
            logger.info(f"  - {table}")

    except Exception as e:
        logger.error(f"❌ Export failed: {e}")
        sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
