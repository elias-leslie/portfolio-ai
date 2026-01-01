"""FastAPI server with WebSocket support for Dev Companion."""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
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

# Permission display limits
PERMISSION_DISPLAY_STRING_LIMIT = 200
PERMISSION_DISPLAY_JSON_LIMIT = 500

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


def _session_to_response(session: dict, is_active: bool = False) -> SessionResponse:
    """Convert a database session dict to SessionResponse.

    Args:
        session: Session dictionary from database
        is_active: Whether the session is currently active

    Returns:
        SessionResponse model
    """
    return SessionResponse(
        id=session["id"],
        working_dir=session["working_dir"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        is_active=is_active,
        metadata=session.get("metadata", {}),
        original_provider=session.get("original_provider"),
        message_count=session.get("message_count", 0),
        description=session.get("description"),
        participants=session.get("participants", []),
    )


async def _store_agent_message(db: Database, session_id: str, content: str, agent: str) -> None:
    """Store an agent message and update session metadata.

    Args:
        db: Database instance
        session_id: Session identifier
        content: Message content
        agent: Agent name (e.g., "claude", "gemini")
    """
    await db.add_message(
        session_id=session_id,
        role="assistant",
        content=content,
        agent=agent,
    )
    await db.increment_message_count(session_id)
    await db.add_participant(session_id, agent)


def require_bridge() -> SessionBridge:
    """Dependency that ensures bridge is available.

    Raises:
        HTTPException: 503 if bridge is not initialized

    Returns:
        The initialized SessionBridge instance
    """
    if not bridge:
        raise HTTPException(status_code=503, detail="Service not ready")
    return bridge


# REST endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "dev-companion"}


@app.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    bridge: SessionBridge = Depends(require_bridge),
):
    """Create a new session."""
    session_id = await bridge.create_session(
        working_dir=request.working_dir,
        metadata=request.metadata,
    )

    session = await bridge.db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=500, detail="Failed to create session")

    return _session_to_response(session)


@app.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    limit: int = 50,
    bridge: SessionBridge = Depends(require_bridge),
):
    """List all sessions."""
    sessions = await bridge.list_sessions(limit=limit)
    return [
        _session_to_response(s, is_active=s.get("is_active", False))
        for s in sessions
    ]


@app.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    bridge: SessionBridge = Depends(require_bridge),
):
    """Get session details."""
    session = await bridge.db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return _session_to_response(
        session,
        is_active=session_id in bridge._active_sessions
    )


@app.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    bridge: SessionBridge = Depends(require_bridge),
):
    """Delete a session."""
    deleted = await bridge.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"deleted": True}


@app.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    limit: int = 100,
    bridge: SessionBridge = Depends(require_bridge),
):
    """Get message history for a session."""
    messages = await bridge.get_session_history(session_id, limit=limit)
    return {"messages": messages}


class MessageCreate(BaseModel):
    """Request body for adding a message."""

    role: str  # user, assistant, system, evidence
    content: str
    metadata: dict | None = None


