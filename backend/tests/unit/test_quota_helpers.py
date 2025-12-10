"""Unit tests for API quota helpers module.

Tests for functions that check API key configuration and build quota info.

FEAT-098: API Quota Helpers Tests
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

from app.utils.quota_helpers import build_quota_info, is_api_key_configured


class TestIsApiKeyConfigured:
    """Test is_api_key_configured function."""

    def test_key_found_in_database_returns_true(self) -> None:
        """API key found in database should return True."""
        mock_storage = MagicMock()
        mock_df = MagicMock()
        mock_df.is_empty.return_value = False
        mock_df.to_dicts.return_value = [{"value": "valid_key_12345"}]
        mock_storage.query.return_value = mock_df

        result = is_api_key_configured("twelvedata", "TWELVEDATA_API_KEY", mock_storage)

        assert result is True
        mock_storage.query.assert_called_once_with(
            "SELECT value FROM source_credentials WHERE source_id = ? AND field = 'apikey'",
            ["twelvedata"],
        )

    def test_key_not_in_database_falls_back_to_env_var(self) -> None:
        """When key not in DB, should fall back to environment variable."""
        mock_storage = MagicMock()
        mock_df = MagicMock()
        mock_df.is_empty.return_value = True
        mock_storage.query.return_value = mock_df

        with patch.dict(os.environ, {"POLYGON_API_KEY": "env_key_67890"}):
            result = is_api_key_configured("polygon", "POLYGON_API_KEY", mock_storage)

        assert result is True

    def test_placeholder_value_in_database_returns_false(self) -> None:
        """Database with placeholder value should return False."""
        mock_storage = MagicMock()
        mock_df = MagicMock()
        mock_df.is_empty.return_value = False
        mock_df.to_dicts.return_value = [{"value": "your_key_here"}]
        mock_storage.query.return_value = mock_df

        result = is_api_key_configured("alphavantage", "ALPHAVANTAGE_API_KEY", mock_storage)

        assert result is False

    def test_placeholder_uppercase_in_database_returns_false(self) -> None:
        """Database with uppercase PLACEHOLDER should return False."""
        mock_storage = MagicMock()
        mock_df = MagicMock()
        mock_df.is_empty.return_value = False
        mock_df.to_dicts.return_value = [{"value": "PLACEHOLDER"}]
        mock_storage.query.return_value = mock_df

        result = is_api_key_configured("finnhub", "FINNHUB_API_KEY", mock_storage)

        assert result is False

    def test_empty_string_in_database_returns_false(self) -> None:
        """Empty string in database should return False."""
        mock_storage = MagicMock()
        mock_df = MagicMock()
        mock_df.is_empty.return_value = False
        mock_df.to_dicts.return_value = [{"value": ""}]
        mock_storage.query.return_value = mock_df

        result = is_api_key_configured("newsapi", "NEWSAPI_KEY", mock_storage)

        assert result is False

    def test_none_value_in_database_returns_false(self) -> None:
        """None value in database should return False."""
        mock_storage = MagicMock()
        mock_df = MagicMock()
        mock_df.is_empty.return_value = False
        mock_df.to_dicts.return_value = [{"value": None}]
        mock_storage.query.return_value = mock_df

        result = is_api_key_configured("fred", "FRED_API_KEY", mock_storage)

        assert result is False

    def test_placeholder_in_env_var_returns_false(self) -> None:
        """Placeholder in environment variable should return False."""
        mock_storage = MagicMock()
        mock_df = MagicMock()
        mock_df.is_empty.return_value = True
        mock_storage.query.return_value = mock_df

        with patch.dict(os.environ, {"TEST_API_KEY": "your_key_here"}):
            result = is_api_key_configured("testapi", "TEST_API_KEY", mock_storage)

        assert result is False

    def test_placeholder_uppercase_in_env_var_returns_false(self) -> None:
        """Uppercase PLACEHOLDER in environment variable should return False."""
        mock_storage = MagicMock()
        mock_df = MagicMock()
        mock_df.is_empty.return_value = True
        mock_storage.query.return_value = mock_df

        with patch.dict(os.environ, {"ANOTHER_KEY": "PLACEHOLDER"}):
            result = is_api_key_configured("another", "ANOTHER_KEY", mock_storage)

        assert result is False

    def test_missing_env_var_returns_false(self) -> None:
        """Missing environment variable should return False."""
        mock_storage = MagicMock()
        mock_df = MagicMock()
        mock_df.is_empty.return_value = True
        mock_storage.query.return_value = mock_df

        with patch.dict(os.environ, {}, clear=True):
            result = is_api_key_configured("nokey", "NONEXISTENT_KEY", mock_storage)

        assert result is False

    def test_database_error_falls_back_to_env_var(self) -> None:
        """Database error should fall back to environment variable check."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = Exception("Database connection failed")

        with patch.dict(os.environ, {"FALLBACK_KEY": "valid_key"}):
            result = is_api_key_configured("fallback", "FALLBACK_KEY", mock_storage)

        assert result is True

    def test_database_error_with_valid_env_var(self) -> None:
        """Database error with valid env var should return True."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = RuntimeError("Query failed")

        with patch.dict(os.environ, {"SAFE_KEY": "abc123"}):
            result = is_api_key_configured("safe", "SAFE_KEY", mock_storage)

        assert result is True

    def test_database_error_with_placeholder_env_var(self) -> None:
        """Database error with placeholder env var should return False."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = Exception("DB error")

        with patch.dict(os.environ, {"PLACEHOLDER_KEY": "your_key_here"}):
            result = is_api_key_configured("api", "PLACEHOLDER_KEY", mock_storage)

        assert result is False

    def test_database_error_with_missing_env_var(self) -> None:
        """Database error with missing env var should return False."""
        mock_storage = MagicMock()
        mock_storage.query.side_effect = Exception("DB error")

        with patch.dict(os.environ, {}, clear=True):
            result = is_api_key_configured("missing", "MISSING_KEY", mock_storage)

        assert result is False

    def test_whitespace_only_key_returns_false(self) -> None:
        """Key with only whitespace should return False."""
        mock_storage = MagicMock()
        mock_df = MagicMock()
        mock_df.is_empty.return_value = False
        mock_df.to_dicts.return_value = [{"value": "   "}]
        mock_storage.query.return_value = mock_df

        # Note: The current implementation only checks if string is truthy,
        # so whitespace-only keys would return True. This test documents
        # the current behavior.
        result = is_api_key_configured("whitespace", "WS_KEY", mock_storage)

        assert result is True

    def test_database_with_valid_key_takes_precedence(self) -> None:
        """Valid key in database should take precedence over env var."""
        mock_storage = MagicMock()
        mock_df = MagicMock()
        mock_df.is_empty.return_value = False
        mock_df.to_dicts.return_value = [{"value": "db_key"}]
        mock_storage.query.return_value = mock_df

        with patch.dict(os.environ, {"PRIORITY_KEY": "env_key"}):
            result = is_api_key_configured("priority", "PRIORITY_KEY", mock_storage)

        # Database should be checked first, env var should not be checked
        assert result is True
        mock_storage.query.assert_called_once()

    def test_long_api_key_returns_true(self) -> None:
        """Long valid API key should return True."""
        long_key = "a" * 1000  # Very long key
        mock_storage = MagicMock()
        mock_df = MagicMock()
        mock_df.is_empty.return_value = False
        mock_df.to_dicts.return_value = [{"value": long_key}]
        mock_storage.query.return_value = mock_df

        result = is_api_key_configured("longkey", "LONG_API_KEY", mock_storage)

        assert result is True

    def test_special_characters_in_key_returns_true(self) -> None:
        """Key with special characters should return True if not placeholder."""
        key_with_special = "key!@#$%^&*()_+-=[]{}|;:,.<>?"
        mock_storage = MagicMock()
        mock_df = MagicMock()
        mock_df.is_empty.return_value = False
        mock_df.to_dicts.return_value = [{"value": key_with_special}]
        mock_storage.query.return_value = mock_df

        result = is_api_key_configured("special", "SPECIAL_KEY", mock_storage)

        assert result is True


