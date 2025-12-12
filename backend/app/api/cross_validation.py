"""Cross-validation API endpoints.

Provides REST API for cross-validation management:
- GET /pending - Get pending validations for review
- GET /{id} - Get single validation result
- POST /resolve/{id} - Resolve a pending validation
- POST /validate - Manually trigger validation
- GET /settings - Get current settings
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..logging_config import get_logger
from ..services.cross_validation import (
    CrossValidationService,
    CrossValidationSettings,
    ValidationResult,
)
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/cross-validation", tags=["cross-validation"])

# Module-level service instance (lazy initialized)
_service: CrossValidationService | None = None


def get_service() -> CrossValidationService:
    """Get or create cross-validation service."""
    global _service  # noqa: PLW0603
    if _service is None:
        _service = CrossValidationService()
    return _service


class ValidateRequest(BaseModel):
    """Request to validate output."""

    output: str
    context_type: str = "insight"
    context_symbol: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] | None = None


class ResolveRequest(BaseModel):
    """Request to resolve a validation."""

    approved: bool
    final_output: str | None = None


class ValidationResultResponse(BaseModel):
    """API response for validation result."""

    id: str
    created_at: str
    generator_provider: str
    generator_output: str
    generator_confidence: float | None
    validator_provider: str
    validator_review: str
    validator_approved: bool
    validator_confidence: float | None
    has_disagreement: bool
    disagreement_reasons: list[str]
    disagreement_details: str | None
    status: str
    resolved_at: str | None
    resolved_by: str | None
    final_output: str | None
    context_type: str
    context_symbol: str | None


def result_to_response(result: ValidationResult) -> ValidationResultResponse:
    """Convert internal result to API response."""
    return ValidationResultResponse(
        id=result.id,
        created_at=result.created_at,
        generator_provider=result.generator_provider,
        generator_output=result.generator_output,
        generator_confidence=result.generator_confidence,
        validator_provider=result.validator_provider,
        validator_review=result.validator_review,
        validator_approved=result.validator_approved,
        validator_confidence=result.validator_confidence,
        has_disagreement=result.has_disagreement,
        disagreement_reasons=[r.value for r in result.disagreement_reasons],
        disagreement_details=result.disagreement_details,
        status=result.status.value,
        resolved_at=result.resolved_at,
        resolved_by=result.resolved_by,
        final_output=result.final_output,
        context_type=result.context_type,
        context_symbol=result.context_symbol,
    )


@router.get("/settings")
async def get_settings() -> CrossValidationSettings:
    """Get current cross-validation settings."""
    service = get_service()
    return service.settings


@router.get("/pending")
async def get_pending_validations(
    limit: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    """Get pending validations awaiting human review."""
    service = get_service()
    results = service.get_pending_validations(limit=limit)
    return {
        "total": len(results),
        "validations": [result_to_response(r) for r in results],
    }


@router.get("/summary")
async def get_summary(days: int = Query(7, ge=1, le=90)) -> dict[str, Any]:
    """Get cross-validation summary statistics."""
    conn_mgr = get_connection_manager()
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    try:
        with conn_mgr.connection() as conn:
            # Total counts by status
            cursor = conn.execute(
                """
                SELECT
                    status,
                    COUNT(*) as count
                FROM cross_validation_results
                WHERE created_at >= %s
                GROUP BY status
                """,
                (cutoff,),
            )
            # fetchall returns tuples: (status, count)
            status_counts = {row[0]: row[1] for row in cursor.fetchall()}

            # Disagreement rate
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN has_disagreement THEN 1 ELSE 0 END) as disagreements,
                    SUM(CASE WHEN validator_approved THEN 1 ELSE 0 END) as approved
                FROM cross_validation_results
                WHERE created_at >= %s
                """,
                (cutoff,),
            )
            row = cursor.fetchone()
            # fetchone returns tuple: (total, disagreements, approved)
            # Cast to int for type safety
            total: int = int(row[0] or 0) if row else 0
            disagreements: int = int(row[1] or 0) if row else 0
            approved: int = int(row[2] or 0) if row else 0

            return {
                "period_days": days,
                "total_validations": total,
                "by_status": status_counts,
                "disagreement_rate": disagreements / total if total > 0 else 0.0,
                "approval_rate": approved / total if total > 0 else 0.0,
                "pending_count": status_counts.get("pending", 0),
            }
    except Exception as e:
        logger.error("get_summary_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{validation_id}")
async def get_validation(validation_id: str) -> ValidationResultResponse:
    """Get a specific validation result."""
    service = get_service()
    conn_mgr = get_connection_manager()
    try:
        with conn_mgr.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM cross_validation_results WHERE id = %s",
                (validation_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Validation not found")
            result = service._row_to_result(row)
            return result_to_response(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_validation_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/validate")
async def validate_output(request: ValidateRequest) -> ValidationResultResponse:
    """Manually trigger validation of output."""
    service = get_service()
    try:
        result = service.validate(
            generator_output=request.output,
            context_type=request.context_type,
            context_symbol=request.context_symbol,
            generator_confidence=request.confidence,
            metadata=request.metadata,
        )
        return result_to_response(result)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        logger.error("validate_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/resolve/{validation_id}")
async def resolve_validation(
    validation_id: str,
    request: ResolveRequest,
) -> ValidationResultResponse:
    """Resolve a pending validation."""
    service = get_service()
    result = service.resolve_validation(
        validation_id=validation_id,
        approved=request.approved,
        final_output=request.final_output,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Validation not found")
    return result_to_response(result)
