"""WebSocket permission handling utilities."""

import json
from typing import Any, Callable

from .constants import PERMISSION_DISPLAY_STRING_LIMIT, PERMISSION_DISPLAY_JSON_LIMIT


def create_permission_callback(
    safe_send_json: Callable[[dict], Any],
    ws_closed_check: Callable[[], bool],
) -> Callable[[str, dict[str, Any], Any], Any]:
    """Create a permission callback function for WebSocket client.

    Args:
        safe_send_json: Function to send JSON to WebSocket
        ws_closed_check: Function to check if WebSocket is closed

    Returns:
        Async callback function for permission requests
    """

    async def permission_callback(
        tool_name: str, tool_input: dict[str, Any], context: Any
    ) -> None:
        """Send permission request to WebSocket client."""
        if ws_closed_check():
            return

        # Format tool input for display (truncate long values)
        display_input: dict[str, Any] = {}
        for key, value in tool_input.items():
            if isinstance(value, str) and len(value) > PERMISSION_DISPLAY_STRING_LIMIT:
                display_input[key] = value[:PERMISSION_DISPLAY_STRING_LIMIT] + "..."
            elif isinstance(value, (dict, list)):
                serialized = json.dumps(value)
                if len(serialized) > PERMISSION_DISPLAY_JSON_LIMIT:
                    display_input[key] = (
                        serialized[:PERMISSION_DISPLAY_JSON_LIMIT] + "..."
                    )
                else:
                    display_input[key] = value  # type: ignore[assignment]
            else:
                display_input[key] = value

        await safe_send_json(
            {
                "type": "permission_request",
                "tool_name": tool_name,
                "tool_input": display_input,
            }
        )

    return permission_callback
