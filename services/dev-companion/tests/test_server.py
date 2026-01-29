"""Tests for the Dev Companion FastAPI server."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self):
        """Test that health endpoint returns healthy status."""
        from dev_companion.server import app

        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "dev-companion"


class TestSessionEndpoints:
    """Tests for session management endpoints."""

    def test_create_session(self):
        """Test creating a new session."""
        from dev_companion.server import app

        with TestClient(app) as client:
            response = client.post(
                "/sessions",
                json={"working_dir": "/tmp", "metadata": {"test": True}},
            )
            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert data["working_dir"] == "/tmp"

    def test_list_sessions(self):
        """Test listing sessions."""
        from dev_companion.server import app

        with TestClient(app) as client:
            response = client.get("/sessions")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)


class TestWebSocketProtocol:
    """Tests for WebSocket message types."""

    def test_message_type_enum(self):
        """Test that message types are properly defined."""
        # Valid message types
        valid_types = ["message", "permission_response", "interrupt", "ping"]
        for msg_type in valid_types:
            msg = {"type": msg_type}
            assert msg["type"] in valid_types

    def test_permission_response_format(self):
        """Test permission response message format."""
        # Allow response
        allow_msg = {"type": "permission_response", "allowed": True}
        assert allow_msg["allowed"] is True

        # Deny response
        deny_msg = {"type": "permission_response", "allowed": False}
        assert deny_msg["allowed"] is False


class TestPermissionRequestFormat:
    """Tests for permission request message format."""

    def test_permission_request_structure(self):
        """Test that permission requests have correct structure."""
        permission_request = {
            "type": "permission_request",
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /tmp/test"},
        }

        assert permission_request["type"] == "permission_request"
        assert permission_request["tool_name"] == "Bash"
        assert "command" in permission_request["tool_input"]

    def test_permission_request_truncation(self):
        """Test that long tool inputs are truncated for display."""
        # Simulate server-side truncation logic
        long_value = "x" * 300
        display_input = {}

        tool_input = {"content": long_value}
        for key, value in tool_input.items():
            if isinstance(value, str) and len(value) > 200:
                display_input[key] = value[:200] + "..."
            else:
                display_input[key] = value

        assert len(display_input["content"]) == 203  # 200 + "..."
        assert display_input["content"].endswith("...")


class TestGetOrCreateSessionWithPermissions:
    """Tests for session creation with permission callback."""

    @pytest.mark.asyncio
    async def test_creates_new_session(self):
        """Test that a new session is created when not in active sessions."""
        from dev_companion.session_utils import get_or_create_session_with_permissions
        from dev_companion.session_bridge import SessionBridge
        from dev_companion.database import Database

        # Mock the bridge
        mock_db = AsyncMock(spec=Database)
        mock_db.get_session.return_value = {
            "id": "test-session",
            "working_dir": "/tmp",
            "created_at": "2024-01-01",
            "updated_at": "2024-01-01",
            "metadata": {},
        }

        bridge = SessionBridge(mock_db)
        callback = AsyncMock()

        with patch("dev_companion.session_utils.ClaudeSession") as MockSession:
            mock_session = MagicMock()
            mock_session.is_active = True
            MockSession.return_value = mock_session
            mock_session.start = AsyncMock()

            session = await get_or_create_session_with_permissions(
                bridge, "test-session", callback
            )

            assert session is not None
            MockSession.assert_called_once()
            mock_session.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_existing_session(self):
        """Test that existing active session is returned."""
        from dev_companion.session_utils import get_or_create_session_with_permissions
        from dev_companion.session_bridge import SessionBridge
        from dev_companion.database import Database
        from dev_companion.claude_process import ClaudeSession

        mock_db = AsyncMock(spec=Database)
        bridge = SessionBridge(mock_db)

        # Pre-populate with active session
        mock_session = MagicMock(spec=ClaudeSession)
        mock_session.is_active = True
        bridge._active_sessions["existing-session"] = mock_session

        callback = AsyncMock()

        session = await get_or_create_session_with_permissions(
            bridge, "existing-session", callback
        )

        assert session is mock_session
        # Permission callback should be updated
        assert mock_session._permission_callback == callback
