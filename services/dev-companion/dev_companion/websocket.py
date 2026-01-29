"""WebSocket endpoint for real-time communication."""

import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from .constants import PERMISSION_DISPLAY_STRING_LIMIT, PERMISSION_DISPLAY_JSON_LIMIT
from .session_bridge import SessionBridge
from .stream_parser import message_to_dict
from .session_utils import (
    get_or_create_gemini_session,
    get_or_create_session_with_permissions,
    build_handoff_context,
    store_agent_message,
)
from .roundtable import handle_roundtable_message

logger = logging.getLogger(__name__)


async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    bridge: SessionBridge,
    provider: str = "claude",
    order: str = "claude-first",
    max_turns: int = 10,
):
    """WebSocket endpoint for real-time LLM communication.

    Query params:
    - provider: "claude" (default), "gemini", or "both" (roundtable mode)
    - order: "claude-first" (default) or "gemini-first" (only for roundtable)
    - max_turns: maximum back-and-forth turns in roundtable (default 10)

    Protocol:
    - Client sends: {"type": "message", "content": "user message"}
    - Client sends: {"type": "permission_response", "allowed": true/false}
    - Server sends: {"type": "stream", "data": <StreamMessage as dict>}
    - Server sends: {"type": "permission_request", "tool_name": "...", "tool_input": {...}}
    - Server sends: {"type": "done"} when response complete
    - Server sends: {"type": "error", "message": "error details"}
    - Server sends: {"type": "provider", "name": "claude"|"gemini"|"both"} on connect
    - Server sends: {"type": "agent_start", "agent": "claude"|"gemini"} (roundtable)
    - Server sends: {"type": "agent_done", "agent": "claude"|"gemini"} (roundtable)
    - Server sends: {"type": "discussion_start", "reason": "..."} (roundtable)
    - Server sends: {"type": "discussion_round", "round": 1|2} (roundtable)
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for session {session_id}, provider={provider}, order={order}")

    # Validate and normalize provider
    provider = provider.lower() if provider else "claude"
    if provider not in ("claude", "gemini", "both"):
        logger.warning(f"Unknown provider '{provider}', defaulting to claude")
        provider = "claude"

    # Validate order for roundtable
    order = order.lower() if order else "claude-first"
    if order not in ("claude-first", "gemini-first"):
        order = "claude-first"

    # Validate max_turns (clamp to reasonable range)
    max_turns = max(1, min(100, max_turns))

    # Send provider confirmation to client
    await websocket.send_json({"type": "provider", "name": provider})

    # Track the current WebSocket for permission callbacks
    active_websocket: WebSocket | None = websocket
    ws_closed = False  # Track if WebSocket has been closed

    async def safe_send_json(data: dict) -> bool:
        """Send JSON to WebSocket, return False if closed."""
        nonlocal ws_closed
        if ws_closed:
            return False
        try:
            await websocket.send_json(data)
            return True
        except Exception:
            ws_closed = True
            return False

    async def permission_callback(tool_name: str, tool_input: dict[str, Any], context: Any) -> None:
        """Send permission request to WebSocket client."""
        nonlocal active_websocket, ws_closed
        if active_websocket and not ws_closed:
            # Format tool input for display (truncate long values)
            display_input = {}
            for key, value in tool_input.items():
                if isinstance(value, str) and len(value) > PERMISSION_DISPLAY_STRING_LIMIT:
                    display_input[key] = value[:PERMISSION_DISPLAY_STRING_LIMIT] + "..."
                elif isinstance(value, (dict, list)):
                    serialized = json.dumps(value)
                    if len(serialized) > PERMISSION_DISPLAY_JSON_LIMIT:
                        display_input[key] = serialized[:PERMISSION_DISPLAY_JSON_LIMIT] + "..."
                    else:
                        display_input[key] = value
                else:
                    display_input[key] = value

            await safe_send_json({
                "type": "permission_request",
                "tool_name": tool_name,
                "tool_input": display_input,
            })

    try:
        # Ensure session exists or create it
        session_data = await bridge.db.get_session(session_id)
        if not session_data:
            # Create new session
            await bridge.db.create_session(
                session_id=session_id,
                working_dir=str(bridge.default_working_dir),
            )

        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await safe_send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                })
                continue

            msg_type = msg.get("type")

            if msg_type == "message":
                content = msg.get("content", "").strip()
                if not content:
                    await safe_send_json({
                        "type": "error",
                        "message": "Empty message",
                    })
                    continue

                # Store user message
                await bridge.db.add_message(
                    session_id=session_id,
                    role="user",
                    content=content,
                )

                # Handle roundtable mode (both agents)
                if provider == "both":
                    await handle_roundtable_message(
                        bridge=bridge,
                        session_id=session_id,
                        content=content,
                        order=order,
                        safe_send_json=safe_send_json,
                        permission_callback=permission_callback,
                        ws_closed_check=lambda: ws_closed,
                        max_turns=max_turns,
                    )
                    continue

                # Single provider mode
                logger.info(f"Single provider mode: {provider}")
                if provider == "gemini":
                    session = await get_or_create_gemini_session(
                        bridge, session_id
                    )
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
                    continue

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
                        if ws_closed:
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

            elif msg_type == "permission_response":
                # Handle permission response from user
                allowed = msg.get("allowed", False)
                session = bridge._active_sessions.get(session_id)
                if session:
                    resolved = session.resolve_permission(allowed)
                    logger.info(f"Permission response: allowed={allowed}, resolved={resolved}")
                else:
                    logger.warning(f"No session for permission response: {session_id}")

            elif msg_type == "interrupt":
                # Handle interrupt signal
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

            elif msg_type == "ping":
                await safe_send_json({"type": "pong"})

            else:
                await safe_send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        ws_closed = True
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        ws_closed = True
        logger.error(f"WebSocket error: {e}")
    finally:
        ws_closed = True
        active_websocket = None
        # Don't stop the Claude session - it can be reconnected
