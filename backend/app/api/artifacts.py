"""Artifacts API - UI verification evidence management.

Endpoints:
- GET /api/artifacts/summary - Summary statistics
- GET /api/artifacts/{feature_id}/{criterion_id} - Get artifact metadata + versions
- GET /api/artifacts/screenshots/{path:path} - Serve screenshot/evidence files
- GET /api/artifacts/needs-review - List artifacts needing AI review
- GET /api/artifacts/with-notes - List artifacts with user notes
- POST /api/artifacts/refresh - Trigger new capture
- POST /api/artifacts/{artifact_id}/review - Submit user review
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..services import artifact_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])

# Base directory for artifacts
ARTIFACTS_BASE_DIR = Path("/home/kasadis/portfolio-ai/data/artifacts")


# ========================================================================
# Request/Response Models
# ========================================================================


class RefreshRequest(BaseModel):
    """Request to refresh evidence for criteria."""

    feature_id: str | None = Field(None, description="Feature ID (refreshes all if not specified)")
    criterion_id: str | None = Field(None, description="Criterion ID (requires feature_id)")
    url: str | None = Field(None, description="URL to capture (overrides default)")


class UserReviewRequest(BaseModel):
    """Request to submit user review."""

    approved: bool | None = Field(None, description="True=approved, False=rejected, None=just notes")
    notes: str | None = Field(None, description="User feedback/notes")


class ArtifactSummary(BaseModel):
    """Artifact summary statistics."""

    total_current: int
    by_status: dict[str, int]
    expired_count: int
    with_user_notes: int
    total_storage_bytes: int


# ========================================================================
# Endpoints
# ========================================================================


@router.get("/summary", response_model=ArtifactSummary)
async def get_summary() -> ArtifactSummary:
    """Get summary statistics for all artifacts."""
    try:
        data = artifact_manager.get_summary()
        return ArtifactSummary(**data)
    except Exception as e:
        logger.error("get_summary_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.get("/needs-review")
async def get_needs_review(
    limit: int = Query(50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get artifacts pending AI review."""
    try:
        return artifact_manager.get_pending_review(limit=limit)
    except Exception as e:
        logger.error("get_needs_review_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.get("/needs-user-review")
async def get_needs_user_review(
    limit: int = Query(50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get artifacts that need user review (low confidence)."""
    try:
        return artifact_manager.get_needs_user_review(limit=limit)
    except Exception as e:
        logger.error("get_needs_user_review_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.get("/with-notes")
async def get_with_notes(
    limit: int = Query(50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Get artifacts with user notes/feedback."""
    try:
        return artifact_manager.get_with_user_notes(limit=limit)
    except Exception as e:
        logger.error("get_with_notes_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.get("/screenshots/{file_path:path}")
async def serve_file(file_path: str) -> FileResponse:
    """Serve screenshot or evidence files.

    Path format: {feature_id}/{criterion_id}/v{n}/filename
    Example: FEAT-001/ac-001/v1/screenshot.png
    """
    full_path = ARTIFACTS_BASE_DIR / file_path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    # Security: ensure path is within artifacts directory
    try:
        full_path.resolve().relative_to(ARTIFACTS_BASE_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied") from None

    # Determine content type
    if file_path.endswith(".png"):
        media_type = "image/png"
    elif file_path.endswith(".json"):
        media_type = "application/json"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        path=full_path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/{feature_id}/{criterion_id}")
async def get_artifact(
    feature_id: str,
    criterion_id: str,
    version: int | None = None,
    include_evidence: bool = False,
) -> dict[str, Any]:
    """Get artifact metadata and optionally all versions.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
        criterion_id: Criterion ID (e.g., ac-001)
        version: Optional specific version (defaults to current)
        include_evidence: Include parsed evidence.json data
    """
    try:
        artifact = artifact_manager.get_artifact(feature_id, criterion_id, version)

        if not artifact:
            raise HTTPException(
                status_code=404,
                detail=f"No artifact found for {feature_id}/{criterion_id}",
            )

        # Get all versions
        versions = artifact_manager.get_artifact_versions(feature_id, criterion_id)

        # Optionally include evidence data
        evidence_data = None
        if include_evidence:
            evidence_data = artifact_manager.read_evidence_file(
                feature_id, criterion_id, artifact.get("version")
            )

        return {
            "artifact": artifact,
            "versions": versions,
            "evidence": evidence_data,
            "screenshot_url": f"/api/artifacts/screenshots/{feature_id}/{criterion_id}/v{artifact['version']}/screenshot.png",
            "evidence_url": f"/api/artifacts/screenshots/{feature_id}/{criterion_id}/v{artifact['version']}/evidence.json",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_artifact_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.post("/refresh")
async def refresh_evidence(request: RefreshRequest) -> dict[str, Any]:
    """Trigger new evidence capture.

    If feature_id and criterion_id provided, captures single criterion.
    If only feature_id provided, captures all UI criteria for feature.
    If neither provided, captures all UI criteria (use with caution).
    """
    try:
        if request.feature_id and request.criterion_id:
            # Single criterion capture
            url = request.url
            if not url:
                # Get URL from criterion verification field
                # For now, return error if URL not provided
                raise HTTPException(
                    status_code=400,
                    detail="URL is required for manual refresh",
                )

            result = await artifact_manager.capture_evidence(
                url=url,
                feature_id=request.feature_id,
                criterion_id=request.criterion_id,
            )

            if result.get("success"):
                # Save artifact record
                artifact_manager.save_artifact(
                    feature_id=request.feature_id,
                    criterion_id=request.criterion_id,
                    version=result.get("version", 1),
                    file_path=f"{request.feature_id}/{request.criterion_id}/v{result.get('version', 1)}",
                    file_size_bytes=sum(f.get("size", 0) for f in result.get("files", [])),
                    evidence_data=result.get("evidence"),
                )

            return result

        # Batch capture not implemented yet
        raise HTTPException(
            status_code=501,
            detail="Batch capture not yet implemented. Provide feature_id and criterion_id.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("refresh_evidence_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.post("/{artifact_id}/review")
async def submit_user_review(
    artifact_id: str,
    request: UserReviewRequest,
) -> dict[str, Any]:
    """Submit user review for an artifact."""
    try:
        success = artifact_manager.update_user_review(
            artifact_id=artifact_id,
            approved=request.approved,
            notes=request.notes,
        )

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Artifact not found: {artifact_id}",
            )

        return {"success": True, "artifact_id": artifact_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("submit_review_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.get("/expired")
async def get_expired() -> list[dict[str, Any]]:
    """Get artifacts that have expired and need refresh."""
    try:
        return artifact_manager.get_expired_artifacts()
    except Exception as e:
        logger.error("get_expired_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from None
