"""FastAPI server with WebSocket support for Dev Companion."""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .database import Database
from .session_bridge import SessionBridge
from .stream_parser import message_to_dict
from .claude_process import ClaudeSession
from .gemini_process import GeminiSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global instances
db: Database | None = None
bridge: SessionBridge | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global db, bridge

    # Startup
    logger.info("Starting Dev Companion server...")

    db = Database()
    await db.connect()

    default_dir = os.environ.get("WORKING_DIR", str(Path.home() / "portfolio-ai"))
    bridge = SessionBridge(db, default_working_dir=default_dir)

    logger.info(f"Server started. Default working dir: {default_dir}")

    yield

    # Shutdown
    logger.info("Shutting down Dev Companion server...")
    if bridge:
        await bridge.shutdown()
    if db:
        await db.close()


app = FastAPI(
    title="Dev Companion",
    description="Web interface for Claude Code with browser context integration",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.8.233:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class CreateSessionRequest(BaseModel):
    """Request to create a new session."""

    working_dir: str | None = None
    metadata: dict[str, Any] | None = None


class SessionResponse(BaseModel):
    """Session information."""

    id: str
    working_dir: str
    created_at: str
    updated_at: str
    is_active: bool = False
    metadata: dict[str, Any] = {}
    original_provider: str | None = None
    message_count: int = 0
    description: str | None = None
    participants: list[str] = []


class MessageRequest(BaseModel):
    """Request to send a message."""

    message: str


# REST endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "dev-companion"}


@app.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create a new session."""
    if not bridge:
        raise HTTPException(status_code=503, detail="Service not ready")

    session_id = await bridge.create_session(
        working_dir=request.working_dir,
        metadata=request.metadata,
    )

    session = await bridge.db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=500, detail="Failed to create session")

    return SessionResponse(
        id=session["id"],
        working_dir=session["working_dir"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        metadata=session.get("metadata", {}),
        original_provider=session.get("original_provider"),
        message_count=session.get("message_count", 0),
        description=session.get("description"),
        participants=session.get("participants", []),
    )


@app.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(limit: int = 50):
    """List all sessions."""
    if not bridge:
        raise HTTPException(status_code=503, detail="Service not ready")

    sessions = await bridge.list_sessions(limit=limit)
    return [
        SessionResponse(
            id=s["id"],
            working_dir=s["working_dir"],
            created_at=s["created_at"],
            updated_at=s["updated_at"],
            is_active=s.get("is_active", False),
            metadata=s.get("metadata", {}),
            original_provider=s.get("original_provider"),
            message_count=s.get("message_count", 0),
            description=s.get("description"),
            participants=s.get("participants", []),
        )
        for s in sessions
    ]


@app.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get session details."""
    if not bridge:
        raise HTTPException(status_code=503, detail="Service not ready")

    session = await bridge.db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        id=session["id"],
        working_dir=session["working_dir"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        is_active=session_id in bridge._active_sessions,
        metadata=session.get("metadata", {}),
        original_provider=session.get("original_provider"),
        message_count=session.get("message_count", 0),
        description=session.get("description"),
        participants=session.get("participants", []),
    )


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    if not bridge:
        raise HTTPException(status_code=503, detail="Service not ready")

    deleted = await bridge.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"deleted": True}


@app.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str, limit: int = 100):
    """Get message history for a session."""
    if not bridge:
        raise HTTPException(status_code=503, detail="Service not ready")

    messages = await bridge.get_session_history(session_id, limit=limit)
    return {"messages": messages}


# Disagreement keywords for roundtable auto-discussion
DISAGREEMENT_KEYWORDS = [
    "disagree", "incorrect", "wrong", "mistake", "error",
    "actually", "however", "but i think", "not quite",
    "missing", "overlooked", "failed to consider",
    "inaccurate", "misleading", "contrary to",
    "i would argue", "that's not", "flaw", "omission",
    "hallucination", "incorrect assumption",
]


def detect_disagreement(response: str) -> bool:
    """Check if a response contains disagreement indicators."""
    response_lower = response.lower()
    return any(kw in response_lower for kw in DISAGREEMENT_KEYWORDS)


# WebSocket endpoint for real-time communication
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    provider: str = "claude",
    order: str = "claude-first",
):
    """WebSocket endpoint for real-time LLM communication.

    Query params:
    - provider: "claude" (default), "gemini", or "both" (roundtable mode)
    - order: "claude-first" (default) or "gemini-first" (only for roundtable)

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
    if not bridge:
        await websocket.close(code=1011, reason="Service not ready")
        return

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
                if isinstance(value, str) and len(value) > 200:
                    display_input[key] = value[:200] + "..."
                elif isinstance(value, (dict, list)):
                    serialized = json.dumps(value)
                    if len(serialized) > 500:
                        display_input[key] = serialized[:500] + "..."
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

                # Check if this is a new agent joining an existing session
                # If so, inject handoff context
                prompt_to_send = content
                session_data = await bridge.db.get_session(session_id)
                if session_data:
                    participants = session_data.get("participants", [])
                    message_count = session_data.get("message_count", 0)
                    # Inject context if session has history and this agent is new
                    if message_count > 0 and provider not in participants:
                        handoff_ctx = await build_handoff_context(bridge.db, session_id)
                        if handoff_ctx:
                            prompt_to_send = f"""{handoff_ctx}

