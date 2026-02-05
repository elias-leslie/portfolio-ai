"""FastAPI server with WebSocket support for Dev Companion."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware

from .database import Database
from .session_bridge import SessionBridge
from .models import CreateSessionRequest, SessionResponse, MessageCreate
from .routes import (
    require_bridge,
    health_check,
    create_session,
    list_sessions,
    get_session,
    delete_session,
    get_session_history,
    add_message,
)
from .websocket import websocket_endpoint

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


# REST endpoints
@app.get("/health")
async def health():
    """Health check endpoint."""
    return await health_check()


@app.post("/sessions", response_model=SessionResponse)
async def create_session_endpoint(
    request: CreateSessionRequest,
    bridge: SessionBridge = Depends(require_bridge),
):
    """Create a new session."""
    return await create_session(request, bridge)


@app.get("/sessions", response_model=list[SessionResponse])
async def list_sessions_endpoint(
    limit: int = 50,
    bridge: SessionBridge = Depends(require_bridge),
):
    """List all sessions."""
    return await list_sessions(limit, bridge)


@app.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session_endpoint(
    session_id: str,
    bridge: SessionBridge = Depends(require_bridge),
):
    """Get session details."""
    return await get_session(session_id, bridge)


@app.delete("/sessions/{session_id}")
async def delete_session_endpoint(
    session_id: str,
    bridge: SessionBridge = Depends(require_bridge),
):
    """Delete a session."""
    return await delete_session(session_id, bridge)


@app.get("/sessions/{session_id}/history")
async def get_session_history_endpoint(
    session_id: str,
    limit: int = 100,
    bridge: SessionBridge = Depends(require_bridge),
):
    """Get message history for a session."""
    return await get_session_history(session_id, limit, bridge)


@app.post("/sessions/{session_id}/messages")
async def add_message_endpoint(
    session_id: str,
    msg: MessageCreate,
    bridge: SessionBridge = Depends(require_bridge),
):
    """Add a message to session history (for evidence, system messages, etc)."""
    return await add_message(session_id, msg, bridge)


# WebSocket endpoint for real-time communication
@app.websocket("/ws/{session_id}")
async def websocket_handler(
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
    """
    if not bridge:
        await websocket.close(code=1011, reason="Service not ready")
        return

    await websocket_endpoint(
        websocket=websocket,
        session_id=session_id,
        bridge=bridge,
        provider=provider,
        order=order,
        max_turns=max_turns,
    )


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
