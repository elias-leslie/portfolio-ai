"""Consensus and conflict resolution for multi-agent workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from app.logging_config import get_logger

logger = get_logger(__name__)


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
        if not conflicting_outputs:
            return {
                "status": "error",
                "error": "No outputs to resolve",
            }

        if len(conflicting_outputs) == 1:
            # No conflict, return single output
            agent_type = next(iter(conflicting_outputs.keys()))
            return {
                "status": "resolved",
                "method": "single_agent",
                "result": conflicting_outputs[agent_type],
                "resolved_by": agent_type,
            }

        # Get workflow context for votes and confidence
        result = storage.query(
            "SELECT shared_context FROM agent_workflows WHERE id = $1",
            [workflow_id],
        )

        if result.is_empty():
            logger.warning(f"Workflow {workflow_id} not found, using first output as fallback")
            first_agent = next(iter(conflicting_outputs.keys()))
            return {
                "status": "resolved",
                "method": "fallback_first",
                "result": conflicting_outputs[first_agent],
                "resolved_by": first_agent,
            }

        shared_context = result.get_column("shared_context")[0]

        if method == "confidence":
            return _resolve_by_confidence(shared_context, conflicting_outputs)
        if method == "voting":
            return _resolve_by_voting(shared_context, conflicting_outputs)
        if method == "majority":
            return _resolve_by_majority(conflicting_outputs)

        # Fallback: Use first agent's output
        first_agent = next(iter(conflicting_outputs.keys()))
        logger.warning(
            f"Using fallback resolution for workflow {workflow_id}: first agent ({first_agent})"
        )

        return {
            "status": "resolved",
            "method": "fallback_first",
            "result": conflicting_outputs[first_agent],
            "resolved_by": first_agent,
        }

    except Exception as e:
        logger.error(f"Failed to resolve conflicts: {e}")
        # Ultimate fallback
        if conflicting_outputs:
            first_agent = next(iter(conflicting_outputs.keys()))
            return {
                "status": "error_fallback",
                "method": "error_first",
                "result": conflicting_outputs[first_agent],
                "resolved_by": first_agent,
                "error": str(e),
            }
        return {
            "status": "error",
            "error": str(e),
        }


def _resolve_by_confidence(
    shared_context: dict[str, object], conflicting_outputs: dict[str, object]
) -> dict[str, object]:
    """Resolve conflicts by selecting the highest confidence output."""
    max_confidence = 0.0
    best_agent = None
    best_output = None

    agents = shared_context.get("agents", {})
    if not isinstance(agents, dict):
        agents = {}

    for agent_type, _outputs in conflicting_outputs.items():
        if agent_type in agents:
            agent_data = agents[agent_type]
            if isinstance(agent_data, dict):
                agent_outputs = agent_data.get("outputs", [])
                if isinstance(agent_outputs, list) and agent_outputs:
                    latest = agent_outputs[-1]
                    if isinstance(latest, dict):
                        confidence = latest.get("confidence", 0.0)
                        if isinstance(confidence, (int, float)) and confidence > max_confidence:
                            max_confidence = float(confidence)
                            best_agent = agent_type
                            best_output = latest.get("output")

    if best_output is not None:
        return {
            "status": "resolved",
            "method": "confidence",
            "result": best_output,
            "resolved_by": best_agent,
            "confidence": max_confidence,
        }

    # Fallback if no outputs found
    first_agent = next(iter(conflicting_outputs.keys()))
    return {
        "status": "resolved",
        "method": "fallback_first",
        "result": conflicting_outputs[first_agent],
        "resolved_by": first_agent,
    }


def _resolve_by_voting(
    shared_context: dict[str, object], conflicting_outputs: dict[str, object]
) -> dict[str, object]:
    """Resolve conflicts by using explicit votes."""
    votes = shared_context.get("votes", {})
    if votes and isinstance(votes, dict):
        # Count votes (simplified - assumes single decision)
        vote_counts: dict[str, int] = {}
        for _decision_id, decision_votes in votes.items():
            if isinstance(decision_votes, list):
                for vote_record in decision_votes:
                    if isinstance(vote_record, dict):
                        vote_val = str(vote_record.get("vote", ""))
                        if vote_val:
                            vote_counts[vote_val] = vote_counts.get(vote_val, 0) + 1

        # Get majority vote
        if vote_counts:
            majority_vote = max(vote_counts, key=vote_counts.get)  # type: ignore
            return {
                "status": "resolved",
                "method": "voting",
                "result": majority_vote,
                "vote_counts": vote_counts,
            }

    # Fallback if no votes
    first_agent = next(iter(conflicting_outputs.keys()))
    return {
        "status": "resolved",
        "method": "fallback_first",
        "result": conflicting_outputs[first_agent],
        "resolved_by": first_agent,
    }


def _resolve_by_majority(conflicting_outputs: dict[str, object]) -> dict[str, object]:
    """Resolve conflicts by simple majority - count identical outputs."""
    output_counts: dict[str, int] = {}
    output_map: dict[str, object] = {}

    for _agent_type, output in conflicting_outputs.items():
        output_str = str(output)  # Simple comparison
        output_counts[output_str] = output_counts.get(output_str, 0) + 1
        output_map[output_str] = output

    majority_output_str = max(output_counts, key=output_counts.get)  # type: ignore
    return {
        "status": "resolved",
        "method": "majority",
        "result": output_map[majority_output_str],
        "count": output_counts[majority_output_str],
        "total": len(conflicting_outputs),
    }
