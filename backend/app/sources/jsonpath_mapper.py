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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ROOT_PATH = "$"
_PATH_SEPARATOR = "."
_CONSECUTIVE_DOTS = ".."
_TS_FIELD = "timestamp"
_UNIT_MS = "ms"
_UNIT_S = "s"

# mapping_config keys
_KEY_FIELD_MAPPING = "field_mapping"
_KEY_DATA_PATH = "data_path"
_KEY_REQUIRED_FIELDS = "required_fields"

# Log event names
_LOG_PATH_FAILED = "jsonpath_extraction_failed"
_LOG_NON_DICT = "jsonpath_non_dict"
_LOG_EMPTY_DATA = "map_response_to_schema_empty_data"
_LOG_OPTIONAL_MISSING = "optional_fields_missing"
_LOG_DF_FAILED = "dataframe_creation_failed"
_LOG_TS_MISSING = "timestamp_column_missing"
_LOG_TS_FAILED = "timestamp_conversion_failed"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


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
    if not path or path == _ROOT_PATH:
        return data

    current: dict[str, Any] | None = data
    for key in path.split(_PATH_SEPARATOR):
        if not isinstance(current, dict):
            logger.warning(
                _LOG_NON_DICT,
                path=path,
                failed_at_key=key,
                current_type=type(current).__name__,
            )
            return None
        current = current.get(key)
        if current is None:
            logger.warning(_LOG_PATH_FAILED, path=path, failed_at_key=key)
            return None

    return current


def convert_timestamp_column(
    df: pl.DataFrame,
    source_col: str,
    target_col: str,
    unit: str = _UNIT_MS,
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
        logger.warning(_LOG_TS_MISSING, source_col=source_col)
        return df

    try:
        df = _apply_timestamp_conversion(df, source_col, target_col, unit)
        if source_col != target_col and source_col in df.columns:
            df = df.drop(source_col)
    except Exception as e:
        logger.error(
            _LOG_TS_FAILED,
            source_col=source_col,
            target_col=target_col,
            unit=unit,
            error=str(e),
            exc_info=True,
        )
        raise

    return df


def map_response_to_schema(
    response: dict[str, Any] | list[dict[str, Any]],
    mapping_config: dict[str, Any],
) -> pl.DataFrame | None:
    """Map API response to portfolio-ai schema using field mapping (see helper functions)."""
    field_mapping = mapping_config.get(_KEY_FIELD_MAPPING)
    if not field_mapping:
        raise ValueError(f"mapping_config must contain '{_KEY_FIELD_MAPPING}' key")

    data_path = mapping_config.get(_KEY_DATA_PATH)
    required_fields = set(mapping_config.get(_KEY_REQUIRED_FIELDS, []))

    data = _extract_data_from_response(response, data_path)
    data_list = _normalize_to_list(data, data_path)

    if not data_list:
        return None

    try:
        df = pl.DataFrame(data_list, strict=False)
    except Exception as e:
        logger.error(_LOG_DF_FAILED, error=str(e), error_type=type(e).__name__, exc_info=True)
        raise ValueError(f"Failed to create DataFrame from response data: {e}") from e

    rename_map = _validate_and_build_rename_map(df, field_mapping, required_fields)
    return df.rename(rename_map) if rename_map else df


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
    errors: list[str] = []
    _validate_field_mapping(field_mapping, errors)
    _validate_data_path(data_path, errors)
    return errors


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_data_from_response(
    response: dict[str, Any] | list[dict[str, Any]],
    data_path: str | None,
) -> Any:
    """Extract data from response using optional data_path."""
    if not data_path or isinstance(response, list):
        return response

    extracted = extract_with_path(response, data_path)
    if extracted is None:
        raise ValueError(f"data_path '{data_path}' extraction failed - path not found in response")
    return extracted


def _normalize_to_list(data: Any, data_path: str | None) -> list[dict[str, Any]] | None:
    """Normalize data to list format."""
    if isinstance(data, list):
        return data if data else None

    if isinstance(data, dict):
        if all(isinstance(v, dict) for v in data.values()):
            return _transform_timeseries_dict_to_list(data)
        return [data]

    logger.warning(_LOG_EMPTY_DATA, data_path=data_path)
    return None


def _validate_and_build_rename_map(
    df: pl.DataFrame,
    field_mapping: dict[str, str],
    required_fields: set[str],
) -> dict[str, str]:
    """Build rename map and validate required fields exist."""
    rename_map: dict[str, str] = {}
    missing_fields: list[str] = []

    for source_field, target_field in field_mapping.items():
        if source_field in df.columns:
            rename_map[source_field] = target_field
            continue
        missing_fields.append(source_field)
        if target_field in required_fields:
            raise ValueError(
                f"Required field '{target_field}' missing from source data "
                f"(source field '{source_field}' not found in response)"
            )

    if missing_fields:
        logger.warning(
            _LOG_OPTIONAL_MISSING,
            missing_fields=missing_fields,
            available_fields=df.columns,
        )

    return rename_map


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
            item = {_TS_FIELD: timestamp}
            item.update(values)
            result.append(item)

    return result


def _apply_timestamp_conversion(
    df: pl.DataFrame,
    source_col: str,
    target_col: str,
    unit: str,
) -> pl.DataFrame:
    """Apply the epoch-to-datetime conversion for a given unit."""
    if unit == _UNIT_MS:
        # Milliseconds: divide by 1000 to get seconds, then convert to ms datetime
        expr = (pl.col(source_col).cast(pl.Int64) / 1000).cast(pl.Int64)
    elif unit == _UNIT_S:
        # Seconds: multiply by 1000 to get milliseconds, then convert to ms datetime
        expr = pl.col(source_col).cast(pl.Int64) * 1000
    else:
        raise ValueError(f"Unsupported time unit: {unit}. Use '{_UNIT_MS}' or '{_UNIT_S}'")

    return df.with_columns(
        expr.cast(pl.Datetime("ms", time_zone="UTC")).alias(target_col)
    )


def _validate_field_mapping(field_mapping: dict[str, str], errors: list[str]) -> None:
    """Append field_mapping validation errors to errors list."""
    if not field_mapping:
        errors.append("field_mapping cannot be empty")
        return

    for source_field, target_field in field_mapping.items():
        if not source_field or not isinstance(source_field, str):
            errors.append(f"Source field must be non-empty string, got: {source_field!r}")
        if not target_field or not isinstance(target_field, str):
            errors.append(f"Target field must be non-empty string, got: {target_field!r}")


def _validate_data_path(data_path: str | None, errors: list[str]) -> None:
    """Append data_path validation errors to errors list."""
    if not data_path:
        return

    if not isinstance(data_path, str):
        errors.append(f"data_path must be string, got: {type(data_path).__name__}")
        return

    if _CONSECUTIVE_DOTS in data_path:
        errors.append("data_path has invalid syntax (consecutive dots not allowed)")
    elif data_path.startswith(_PATH_SEPARATOR) or data_path.endswith(_PATH_SEPARATOR):
        errors.append("data_path cannot start or end with dot")
