"""Request/Response models for Dev Companion API."""

from typing import Any
from pydantic import BaseModel


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


class MessageCreate(BaseModel):
    """Request body for adding a message."""

    role: str  # user, assistant, system, evidence
    content: str
    metadata: dict | None = None
