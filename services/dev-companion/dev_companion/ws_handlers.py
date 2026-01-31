"""WebSocket message handlers."""

import logging
from typing import Callable, Any

from .session_bridge import SessionBridge
from .stream_parser import message_to_dict
from .session_utils import (
    get_or_create_gemini_session,
    get_or_create_session_with_permissions,
    build_handoff_context,
    store_agent_message,
)

logger = logging.getLogger(__name__)


async def handle_user_message(
    bridge: SessionBridge,
    session_id: str,
    content: str,
    provider: str,
    safe_send_json: Callable[[dict], Any],
    permission_callback: Callable[[str, dict[str, Any], Any], Any],
    ws_closed_check: Callable[[], bool],
) -> None:
    """Handle user message in single provider mode.

    Args:
        bridge: SessionBridge instance
        session_id: Session identifier
        content: User message content
        provider: Provider name ("claude" or "gemini")
        safe_send_json: Function to send JSON to WebSocket
        permission_callback: Callback for permission requests
        ws_closed_check: Function to check if WebSocket is closed
    """
    logger.info(f"Single provider mode: {provider}")

    # Create session based on provider
    if provider == "gemini":
        session = await get_or_create_gemini_session(bridge, session_id)
        logger.info(f"Gemini session created: {session is not None}")
    else:
        session = await get_or_create_session_with_permissions(
            bridge, session_id, permission_callback
        )

    if not session:
        await safe_send_json({
            "type": "error",
            "message": f"Failed to start {provider} session",
        })
        return

    # Always inject conversation context if session has history
    # This ensures continuity across mode switches (roundtable -> single)
    prompt_to_send = content
    session_data = await bridge.db.get_session(session_id)
    if session_data:
        message_count = session_data.get("message_count", 0)
        if message_count > 0:
            handoff_ctx = await build_handoff_context(bridge.db, session_id)
            if handoff_ctx:
                prompt_to_send = f"""{handoff_ctx}

---

**New message from user:**
{content}"""
                logger.info(f"Injected conversation context for {provider}")

    # Stream response
    try:
        response_text_parts = []
        async for stream_msg in session.send(prompt_to_send):
            if ws_closed_check():
                logger.info(f"WebSocket closed during streaming for {session_id}")
                break
            msg_dict = message_to_dict(stream_msg)
            if not await safe_send_json({
                "type": "stream",
                "data": msg_dict,
            }):
                break  # WebSocket closed
            # Collect text for storage
            for block in msg_dict.get("content", []):
                if block.get("type") == "text" and block.get("text"):
                    response_text_parts.append(block["text"])

        # Store assistant response
        if response_text_parts:
            await store_agent_message(
                bridge.db, session_id, "".join(response_text_parts), provider
            )

        # Set original_provider on first message (only if not already set)
        await bridge.db.set_original_provider(session_id, provider)

        # Persist SDK/Gemini session ID for conversation continuity
        sdk_id = getattr(session, "sdk_session_id", None) or getattr(
            session, "_sdk_session_id", None
        )
        if sdk_id:
            await bridge.db.update_session(
                session_id=session_id,
                metadata={
                    "sdk_session_id": sdk_id,
                    "provider": provider,
                },
            )

        await safe_send_json({"type": "done"})

    except Exception as e:
        logger.error(f"Error streaming response: {e}")
        await safe_send_json({
            "type": "error",
            "message": str(e),
        })


async def handle_permission_response(
    bridge: SessionBridge,
    session_id: str,
    allowed: bool,
) -> None:
    """Handle permission response from user.

    Args:
        bridge: SessionBridge instance
        session_id: Session identifier
        allowed: Whether permission was granted
    """
    session = bridge._active_sessions.get(session_id)
    if session:
        resolved = session.resolve_permission(allowed)
        logger.info(f"Permission response: allowed={allowed}, resolved={resolved}")
    else:
        logger.warning(f"No session for permission response: {session_id}")


async def handle_interrupt(
    bridge: SessionBridge,
    session_id: str,
    safe_send_json: Callable[[dict], Any],
) -> None:
    """Handle interrupt signal from client.

    Args:
        bridge: SessionBridge instance
        session_id: Session identifier
        safe_send_json: Function to send JSON to WebSocket
    """
    session = bridge._active_sessions.get(session_id)
    if session:
        # Also cancel any pending permission
        if session.has_pending_permission:
            session.resolve_permission(False)
        success = await session.interrupt()
        await safe_send_json({
            "type": "interrupt_ack",
            "success": success,
        })
    else:
        await safe_send_json({
            "type": "interrupt_ack",
            "success": False,
            "message": "No active session",
        })
