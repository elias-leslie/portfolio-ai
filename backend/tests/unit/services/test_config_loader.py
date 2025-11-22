"""Unit tests for capabilities config loader."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml

from app.services.config_loader import (
    categorize_by_name,
    get_expected_freshness,
    get_freshness_thresholds,
    load_capabilities_config,
    reload_config,
)


class TestLoadCapabilitiesConfig:
    """Test load_capabilities_config() function."""

    @pytest.fixture
    def mock_config_data(self) -> dict:
        """Create mock config data."""
        return {
            "scan_config": {
                "enabled": True,
                "targets": {
                    "database": {"enabled": True},
                    "celery": {"enabled": True},
                    "api": {"enabled": True},
                },
            },
            "categorization": {
                "market_data": {"patterns": ["market", "price"]},
            },
            "freshness_rules": {
                "daily": {
                    "current": 1,
                    "acceptable": 2,
                    "stale": 7,
                    "critical": 7,
                }
            },
        }

    def test_load_config_success(self, mock_config_data: dict) -> None:
        """Test loading valid config file."""
        mock_yaml_content = yaml.dump(mock_config_data)

        with (
            patch("builtins.open", mock_open(read_data=mock_yaml_content)),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "stat") as mock_stat,
        ):
            mock_stat.return_value.st_mtime = 123456

            # Clear cache first
            import app.services.config_loader

            app.services.config_loader._cached_config = None

            config = load_capabilities_config()

            assert config == mock_config_data
            assert "scan_config" in config
            assert "categorization" in config

    def test_load_config_file_not_found(self) -> None:
        """Test error when config file doesn't exist."""
        with patch.object(Path, "exists", return_value=False):
            # Clear cache
            import app.services.config_loader

            app.services.config_loader._cached_config = None

            with pytest.raises(FileNotFoundError) as exc_info:
                load_capabilities_config()

            assert "config file not found" in str(exc_info.value).lower()

    def test_load_config_missing_required_keys(self) -> None:
        """Test error when required keys are missing."""
        invalid_config = {"scan_config": {}}  # Missing categorization

        mock_yaml_content = yaml.dump(invalid_config)

        with (
            patch("builtins.open", mock_open(read_data=mock_yaml_content)),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "stat") as mock_stat,
        ):
            mock_stat.return_value.st_mtime = 123456

            # Clear cache
            import app.services.config_loader

            app.services.config_loader._cached_config = None

            with pytest.raises(ValueError) as exc_info:
                load_capabilities_config()

            assert "missing required config keys" in str(exc_info.value).lower()

    def test_load_config_uses_cache(self, mock_config_data: dict) -> None:
        """Test that config is cached and reused."""
        mock_yaml_content = yaml.dump(mock_config_data)

        with (
            patch("builtins.open", mock_open(read_data=mock_yaml_content)) as mock_file,
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "stat") as mock_stat,
        ):
            mock_stat.return_value.st_mtime = 123456

            # Clear cache and load first time
            import app.services.config_loader

            app.services.config_loader._cached_config = None
            config1 = load_capabilities_config()

            # Load second time (should use cache)
            config2 = load_capabilities_config()

            assert config1 == config2
            # File should only be opened once (cached on second call)
            assert mock_file.call_count == 1

    def test_load_config_reloads_on_file_change(self, mock_config_data: dict) -> None:
        """Test that config reloads when file timestamp changes."""
        mock_yaml_content = yaml.dump(mock_config_data)

        with (
            patch("builtins.open", mock_open(read_data=mock_yaml_content)) as mock_file,
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "stat") as mock_stat,
        ):
            # First load with mtime 123456
            mock_stat.return_value.st_mtime = 123456

            import app.services.config_loader

            app.services.config_loader._cached_config = None
            config1 = load_capabilities_config()

            # Second load with different mtime (file changed)
            mock_stat.return_value.st_mtime = 999999
            config2 = load_capabilities_config()

            # File should be opened twice (cache invalidated)
            assert mock_file.call_count == 2


class TestGetExpectedFreshness:
    """Test get_expected_freshness() function."""

    def test_get_expected_freshness_existing_table(self) -> None:
        """Test getting freshness for a table in config."""
        mock_config = {
            "scan_config": {
                "targets": {
                    "database": {
                        "expected_freshness": {
                            "news_cache": "hourly",
                            "market_data": "daily",
                        }
                    }
                }
            },
            "categorization": {},
        }

        with patch(
            "app.services.config_loader.load_capabilities_config",
            return_value=mock_config,
        ):
            freshness = get_expected_freshness("news_cache")
            assert freshness == "hourly"

    def test_get_expected_freshness_default(self) -> None:
        """Test getting freshness for a table not in config (defaults to daily)."""
        mock_config = {
            "scan_config": {"targets": {"database": {"expected_freshness": {}}}},
            "categorization": {},
        }

        with patch(
            "app.services.config_loader.load_capabilities_config",
            return_value=mock_config,
        ):
            freshness = get_expected_freshness("unknown_table")
            assert freshness == "daily"


