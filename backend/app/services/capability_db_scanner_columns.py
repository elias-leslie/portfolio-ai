"""Column analysis utilities for database scanner."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.storage.types import DatabaseConnection


def analyze_column_completeness(
    table_name: str,
    column_names: list[str],
    row_count: int,
    conn: DatabaseConnection,
    null_threshold_pct: float,
) -> tuple[list[str], list[str]]:
    """Analyze column completeness for a table.

    Args:
        table_name: Name of table to analyze
        column_names: List of column names
        row_count: Total row count in table
        conn: Database connection
        null_threshold_pct: Percentage threshold for "mostly null" classification

    Returns:
        Tuple of (columns_with_data, columns_mostly_null)
    """
    columns_with_data: list[str] = []
    columns_mostly_null: list[str] = []

    if row_count == 0:
        return columns_with_data, columns_mostly_null

    for col_name in column_names:
        try:
            # Count non-NULL values
            # Note: col_name from introspection, not user input
            result = conn.execute(
                f"SELECT COUNT({col_name}) as cnt FROM {table_name}"
            )  # validated: table/column from SQLAlchemy inspector
            row = result.fetchone()
            non_null_value = row[0] if row else 0
            non_null_count: int = (
                int(non_null_value) if isinstance(non_null_value, (int, float, str)) else 0
            )

            if non_null_count > 0:
                columns_with_data.append(col_name)

            # Calculate NULL percentage
            null_pct = ((row_count - non_null_count) / row_count) * 100 if row_count > 0 else 0

            if null_pct > null_threshold_pct:
                columns_mostly_null.append(col_name)

        except Exception:
            # Skip columns that cause errors (e.g., incompatible types)
            continue

    return columns_with_data, columns_mostly_null


def calculate_completeness_pct(
    columns_with_data: list[str],
    total_columns: int,
) -> int:
    """Calculate completeness percentage.

    Args:
        columns_with_data: List of columns with non-NULL data
        total_columns: Total number of columns

    Returns:
        Completeness percentage (0-100)
    """
    return int((len(columns_with_data) / total_columns) * 100) if total_columns > 0 else 0


def detect_date_range(
    table_name: str,
    conn: DatabaseConnection,
    column_names: list[str],
) -> tuple[Any | None, Any | None]:
    """Detect date range for a table by finding MIN/MAX of timestamp columns.

    Args:
        table_name: Name of table
        conn: Database connection
        column_names: List of column names in table

    Returns:
        Tuple of (min_date, max_date) or (None, None) if no date columns found
    """
    # Try common timestamp column names in order of preference
    date_columns = ["created_at", "updated_at", "as_of_date", "date", "timestamp"]

    for col_name in date_columns:
        if col_name in column_names:
            try:
                # validated: table_name from inspector.get_table_names(), col_name from schema column list
                # Note: col_name validated from column_names list, not user input
                result = conn.execute(
                    f"SELECT MIN({col_name}), MAX({col_name}) FROM {table_name} WHERE {col_name} IS NOT NULL"
                )
                row = result.fetchone()
                if row is None:
                    continue

                min_date, max_date = row

                if min_date is not None and max_date is not None:
                    # Convert to date if timestamp
                    min_date_fn = getattr(min_date, "date", None)
                    if callable(min_date_fn):
                        min_date = min_date_fn()
                    max_date_fn = getattr(max_date, "date", None)
                    if callable(max_date_fn):
                        max_date = max_date_fn()

                    return min_date, max_date

            except Exception:
                # Skip if column causes errors
                continue

    return None, None
