"""Unit tests for capability scanner services."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from celery.schedules import crontab

from app.services.capability_scanner import (
    APIScanner,
    CeleryScanner,
    DatabaseScanner,
    _to_json_string,
)


class TestDatabaseScanner:
    """Test DatabaseScanner class."""

    @pytest.fixture
    def mock_conn_mgr(self) -> MagicMock:
        """Create mock ConnectionManager."""
        return MagicMock()

    @pytest.fixture
    def mock_config(self) -> dict:
        """Create mock config dict."""
        return {
            "scan_config": {
                "targets": {
                    "database": {
                        "enabled": True,
                        "track_field_completeness": True,
                        "track_freshness": True,
                        "null_threshold_pct": 80,
                    }
                }
            },
            "categorization": {
                "market_data": {"patterns": ["price", "market"]},
                "infrastructure": {"patterns": ["user", "auth"]},
            },
        }

    def test_init(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test scanner initialization."""
        scanner = DatabaseScanner(mock_conn_mgr, config=mock_config)

        assert scanner.conn_mgr == mock_conn_mgr
        assert scanner.config == mock_config
        assert scanner.db_config == mock_config["scan_config"]["targets"]["database"]

    @patch("app.services.capability_db_scanner.create_engine")
    @patch("app.services.capability_db_scanner.inspect")
    def test_scan_disabled(
        self,
        mock_inspect: MagicMock,
        mock_create_engine: MagicMock,
        mock_conn_mgr: MagicMock,
        mock_config: dict,
    ) -> None:
        """Test scan returns empty list when disabled."""
        # Disable scanning
        mock_config["scan_config"]["targets"]["database"]["enabled"] = False

        scanner = DatabaseScanner(mock_conn_mgr, config=mock_config)
        result = scanner.scan()

        assert result == []
        mock_create_engine.assert_not_called()
        mock_inspect.assert_not_called()

    @patch("app.services.capability_db_scanner.create_engine")
    @patch("app.services.capability_db_scanner.inspect")
    @patch("app.services.capability_db_scanner.get_expected_freshness")
    @patch("app.services.capability_db_scanner.categorize_by_name")
    def test_scan_single_table(
        self,
        mock_categorize: MagicMock,
        mock_get_freshness: MagicMock,
        mock_inspect: MagicMock,
        mock_create_engine: MagicMock,
        mock_conn_mgr: MagicMock,
        mock_config: dict,
    ) -> None:
        """Test scanning a single table."""
        # Setup mocks
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        # Also attach to connection manager which is used for queries
        mock_conn_mgr.connection.return_value.__enter__.return_value = mock_conn

        mock_inspector = MagicMock()
        mock_inspect.return_value = mock_inspector
        mock_inspector.get_table_names.return_value = ["test_table"]

        # Mock row count query
        mock_result = MagicMock()
        # Configure fetchone to return [100] for row count and column counts
        mock_result.fetchone.return_value = [100]
        # Also scalar just in case (though code uses fetchone)
        mock_result.scalar.return_value = 100
        mock_conn.execute.return_value = mock_result

        # Mock columns
        mock_inspector.get_columns.return_value = [
            {"name": "id"},
            {"name": "name"},
            {"name": "created_at"},
        ]

        # Mock categorization and freshness
        mock_categorize.return_value = "market_data"
        mock_get_freshness.return_value = "daily"

        scanner = DatabaseScanner(mock_conn_mgr, config=mock_config)
        result = scanner.scan()

        assert len(result) == 1
        assert result[0]["table_name"] == "test_table"
        assert result[0]["category"] == "market_data"
        assert result[0]["row_count"] == 100
        assert result[0]["total_columns"] == 3
        assert result[0]["expected_freshness"] == "daily"

    def test_calculate_freshness_status_current(
        self, mock_conn_mgr: MagicMock, mock_config: dict
    ) -> None:
        """Test freshness status calculation - current."""
        scanner = DatabaseScanner(mock_conn_mgr, config=mock_config)

        # Mock thresholds
        with patch("app.services.config_loader.get_freshness_thresholds") as mock_thresholds:
            mock_thresholds.return_value = {
                "current": 1,
                "acceptable": 2,
                "stale": 7,
                "critical": 7,
            }

            status = scanner._calculate_freshness_status("daily", 0)
            assert status == "current"

    def test_calculate_freshness_status_stale(
        self, mock_conn_mgr: MagicMock, mock_config: dict
    ) -> None:
        """Test freshness status calculation - stale."""
        scanner = DatabaseScanner(mock_conn_mgr, config=mock_config)

        with patch("app.services.config_loader.get_freshness_thresholds") as mock_thresholds:
            mock_thresholds.return_value = {
                "current": 1,
                "acceptable": 2,
                "stale": 7,
                "critical": 7,
            }

            status = scanner._calculate_freshness_status("daily", 5)
            assert status == "stale"

    def test_calculate_freshness_status_critical(
        self, mock_conn_mgr: MagicMock, mock_config: dict
    ) -> None:
        """Test freshness status calculation - critical."""
        scanner = DatabaseScanner(mock_conn_mgr, config=mock_config)

        with patch("app.services.config_loader.get_freshness_thresholds") as mock_thresholds:
            mock_thresholds.return_value = {
                "current": 1,
                "acceptable": 2,
                "stale": 7,
                "critical": 7,
            }

            status = scanner._calculate_freshness_status("daily", 10)
            assert status == "critical"

    def test_save_capabilities_upsert(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test saving capabilities with UPSERT logic."""
        mock_conn = MagicMock()
        mock_conn_mgr.connection.return_value.__enter__.return_value = mock_conn

        scanner = DatabaseScanner(mock_conn_mgr, config=mock_config)

        capabilities = [
            {
                "table_name": "test_table",
                "category": "market_data",
                "row_count": 100,
                "total_columns": 3,
                "columns": ["id", "name", "created_at"],
                "columns_with_data": ["id", "name"],
                "columns_mostly_null": ["created_at"],
                "completeness_pct": 67,
                "date_range_start": date(2025, 1, 1),
                "date_range_end": date(2025, 1, 10),
                "expected_freshness": "daily",
                "days_since_update": 1,
                "freshness_status": "current",
                "health_status": "active",  # Added missing field
            }
        ]

        count = scanner.save_capabilities(capabilities)

        assert count == 1
        assert mock_conn.execute.call_count == 1
        mock_conn.commit.assert_called_once()

    def test_save_capabilities_empty_list(
        self, mock_conn_mgr: MagicMock, mock_config: dict
    ) -> None:
        """Test saving empty capabilities list."""
        scanner = DatabaseScanner(mock_conn_mgr, config=mock_config)

        count = scanner.save_capabilities([])

        assert count == 0


class TestCeleryScanner:
    """Test CeleryScanner class."""

    @pytest.fixture
    def mock_conn_mgr(self) -> MagicMock:
        """Create mock ConnectionManager."""
        return MagicMock()

    @pytest.fixture
    def mock_config(self) -> dict:
        """Create mock config dict."""
        return {
            "scan_config": {
                "targets": {
                    "celery": {
                        "enabled": True,
                        "track_success_rate": True,
                        "lookback_days": 7,
                    }
                }
            },
            "categorization": {
                "market_data": {"patterns": ["market", "price"]},
                "infrastructure": {"patterns": ["maintenance"]},
            },
        }

    def test_init(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test scanner initialization."""
        scanner = CeleryScanner(mock_conn_mgr, config=mock_config)

        assert scanner.conn_mgr == mock_conn_mgr
        assert scanner.config == mock_config
        assert scanner.celery_config == mock_config["scan_config"]["targets"]["celery"]

    def test_scan_disabled(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test scan returns empty list when disabled."""
        mock_config["scan_config"]["targets"]["celery"]["enabled"] = False

        scanner = CeleryScanner(mock_conn_mgr, config=mock_config)
        result = scanner.scan()

        assert result == []

    @patch("app.services.capability_celery_scanner.categorize_by_name")
    def test_scan_with_tasks(
        self,
        mock_categorize: MagicMock,
        mock_conn_mgr: MagicMock,
        mock_config: dict,
    ) -> None:
        """Test scanning Celery tasks."""
        mock_categorize.return_value = "market_data"

        # Mock celery_app - patch the global app since it's imported locally
        with patch("app.celery_app.celery_app") as mock_celery:
            mock_celery.conf.beat_schedule = {
                "fetch-prices": {
                    "task": "app.tasks.market_data_tasks.fetch_prices",
                    "schedule": crontab(hour=4, minute=0),
                }
            }

            # Mock task metadata query
            mock_conn = MagicMock()
            mock_conn_mgr.connection.return_value.__enter__.return_value = mock_conn

            # Table exists check
            table_check = MagicMock()
            table_check.scalar.return_value = True
            mock_conn.execute.side_effect = [
                table_check,  # Table exists check
                MagicMock(
                    first=lambda: (
                        datetime(2025, 1, 10, 4, 0, tzinfo=UTC),
                        5,
                        0,
                    )
                ),  # Metadata query
            ]

            scanner = CeleryScanner(mock_conn_mgr, config=mock_config)
            result = scanner.scan()

            assert len(result) == 1
            assert result[0]["task_name"] == "fetch-prices"
            assert result[0]["category"] == "market_data"
            assert result[0]["task_path"] == "app.tasks.market_data_tasks.fetch_prices"
            assert result[0]["function_name"] == "fetch_prices"
            assert "Daily at 04:00 UTC" in result[0]["schedule_description"]

    def test_parse_schedule_crontab(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test parsing crontab schedule."""
        scanner = CeleryScanner(mock_conn_mgr, config=mock_config)

        schedule_obj = crontab(hour=4, minute=30)
        description, crontab_str, interval_seconds = scanner._parse_schedule(schedule_obj)

        assert "04:30 UTC" in description
        assert crontab_str == "30 4 * * *"
        assert interval_seconds == 86400  # Daily

    def test_parse_schedule_interval(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test parsing interval schedule."""
        scanner = CeleryScanner(mock_conn_mgr, config=mock_config)

        description, crontab_str, interval_seconds = scanner._parse_schedule(300)

        assert "5 minutes" in description
        assert crontab_str is None
        assert interval_seconds == 300

    def test_detect_populates_tables(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test detecting populated tables from task file."""
        scanner = CeleryScanner(mock_conn_mgr, config=mock_config)

        # Mock file content
        mock_content = """
def fetch_prices():
    conn.execute("INSERT INTO market_data (symbol, price) VALUES (%s, %s)")
    conn.execute("UPDATE price_cache SET last_updated = NOW()")
"""

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=mock_content),
        ):
            tables = scanner._detect_populates_tables("app.tasks.market_data_tasks.fetch_prices")

            assert "market_data" in tables
            assert "price_cache" in tables


class TestAPIScanner:
    """Test APIScanner class."""

    @pytest.fixture
    def mock_conn_mgr(self) -> MagicMock:
        """Create mock ConnectionManager."""
        return MagicMock()

    @pytest.fixture
    def mock_config(self) -> dict:
        """Create mock config dict."""
        return {
            "scan_config": {
                "targets": {
                    "api": {
                        "enabled": True,
                        "track_response_times": False,
                        "track_error_rates": False,
                    }
                }
            },
            "categorization": {
                "portfolio": {"patterns": ["portfolio", "watchlist"]},
                "market_data": {"patterns": ["market", "price"]},
            },
        }

    def test_init(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test scanner initialization."""
        scanner = APIScanner(mock_conn_mgr, config=mock_config)

        assert scanner.conn_mgr == mock_conn_mgr
        assert scanner.config == mock_config
        assert scanner.api_config == mock_config["scan_config"]["targets"]["api"]

    def test_scan_disabled(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test scan returns empty list when disabled."""
        mock_config["scan_config"]["targets"]["api"]["enabled"] = False

        scanner = APIScanner(mock_conn_mgr, config=mock_config)
        result = scanner.scan()

        assert result == []

    @patch("app.services.capability_api_scanner.categorize_by_name")
    def test_scan_route_file(
        self,
        mock_categorize: MagicMock,
        mock_conn_mgr: MagicMock,
        mock_config: dict,
    ) -> None:
        """Test scanning a route file for endpoints."""
        mock_categorize.return_value = "portfolio"

        scanner = APIScanner(mock_conn_mgr, config=mock_config)

        # Mock route file content
        route_content = '''
@router.get("/api/portfolio/accounts")
async def get_accounts():
    """Get all portfolio accounts."""
    pass

@router.post("/api/portfolio/account")
async def create_account():
    """Create new account."""
    pass
'''

        mock_path = MagicMock(spec=Path)
        mock_path.name = "portfolio.py"
        mock_path.read_text.return_value = route_content

        endpoints = scanner._scan_route_file(mock_path)

        assert len(endpoints) == 2
        assert endpoints[0]["endpoint_path"] == "/api/portfolio/accounts"
        assert endpoints[0]["http_method"] == "GET"
        assert endpoints[0]["category"] == "portfolio"
        assert endpoints[1]["endpoint_path"] == "/api/portfolio/account"
        assert endpoints[1]["http_method"] == "POST"

    def test_extract_function_name(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test extracting function name from route decorator."""
        scanner = APIScanner(mock_conn_mgr, config=mock_config)

        content = """
@router.get("/api/test")
async def test_endpoint():
    pass
"""

        func_name = scanner._extract_function_name(content, "get", "/api/test")
        assert func_name == "test_endpoint"

    def test_detect_table_dependencies(self, mock_conn_mgr: MagicMock, mock_config: dict) -> None:
        """Test detecting table dependencies from SQL queries."""
        scanner = APIScanner(mock_conn_mgr, config=mock_config)

        content = """
async def get_portfolio():
    result = conn.execute("SELECT * FROM portfolio_positions WHERE account_id = %s")
    accounts = conn.execute("SELECT * FROM portfolio_accounts JOIN watchlist_items ON ...")
"""

        tables = scanner._detect_table_dependencies(content, "get_portfolio")

        assert "portfolio_positions" in tables
        assert "portfolio_accounts" in tables
        assert "watchlist_items" in tables


class TestHelperFunctions:
    """Test helper functions."""

    def test_to_json_string_with_list(self) -> None:
        """Test converting list to JSON string."""
        result = _to_json_string(["a", "b", "c"])
        assert result == '["a", "b", "c"]'

    def test_to_json_string_with_none(self) -> None:
        """Test converting None to empty JSON array."""
        result = _to_json_string(None)
        assert result == "[]"

    def test_to_json_string_with_empty_list(self) -> None:
        """Test converting empty list to empty JSON array."""
        result = _to_json_string([])
        assert result == "[]"
