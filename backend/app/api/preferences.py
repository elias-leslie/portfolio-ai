"""User preferences API router."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from app.models.preferences import (
    PreferencesResponse,
    PreferencesUpdate,
    ScoringWeightsUpdate,
)
from app.services.preferences_service import (
    dict_to_preferences_response,
    get_or_create_preferences,
    get_scoring_weights,
    update_preferences,
    update_scoring_weights,
)

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("", response_model=PreferencesResponse)
async def get_preferences() -> PreferencesResponse:
    """Get user's risk tolerance and trade preferences."""
    prefs = await run_in_threadpool(get_or_create_preferences)
    return dict_to_preferences_response(prefs)


@router.post("", response_model=PreferencesResponse)
async def update_preferences_endpoint(update: PreferencesUpdate) -> PreferencesResponse:
    """Update user preferences."""
    updated = await run_in_threadpool(update_preferences, update)
    return dict_to_preferences_response(updated)


@router.get("/scoring-weights", response_model=ScoringWeightsUpdate)
async def get_scoring_weights_endpoint() -> ScoringWeightsUpdate:
    """Get current scoring weights (4-pillar system)."""
    return await run_in_threadpool(get_scoring_weights)


@router.put("/scoring-weights", response_model=ScoringWeightsUpdate)
async def update_scoring_weights_endpoint(weights: ScoringWeightsUpdate) -> ScoringWeightsUpdate:
    """Update scoring weights (4-pillar system).

    Weights must sum to 100. Updates are stored in the watchlist_score_weights JSONB column.
    """
    return await run_in_threadpool(update_scoring_weights, weights)
