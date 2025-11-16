"""Shared utilities for capability scanners."""

from __future__ import annotations

from typing import Any


def _to_json_string(value: list[Any] | None) -> str:
    """Convert Python list to JSON string for JSONB column.

    Args:
        value: List to convert or None

    Returns:
        JSON string representation
    """
    import json  # noqa: PLC0415

    return json.dumps(value) if value else "[]"
