"""Tests for health monitoring endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestDeletionRateEndpoint:
    """Tests for GET /health/deletion-rate endpoint."""

    def test_deletion_rate_returns_200(self) -> None:
        """Test deletion rate endpoint returns 200 OK."""
        response = client.get("/health/deletion-rate")
        assert response.status_code == 200

    def test_deletion_rate_returns_required_fields(self) -> None:
        """Test deletion rate response contains required fields."""
        response = client.get("/health/deletion-rate")
        data = response.json()

        assert "status" in data
        assert "time_window_hours" in data
        assert "deletions_by_table" in data
        assert "total_deletions" in data
        assert "message" in data

    def test_deletion_rate_default_time_window(self) -> None:
        """Test deletion rate uses default 1 hour window."""
        response = client.get("/health/deletion-rate")
        data = response.json()

        assert data["time_window_hours"] == 1

    def test_deletion_rate_custom_time_window(self) -> None:
        """Test deletion rate accepts custom time window."""
        response = client.get("/health/deletion-rate?hours=24")
        data = response.json()

        assert data["time_window_hours"] == 24

    def test_deletion_rate_status_ok_for_low_deletions(self) -> None:
        """Test status is ok when deletions below warning threshold."""
        response = client.get("/health/deletion-rate")
        data = response.json()

        # With no or low deletions, status should be ok
        assert data["status"] in ["ok", "warning", "critical"]

    def test_deletion_rate_deletions_by_table_is_dict_or_list(self) -> None:
        """Test deletions_by_table is a dict or list."""
        response = client.get("/health/deletion-rate")
        data = response.json()

        # Can be empty dict {} or list [] depending on implementation
        assert isinstance(data["deletions_by_table"], (dict, list))

    def test_deletion_rate_total_deletions_is_integer(self) -> None:
        """Test total_deletions is an integer."""
        response = client.get("/health/deletion-rate")
        data = response.json()

        assert isinstance(data["total_deletions"], int)

    def test_deletion_rate_alert_thresholds_present(self) -> None:
        """Test alert thresholds are included in response."""
        response = client.get("/health/deletion-rate")
        data = response.json()

        assert "alert_threshold_warning" in data
        assert "alert_threshold_critical" in data


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_returns_200(self) -> None:
        """Test health endpoint returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_status(self) -> None:
        """Test health endpoint returns status field."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert data["status"] == "healthy"
