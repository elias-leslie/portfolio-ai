"""Permission handling for Claude sessions."""

import asyncio
import logging
from typing import Callable, Any

from claude_agent_sdk.types import (
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

logger = logging.getLogger(__name__)

# Timeout in seconds for user to respond to a permission request.
PERMISSION_TIMEOUT_SECONDS = 300

# Type for permission request callback
PermissionCallback = Callable[
    [str, dict[str, Any], ToolPermissionContext], asyncio.Future[bool]
]


class PermissionMixin:
    """Mixin that adds permission-request handling to a Claude session.

    Subclasses must provide:
        self.session_id: str
        self._permission_callback: PermissionCallback | None
        self._pending_permission: asyncio.Future[bool] | None
    """

    session_id: str
    _permission_callback: PermissionCallback | None
    _pending_permission: "asyncio.Future[bool] | None"

    async def _handle_permission_request(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        context: ToolPermissionContext,
    ) -> PermissionResultAllow | PermissionResultDeny:
        """Handle a permission request from the Claude SDK.

        Sends the request to the registered callback and waits for user
        resolution, with a timeout.
        """
        logger.info(f"[{self.session_id}] Permission request for tool: {tool_name}")

        if not self._permission_callback:
            logger.warning(
                f"[{self.session_id}] No permission callback - denying {tool_name}"
            )
            return PermissionResultDeny(message="No permission handler configured")

        try:
            loop = asyncio.get_event_loop()
            self._pending_permission = loop.create_future()

            await self._permission_callback(tool_name, tool_input, context)

            return await self._wait_for_permission(tool_name)
        except Exception as e:
            logger.error(f"[{self.session_id}] Error handling permission: {e}")
            return PermissionResultDeny(message=f"Permission error: {e}")
        finally:
            self._pending_permission = None

    async def _wait_for_permission(
        self, tool_name: str
    ) -> PermissionResultAllow | PermissionResultDeny:
        """Wait for the user to resolve the pending permission future."""
        assert self._pending_permission is not None
        try:
            allowed = await asyncio.wait_for(
                self._pending_permission,
                timeout=PERMISSION_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"[{self.session_id}] Permission request timed out for {tool_name}"
            )
            return PermissionResultDeny(message="Permission request timed out")

        if allowed:
            logger.info(f"[{self.session_id}] Permission ALLOWED for {tool_name}")
            return PermissionResultAllow()
        logger.info(f"[{self.session_id}] Permission DENIED for {tool_name}")
        return PermissionResultDeny(message="User denied permission")

    def resolve_permission(self, allowed: bool) -> bool:
        """Resolve a pending permission request.

        Called by the WebSocket handler when the user responds.

        Returns:
            True if there was a pending request to resolve.
        """
        if self._pending_permission and not self._pending_permission.done():
            self._pending_permission.set_result(allowed)
            return True
        return False

    @property
    def has_pending_permission(self) -> bool:
        """True if a permission request is awaiting user response."""
        return (
            self._pending_permission is not None
            and not self._pending_permission.done()
        )