---

**New message from user:**
{content}"""
                            logger.info(f"Injected handoff context for {provider} joining session")

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
                        await bridge.db.add_message(
                            session_id=session_id,
                            role="assistant",
                            content="".join(response_text_parts),
                            agent=provider,
                        )

                    # Set original_provider on first message (only if not already set)
                    await bridge.db.set_original_provider(session_id, provider)

                    # Increment message count and add participant
                    await bridge.db.increment_message_count(session_id)
                    await bridge.db.add_participant(session_id, provider)

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


async def get_or_create_gemini_session(
    bridge: SessionBridge,
    session_id: str,
) -> GeminiSession | None:
    """Get or create a Gemini session.

    Uses a separate namespace to avoid conflicts with Claude sessions.
    """
    gemini_key = f"gemini:{session_id}"

    # Check if already active
    if gemini_key in bridge._active_sessions:
        session = bridge._active_sessions[gemini_key]
        if session.is_active:
            return session
        # Clean up dead session
        del bridge._active_sessions[gemini_key]

    # Look up in database
    db_session = await bridge.db.get_session(session_id)
    if not db_session:
        return None

    # Create Gemini session
    session = GeminiSession(
        session_id=session_id,
        working_dir=db_session["working_dir"],
    )
    await session.start()

    # Restore Gemini session ID if we have one
    metadata = db_session.get("metadata", {})
    if metadata.get("sdk_session_id") and metadata.get("provider") == "gemini":
        session.sdk_session_id = metadata["sdk_session_id"]
        logger.info(f"Restored Gemini session ID: {session.sdk_session_id}")

    bridge._active_sessions[gemini_key] = session
    return session


async def get_or_create_session_with_permissions(
    bridge: SessionBridge,
    session_id: str,
    permission_callback: Any,
) -> ClaudeSession | None:
    """Get or create a Claude session with permission callback.

    This is a custom version that injects the permission callback.
    """
    # Check if already active
    if session_id in bridge._active_sessions:
        session = bridge._active_sessions[session_id]
        if session.is_active:
            # Update permission callback for this WebSocket connection
            session._permission_callback = permission_callback
            return session
        # Clean up dead session
        del bridge._active_sessions[session_id]

    # Look up in database
    db_session = await bridge.db.get_session(session_id)
    if not db_session:
        return None

    # Create Claude session with permission callback
    session = ClaudeSession(
        session_id=session_id,
        working_dir=db_session["working_dir"],
        permission_callback=permission_callback,
    )
    await session.start()

    # Restore SDK session ID if we have one
    metadata = db_session.get("metadata", {})
    if metadata.get("sdk_session_id"):
        session._sdk_session_id = metadata["sdk_session_id"]
        logger.info(f"Restored SDK session ID: {session._sdk_session_id}")

    bridge._active_sessions[session_id] = session
    return session


async def build_roundtable_context(db, session_id: str) -> str:
    """Build full conversation context for roundtable mode.

    Parses message history and formats with clear attribution so both
    agents understand who said what in previous exchanges.

    Args:
        db: Database instance
        session_id: Session identifier

    Returns:
        Formatted conversation history string, empty if no history
    """
    messages = await db.get_messages(session_id)

    if not messages:
        return ""

    context_parts = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "user":
            context_parts.append(f"[USER] {content}")
        elif role == "assistant":
            # Parse agent attribution from content prefix
            if content.startswith("[CLAUDE]"):
                context_parts.append(f"[CLAUDE] {content[8:].strip()}")
            elif content.startswith("[GEMINI]"):
                context_parts.append(f"[GEMINI] {content[8:].strip()}")
            elif " - Discussion Round " in content:
                # Handle discussion round format: [CLAUDE - Discussion Round 1]
                context_parts.append(content)
            else:
                context_parts.append(f"[ASSISTANT] {content}")

    return "\n\n".join(context_parts)


async def build_handoff_context(db: Database, session_id: str) -> str:
    """Build concise handoff context from session logs for agent switching.

    This provides the new agent with essential context about what was
    accomplished in the session, without replaying full message history.

    Args:
        db: Database instance
        session_id: Session identifier

    Returns:
        Formatted handoff context string
    """
    session = await db.get_session(session_id)
    if not session:
        return ""

    logs = await db.get_session_logs(session_id, limit=20)

    # Build worklog-style summary
    parts = []
    parts.append(f"## Session Context (ID: {session_id[:8]})")
    parts.append(f"**Topic**: {session.get('description') or 'No description'}")
    parts.append(f"**Started by**: {session.get('original_provider') or 'Unknown'}")

    participants = session.get("participants", [])
    if participants:
        parts.append(f"**Participants**: {', '.join(participants)}")

    parts.append(f"**Messages**: {session.get('message_count', 0)}")
    parts.append("")

    if logs:
        parts.append("## Recent Activity (worklog)")
        for log in logs:
            agent_icon = "◈" if log["agent"] == "claude" else "★"
            if log.get("log_entry"):
                parts.append(f"- [{agent_icon}] {log['log_entry']}")
                if log.get("key_files"):
                    try:
                        files = json.loads(log["key_files"])
                        if files:
                            parts.append(f"  Files: {', '.join(files)}")
                    except json.JSONDecodeError:
                        pass
                if log.get("learnings"):
                    parts.append(f"  Learning: {log['learnings']}")
        parts.append("")

        # Collect learnings
        learnings = [log["learnings"] for log in logs if log.get("learnings")]
        if learnings:
            parts.append("## Learnings from Session")
            for learning in learnings[-5:]:  # Last 5 learnings
                parts.append(f"- {learning}")

    return "\n".join(parts)


async def stream_agent_response(
    session: ClaudeSession | GeminiSession,
    content: str,
    safe_send_json,
    ws_closed_check,
    agent_name: str,
) -> str:
    """Stream a single agent's response and return the full text.

    Args:
        session: The agent session (Claude or Gemini)
        content: The prompt to send
        safe_send_json: Function to send JSON to WebSocket
        ws_closed_check: Function to check if WebSocket is closed
        agent_name: "claude" or "gemini" for attribution

    Returns:
        The complete response text
    """
    response_text_parts = []

    async for stream_msg in session.send(content):
        if ws_closed_check():
            break
        msg_dict = message_to_dict(stream_msg)
        # Add agent attribution to stream messages
        if not await safe_send_json({
            "type": "stream",
            "data": msg_dict,
            "agent": agent_name,
        }):
            break
        # Collect text
        for block in msg_dict.get("content", []):
            if block.get("type") == "text" and block.get("text"):
                response_text_parts.append(block["text"])

    return "".join(response_text_parts)


async def handle_roundtable_message(
    bridge: SessionBridge,
    session_id: str,
    content: str,
    order: str,
    safe_send_json,
    permission_callback,
    ws_closed_check,
    max_discussion_rounds: int = 2,
) -> None:
    """Handle a roundtable message with both Claude and Gemini.

    Both agents respond sequentially, with the second agent seeing the first's response.
    If disagreement is detected, they can have a brief discussion (up to max_discussion_rounds).
    """
    # Determine agent order
    if order == "gemini-first":
        first_agent = "gemini"
        second_agent = "claude"
    else:
        first_agent = "claude"
        second_agent = "gemini"

    logger.info(f"Roundtable: {first_agent} first, then {second_agent}")

    try:
        # Build conversation history context for multi-turn awareness
        history_context = await build_roundtable_context(bridge.db, session_id)
        if history_context:
            logger.info(f"Roundtable: Loaded {len(history_context)} chars of history context")

        # Get or create first agent session
        if first_agent == "gemini":
            first_session = await get_or_create_gemini_session(bridge, session_id)
        else:
            first_session = await get_or_create_session_with_permissions(
                bridge, session_id, permission_callback
            )

        if not first_session:
            await safe_send_json({
                "type": "error",
                "message": f"Failed to start {first_agent} session",
            })
            return

        # Build first agent prompt with history context
        if history_context:
            first_prompt = f"""This is a roundtable discussion. Previous conversation:

