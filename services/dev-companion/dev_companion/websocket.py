"""WebSocket endpoint for real-time communication."""

import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from .session_bridge import SessionBridge
from .roundtable import handle_roundtable_message
from .ws_connection import ConnectionManager
from .ws_permissions import create_permission_callback
from .ws_handlers import handle_user_message, handle_permission_response, handle_interrupt
from .ws_validation import validate_provider, validate_order, validate_max_turns

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

    # Validate parameters
    provider = validate_provider(provider)
    order = validate_order(order)
    max_turns = validate_max_turns(max_turns)

    # Send provider confirmation to client
    await websocket.send_json({"type": "provider", "name": provider})

    # Connection manager
    conn = ConnectionManager(websocket)

    # Create permission callback
    permission_callback = create_permission_callback(
        conn.safe_send_json, conn.is_closed
    )

    try:
        # Ensure session exists or create it
        session_data = await bridge.db.get_session(session_id)
        if not session_data:
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
                await conn.safe_send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = msg.get("type")

            if msg_type == "message":
                content = msg.get("content", "").strip()
                if not content:
                    await conn.safe_send_json({"type": "error", "message": "Empty message"})
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
                        safe_send_json=conn.safe_send_json,
                        permission_callback=permission_callback,
                        ws_closed_check=conn.is_closed,
                        max_turns=max_turns,
                    )
                    continue

                # Single provider mode
                await handle_user_message(
                    bridge=bridge,
                    session_id=session_id,
                    content=content,
                    provider=provider,
                    safe_send_json=conn.safe_send_json,
                    permission_callback=permission_callback,
                    ws_closed_check=conn.is_closed,
                )

            elif msg_type == "permission_response":
                allowed = msg.get("allowed", False)
                await handle_permission_response(bridge, session_id, allowed)

            elif msg_type == "interrupt":
                await handle_interrupt(bridge, session_id, conn.safe_send_json)

            elif msg_type == "ping":
                await conn.safe_send_json({"type": "pong"})

            else:
                await conn.safe_send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        conn.close()
        # Don't stop the Claude session - it can be reconnected
