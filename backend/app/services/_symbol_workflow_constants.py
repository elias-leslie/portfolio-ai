"""Constants and pure helper functions for symbol workflow stage logic."""

from __future__ import annotations

WORKFLOW_STAGES = (
    "discover",
    "thesis_ready",
    "tracked",
    "live",
    "review_due",
    "invalidated",
    "exited",
)

WORKFLOW_SUMMARIES = {
    "discover": "The symbol is on the radar but still needs a worked thesis.",
    "thesis_ready": "The thesis is ready and the symbol can move into active tracking.",
    "tracked": "The symbol is being tracked deliberately before capital is committed.",
    "live": "The symbol is managed as a live position.",
    "review_due": "A portfolio or thesis review is due before the next decision.",
    "invalidated": "The thesis has broken and the symbol should stay out of the active loop.",
    "exited": "The position is closed and the outcome can be reviewed for learning.",
}

WORKFLOW_TRANSITIONS = {
    "discover": ["thesis_ready", "tracked", "invalidated"],
    "thesis_ready": ["tracked", "live", "review_due", "invalidated"],
    "tracked": ["thesis_ready", "live", "review_due", "invalidated"],
    "live": ["review_due", "exited", "invalidated"],
    "review_due": ["tracked", "live", "exited", "invalidated"],
    "invalidated": ["discover", "tracked"],
    "exited": ["discover", "review_due"],
}

OUTCOME_ACTION_STAGE_MAP = {
    "hold": "live",
    "trim": "review_due",
    "exit": "exited",
    "invalidate": "invalidated",
}


def derive_default_stage(
    *,
    has_watchlist_item: bool,
    has_thesis: bool,
    has_live_position: bool,
    has_trade_review: bool,
) -> str:
    if has_live_position:
        return "live"
    if has_trade_review:
        return "review_due"
    if has_thesis:
        return "thesis_ready"
    return "discover"


def available_transitions_for_stage(stage: str) -> list[str]:
    return WORKFLOW_TRANSITIONS.get(stage, ["discover"])


def stage_for_outcome_action(action: str) -> str:
    normalized = action.strip().lower()
    if normalized not in OUTCOME_ACTION_STAGE_MAP:
        raise ValueError(f"Unsupported outcome action: {action}")
    return OUTCOME_ACTION_STAGE_MAP[normalized]