{history_context}

---

User's new message: {content}

You are {first_agent.upper()}. Respond to the user's message, considering the full conversation history above."""
        else:
            first_prompt = content

        # First agent responds
        await safe_send_json({"type": "agent_start", "agent": first_agent})
        first_response = await stream_agent_response(
            first_session, first_prompt, safe_send_json, ws_closed_check, first_agent
        )
        await safe_send_json({"type": "agent_done", "agent": first_agent})

        if ws_closed_check():
            return

        # Store first response
        await bridge.db.add_message(
            session_id=session_id,
            role="assistant",
            content=f"[{first_agent.upper()}] {first_response}",
            agent=first_agent,
        )

        # Set original_provider on first message (for roundtable: "both")
        await bridge.db.set_original_provider(session_id, "both")

        # Track participants and message count for first agent
        await bridge.db.increment_message_count(session_id)
        await bridge.db.add_participant(session_id, first_agent)

        # Get or create second agent session
        logger.info(f"Roundtable: Getting session for {second_agent}")
        if second_agent == "gemini":
            second_session = await get_or_create_gemini_session(bridge, session_id)
        else:
            second_session = await get_or_create_session_with_permissions(
                bridge, session_id, permission_callback
            )
        logger.info(f"Roundtable: {second_agent} session: {second_session is not None}")

        if not second_session:
            await safe_send_json({
                "type": "error",
                "message": f"Failed to start {second_agent} session",
            })
            await safe_send_json({"type": "done"})
            return

        # Second agent responds with full history context + first agent's response
        if history_context:
            context_prompt = f"""This is a roundtable discussion. Previous conversation:

{history_context}

---

User's new message: {content}

{first_agent.upper()} just responded:
{first_response}

---

You are {second_agent.upper()}. Provide your perspective on the user's message, considering the full conversation history. If you agree with {first_agent.upper()}'s response, say so briefly and add any additional insights. If you disagree or see any flaws, omissions, incorrect assumptions, or potential hallucinations in their response, clearly explain your concerns."""
        else:
            context_prompt = f"""The user asked: {content}

{first_agent.capitalize()} responded:
{first_response}

Now provide your perspective. If you agree with {first_agent.capitalize()}'s response, say so briefly and add any additional insights. If you disagree or see any flaws, omissions, incorrect assumptions, or potential hallucinations in the response, clearly explain your concerns."""

        await safe_send_json({"type": "agent_start", "agent": second_agent})
        logger.info(f"Roundtable: Starting {second_agent} stream, prompt length: {len(context_prompt)}")
        second_response = await stream_agent_response(
            second_session, context_prompt, safe_send_json, ws_closed_check, second_agent
        )
        logger.info(f"Roundtable: {second_agent} response length: {len(second_response)}")
        await safe_send_json({"type": "agent_done", "agent": second_agent})

        if ws_closed_check():
            return

        # Store second response
        await bridge.db.add_message(
            session_id=session_id,
            role="assistant",
            content=f"[{second_agent.upper()}] {second_response}",
            agent=second_agent,
        )

        # Track participants and message count for second agent
        await bridge.db.increment_message_count(session_id)
        await bridge.db.add_participant(session_id, second_agent)

        # Check for disagreement and start discussion if needed
        if detect_disagreement(second_response):
            await safe_send_json({
                "type": "discussion_start",
                "reason": "disagreement_detected",
            })

            responses = {first_agent: first_response, second_agent: second_response}
            sessions = {first_agent: first_session, second_agent: second_session}
            agents = [first_agent, second_agent]

            for round_num in range(1, max_discussion_rounds + 1):
                if ws_closed_check():
                    break

                # The agent who wasn't last to speak responds
                speaker = agents[(round_num - 1) % 2]
                other = agents[round_num % 2]

                # Include history context in discussion rounds too
                if history_context:
                    discussion_prompt = f"""This is a roundtable discussion. Previous conversation:

{history_context}

---

The original user message was: {content}

You are {speaker.upper()}. The other agent ({other.upper()}) just said:
{responses[other]}

Respond to their points briefly (2-3 sentences max). If you now agree, say so. If you still have concerns, explain."""
                else:
                    discussion_prompt = f"""The other agent ({other.capitalize()}) said:
{responses[other]}

Respond to their points. If you now agree, say so. If you still have concerns, explain briefly (2-3 sentences max)."""

                await safe_send_json({"type": "discussion_round", "round": round_num})
                await safe_send_json({"type": "agent_start", "agent": speaker})

                discussion_response = await stream_agent_response(
                    sessions[speaker],
                    discussion_prompt,
                    safe_send_json,
                    ws_closed_check,
                    speaker,
                )
                await safe_send_json({"type": "agent_done", "agent": speaker})

                # Store discussion turn
                await bridge.db.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=f"[{speaker.upper()} - Discussion Round {round_num}] {discussion_response}",
                    agent=speaker,
                )

                responses[speaker] = discussion_response

                # Check if they now agree (no more disagreement keywords)
                if not detect_disagreement(discussion_response):
                    logger.info(f"Roundtable: Agents reached agreement at round {round_num}")
                    break

        await safe_send_json({"type": "done"})

    except Exception as e:
        logger.error(f"Roundtable error: {e}")
        await safe_send_json({
            "type": "error",
            "message": f"Roundtable error: {str(e)}",
        })


def main():
    """Run the server."""
    import uvicorn

    port = int(os.environ.get("PORT", 9999))
    host = os.environ.get("HOST", "0.0.0.0")

    uvicorn.run(
        "dev_companion.server:app",
        host=host,
        port=port,
        reload=os.environ.get("DEV", "").lower() == "true",
    )


if __name__ == "__main__":
    main()
