"""Tests for JSONPath field mapping utilities."""

from __future__ import annotations

import polars as pl
import pytest

from app.sources.jsonpath_mapper import (
    convert_timestamp_column,
    extract_with_path,
    map_response_to_schema,
    validate_mapping_config,
)


class TestExtractWithPath:
    """Test extract_with_path function."""

    def test_no_path_returns_original(self) -> None:
        """Test that None or empty path returns data as-is."""
        data = {"results": [{"o": 123.45}]}
        assert extract_with_path(data, None) == data
        assert extract_with_path(data, "") == data
        assert extract_with_path(data, "$") == data

    def test_simple_path_extraction(self) -> None:
        """Test extraction with simple path."""
        data = {"results": [{"o": 123.45, "h": 125.00}]}
        result = extract_with_path(data, "results")
        assert result == [{"o": 123.45, "h": 125.00}]

    def test_nested_path_extraction(self) -> None:
        """Test extraction with nested path."""
        data = {"data": {"items": [{"price": 100.0}]}}
        result = extract_with_path(data, "data.items")
        assert result == [{"price": 100.0}]

    def test_missing_path_returns_none(self) -> None:
        """Test that missing path returns None."""
        data = {"results": [{"o": 123.45}]}
        result = extract_with_path(data, "missing")
        assert result is None

    def test_partial_path_failure_returns_none(self) -> None:
        """Test that partial path failure returns None."""
        data = {"data": {"items": [{"price": 100.0}]}}
        result = extract_with_path(data, "data.missing.nested")
        assert result is None


class TestMapResponseToSchema:
    """Test map_response_to_schema function."""

    def test_simple_field_mapping(self) -> None:
        """Test basic field mapping without data_path."""
        response = [{"t": 1705324800000, "o": 123.45, "h": 125.00}]
        config = {
            "field_mapping": {"t": "ts_utc", "o": "open", "h": "high"},
        }
        df = map_response_to_schema(response, config)
        assert df is not None
        assert set(df.columns) == {"ts_utc", "open", "high"}
        assert df["open"][0] == 123.45

    def test_mapping_with_data_path(self) -> None:
        """Test field mapping with nested data extraction."""
        response = {"results": [{"t": 123, "o": 150.25}]}
        config = {
            "field_mapping": {"t": "ts_utc", "o": "open"},
            "data_path": "results",
        }
        df = map_response_to_schema(response, config)
        assert df is not None
        assert set(df.columns) == {"ts_utc", "open"}

    def test_missing_optional_fields(self) -> None:
        """Test that missing optional fields are skipped with warning."""
        response = [{"t": 123}]
        config = {
            "field_mapping": {"t": "ts_utc", "o": "open", "h": "high"},
        }
        df = map_response_to_schema(response, config)
        assert df is not None
        assert "ts_utc" in df.columns
        assert "open" not in df.columns  # Missing from response
        assert "high" not in df.columns  # Missing from response

    def test_missing_required_fields_raises_error(self) -> None:
        """Test that missing required fields raise ValueError."""
        response = [{"t": 123}]
        config = {
            "field_mapping": {"t": "ts_utc", "o": "open"},
            "required_fields": ["ts_utc", "open"],  # "open" is required but missing
        }
        with pytest.raises(ValueError, match="Required field 'open' missing"):
            map_response_to_schema(response, config)

    def test_invalid_data_path_raises_error(self) -> None:
        """Test that invalid data_path raises ValueError."""
        response = {"results": [{"t": 123}]}
        config = {
            "field_mapping": {"t": "ts_utc"},
            "data_path": "missing.path",
        }
        with pytest.raises(ValueError, match="data_path 'missing.path' extraction failed"):
            map_response_to_schema(response, config)

    def test_empty_data_returns_none(self) -> None:
        """Test that empty data after extraction returns None."""
        response = {"results": []}
        config = {
            "field_mapping": {"t": "ts_utc"},
            "data_path": "results",
        }
        df = map_response_to_schema(response, config)
        assert df is None

    def test_single_object_wrapped_in_list(self) -> None:
        """Test that single object is automatically wrapped in list."""
        response = {"t": 123, "o": 150.25}
        config = {
            "field_mapping": {"t": "ts_utc", "o": "open"},
        }
        df = map_response_to_schema(response, config)
        assert df is not None
        assert len(df) == 1
        assert df["open"][0] == 150.25

    def test_timeseries_dict_transformation(self) -> None:
        """Test automatic transformation of timeseries dict to list."""
        response = {
            "2024-01-15": {"open": 123.45, "close": 125.00},
            "2024-01-16": {"open": 125.00, "close": 127.50},
        }
        config = {
            "field_mapping": {"timestamp": "date", "open": "open", "close": "close"},
        }
        df = map_response_to_schema(response, config)
        assert df is not None
        assert len(df) == 2
        assert "date" in df.columns
        assert "open" in df.columns


