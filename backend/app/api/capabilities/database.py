"""Shared database utilities for capabilities module.

This module provides common database helpers used across capabilities routers
to eliminate code duplication.
"""

from __future__ import annotations

from typing import Any

from ..types import CapabilityDict, InsightDict, NoteDict

# Table mapping
TABLE_MAPPING = {
    "db": "db_capabilities",
    "hatchet": "celery_capabilities",  # DB table not yet renamed
    "api": "api_capabilities",
}


def get_table_name(capability_type: str) -> str:
    """Get database table name for capability type.

    Args:
        capability_type: One of 'db', 'hatchet', 'api'

    Returns:
        Corresponding table name

    Raises:
        ValueError: If capability_type is invalid
    """
    if capability_type not in TABLE_MAPPING:
        raise ValueError(f"Invalid capability type: {capability_type}")
    return TABLE_MAPPING[capability_type]


def dict_from_row(row: tuple[Any, ...], columns: list[str]) -> dict[str, Any]:
    """Convert database row tuple to dictionary.

    Generic helper for any row type.

    Args:
        row: Database row tuple
        columns: Column names matching row values

    Returns:
        Dictionary with column names as keys
    """
    result: dict[str, Any] = {}
    for key, value in zip(columns, row, strict=True):
        result[key] = value
    return result


def capability_from_row(row: tuple[Any, ...], columns: list[str]) -> CapabilityDict:
    """Convert database row to CapabilityDict.

    Converts datetime and date objects to ISO format strings for JSON serialization.

    Args:
        row: Database row tuple
        columns: Column names matching row values

    Returns:
        CapabilityDict instance
    """
    result: CapabilityDict = {}
    for key, value in zip(columns, row, strict=True):
        if hasattr(value, "isoformat"):
            # Convert datetime and date objects to ISO format strings
            result[key] = value.isoformat()  # type: ignore
        else:
            result[key] = value  # type: ignore
    return result


def insight_from_row(row: tuple[Any, ...], columns: list[str]) -> InsightDict:
    """Convert database row to InsightDict.

    Maps ai_confidence -> confidence for frontend compatibility.

    Args:
        row: Database row tuple
        columns: Column names matching row values

    Returns:
        InsightDict instance
    """
    result: InsightDict = {}
    for key, value in zip(columns, row, strict=True):
        # Map ai_confidence to confidence for frontend compatibility
        output_key = "confidence" if key == "ai_confidence" else key
        if hasattr(value, "isoformat"):
            result[output_key] = value.isoformat()  # type: ignore
        else:
            result[output_key] = value  # type: ignore
    return result


def note_from_row(row: tuple[Any, ...], columns: list[str]) -> NoteDict:
    """Convert database row to NoteDict.

    Args:
        row: Database row tuple
        columns: Column names matching row values

    Returns:
        NoteDict instance
    """
    result: NoteDict = {}
    for key, value in zip(columns, row, strict=True):
        if hasattr(value, "isoformat"):
            result[key] = value.isoformat()  # type: ignore
        else:
            result[key] = value  # type: ignore
    return result


def transform_db_capability(cap: CapabilityDict) -> CapabilityDict:
    """Transform db_capability to add computed fields expected by frontend.

    Adds age_hours field by converting days_since_update to hours.
    Frontend expects age_hours (number | null) but DB stores days_since_update (integer | null).

    Args:
        cap: Capability dictionary from database

    Returns:
        Transformed capability dictionary
    """
    if cap.get("capability_type") == "db":
        # Convert days_since_update to age_hours for frontend compatibility
        days = cap.get("days_since_update")
        cap["age_hours"] = days * 24 if days is not None else None

        # Add missing fields with defaults if needed
        cap.setdefault("source", None)
        cap.setdefault("description", "")

    return cap
