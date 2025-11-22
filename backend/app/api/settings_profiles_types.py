"""TypedDict definitions for settings profiles API endpoints.

Response models for profile CRUD, activation, import/export operations.
"""

from __future__ import annotations

from typing import TypedDict


class ProfileDict(TypedDict, total=False):
    """Settings profile structure."""

    id: int
    user_id: int
    name: str
    description: str | None
    profile_data: dict[str, object]
    is_active: bool
    created_at: str
    updated_at: str


class ProfileListDict(TypedDict):
    """Response for listing profiles."""

    # Represents list of ProfileDict items
    pass


class ProfileExportDict(TypedDict):
    """Export/import structure for profiles."""

    name: str
    description: str | None
    profile_data: dict[str, object]
    exported_at: str
    version: str


class MessageResponseDict(TypedDict):
    """Generic message response."""

    message: str
