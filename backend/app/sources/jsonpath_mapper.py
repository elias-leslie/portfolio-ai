"""JSONPath field mapping utilities for dynamic API response transformation.

This module provides utilities for extracting data from nested JSON responses
and mapping fields from source API schemas to portfolio-ai database schemas.

Adapted from market-sim field_mappings.py for portfolio-ai.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ..logging_config import get_logger

logger = get_logger(__name__)


def extract_with_path(data: dict[str, Any], path: str | None) -> Any:
    """Extract data from nested JSON using dot-notation path.

    Args:
        data: Full API response JSON
        path: Dot-separated path (e.g., "results", "data.items")
              None or "" returns data as-is

    Returns:
        Extracted data (usually a list or dict)
        None if path not found

    Examples:
        >>> data = {"results": [{"o": 123.45}]}
        >>> extract_with_path(data, "results")
        [{"o": 123.45}]

        >>> extract_with_path(data, None)
        {"results": [{"o": 123.45}]}

        >>> extract_with_path(data, "data.items")
        None  # if path doesn't exist
    """
    if not path or path == "$":
        return data

    keys = path.split(".")
    current: Any = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                logger.warning(
                    "jsonpath_extraction_failed",
                    path=path,
                    failed_at_key=key,
                )
                return None
        else:
            logger.warning(
                "jsonpath_non_dict",
                path=path,
                failed_at_key=key,
                current_type=type(current).__name__,
            )
            return None

    return current


def map_response_to_schema(
    response: dict[str, Any],
    mapping_config: dict[str, Any],
) -> pl.DataFrame | None:
    """Map API response to portfolio-ai schema using field mapping configuration.

    Args:
        response: Raw API response dictionary
        mapping_config: Configuration dict with keys:
            - field_mapping: Dict[str, str] mapping source fields to target fields
            - data_path: Optional str path to extract nested data first
            - required_fields: Optional list[str] of required target fields

    Returns:
        Polars DataFrame with mapped columns, or None if no data

    Raises:
        ValueError: If required fields missing or mapping configuration invalid

    Example:
        >>> response = {"results": [{"t": 1705324800000, "o": 123.45}]}
        >>> config = {
        ...     "field_mapping": {"t": "ts_utc", "o": "open"},
        ...     "data_path": "results",
        ...     "required_fields": ["ts_utc", "open"]
        ... }
        >>> df = map_response_to_schema(response, config)
        >>> df.columns
        ['ts_utc', 'open']
    """
    field_mapping = mapping_config.get("field_mapping")
    if not field_mapping:
        raise ValueError("mapping_config must contain 'field_mapping' key")

    data_path = mapping_config.get("data_path")
    required_fields = set(mapping_config.get("required_fields", []))

    # Extract nested data if data_path specified
    data: Any = response
    if data_path:
        extracted = extract_with_path(response, data_path)
        if extracted is None:
            raise ValueError(
                f"data_path '{data_path}' extraction failed - path not found in response"
            )
        data = extracted

    # Ensure data is a list of dicts
    if isinstance(data, dict) and not isinstance(data, list):
        # Check if it's a timeseries dict (all values are dicts)
        if all(isinstance(v, dict) for v in data.values()):
            data = _transform_timeseries_dict_to_list(data)
        else:
            # Single object, wrap in list
            data = [data]

    if not data:
        logger.warning("map_response_to_schema_empty_data", data_path=data_path)
        return None

    # Create DataFrame from raw data
    try:
        df = pl.DataFrame(data, strict=False)
    except Exception as e:
        logger.error("dataframe_creation_failed", error=str(e), error_type=type(e).__name__)
        raise ValueError(f"Failed to create DataFrame from response data: {e}") from e

    # Apply field mapping (rename columns)
    rename_map = {}
    missing_fields = []

    for source_field, target_field in field_mapping.items():
        if source_field in df.columns:
            rename_map[source_field] = target_field
        else:
            missing_fields.append(source_field)
            # Check if this missing field is required
            if target_field in required_fields:
                raise ValueError(
                    f"Required field '{target_field}' missing from source data "
                    f"(source field '{source_field}' not found in response)"
                )

    # Log warnings for missing optional fields
    if missing_fields:
        logger.warning(
            "optional_fields_missing",
            missing_fields=missing_fields,
            available_fields=df.columns,
        )

    # Rename columns
    if rename_map:
        df = df.rename(rename_map)

    return df


def _transform_timeseries_dict_to_list(
    timeseries_dict: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Transform nested time series dict to list format.

    Alpha Vantage (and similar APIs) return time series as:
    {
        "2024-01-15 09:30:00": {"1. open": 123.45, "2. high": 125.00, ...},
        "2024-01-15 09:31:00": {"1. open": 125.00, "2. high": 126.00, ...}
    }

    This transforms it to:
    [
        {"timestamp": "2024-01-15 09:30:00", "1. open": 123.45, "2. high": 125.00, ...},
        {"timestamp": "2024-01-15 09:31:00", "1. open": 125.00, "2. high": 126.00, ...}
    ]

    Args:
        timeseries_dict: Dict where keys are timestamps and values are OHLCV dicts

    Returns:
        List of dicts with timestamp field added
    """
    if not isinstance(timeseries_dict, dict):
        return []

    result = []
    for timestamp, values in timeseries_dict.items():
        if isinstance(values, dict):
            # Add timestamp to the values dict
            item = {"timestamp": timestamp}
            item.update(values)
            result.append(item)

    return result


