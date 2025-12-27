"""Database result helpers for consistent row-to-dict conversion."""

from typing import Any


def row_to_dict(row: tuple[Any, ...], description: list[Any]) -> dict[str, Any]:
    """Convert a single database row to a dictionary.

    Args:
        row: The database row tuple
        description: The cursor.description from the result

    Returns:
        Dictionary with column names as keys
    """
    cols = [desc[0] for desc in description]
    return dict(zip(cols, row, strict=True))


def rows_to_dicts(rows: list[tuple[Any, ...]], description: list[Any]) -> list[dict[str, Any]]:
    """Convert multiple database rows to a list of dictionaries.

    Args:
        rows: List of database row tuples
        description: The cursor.description from the result

    Returns:
        List of dictionaries with column names as keys
    """
    cols = [desc[0] for desc in description]
    return [dict(zip(cols, row, strict=True)) for row in rows]
