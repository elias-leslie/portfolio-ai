"""REST API routes for Dev Companion."""

from fastapi import HTTPException, Depends

from .models import CreateSessionRequest, SessionResponse, MessageCreate
from .session_bridge import SessionBridge


def require_bridge() -> SessionBridge:
    """Dependency that ensures bridge is available.

    Raises:
        HTTPException: 503 if bridge is not initialized

    Returns:
        The initialized SessionBridge instance
    """
    from .server import bridge

    if not bridge:
        raise HTTPException(status_code=503, detail="Service not ready")
    return bridge


def session_to_response(session: dict, is_active: bool = False) -> SessionResponse:
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


async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "dev-companion"}


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

    return session_to_response(session)


async def list_sessions(
    limit: int = 50,
    bridge: SessionBridge = Depends(require_bridge),
):
    """List all sessions."""
    sessions = await bridge.list_sessions(limit=limit)
    return [
        session_to_response(s, is_active=s.get("is_active", False)) for s in sessions
    ]


async def get_session(
    session_id: str,
    bridge: SessionBridge = Depends(require_bridge),
):
    """Get session details."""
    session = await bridge.db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session_to_response(session, is_active=session_id in bridge._active_sessions)


async def delete_session(
    session_id: str,
    bridge: SessionBridge = Depends(require_bridge),
):
    """Delete a session."""
    deleted = await bridge.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"deleted": True}


async def get_session_history(
    session_id: str,
    limit: int = 100,
    bridge: SessionBridge = Depends(require_bridge),
):
    """Get message history for a session."""
    messages = await bridge.get_session_history(session_id, limit=limit)
    return {"messages": messages}


async def add_message(
    session_id: str,
    msg: MessageCreate,
    bridge: SessionBridge = Depends(require_bridge),
):
    """Add a message to session history (for evidence, system messages, etc)."""
    await bridge.db.add_message(
        session_id=session_id,
        role=msg.role,
        content=msg.content,
        metadata=msg.metadata or {},
    )

    return {"added": True}
