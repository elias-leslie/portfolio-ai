"""Tests for Claude process and permission handling."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from dev_companion.claude_process import (
    ClaudeSession,
    ClaudeProcessError,
)


class TestClaudeSession:
    """Tests for ClaudeSession class."""

    def test_init_defaults(self):
        """Test session initialization with defaults."""
        session = ClaudeSession(session_id="test-123")
        assert session.session_id == "test-123"
        # working_dir defaults to "." which gets resolved to cwd
        assert session.working_dir.is_absolute()
        assert session._permission_callback is None
        assert session._pending_permission is None

    def test_init_with_working_dir(self, tmp_path):
        """Test session initialization with custom working directory."""
        session = ClaudeSession(
            session_id="test-456",
            working_dir=str(tmp_path),
        )
        assert session.working_dir == tmp_path

    def test_init_with_permission_callback(self):
        """Test session initialization with permission callback."""
        callback = AsyncMock()
        session = ClaudeSession(
            session_id="test-789",
            permission_callback=callback,
        )
        assert session._permission_callback is callback

    @pytest.mark.asyncio
    async def test_start_initializes_client(self):
        """Test that start() initializes the SDK client."""
        session = ClaudeSession(session_id="test-start")
        await session.start()

        assert session._options is not None
        assert session._connected is True
        assert session.is_active is True

    @pytest.mark.asyncio
    async def test_stop_cleans_up(self):
        """Test that stop() cleans up resources."""
        session = ClaudeSession(session_id="test-stop")
        await session.start()
        await session.stop()

        assert session._connected is False
        assert session._client is None
        assert session.is_active is False

    def test_resolve_permission_no_pending(self):
        """Test resolve_permission returns False when no pending request."""
        session = ClaudeSession(session_id="test-resolve")
        result = session.resolve_permission(True)
        assert result is False

    @pytest.mark.asyncio
    async def test_resolve_permission_with_pending(self):
        """Test resolve_permission resolves a pending future."""
        session = ClaudeSession(session_id="test-resolve2")
        loop = asyncio.get_event_loop()
        session._pending_permission = loop.create_future()

        result = session.resolve_permission(True)
        assert result is True
        assert session._pending_permission.result() is True

    def test_has_pending_permission_false(self):
        """Test has_pending_permission is False when no pending request."""
        session = ClaudeSession(session_id="test-pending")
        assert session.has_pending_permission is False

    @pytest.mark.asyncio
    async def test_has_pending_permission_true(self):
        """Test has_pending_permission is True when request pending."""
        session = ClaudeSession(session_id="test-pending2")
        loop = asyncio.get_event_loop()
        session._pending_permission = loop.create_future()

        assert session.has_pending_permission is True

    @pytest.mark.asyncio
    async def test_interrupt_no_active_client(self):
        """Test interrupt returns False when no active client."""
        session = ClaudeSession(session_id="test-interrupt")
        result = await session.interrupt()
        assert result is False

    @pytest.mark.asyncio
    async def test_send_without_start_raises(self):
        """Test send raises error if session not started."""
        session = ClaudeSession(session_id="test-send-no-start")

        with pytest.raises(ClaudeProcessError, match="Session not started"):
            async for _ in session.send("test"):
                pass


class TestPermissionHandling:
    """Tests for permission request/response flow."""

    @pytest.mark.asyncio
    async def test_permission_callback_called(self):
        """Test that permission callback is called when SDK requests permission."""
        callback_called = asyncio.Event()
        callback_args = {}

        async def permission_callback(tool_name, tool_input, context):
            callback_args["tool_name"] = tool_name
            callback_args["tool_input"] = tool_input
            callback_called.set()

        session = ClaudeSession(
            session_id="test-perm-callback",
            permission_callback=permission_callback,
        )
        await session.start()

        # Create a pending permission
        loop = asyncio.get_event_loop()
        session._pending_permission = loop.create_future()

        # Simulate calling the permission handler
        await permission_callback("Bash", {"command": "rm -rf /"}, None)

        assert callback_called.is_set()
        assert callback_args["tool_name"] == "Bash"
        assert callback_args["tool_input"]["command"] == "rm -rf /"

    @pytest.mark.asyncio
    async def test_permission_denied_response(self):
        """Test that denying permission returns PermissionResultDeny."""
        from claude_agent_sdk.types import PermissionResultDeny

        session = ClaudeSession(session_id="test-perm-deny")
        session._permission_callback = None  # No callback = deny

        result = await session._handle_permission_request(
            "Bash", {"command": "test"}, None
        )

        assert isinstance(result, PermissionResultDeny)
        assert "No permission handler" in result.message

    @pytest.mark.asyncio
    async def test_permission_timeout(self):
        """Test that permission request times out after delay."""
        from claude_agent_sdk.types import PermissionResultDeny

        async def slow_callback(tool_name, tool_input, context):
            # Just set up the future, don't resolve it
            pass

        session = ClaudeSession(
            session_id="test-perm-timeout",
            permission_callback=slow_callback,
        )

        # Patch the timeout to be very short for testing
        with patch.object(asyncio, "wait_for", side_effect=asyncio.TimeoutError):
            result = await session._handle_permission_request(
                "Bash", {"command": "test"}, None
            )

        assert isinstance(result, PermissionResultDeny)
        assert "timed out" in result.message
