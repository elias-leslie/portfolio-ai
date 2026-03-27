"""Consensus and conflict resolution for multi-agent workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from app.logging_config import get_logger

logger = get_logger(__name__)


def _first_agent_result(
    conflicting_outputs: dict[str, object],
    method: str = "fallback_first",
) -> dict[str, object]:
    """Return a resolved-by-first-agent response."""
    first_agent = next(iter(conflicting_outputs.keys()))
    return {
        "status": "resolved",
        "method": method,
        "result": conflicting_outputs[first_agent],
        "resolved_by": first_agent,
    }


def _fetch_shared_context(
    storage: PortfolioStorage,
    workflow_id: str,
) -> dict[str, object] | None:
    """Fetch shared_context for a workflow; return None if not found."""
    result = storage.query(
        "SELECT shared_context FROM agent_workflows WHERE id = $1",
        [workflow_id],
    )
    if result.is_empty():
        return None
    return result.get_column("shared_context")[0]


def resolve_conflicts(
    storage: PortfolioStorage,
    workflow_id: str,
    conflicting_outputs: dict[str, object],
    method: Literal["voting", "majority", "confidence", "first"] = "confidence",
) -> dict[str, object]:
    """Resolve conflicts between agent outputs using specified method.

    Args:
        storage: PortfolioStorage instance for database access
        workflow_id: ID of the workflow
        conflicting_outputs: Dictionary mapping agent_type to output
        method: Resolution method:
            - 'voting': Use explicit votes from agents
            - 'majority': Simple majority of agent outputs
            - 'confidence': Weighted by confidence scores
            - 'first': Use first agent's output (fallback)

    Returns:
        Resolved output with metadata about resolution
    """
    try:
        return _run_resolution(storage, workflow_id, conflicting_outputs, method)
    except Exception as e:
        logger.error("conflict_resolution_failed", error=str(e), exc_info=True)
        if conflicting_outputs:
            first_agent = next(iter(conflicting_outputs.keys()))
            return {
                "status": "error_fallback",
                "method": "error_first",
                "result": conflicting_outputs[first_agent],
                "resolved_by": first_agent,
                "error": str(e),
            }
        return {"status": "error", "error": str(e)}


def _run_resolution(
    storage: PortfolioStorage,
    workflow_id: str,
    conflicting_outputs: dict[str, object],
    method: str,
) -> dict[str, object]:
    """Core resolution logic without exception handling."""
    if not conflicting_outputs:
        return {"status": "error", "error": "No outputs to resolve"}

    if len(conflicting_outputs) == 1:
        agent_type = next(iter(conflicting_outputs.keys()))
        return {
            "status": "resolved",
            "method": "single_agent",
            "result": conflicting_outputs[agent_type],
            "resolved_by": agent_type,
        }

    shared_context = _fetch_shared_context(storage, workflow_id)

    if shared_context is None:
        logger.warning("workflow_not_found_fallback", workflow_id=workflow_id)
        return _first_agent_result(conflicting_outputs)

    if method == "confidence":
        return _resolve_by_confidence(shared_context, conflicting_outputs)
    if method == "voting":
        return _resolve_by_voting(shared_context, conflicting_outputs)
    if method == "majority":
        return _resolve_by_majority(conflicting_outputs)

    # Fallback: Use first agent's output
    first_agent = next(iter(conflicting_outputs.keys()))
    logger.warning(
        "fallback_resolution_used", workflow_id=workflow_id, resolved_by=first_agent
    )
    return _first_agent_result(conflicting_outputs)


def _extract_agent_confidence(
    agents: dict[str, object], agent_type: str
) -> tuple[float, object]:
    """Extract the latest confidence and output for an agent. Returns (0.0, None) if unavailable."""
    agent_data = agents.get(agent_type)
    if not isinstance(agent_data, dict):
        return 0.0, None

    agent_outputs = agent_data.get("outputs", [])
    if not (isinstance(agent_outputs, list) and agent_outputs):
        return 0.0, None

    latest = agent_outputs[-1]
    if not isinstance(latest, dict):
        return 0.0, None

    confidence = latest.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)):
        return 0.0, None

    return float(confidence), latest.get("output")


def _resolve_by_confidence(
    shared_context: dict[str, object], conflicting_outputs: dict[str, object]
) -> dict[str, object]:
    """Resolve conflicts by selecting the highest confidence output."""
    agents = shared_context.get("agents", {})
    if not isinstance(agents, dict):
        agents = {}

    max_confidence = 0.0
    best_agent = None
    best_output = None

    for agent_type in conflicting_outputs:
        confidence, output = _extract_agent_confidence(agents, agent_type)
        if output is not None and confidence > max_confidence:
            max_confidence = confidence
            best_agent = agent_type
            best_output = output

    if best_output is not None:
        return {
            "status": "resolved",
            "method": "confidence",
            "result": best_output,
            "resolved_by": best_agent,
            "confidence": max_confidence,
        }

    return _first_agent_result(conflicting_outputs)


def _count_votes(votes: dict[str, object]) -> dict[str, int]:
    """Count votes from the votes mapping (decision_id -> list of vote records)."""
    vote_counts: dict[str, int] = {}
    for decision_votes in votes.values():
        if not isinstance(decision_votes, list):
            continue
        for vote_record in decision_votes:
            if not isinstance(vote_record, dict):
                continue
            vote_val = str(vote_record.get("vote", ""))
            if vote_val:
                vote_counts[vote_val] = vote_counts.get(vote_val, 0) + 1
    return vote_counts


def _resolve_by_voting(
    shared_context: dict[str, object], conflicting_outputs: dict[str, object]
) -> dict[str, object]:
    """Resolve conflicts by using explicit votes."""
    votes = shared_context.get("votes", {})
    if votes and isinstance(votes, dict):
        vote_counts = _count_votes(votes)
        if vote_counts:
            majority_vote = max(vote_counts, key=vote_counts.get)
            return {
                "status": "resolved",
                "method": "voting",
                "result": majority_vote,
                "vote_counts": vote_counts,
            }

    return _first_agent_result(conflicting_outputs)


def _resolve_by_majority(conflicting_outputs: dict[str, object]) -> dict[str, object]:
    """Resolve conflicts by simple majority - count identical outputs."""
    output_counts: dict[str, int] = {}
    output_map: dict[str, object] = {}

    for output in conflicting_outputs.values():
        output_str = str(output)
        output_counts[output_str] = output_counts.get(output_str, 0) + 1
        output_map[output_str] = output

    majority_output_str = max(output_counts, key=output_counts.get)
    return {
        "status": "resolved",
        "method": "majority",
        "result": output_map[majority_output_str],
        "count": output_counts[majority_output_str],
        "total": len(conflicting_outputs),
    }
