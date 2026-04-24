"""Thesis API - Investment thesis generation and management.

Provides endpoints for generating, retrieving, and managing LLM-generated
investment theses with dual-agent validation.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from app.logging_config import get_logger
from app.models.thesis import (
    ThesisDecisionEligibility,
    ThesisGenerateRequest,
    ThesisResponse,
    ThesisVersion,
)

if TYPE_CHECKING:
    from app.services.thesis_service import ThesisService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/thesis", tags=["thesis"])


def _default_eligibility(thesis_present: bool) -> ThesisDecisionEligibility:
    if thesis_present:
        return ThesisDecisionEligibility(eligible=True, status="eligible", reasons=[])
    return ThesisDecisionEligibility(
        eligible=False,
        status="unavailable",
        reasons=["No thesis is available for this symbol."],
    )


@lru_cache(maxsize=1)
def _get_thesis_service() -> ThesisService:
    """Get ThesisService instance."""
    return import_module("app.services.thesis_service").ThesisService()


@router.get("/{symbol}", response_model=ThesisResponse)
async def get_thesis(symbol: str) -> ThesisResponse:
    """Get current thesis and version history for a symbol.

    Args:
        symbol: Stock symbol

    Returns:
        ThesisResponse with current thesis, versions, and version count.
        Returns empty response with null thesis if no thesis exists.
    """
    try:
        service = _get_thesis_service()
        thesis = await run_in_threadpool(service.get_thesis, symbol.upper())

        if not thesis:
            # No thesis exists - return empty response
            return ThesisResponse(
                thesis=None,
                versions=[],
                version_count=0,
                decision_eligibility=await run_in_threadpool(
                    service.evaluate_decision_eligibility,
                    symbol.upper(),
                    None,
                )
                if hasattr(service, "evaluate_decision_eligibility")
                else _default_eligibility(False),
            )

        # Get versions for the response
        versions = await run_in_threadpool(
            service.get_thesis_versions,
            symbol.upper(),
            10,
        )

        return ThesisResponse(
            thesis=thesis,
            versions=versions,
            version_count=len(versions),
            decision_eligibility=await run_in_threadpool(
                service.evaluate_decision_eligibility,
                symbol.upper(),
                thesis,
            )
            if hasattr(service, "evaluate_decision_eligibility")
            else _default_eligibility(True),
        )

    except Exception as e:
        logger.exception("thesis_get_failed", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get thesis: {e!s}") from e


@router.post("/{symbol}/generate", response_model=ThesisResponse)
async def generate_thesis(
    symbol: str,
    request: ThesisGenerateRequest,
) -> ThesisResponse:
    """Generate or regenerate investment thesis for a symbol.

    Args:
        symbol: Stock symbol
        request: Generation parameters including force_regenerate flag

    Returns:
        ThesisResponse with newly generated thesis
    """
    try:
        service = _get_thesis_service()
        thesis = await run_in_threadpool(
            service.generate_thesis,
            symbol.upper(),
            request.force_regenerate,
        )

        # Get versions for the response
        versions = await run_in_threadpool(
            service.get_thesis_versions,
            symbol.upper(),
            10,
        )

        return ThesisResponse(
            thesis=thesis,
            versions=versions,
            version_count=len(versions),
            decision_eligibility=await run_in_threadpool(
                service.evaluate_decision_eligibility,
                symbol.upper(),
                thesis,
            )
            if hasattr(service, "evaluate_decision_eligibility")
            else _default_eligibility(True),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("thesis_generation_failed", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate thesis: {e!s}") from e


@router.post("/{symbol}/invalidate", response_model=ThesisResponse)
async def invalidate_thesis(
    symbol: str,
    reason: dict[str, str],
) -> ThesisResponse:
    """Manually invalidate a thesis.

    Args:
        symbol: Stock symbol
        reason: Dict with "reason" key explaining invalidation

    Returns:
        ThesisResponse with updated thesis status
    """
    try:
        invalidation_reason = reason.get("reason")
        if not invalidation_reason:
            raise HTTPException(status_code=400, detail="Missing 'reason' field in request body")

        service = _get_thesis_service()
        thesis = await run_in_threadpool(
            service.invalidate_thesis,
            symbol.upper(),
            invalidation_reason,
        )

        if not thesis:
            raise HTTPException(
                status_code=404,
                detail=f"No thesis found for {symbol}",
            )

        # Get versions for the response
        versions = await run_in_threadpool(
            service.get_thesis_versions,
            symbol.upper(),
            10,
        )

        return ThesisResponse(
            thesis=thesis,
            versions=versions,
            version_count=len(versions),
            decision_eligibility=await run_in_threadpool(
                service.evaluate_decision_eligibility,
                symbol.upper(),
                thesis,
            )
            if hasattr(service, "evaluate_decision_eligibility")
            else _default_eligibility(True),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("thesis_invalidation_failed", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to invalidate thesis: {e!s}") from e


@router.get("/{symbol}/versions", response_model=list[ThesisVersion])
async def get_thesis_versions(
    symbol: str,
    limit: int = Query(10, ge=1, le=100, description="Maximum versions to return"),
) -> list[ThesisVersion]:
    """Get version history for a thesis.

    Args:
        symbol: Stock symbol
        limit: Maximum number of versions to return

    Returns:
        List of ThesisVersion objects (newest first)
    """
    try:
        service = _get_thesis_service()
        versions = await run_in_threadpool(
            service.get_thesis_versions,
            symbol.upper(),
            limit=limit,
        )

        return versions

    except Exception as e:
        logger.exception("thesis_versions_get_failed", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get versions: {e!s}") from e


@router.get("/{symbol}/check-invalidation", response_model=dict[str, list[str] | bool])
async def check_invalidation_triggers(symbol: str) -> dict[str, list[str] | bool]:
    """Check if thesis invalidation triggers are active.

    Args:
        symbol: Stock symbol

    Returns:
        Dict with "triggered" bool and "reasons" list of triggered invalidation reasons
    """
    try:
        service = _get_thesis_service()
        triggers = await run_in_threadpool(
            service.check_invalidation_triggers,
            symbol.upper(),
        )

        return {"triggered": len(triggers) > 0, "reasons": triggers}

    except Exception as e:
        logger.exception("thesis_invalidation_check_failed", symbol=symbol, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to check invalidation triggers: {e!s}"
        ) from e
