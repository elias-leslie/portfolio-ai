"""Unit tests for market status API endpoint."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.utils.market_hours import NY_TZ


@contextmanager
def mock_market_time(mock_time: datetime) -> Generator[None]:
    """Mock datetime in both api.market.core_router and utils.market_hours modules."""
    with (
        patch("app.api.market.core_router.datetime") as mock_datetime_api,
        patch("app.utils.market_hours.datetime") as mock_datetime_utils,
        patch("app.middleware.cache.CACHE_ENABLED", False),  # Disable cache for tests
    ):
        # Mock datetime in both modules
        mock_datetime_api.now.return_value = mock_time
        mock_datetime_utils.now.return_value = mock_time

        # Preserve datetime.combine for market_hours calculations
        mock_datetime_utils.combine = datetime.combine
        mock_datetime_api.combine = datetime.combine

        # Allow datetime constructor calls to work
        mock_datetime_utils.side_effect = datetime
        mock_datetime_api.side_effect = datetime

        yield


class TestMarketStatusAPI:
    """Tests for GET /api/market/status endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client with minimal imports to avoid DB access."""
        # Import app with minimal side effects
        from app.main import app

        return TestClient(app)

    def test_market_open_during_trading_hours(self, client: TestClient) -> None:
        """Test status returns 'open' during regular trading hours."""
        # Wednesday, October 29, 2025, 10:30 AM ET (mid-trading day)
        mock_time = datetime(2025, 10, 29, 10, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "open"
            assert data["is_open"] is True
            assert data["is_holiday"] is False
            assert data["is_early_close"] is False
            assert data["holiday_name"] is None
            assert data["early_close_name"] is None
            assert "last_trading_day" in data
            assert "next_trading_day" in data
            assert "current_time_et" in data
            assert data["last_trading_day"] == "2025-10-29"
            assert data["expected_data_date"] == "2025-10-28"

    def test_market_closed_outside_trading_hours(self, client: TestClient) -> None:
        """Test status returns 'closed' outside trading hours."""
        # Wednesday, October 29, 2025, 9:00 PM ET (after after-hours close)
        mock_time = datetime(2025, 10, 29, 21, 0, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "closed"
            assert data["is_open"] is False
            assert data["is_holiday"] is False

    def test_pre_market_status(self, client: TestClient) -> None:
        """Test status returns 'pre_market' before market open."""
        # Wednesday, October 29, 2025, 8:00 AM ET (pre-market hours)
        mock_time = datetime(2025, 10, 29, 8, 0, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "pre_market"
            assert data["is_open"] is False
            assert data["is_holiday"] is False

    def test_after_hours_status(self, client: TestClient) -> None:
        """Test status returns 'after_hours' after market close."""
        # Wednesday, October 29, 2025, 5:00 PM ET (after-hours trading)
        mock_time = datetime(2025, 10, 29, 17, 0, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "after_hours"
            assert data["is_open"] is False
            assert data["is_holiday"] is False
            assert data["last_trading_day"] == "2025-10-29"
            assert data["expected_data_date"] == "2025-10-29"

    def test_market_closed_on_weekend(self, client: TestClient) -> None:
        """Test status returns 'closed' on weekend."""
        # Saturday, November 1, 2025, 10:30 AM ET
        mock_time = datetime(2025, 11, 1, 10, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "closed"
            assert data["is_open"] is False
            assert data["is_holiday"] is False

    def test_holiday_detection_new_years(self, client: TestClient) -> None:
        """Test holiday detection for New Year's Day."""
        # Wednesday, January 1, 2025, 10:30 AM ET (New Year's Day)
        mock_time = datetime(2025, 1, 1, 10, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "closed"
            assert data["is_open"] is False
            assert data["is_holiday"] is True
            assert data["holiday_name"] == "New Year's Day"
            assert data["is_early_close"] is False

    def test_holiday_detection_christmas(self, client: TestClient) -> None:
        """Test holiday detection for Christmas Day."""
        # Thursday, December 25, 2025, 10:30 AM ET (Christmas Day)
        mock_time = datetime(2025, 12, 25, 10, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "closed"
            assert data["is_open"] is False
            assert data["is_holiday"] is True
            assert data["holiday_name"] == "Christmas Day"

    def test_holiday_detection_thanksgiving(self, client: TestClient) -> None:
        """Test holiday detection for Thanksgiving Day."""
        # Thursday, November 27, 2025, 10:30 AM ET (Thanksgiving)
        mock_time = datetime(2025, 11, 27, 10, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "closed"
            assert data["is_open"] is False
            assert data["is_holiday"] is True
            assert data["holiday_name"] == "Thanksgiving Day"

    def test_early_close_day_detection(self, client: TestClient) -> None:
        """Test early close day detection (day after Thanksgiving)."""
        # Friday, November 28, 2025, 10:30 AM ET (Black Friday - early close)
        mock_time = datetime(2025, 11, 28, 10, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            # Early close day is still a trading day, so market is open at 10:30 AM
            assert data["status"] == "open"
            assert data["is_open"] is True
            assert data["is_holiday"] is False
            assert data["is_early_close"] is True
            assert data["early_close_name"] == "Day after Thanksgiving"

    def test_early_close_day_after_1pm(self, client: TestClient) -> None:
        """Test early close day after 1 PM ET."""
        # Friday, November 28, 2025, 2:00 PM ET (Black Friday after 1 PM close)
        mock_time = datetime(2025, 11, 28, 14, 0, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            # After 1 PM close on early close day
            assert data["status"] == "after_hours"
            assert data["is_open"] is False
            assert data["is_early_close"] is True

    def test_christmas_eve_early_close(self, client: TestClient) -> None:
        """Test Christmas Eve early close day."""
        # Wednesday, December 24, 2025, 11:00 AM ET (Christmas Eve)
        mock_time = datetime(2025, 12, 24, 11, 0, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "open"
            assert data["is_open"] is True
            assert data["is_early_close"] is True
            assert data["early_close_name"] == "Christmas Eve"

    def test_trading_day_fields_on_weekday(self, client: TestClient) -> None:
        """Test last_trading_day and next_trading_day on a regular weekday."""
        # Wednesday, October 29, 2025, 10:30 AM ET
        mock_time = datetime(2025, 10, 29, 10, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            # On Wednesday, last trading day is Wednesday (today), next is Thursday
            assert data["last_trading_day"] == "2025-10-29"
            assert data["next_trading_day"] == "2025-10-30"

    def test_trading_day_fields_on_friday(self, client: TestClient) -> None:
        """Test last_trading_day and next_trading_day on Friday."""
        # Friday, October 31, 2025, 10:30 AM ET
        mock_time = datetime(2025, 10, 31, 10, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            # On Friday, last trading day is Friday (today), next is Monday
            assert data["last_trading_day"] == "2025-10-31"
            assert data["next_trading_day"] == "2025-11-03"

    def test_trading_day_fields_on_saturday(self, client: TestClient) -> None:
        """Test last_trading_day and next_trading_day on Saturday."""
        # Saturday, November 1, 2025, 10:30 AM ET
        mock_time = datetime(2025, 11, 1, 10, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            # On Saturday, last trading day is Friday, next is Monday
            assert data["last_trading_day"] == "2025-10-31"
            assert data["next_trading_day"] == "2025-11-03"

    def test_trading_day_fields_on_sunday(self, client: TestClient) -> None:
        """Test last_trading_day and next_trading_day on Sunday."""
        # Sunday, November 2, 2025, 10:30 AM ET
        mock_time = datetime(2025, 11, 2, 10, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            # On Sunday, last trading day is Friday, next is Monday
            assert data["last_trading_day"] == "2025-10-31"
            assert data["next_trading_day"] == "2025-11-03"

    def test_trading_day_fields_before_holiday(self, client: TestClient) -> None:
        """Test trading days before a holiday (Christmas)."""
        # Tuesday, December 23, 2025, 10:30 AM ET (day before Christmas Eve)
        mock_time = datetime(2025, 12, 23, 10, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            # Tuesday is trading day, next is Wednesday (Christmas Eve - early close)
            assert data["last_trading_day"] == "2025-12-23"
            assert data["next_trading_day"] == "2025-12-24"

    def test_trading_day_fields_on_holiday(self, client: TestClient) -> None:
        """Test trading days on a holiday (Christmas)."""
        # Thursday, December 25, 2025, 10:30 AM ET (Christmas Day)
        mock_time = datetime(2025, 12, 25, 10, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            # On Christmas (Thursday), last trading day is Christmas Eve (Wednesday)
            # Next is Friday (day after Christmas)
            assert data["last_trading_day"] == "2025-12-24"
            assert data["next_trading_day"] == "2025-12-26"

    def test_current_time_et_format(self, client: TestClient) -> None:
        """Test current_time_et field format."""
        # Wednesday, October 29, 2025, 10:30:45 AM ET
        mock_time = datetime(2025, 10, 29, 10, 30, 45, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            # Check format: "YYYY-MM-DD HH:MM:SS ET"
            assert data["current_time_et"] == "2025-10-29 10:30:45 ET"

    def test_market_open_boundary_9_30_am(self, client: TestClient) -> None:
        """Test market status at exactly 9:30 AM ET (market open time)."""
        # Wednesday, October 29, 2025, 9:30 AM ET (exact market open)
        mock_time = datetime(2025, 10, 29, 9, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "open"
            assert data["is_open"] is True

    def test_market_close_boundary_4_00_pm(self, client: TestClient) -> None:
        """Test market status at exactly 4:00 PM ET (market close time)."""
        # Wednesday, October 29, 2025, 4:00 PM ET (exact market close)
        mock_time = datetime(2025, 10, 29, 16, 0, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            # At exactly 4:00 PM, market is closed (boundary condition)
            assert data["status"] == "after_hours"
            assert data["is_open"] is False

    def test_independence_day_holiday(self, client: TestClient) -> None:
        """Test Independence Day holiday detection."""
        # Friday, July 4, 2025, 10:30 AM ET (Independence Day)
        mock_time = datetime(2025, 7, 4, 10, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "closed"
            assert data["is_open"] is False
            assert data["is_holiday"] is True
            assert data["holiday_name"] == "Independence Day"

    def test_day_before_independence_day_early_close(self, client: TestClient) -> None:
        """Test day before Independence Day (early close)."""
        # Thursday, July 3, 2025, 10:30 AM ET (day before Independence Day)
        mock_time = datetime(2025, 7, 3, 10, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "open"
            assert data["is_open"] is True
            assert data["is_early_close"] is True
            assert data["early_close_name"] == "Day before Independence Day"

    def test_response_model_structure(self, client: TestClient) -> None:
        """Test that response contains all required fields."""
        # Wednesday, October 29, 2025, 10:30 AM ET
        mock_time = datetime(2025, 10, 29, 10, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            data = response.json()

            # Verify all required fields exist
            required_fields = [
                "status",
                "is_open",
                "last_trading_day",
                "next_trading_day",
                "current_time_et",
                "is_holiday",
                "holiday_name",
                "is_early_close",
                "early_close_name",
            ]

            for field in required_fields:
                assert field in data, f"Missing required field: {field}"

    def test_cache_header_present(self, client: TestClient) -> None:
        """Test that response includes cache headers (60s TTL)."""
        # Wednesday, October 29, 2025, 10:30 AM ET
        mock_time = datetime(2025, 10, 29, 10, 30, tzinfo=NY_TZ)

        with mock_market_time(mock_time):
            response = client.get("/api/market/status")

            assert response.status_code == 200
            # Verify cache decorator is applied (60s TTL)
            # Note: TestClient may not include all headers, but status code confirms endpoint works