@app.post("/sessions/{session_id}/messages")
async def add_message(session_id: str, msg: MessageCreate):
    """Add a message to session history (for evidence, system messages, etc)."""
    if not bridge:
        raise HTTPException(status_code=503, detail="Service not ready")

    await bridge.db.add_message(
        session_id=session_id,
        role=msg.role,
        content=msg.content,
        metadata=msg.metadata or {},
    )

    return {"added": True}


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
                        await _store_agent_message(
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
    """Build handoff context for agent switching.

    Includes actual conversation history so the new agent understands
    what was discussed. Falls back to session metadata if no messages.

    Args:
        db: Database instance
        session_id: Session identifier

    Returns:
        Formatted handoff context string
    """
    session = await db.get_session(session_id)
    if not session:
        return ""

    # Build header with session info
    parts = []
    parts.append(f"## Session Context (ID: {session_id[:8]})")
    parts.append(f"**Started by**: {session.get('original_provider') or 'Unknown'}")

    participants = session.get("participants", [])
    if participants:
        parts.append(f"**Participants so far**: {', '.join(participants)}")
    parts.append("")

    # Include actual conversation history (most important for context)
    messages = await db.get_messages(session_id, limit=20)
    if messages:
        parts.append("## Conversation History")
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            agent = msg.get("agent")

            if role == "user":
                parts.append(f"[USER] {content}")
            elif role == "assistant":
                # Use agent field if available, else parse from content
                if agent:
                    agent_label = agent.upper()
                elif content.startswith("[CLAUDE]"):
                    agent_label = "CLAUDE"
                    content = content[8:].strip()
                elif content.startswith("[GEMINI]"):
                    agent_label = "GEMINI"
                    content = content[8:].strip()
                else:
                    agent_label = "ASSISTANT"
                parts.append(f"[{agent_label}] {content}")
        parts.append("")

    parts.append("You are now joining this conversation. Continue naturally from where it left off.")

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


def parse_agent_response(response: str) -> tuple[str, str, str]:
    """Parse agent response to extract message and addressing.

    Agents should wrap responses in JSON:
    {"message": "...", "addressing": "user|claude|gemini", "action": "respond|pass|correct"}

    Returns:
        Tuple of (message_text, addressing, action)
        - addressing: "user", "claude", or "gemini"
        - action: "respond", "pass", or "correct"
    """
    # Try to parse JSON wrapper
    try:
        # Handle case where response is just JSON
        data = json.loads(response.strip())
        return (
            data.get("message", response),
            data.get("addressing", "user"),
            data.get("action", "respond"),
        )
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from end of response (agent might include message then JSON)
    import re
    json_match = re.search(r'\{[^{}]*"addressing"[^{}]*\}\s*$', response)
    if json_match:
        try:
            data = json.loads(json_match.group())
            message = response[:json_match.start()].strip()
            return (
                message or data.get("message", response),
                data.get("addressing", "user"),
                data.get("action", "respond"),
            )
        except json.JSONDecodeError:
            pass

    # No JSON found - default to addressing user
    return (response, "user", "respond")


def build_roundtable_prompt(
    agent_name: str,
    other_agent: str,
    history_context: str,
    user_message: str,
    is_review: bool = False,
    previous_response: str | None = None,
) -> str:
    """Build a prompt for roundtable mode with JSON addressing instructions."""

    json_instructions = f"""
IMPORTANT: End your response with a JSON block indicating who you're addressing next:
{{"addressing": "user"}} - if you're done and waiting for the user
{{"addressing": "{other_agent}"}} - if you're asking {other_agent.upper()} a question or passing to them
{{"addressing": "{agent_name}"}} - only if someone asked you directly

Examples:
- "Here's my answer to your question. {{"addressing": "user"}}"
- "What do you think, {other_agent.upper()}? {{"addressing": "{other_agent}"}}"
"""

    if is_review:
        # Silent review mode - only respond if correction needed
        return f"""You are {agent_name.upper()} in a roundtable with {other_agent.upper()} and a user.

{other_agent.upper()} just responded to the user:
{previous_response}

Review their response for accuracy. You have two options:
1. If the response is accurate and complete, respond ONLY with: {{"action": "pass"}}
2. If you see errors, omissions, or important additions needed, provide your correction.

If correcting, keep it brief and factual. End with {{"addressing": "user"}} or {{"addressing": "{other_agent}"}} if asking them to clarify.

DO NOT repeat what {other_agent.upper()} said correctly. Only speak up if there's something to add or correct.
"""

    # Regular response prompt
    parts = [f"You are {agent_name.upper()} in a roundtable discussion with {other_agent.upper()} and a user."]

    if history_context:
        parts.append(f"\nConversation history:\n{history_context}\n")

    if previous_response:
        parts.append(f"\n{other_agent.upper()} just said:\n{previous_response}\n")

    parts.append(f"\nUser's message: {user_message}")
    parts.append(json_instructions)

    return "\n".join(parts)


async def handle_roundtable_message(
    bridge: SessionBridge,
    session_id: str,
    content: str,
    order: str,
    safe_send_json,
    permission_callback,
    ws_closed_check,
    max_turns: int = 10,
) -> None:
    """Handle a roundtable message with shared-channel model.

    Features:
    - JSON addressing: agents indicate who they're talking to
    - Silent review: second agent only speaks if they have corrections
    - Automatic continuation: agents can address each other directly
    """
    # Determine agent order
    if order == "gemini-first":
        first_agent = "gemini"
        second_agent = "claude"
    else:
        first_agent = "claude"
        second_agent = "gemini"

    logger.info(f"Roundtable: {first_agent} first, {second_agent} reviews")

    try:
        # Build conversation history
        history_context = await build_roundtable_context(bridge.db, session_id)
        if history_context:
            logger.info(f"Roundtable: Loaded {len(history_context)} chars of history")

        # Get sessions for both agents
        sessions = {}
        for agent in [first_agent, second_agent]:
            if agent == "gemini":
                sessions[agent] = await get_or_create_gemini_session(bridge, session_id)
            else:
                sessions[agent] = await get_or_create_session_with_permissions(
                    bridge, session_id, permission_callback
                )
            if not sessions[agent]:
                await safe_send_json({
                    "type": "error",
                    "message": f"Failed to start {agent} session",
                })
                return

        # Set original_provider for roundtable
        await bridge.db.set_original_provider(session_id, "both")

        # First agent responds
        first_prompt = build_roundtable_prompt(
            agent_name=first_agent,
            other_agent=second_agent,
            history_context=history_context,
            user_message=content,
        )

        await safe_send_json({"type": "agent_start", "agent": first_agent})
        first_response_raw = await stream_agent_response(
            sessions[first_agent], first_prompt, safe_send_json, ws_closed_check, first_agent
        )
        await safe_send_json({"type": "agent_done", "agent": first_agent})

        if ws_closed_check():
            return

        # Parse first response
        first_message, addressing, _ = parse_agent_response(first_response_raw)

        # Store first response (use clean message for display)
        await _store_agent_message(bridge.db, session_id, first_message, first_agent)

        logger.info(f"Roundtable: {first_agent} addressing: {addressing}")

        # Track current state
        current_agent = first_agent
        current_response = first_message
        turn_count = 1

        # Conversation loop
        while turn_count < max_turns and not ws_closed_check():
            other_agent = second_agent if current_agent == first_agent else first_agent

            # Determine next action based on addressing
            if addressing == other_agent:
                # Agent addressed the other agent - they should respond
                next_agent = other_agent
                is_review = False
                logger.info(f"Roundtable: {current_agent} addressed {other_agent}")
            elif addressing == "user":
                # Agent addressed user - other agent does silent review
                next_agent = other_agent
                is_review = True
                logger.info(f"Roundtable: {other_agent} doing silent review")
            else:
                # Addressed self or unknown - end turn
                logger.info(f"Roundtable: Ending, addressing={addressing}")
                break

            # Build prompt for next agent
            next_prompt = build_roundtable_prompt(
                agent_name=next_agent,
                other_agent=current_agent,
                history_context=history_context,
                user_message=content,
                is_review=is_review,
                previous_response=current_response,
            )

            await safe_send_json({"type": "agent_start", "agent": next_agent})
            next_response_raw = await stream_agent_response(
                sessions[next_agent], next_prompt, safe_send_json, ws_closed_check, next_agent
            )
            await safe_send_json({"type": "agent_done", "agent": next_agent})

            if ws_closed_check():
                return

            # Parse response
            next_message, next_addressing, action = parse_agent_response(next_response_raw)

            # Handle silent review pass
            if is_review and action == "pass":
                logger.info(f"Roundtable: {next_agent} passed (no corrections)")
                # Send a signal that review passed (no visible message)
                await safe_send_json({"type": "review_pass", "agent": next_agent})
                break

            # Store response if not a pass
            if action != "pass":
                await _store_agent_message(bridge.db, session_id, next_message, next_agent)

            # If review resulted in correction, end (user got both perspectives)
            if is_review and action == "correct":
                logger.info(f"Roundtable: {next_agent} provided correction")
                break

            # Update state for next iteration
            current_agent = next_agent
            current_response = next_message
            addressing = next_addressing
            turn_count += 1

            # If now addressing user, end
            if addressing == "user":
                logger.info(f"Roundtable: {current_agent} addressing user, ending")
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
