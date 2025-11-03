"""YAML source configuration loader for portfolio-ai.

Loads data source configurations from YAML files and populates DuckDB tables.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from ..logging_config import get_logger

if TYPE_CHECKING:
    from .facade import DuckDBStorage

logger = get_logger(__name__)


def load_source_config(yaml_path: str) -> dict[str, Any]:
    """Parse YAML source configuration file.

    Args:
        yaml_path: Path to YAML configuration file.

    Returns:
        Dictionary with source metadata, definition, and field mappings.
    """
    yaml_file = Path(yaml_path)
    with yaml_file.open() as f:
        config = yaml.safe_load(f)

    # Extract source metadata
    source_id = config["source_id"]
    display_name = config["display_name"]
    priority = config["priority"]
    enabled = config.get("enabled", True)

    # Build definition JSON (everything except field_mapping)
    definition = {
        "type": config["type"],
        "connection": config["connection"],
        "auth": config["auth"],
        "capabilities": config.get("capabilities", {}),
        "rate_limit": config.get("rate_limit", ""),
        "rate_limit_config": config.get("rate_limit_config", {}),
        "transforms": config.get("transforms", {}),
        "notes": config.get("notes", ""),
        "category": config.get("category", ""),
        "validation": config.get("validation", {}),
    }

    # Extract field mappings per target table
    field_mappings = config.get("field_mapping", {})
    target_tables = config.get("target_tables", [])

    return {
        "source_id": source_id,
        "display_name": display_name,
        "priority": priority,
        "enabled": enabled,
        "definition": definition,
        "field_mappings": field_mappings,
        "target_tables": target_tables,
    }


def insert_source_to_db(source_config: dict[str, Any], storage: DuckDBStorage) -> None:
    """Insert source configuration into DuckDB tables.

    Args:
        source_config: Configuration dictionary from load_source_config().
        storage: DuckDBStorage instance.
    """
    with storage.connection() as conn:
        # Insert into source_registry
        conn.execute(
            """
            INSERT INTO source_registry (source_id, display_name, priority, enabled, definition)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (source_id) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                priority = EXCLUDED.priority,
                enabled = EXCLUDED.enabled,
                definition = EXCLUDED.definition,
                updated_at = now()
            """,
            [
                source_config["source_id"],
                source_config["display_name"],
                source_config["priority"],
                source_config["enabled"],
                json.dumps(source_config["definition"]),
            ],
        )

        # Extract credentials from definition
        connection_params = source_config["definition"].get("connection", {}).get("params", {})

        # Look for {{secret:source:field}} placeholders
        credentials = {}
        for _key, value in connection_params.items():
            if isinstance(value, str) and value.startswith("{{secret:"):
                # Extract field name from {{secret:source:field}}
                parts = value.strip("{}").split(":")
                if len(parts) == 3 and parts[1] == source_config["source_id"]:
                    credentials[parts[2]] = parts[2]  # Placeholder, actual value from .env

        # Insert credentials (if any)
        for field in credentials:
            conn.execute(
                """
                INSERT INTO source_credentials (source_id, field, value)
                VALUES (?, ?, ?)
                ON CONFLICT (source_id, field) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = now()
                """,
                [source_config["source_id"], field, f"{{{{ENV:{field.upper()}}}}}"],
            )

        # Insert endpoints into endpoint_catalog
        field_mappings = source_config["field_mappings"]
        target_tables = source_config["target_tables"]

        for target_table in target_tables:
            if target_table in field_mappings:
                endpoint_id = f"{source_config['source_id']}_{target_table}"
                path_template = source_config["definition"]["connection"].get("sample_path", "")

                conn.execute(
                    """
                    INSERT INTO endpoint_catalog (id, source_id, endpoint_key, target_table, path_template, field_mapping)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (id) DO UPDATE SET
                        endpoint_key = EXCLUDED.endpoint_key,
                        target_table = EXCLUDED.target_table,
                        path_template = EXCLUDED.path_template,
                        field_mapping = EXCLUDED.field_mapping
                    """,
                    [
                        endpoint_id,
                        source_config["source_id"],
                        target_table,
                        target_table,
                        path_template,
                        json.dumps(field_mappings[target_table]),
                    ],
                )

        logger.info(
            f"Loaded source {source_config['source_id']} (priority {source_config['priority']}, {len(target_tables)} endpoints)"
        )


def load_all_sources(storage: DuckDBStorage, sources_dir: str = "config/sources") -> None:
    """Load all YAML source configurations from directory.

    Args:
        storage: DuckDBStorage instance.
        sources_dir: Directory containing YAML files (default: config/sources).
    """
    sources_path = Path(sources_dir)
    if not sources_path.exists():
        logger.warning(f"Sources directory not found: {sources_dir}")
        return

    yaml_files = list(sources_path.glob("*.yaml"))
    logger.info(f"Loading {len(yaml_files)} source configurations from {sources_dir}")

    for yaml_file in yaml_files:
        try:
            config = load_source_config(str(yaml_file))
            insert_source_to_db(config, storage)
        except Exception as e:
            logger.error(f"Failed to load {yaml_file.name}: {e}")

    logger.info(f"Successfully loaded {len(yaml_files)} data sources")
