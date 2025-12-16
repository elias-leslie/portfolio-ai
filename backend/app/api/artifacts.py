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

from datetime import datetime, timezone
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


class ClientEvidence(BaseModel):
    """Client-side evidence gathered before screenshot."""

    console: dict = Field(default_factory=dict, description="Console errors/warnings")
    network: dict = Field(default_factory=dict, description="Network failures")


class ViewportCaptureRequest(BaseModel):
    """Request to upload a client-side viewport capture."""

    feature_id: str = Field(..., description="Feature ID")
    criterion_id: str = Field(..., description="Criterion ID")
    screenshot_base64: str = Field(..., description="Base64-encoded PNG screenshot")
    url: str = Field(..., description="URL of the captured page")
    viewport_width: int = Field(..., description="Viewport width")
    viewport_height: int = Field(..., description="Viewport height")
    scroll_x: int = Field(0, description="Horizontal scroll position")
    scroll_y: int = Field(0, description="Vertical scroll position")
    page_title: str = Field("", description="Page title")
    client_evidence: ClientEvidence | None = Field(None, description="Client-side console/network evidence")


class UserReviewRequest(BaseModel):
    """Request to submit user review."""

    approved: bool | None = Field(
        None, description="True=approved, False=rejected, None=just notes"
    )
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


@router.get("/latest")
async def get_latest_artifact(
    include_evidence: bool = True,
) -> dict[str, Any]:
    """Get the most recently captured artifact.

    This is useful for Claude to detect when new evidence has been captured
    via the header camera button.

    Returns the latest artifact with optional evidence data.
    """
    try:
        artifact = artifact_manager.get_latest_artifact()

        if not artifact:
            return {
                "artifact": None,
                "message": "No artifacts captured yet",
            }

        # Optionally include evidence data
        evidence_data = None
        if include_evidence:
            evidence_data = artifact_manager.read_evidence_file(
                artifact["feature_id"],
                artifact["criterion_id"],
                artifact.get("version"),
            )

        return {
            "artifact": artifact,
            "evidence": evidence_data,
            "screenshot_url": f"/api/artifacts/screenshots/{artifact['feature_id']}/{artifact['criterion_id']}/v{artifact['version']}/screenshot.png",
            "evidence_url": f"/api/artifacts/screenshots/{artifact['feature_id']}/{artifact['criterion_id']}/v{artifact['version']}/evidence.json",
        }

    except Exception as e:
        logger.error("get_latest_artifact_failed", error=str(e))
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