class TestConvertTimestampColumn:
    """Test convert_timestamp_column function."""

    def test_convert_milliseconds_to_datetime(self) -> None:
        """Test conversion from millisecond epoch to datetime."""
        df = pl.DataFrame({"t": [1705324800000, 1705411200000]})
        result = convert_timestamp_column(df, "t", "ts_utc", unit="ms")
        assert "ts_utc" in result.columns
        assert "t" not in result.columns  # Original column dropped
        assert result["ts_utc"].dtype == pl.Datetime("ms", time_zone="UTC")

    def test_convert_seconds_to_datetime(self) -> None:
        """Test conversion from second epoch to datetime."""
        df = pl.DataFrame({"t": [1705324800, 1705411200]})
        result = convert_timestamp_column(df, "t", "ts_utc", unit="s")
        assert "ts_utc" in result.columns
        assert result["ts_utc"].dtype == pl.Datetime("ms", time_zone="UTC")

    def test_missing_source_column(self) -> None:
        """Test that missing source column returns DataFrame unchanged."""
        df = pl.DataFrame({"other": [1, 2, 3]})
        result = convert_timestamp_column(df, "t", "ts_utc", unit="ms")
        assert result.equals(df)

    def test_invalid_unit_raises_error(self) -> None:
        """Test that invalid time unit raises ValueError."""
        df = pl.DataFrame({"t": [1705324800000]})
        with pytest.raises(ValueError, match="Unsupported time unit"):
            convert_timestamp_column(df, "t", "ts_utc", unit="invalid")


class TestValidateMappingConfig:
    """Test validate_mapping_config function."""

    def test_valid_mapping_no_errors(self) -> None:
        """Test that valid mapping returns no errors."""
        errors = validate_mapping_config({"t": "ts_utc", "o": "open"}, "results")
        assert errors == []

    def test_empty_field_mapping_error(self) -> None:
        """Test that empty field_mapping returns error."""
        errors = validate_mapping_config({})
        assert len(errors) == 1
        assert "field_mapping cannot be empty" in errors[0]

    def test_empty_source_field_error(self) -> None:
        """Test that empty source field returns error."""
        errors = validate_mapping_config({"": "open"})
        assert len(errors) > 0
        assert any("Source field must be non-empty string" in e for e in errors)

    def test_empty_target_field_error(self) -> None:
        """Test that empty target field returns error."""
        errors = validate_mapping_config({"t": ""})
        assert len(errors) > 0
        assert any("Target field must be non-empty string" in e for e in errors)

    def test_consecutive_dots_in_path_error(self) -> None:
        """Test that consecutive dots in data_path returns error."""
        errors = validate_mapping_config({"t": "ts_utc"}, "invalid..path")
        assert len(errors) == 1
        assert "consecutive dots not allowed" in errors[0]

    def test_path_starting_with_dot_error(self) -> None:
        """Test that path starting with dot returns error."""
        errors = validate_mapping_config({"t": "ts_utc"}, ".invalid")
        assert len(errors) == 1
        assert "cannot start or end with dot" in errors[0]

    def test_path_ending_with_dot_error(self) -> None:
        """Test that path ending with dot returns error."""
        errors = validate_mapping_config({"t": "ts_utc"}, "invalid.")
        assert len(errors) == 1
        assert "cannot start or end with dot" in errors[0]
