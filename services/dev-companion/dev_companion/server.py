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


# WebSocket endpoint for real-time communication
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time Claude communication.

    Protocol:
    - Client sends: {"type": "message", "content": "user message"}
    - Server sends: {"type": "stream", "data": <StreamMessage as dict>}
    - Server sends: {"type": "done"} when response complete
    - Server sends: {"type": "error", "message": "error details"}
    """
    if not bridge:
        await websocket.close(code=1011, reason="Service not ready")
        return

    await websocket.accept()
    logger.info(f"WebSocket connected for session {session_id}")

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
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                })
                continue

            msg_type = msg.get("type")

            if msg_type == "message":
                content = msg.get("content", "").strip()
                if not content:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Empty message",
                    })
                    continue

                # Get or start Claude session
                session = await bridge.get_session(session_id)
                if not session:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Failed to start Claude session",
                    })
                    continue

                # Store user message
                await bridge.db.add_message(
                    session_id=session_id,
                    role="user",
                    content=content,
                )

                # Stream response
                try:
                    response_text_parts = []
                    async for stream_msg in session.send(content):
                        msg_dict = message_to_dict(stream_msg)
                        await websocket.send_json({
                            "type": "stream",
                            "data": msg_dict,
                        })
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
                        )

                    # Persist SDK session ID for conversation continuity
                    if session._sdk_session_id:
                        await bridge.db.update_session(
                            session_id=session_id,
                            metadata={"sdk_session_id": session._sdk_session_id},
                        )

                    await websocket.send_json({"type": "done"})

                except Exception as e:
                    logger.error(f"Error streaming response: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e),
                    })

            elif msg_type == "interrupt":
                # Handle interrupt signal
                session = bridge._active_sessions.get(session_id)
                if session:
                    success = await session.interrupt()
                    await websocket.send_json({
                        "type": "interrupt_ack",
                        "success": success,
                    })
                else:
                    await websocket.send_json({
                        "type": "interrupt_ack",
                        "success": False,
                        "message": "No active session",
                    })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Don't stop the Claude session - it can be reconnected
        pass


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