@router.post("/viewport-capture")
async def viewport_capture(request: ViewportCaptureRequest) -> dict[str, Any]:
    """Upload a client-side viewport capture.

    This endpoint receives a screenshot captured directly from the user's browser
    using html2canvas, preserving exact viewport state (scroll position, expanded
    sections, form values, etc.).
    """
    import base64
    import json
    from datetime import datetime, timezone

    try:
        # Decode base64 screenshot
        try:
            screenshot_data = base64.b64decode(request.screenshot_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 screenshot data")

        # Create versioned output directory
        version = artifact_manager.get_next_version(request.feature_id, request.criterion_id)
        output_dir = ARTIFACTS_BASE_DIR / request.feature_id / request.criterion_id / f"v{version}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save screenshot
        screenshot_path = output_dir / "screenshot.png"
        screenshot_path.write_bytes(screenshot_data)

        # Create evidence.json with viewport metadata
        evidence = {
            "metadata": {
                "url": request.url,
                "featureId": request.feature_id,
                "criterionId": request.criterion_id,
                "version": version,
                "capturedAt": datetime.now(timezone.utc).isoformat(),
                "pageTitle": request.page_title,
                "viewport": {
                    "width": request.viewport_width,
                    "height": request.viewport_height,
                },
                "scroll": {
                    "x": request.scroll_x,
                    "y": request.scroll_y,
                },
                "captureMethod": "client-side-screen-capture-api",
            },
            "console": {
                "errorCount": request.client_evidence.console.get("errorCount", 0) if request.client_evidence else 0,
                "warningCount": request.client_evidence.console.get("warningCount", 0) if request.client_evidence else 0,
                "errors": request.client_evidence.console.get("errors", []) if request.client_evidence else [],
                "warnings": request.client_evidence.console.get("warnings", []) if request.client_evidence else [],
                "note": "Client-side evidence from visible error elements",
            },
            "network": {
                "totalRequests": 0,
                "failedRequests": request.client_evidence.network.get("failureCount", 0) if request.client_evidence else 0,
                "failures": request.client_evidence.network.get("failures", []) if request.client_evidence else [],
                "slowRequests": [],
                "note": "Client-side evidence from Performance API",
            },
            "pageState": {
                "hasContent": True,
                "visibleTextSample": "",
                "keyElements": {},
                "note": "Captured user's exact viewport state",
            },
        }

        evidence_path = output_dir / "evidence.json"
        evidence_path.write_text(json.dumps(evidence, indent=2))

        # Update current symlink
        current_link = ARTIFACTS_BASE_DIR / request.feature_id / request.criterion_id / "current"
        if current_link.is_symlink():
            current_link.unlink()
        current_link.symlink_to(f"v{version}")

        # Save artifact to database
        file_size = len(screenshot_data) + len(json.dumps(evidence))
        artifact_manager.save_artifact(
            feature_id=request.feature_id,
            criterion_id=request.criterion_id,
            version=version,
            file_path=f"{request.feature_id}/{request.criterion_id}/v{version}",
            file_size_bytes=file_size,
            evidence_data=evidence,
        )

        logger.info(
            "viewport_capture_saved",
            feature_id=request.feature_id,
            criterion_id=request.criterion_id,
            version=version,
            scroll_y=request.scroll_y,
        )

        return {
            "success": True,
            "version": version,
            "feature_id": request.feature_id,
            "criterion_id": request.criterion_id,
            "evidence": evidence,
            "files": [
                {"name": "screenshot.png", "size": len(screenshot_data)},
                {"name": "evidence.json", "size": len(json.dumps(evidence))},
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("viewport_capture_failed", error=str(e))
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


# ========================================================================
# Debug Capture (no DB entry, easy for Claude to find)
# ========================================================================

DEBUG_CAPTURES_DIR = Path("/home/kasadis/portfolio-ai/data/debug-captures")


class DebugCaptureRequest(BaseModel):
    """Request for debug viewport capture (no DB entry)."""

    screenshot_base64: str = Field(..., description="Base64-encoded PNG screenshot")
    url: str = Field(..., description="URL of the captured page")
    page_title: str = Field("", description="Page title")
    client_evidence: ClientEvidence | None = Field(None, description="Client-side console/network evidence")


@router.post("/debug-capture")
async def debug_capture(request: DebugCaptureRequest) -> dict[str, Any]:
    """Save a debug viewport capture without creating a feature entry.

    Saves to: data/debug-captures/{timestamp}.png
    Also maintains: data/debug-captures/latest.png (symlink to most recent)

    This is for quick debugging - Claude can easily find via:
    - Read /home/kasadis/portfolio-ai/data/debug-captures/latest.png
    - ls -lt data/debug-captures/ | head
    """
    import base64
    from datetime import datetime, timezone

    try:
        # Decode base64 screenshot
        try:
            screenshot_data = base64.b64decode(request.screenshot_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 screenshot data")

        # Ensure directory exists
        DEBUG_CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

        # Create timestamped filename
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        screenshot_filename = f"{timestamp}.png"
        screenshot_path = DEBUG_CAPTURES_DIR / screenshot_filename

        # Save screenshot
        screenshot_path.write_bytes(screenshot_data)

        # Save evidence.json alongside screenshot
        import json
        evidence_filename = f"{timestamp}.json"
        evidence_path = DEBUG_CAPTURES_DIR / evidence_filename
        evidence_data = {
            "metadata": {
                "url": request.url,
                "pageTitle": request.page_title,
                "capturedAt": datetime.now(timezone.utc).isoformat(),
                "captureMethod": "client-side-screen-capture-api",
            },
            "console": {
                "errorCount": request.client_evidence.console.get("errorCount", 0) if request.client_evidence else 0,
                "warningCount": request.client_evidence.console.get("warningCount", 0) if request.client_evidence else 0,
                "errors": request.client_evidence.console.get("errors", []) if request.client_evidence else [],
                "warnings": request.client_evidence.console.get("warnings", []) if request.client_evidence else [],
            },
            "network": {
                "failedRequests": request.client_evidence.network.get("failureCount", 0) if request.client_evidence else 0,
                "failures": request.client_evidence.network.get("failures", []) if request.client_evidence else [],
            },
        }
        evidence_path.write_text(json.dumps(evidence_data, indent=2))

        # Update latest.png symlink
        latest_link = DEBUG_CAPTURES_DIR / "latest.png"
        if latest_link.is_symlink() or latest_link.exists():
            latest_link.unlink()
        latest_link.symlink_to(screenshot_filename)

        # Update latest.json symlink
        latest_json_link = DEBUG_CAPTURES_DIR / "latest.json"
        if latest_json_link.is_symlink() or latest_json_link.exists():
            latest_json_link.unlink()
        latest_json_link.symlink_to(evidence_filename)

        # Clean up old captures (keep last 20 pairs)
        all_captures = sorted(DEBUG_CAPTURES_DIR.glob("*.png"))
        all_captures = [p for p in all_captures if p.name not in ("latest.png",)]
        if len(all_captures) > 20:
            for old_capture in all_captures[:-20]:
                old_capture.unlink()
                # Also remove matching .json
                old_json = old_capture.with_suffix(".json")
                if old_json.exists():
                    old_json.unlink()

        logger.info(
            "debug_capture_saved",
            filename=screenshot_filename,
            url=request.url,
            size_kb=len(screenshot_data) // 1024,
        )

        return {
            "success": True,
            "filename": screenshot_filename,
            "evidence_filename": evidence_filename,
            "path": str(screenshot_path),
            "evidence_path": str(evidence_path),
            "latest_path": str(latest_link),
            "latest_json_path": str(latest_json_link),
            "url": request.url,
            "size_bytes": len(screenshot_data),
            "evidence": evidence_data,
            "message": f"Saved to {screenshot_path}. Claude: Read data/debug-captures/latest.png and latest.json",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("debug_capture_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.get("/debug-captures")
async def list_debug_captures(limit: int = Query(10, ge=1, le=50)) -> dict[str, Any]:
    """List recent debug captures.

    Useful for Claude to see what captures are available.
    """
    try:
        if not DEBUG_CAPTURES_DIR.exists():
            return {"captures": [], "count": 0, "latest": None}

        # Get all PNG files except latest.png
        captures = []
        for path in sorted(DEBUG_CAPTURES_DIR.glob("*.png"), reverse=True):
            if path.name == "latest.png":
                continue
            captures.append({
                "filename": path.name,
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "created_at": datetime.fromtimestamp(
                    path.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
            })
            if len(captures) >= limit:
                break

        # Check latest symlink
        latest_link = DEBUG_CAPTURES_DIR / "latest.png"
        latest_target = None
        if latest_link.is_symlink():
            latest_target = latest_link.resolve().name

        return {
            "captures": captures,
            "count": len(captures),
            "latest": latest_target,
            "latest_path": str(DEBUG_CAPTURES_DIR / "latest.png"),
        }

    except Exception as e:
        logger.error("list_debug_captures_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from None
