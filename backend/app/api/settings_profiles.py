"""Settings Profiles API routes (FastAPI)."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.models.settings_profile import (
    activate_profile,
    create_profile,
    delete_profile,
    duplicate_profile,
    get_active_profile,
    get_all_profiles,
    get_profile_by_id,
    update_profile,
)
from app.storage import get_storage

router = APIRouter(prefix="/api/settings/profiles", tags=["settings_profiles"])

# Initialize storage
storage = get_storage()


class ProfileCreate(BaseModel):
    """Request model for creating a profile."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    profile_data: dict[str, Any]
    is_active: bool = False
    user_id: int = 1


class ProfileUpdate(BaseModel):
    """Request model for updating a profile."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    profile_data: dict[str, Any] | None = None
    is_active: bool | None = None
    user_id: int = 1


class ProfileDuplicate(BaseModel):
    """Request model for duplicating a profile."""

    name: str = Field(..., min_length=1, max_length=255)
    user_id: int = 1


class ProfileImport(BaseModel):
    """Request model for importing a profile."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = "Imported profile"
    profile_data: dict[str, Any]
    user_id: int = 1


@router.get("")
async def list_profiles(user_id: int = Query(default=1)) -> list[dict[str, Any]]:
    """Get all settings profiles for the user."""
    try:
        with storage.connection() as conn:
            profiles = get_all_profiles(conn._conn, user_id)  # type: ignore[attr-defined]
            return [p.to_dict() for p in profiles]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/active")
async def get_active(user_id: int = Query(default=1)) -> dict[str, Any]:
    """Get the currently active profile."""
    try:
        with storage.connection() as conn:
            profile = get_active_profile(conn._conn, user_id)
            if not profile:
                raise HTTPException(status_code=404, detail="No active profile")
            return profile.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{profile_id}")
async def get_profile(profile_id: int, user_id: int = Query(default=1)) -> dict[str, Any]:
    """Get a specific profile."""
    try:
        with storage.connection() as conn:
            profile = get_profile_by_id(conn._conn, profile_id, user_id)
            if not profile:
                raise HTTPException(status_code=404, detail="Profile not found")
            return profile.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("")
async def create(data: ProfileCreate) -> dict[str, Any]:
    """Create a new settings profile."""
    try:
        with storage.connection() as conn:
            profile = create_profile(
                conn._conn,
                user_id=data.user_id,
                name=data.name,
                profile_data=data.profile_data,
                description=data.description,
                is_active=data.is_active,
            )
            return profile.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/{profile_id}")
async def update(profile_id: int, data: ProfileUpdate) -> dict[str, Any]:
    """Update an existing profile."""
    try:
        with storage.connection() as conn:
            profile = update_profile(
                conn._conn,
                profile_id=profile_id,
                user_id=data.user_id,
                name=data.name,
                description=data.description,
                profile_data=data.profile_data,
                is_active=data.is_active,
            )
            if not profile:
                raise HTTPException(status_code=404, detail="Profile not found")
            return profile.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{profile_id}")
async def delete(profile_id: int, user_id: int = Query(default=1)) -> dict[str, str]:
    """Delete a profile."""
    try:
        with storage.connection() as conn:
            deleted = delete_profile(conn._conn, profile_id, user_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Profile not found")
            return {"message": "Profile deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{profile_id}/activate")
async def activate(profile_id: int, user_id: int = Query(default=1)) -> dict[str, Any]:
    """Activate a profile."""
    try:
        with storage.connection() as conn:
            profile = activate_profile(conn._conn, profile_id, user_id)
            if not profile:
                raise HTTPException(status_code=404, detail="Profile not found")
            return profile.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{profile_id}/duplicate")
async def duplicate(profile_id: int, data: ProfileDuplicate) -> dict[str, Any]:
    """Duplicate a profile."""
    try:
        with storage.connection() as conn:
            profile = duplicate_profile(conn._conn, profile_id, data.name, data.user_id)
            if not profile:
                raise HTTPException(status_code=404, detail="Original profile not found")
            return profile.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{profile_id}/export")
async def export_profile(profile_id: int, user_id: int = Query(default=1)) -> dict[str, Any]:
    """Export a profile as JSON for sharing/backup."""
    try:
        with storage.connection() as conn:
            profile = get_profile_by_id(conn._conn, profile_id, user_id)
            if not profile:
                raise HTTPException(status_code=404, detail="Profile not found")

            # Export format includes metadata
            export_data = {
                "name": profile.name,
                "description": profile.description,
                "profile_data": profile.profile_data,
                "exported_at": profile.updated_at.isoformat(),
                "version": "1.0",
            }
            return export_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/import")
async def import_profile(data: ProfileImport) -> dict[str, Any]:
    """Import a profile from exported JSON."""
    try:
        with storage.connection() as conn:
            profile = create_profile(
                conn._conn,
                user_id=data.user_id,
                name=data.name,
                profile_data=data.profile_data,
                description=data.description,
                is_active=False,
            )
            return profile.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