def convert_timestamp_column(
    df: pl.DataFrame,
    source_col: str,
    target_col: str,
    unit: str = "ms",
) -> pl.DataFrame:
    """Convert timestamp column from epoch to datetime.

    Args:
        df: Input DataFrame
        source_col: Source column name containing epoch timestamps
        target_col: Target column name for datetime values
        unit: Time unit - "ms" (milliseconds) or "s" (seconds)

    Returns:
        DataFrame with converted timestamp column

    Example:
        >>> df = pl.DataFrame({"t": [1705324800000, 1705411200000]})
        >>> df = convert_timestamp_column(df, "t", "ts_utc", unit="ms")
        >>> df.columns
        ['ts_utc']
    """
    if source_col not in df.columns:
        logger.warning("timestamp_column_missing", source_col=source_col)
        return df

    try:
        if unit == "ms":
            # Milliseconds: divide by 1000 to get seconds, then convert to ms datetime
            df = df.with_columns(
                (pl.col(source_col).cast(pl.Int64) / 1000)
                .cast(pl.Int64)
                .cast(pl.Datetime("ms", time_zone="UTC"))
                .alias(target_col)
            )
        elif unit == "s":
            # Seconds: multiply by 1000 to get milliseconds, then convert to ms datetime
            df = df.with_columns(
                (pl.col(source_col).cast(pl.Int64) * 1000)
                .cast(pl.Int64)
                .cast(pl.Datetime("ms", time_zone="UTC"))
                .alias(target_col)
            )
        else:
            raise ValueError(f"Unsupported time unit: {unit}. Use 'ms' or 's'")

        # Drop original column if renamed
        if source_col != target_col and source_col in df.columns:
            df = df.drop(source_col)

    except Exception as e:
        logger.error(
            "timestamp_conversion_failed",
            source_col=source_col,
            target_col=target_col,
            unit=unit,
            error=str(e),
        )
        raise

    return df


def validate_mapping_config(
    field_mapping: dict[str, str],
    data_path: str | None = None,
) -> list[str]:
    """Validate field mapping configuration before use.

    Args:
        field_mapping: Mapping dictionary to validate
        data_path: Optional data path to validate

    Returns:
        List of validation errors (empty list if valid)

    Example:
        >>> errors = validate_mapping_config(
        ...     {"": "open"},  # Invalid: empty source field
        ...     "invalid..path"  # Invalid: consecutive dots
        ... )
        >>> errors
        ['Source field must be non-empty string, got: ""', 'data_path has invalid syntax']
    """
    errors = []

    # Validate field_mapping
    if not field_mapping:
        errors.append("field_mapping cannot be empty")
    else:
        for source_field, target_field in field_mapping.items():
            if not source_field or not isinstance(source_field, str):
                errors.append(f"Source field must be non-empty string, got: {source_field!r}")
            if not target_field or not isinstance(target_field, str):
                errors.append(f"Target field must be non-empty string, got: {target_field!r}")

    # Validate data_path
    if data_path:
        if not isinstance(data_path, str):
            errors.append(f"data_path must be string, got: {type(data_path).__name__}")
        elif ".." in data_path:
            errors.append("data_path has invalid syntax (consecutive dots not allowed)")
        elif data_path.startswith(".") or data_path.endswith("."):
            errors.append("data_path cannot start or end with dot")

    return errors