class TestGetFreshnessThresholds:
    """Test get_freshness_thresholds() function."""

    def test_get_thresholds_daily(self) -> None:
        """Test getting thresholds for daily freshness."""
        mock_config = {
            "scan_config": {"targets": {}},
            "categorization": {},
            "freshness_rules": {
                "daily": {
                    "current": 1,
                    "acceptable": 2,
                    "stale": 7,
                    "critical": 7,
                }
            },
        }

        with patch(
            "app.services.config_loader.load_capabilities_config",
            return_value=mock_config,
        ):
            thresholds = get_freshness_thresholds("daily")

            assert thresholds["current"] == 1
            assert thresholds["acceptable"] == 2
            assert thresholds["stale"] == 7
            assert thresholds["critical"] == 7

    def test_get_thresholds_hourly(self) -> None:
        """Test getting thresholds for hourly freshness."""
        mock_config = {
            "scan_config": {"targets": {}},
            "categorization": {},
            "freshness_rules": {
                "hourly": {
                    "current": 0.08,
                    "acceptable": 0.25,
                    "stale": 1,
                    "critical": 1,
                },
                "daily": {
                    "current": 1,
                    "acceptable": 2,
                    "stale": 7,
                    "critical": 7,
                },
            },
        }

        with patch(
            "app.services.config_loader.load_capabilities_config",
            return_value=mock_config,
        ):
            thresholds = get_freshness_thresholds("hourly")

            assert thresholds["current"] == 0.08
            assert thresholds["acceptable"] == 0.25

    def test_get_thresholds_fallback_to_daily(self) -> None:
        """Test getting thresholds for unknown freshness (falls back to daily)."""
        mock_config = {
            "scan_config": {"targets": {}},
            "categorization": {},
            "freshness_rules": {
                "daily": {
                    "current": 1,
                    "acceptable": 2,
                    "stale": 7,
                    "critical": 7,
                }
            },
        }

        with patch(
            "app.services.config_loader.load_capabilities_config",
            return_value=mock_config,
        ):
            thresholds = get_freshness_thresholds("unknown_freshness")

            # Should fall back to daily
            assert thresholds["current"] == 1
            assert thresholds["acceptable"] == 2


class TestCategorizeByName:
    """Test categorize_by_name() function."""

    def test_categorize_market_data(self) -> None:
        """Test categorizing market data tables/tasks."""
        mock_config = {
            "scan_config": {"targets": {}},
            "categorization": {
                "market_data": {"patterns": ["market", "price", "ohlcv"]},
                "news": {"patterns": ["news", "article"]},
            },
        }

        with patch(
            "app.services.config_loader.load_capabilities_config",
            return_value=mock_config,
        ):
            category = categorize_by_name("market_data_daily")
            assert category == "market_data"

            category = categorize_by_name("price_cache")
            assert category == "market_data"

    def test_categorize_news(self) -> None:
        """Test categorizing news tables/tasks."""
        mock_config = {
            "scan_config": {"targets": {}},
            "categorization": {
                "market_data": {"patterns": ["market", "price"]},
                "news": {"patterns": ["news", "article"]},
            },
        }

        with patch(
            "app.services.config_loader.load_capabilities_config",
            return_value=mock_config,
        ):
            category = categorize_by_name("news_cache")
            assert category == "news"

            category = categorize_by_name("article_quality")
            assert category == "news"

    def test_categorize_default_to_infrastructure(self) -> None:
        """Test categorizing unknown names defaults to infrastructure."""
        mock_config = {
            "scan_config": {"targets": {}},
            "categorization": {
                "market_data": {"patterns": ["market", "price"]},
            },
        }

        with patch(
            "app.services.config_loader.load_capabilities_config",
            return_value=mock_config,
        ):
            category = categorize_by_name("unknown_table")
            assert category == "infrastructure"

    def test_categorize_case_insensitive(self) -> None:
        """Test categorization is case insensitive."""
        mock_config = {
            "scan_config": {"targets": {}},
            "categorization": {
                "portfolio": {"patterns": ["portfolio", "watchlist"]},
            },
        }

        with patch(
            "app.services.config_loader.load_capabilities_config",
            return_value=mock_config,
        ):
            # Should match "portfolio" pattern
            category = categorize_by_name("PORTFOLIO_positions")
            assert category == "portfolio"

            category = categorize_by_name("WatchList_Items")
            assert category == "portfolio"


class TestReloadConfig:
    """Test reload_config() function."""

    def test_reload_clears_cache(self) -> None:
        """Test that reload_config clears the cache."""
        mock_config = {
            "scan_config": {
                "enabled": True,
                "targets": {
                    "database": {"enabled": True},
                    "celery": {"enabled": True},
                    "api": {"enabled": True},
                },
            },
            "categorization": {},
        }

        mock_yaml_content = yaml.dump(mock_config)

        with (
            patch("builtins.open", mock_open(read_data=mock_yaml_content)),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "stat") as mock_stat,
        ):
            mock_stat.return_value.st_mtime = 123456

            import app.services.config_loader

            # Set cache
            app.services.config_loader._cached_config = {"old": "data"}
            app.services.config_loader._config_mtime = 999999

            # Reload should clear cache and load fresh
            config = reload_config()

            assert config == mock_config
            assert app.services.config_loader._cached_config == mock_config