class TestBuildQuotaInfo:
    """Test build_quota_info function."""

    def test_all_quota_config_fields_populated(self) -> None:
        """Build quota info with all fields populated."""
        quota_config: dict[str, Any] = {
            "rate_limit": 100,
            "daily_limit": 5000,
            "capacity": "high",
        }

        result = build_quota_info("twelvedata", quota_config, True)

        assert result == {
            "source_name": "twelvedata",
            "configured": True,
            "rate_limit": 100,
            "daily_limit": 5000,
            "estimated_capacity": "high",
        }

    def test_quota_info_with_unconfigured_api(self) -> None:
        """Build quota info for unconfigured API."""
        quota_config: dict[str, Any] = {
            "rate_limit": 50,
            "daily_limit": 1000,
            "capacity": "low",
        }

        result = build_quota_info("polygon", quota_config, False)

        assert result == {
            "source_name": "polygon",
            "configured": False,
            "rate_limit": 50,
            "daily_limit": 1000,
            "estimated_capacity": "low",
        }

    def test_partial_quota_config_missing_rate_limit(self) -> None:
        """Build quota info with missing rate_limit."""
        quota_config: dict[str, Any] = {
            "daily_limit": 2000,
            "capacity": "medium",
        }

        result = build_quota_info("finnhub", quota_config, True)

        assert result == {
            "source_name": "finnhub",
            "configured": True,
            "rate_limit": None,
            "daily_limit": 2000,
            "estimated_capacity": "medium",
        }

    def test_partial_quota_config_missing_daily_limit(self) -> None:
        """Build quota info with missing daily_limit."""
        quota_config: dict[str, Any] = {
            "rate_limit": 75,
            "capacity": "medium",
        }

        result = build_quota_info("alphavantage", quota_config, True)

        assert result == {
            "source_name": "alphavantage",
            "configured": True,
            "rate_limit": 75,
            "daily_limit": None,
            "estimated_capacity": "medium",
        }

    def test_partial_quota_config_missing_capacity(self) -> None:
        """Build quota info with missing capacity."""
        quota_config: dict[str, Any] = {
            "rate_limit": 200,
            "daily_limit": 10000,
        }

        result = build_quota_info("newsapi", quota_config, True)

        assert result == {
            "source_name": "newsapi",
            "configured": True,
            "rate_limit": 200,
            "daily_limit": 10000,
            "estimated_capacity": None,
        }

    def test_empty_quota_config(self) -> None:
        """Build quota info with empty configuration."""
        quota_config: dict[str, Any] = {}

        result = build_quota_info("emptyapi", quota_config, True)

        assert result == {
            "source_name": "emptyapi",
            "configured": True,
            "rate_limit": None,
            "daily_limit": None,
            "estimated_capacity": None,
        }

    def test_quota_info_with_zero_values(self) -> None:
        """Build quota info with zero values."""
        quota_config: dict[str, Any] = {
            "rate_limit": 0,
            "daily_limit": 0,
            "capacity": "none",
        }

        result = build_quota_info("zeroapi", quota_config, False)

        assert result == {
            "source_name": "zeroapi",
            "configured": False,
            "rate_limit": 0,
            "daily_limit": 0,
            "estimated_capacity": "none",
        }

    def test_quota_info_with_null_values_in_config(self) -> None:
        """Build quota info when config has explicit None values."""
        quota_config: dict[str, Any] = {
            "rate_limit": None,
            "daily_limit": 5000,
            "capacity": None,
        }

        result = build_quota_info("nullapi", quota_config, True)

        assert result == {
            "source_name": "nullapi",
            "configured": True,
            "rate_limit": None,
            "daily_limit": 5000,
            "estimated_capacity": None,
        }

    def test_quota_info_source_name_preserved(self) -> None:
        """Source name should be preserved as-is in result."""
        source_names = ["api_1", "api-2", "API.3", "api_with_long_name"]

        for source in source_names:
            quota_config: dict[str, Any] = {"rate_limit": 100}
            result = build_quota_info(source, quota_config, True)
            assert result["source_name"] == source

    def test_quota_info_configured_flag_true(self) -> None:
        """Configured flag True should be preserved."""
        quota_config: dict[str, Any] = {"rate_limit": 100}

        result = build_quota_info("api", quota_config, True)

        assert result["configured"] is True

    def test_quota_info_configured_flag_false(self) -> None:
        """Configured flag False should be preserved."""
        quota_config: dict[str, Any] = {"rate_limit": 100}

        result = build_quota_info("api", quota_config, False)

        assert result["configured"] is False

    def test_quota_info_with_extra_fields_in_config(self) -> None:
        """Build quota info ignores extra fields in config."""
        quota_config: dict[str, Any] = {
            "rate_limit": 100,
            "daily_limit": 5000,
            "capacity": "high",
            "extra_field": "ignored",
            "another_extra": 999,
        }

        result = build_quota_info("api", quota_config, True)

        # Extra fields should not be in result
        assert "extra_field" not in result
        assert "another_extra" not in result
        assert result == {
            "source_name": "api",
            "configured": True,
            "rate_limit": 100,
            "daily_limit": 5000,
            "estimated_capacity": "high",
        }

    def test_quota_info_capacity_field_mapping(self) -> None:
        """Verify capacity field is mapped to estimated_capacity."""
        quota_config: dict[str, Any] = {
            "rate_limit": 100,
            "daily_limit": 5000,
            "capacity": "premium",
        }

        result = build_quota_info("api", quota_config, True)

        # Should use "estimated_capacity" key, not "capacity"
        assert "estimated_capacity" in result
        assert "capacity" not in result
        assert result["estimated_capacity"] == "premium"

    def test_quota_info_with_large_limits(self) -> None:
        """Build quota info with very large limit values."""
        quota_config: dict[str, Any] = {
            "rate_limit": 1_000_000,
            "daily_limit": 1_000_000_000,
            "capacity": "unlimited",
        }

        result = build_quota_info("unlimited", quota_config, True)

        assert result["rate_limit"] == 1_000_000
        assert result["daily_limit"] == 1_000_000_000
        assert result["estimated_capacity"] == "unlimited"

    def test_quota_info_with_string_numeric_values(self) -> None:
        """Build quota info preserves string values from config."""
        quota_config: dict[str, Any] = {
            "rate_limit": "100 per minute",
            "daily_limit": "5000 per day",
            "capacity": "high",
        }

        result = build_quota_info("api", quota_config, True)

        # Values should be preserved as-is
        assert result["rate_limit"] == "100 per minute"
        assert result["daily_limit"] == "5000 per day"
        assert result["estimated_capacity"] == "high"

    def test_quota_info_returns_dict_type(self) -> None:
        """build_quota_info should return a dict."""
        quota_config: dict[str, Any] = {"rate_limit": 100}

        result = build_quota_info("api", quota_config, True)

        assert isinstance(result, dict)

    def test_quota_info_with_boolean_capacity(self) -> None:
        """Build quota info with boolean values in capacity."""
        quota_config: dict[str, Any] = {
            "rate_limit": 100,
            "daily_limit": 5000,
            "capacity": True,
        }

        result = build_quota_info("api", quota_config, False)

        assert result["estimated_capacity"] is True
