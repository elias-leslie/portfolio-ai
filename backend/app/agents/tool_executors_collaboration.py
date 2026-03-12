"""Collaboration tool executors for inter-agent communication.

This module provides execution logic for collaboration tools:
- send_message_to_agent: Send messages between agents
- query_agent_memory: Query shared workflow context
- vote_on_decision: Vote on decisions for multi-agent consensus
- wait_for_agent_response: Wait for agent responses
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from app.logging_config import get_logger

logger = get_logger(__name__)


class CollaborationTools:
    """Collaboration tool executors for agents."""

    def __init__(self, storage: PortfolioStorage) -> None:
        """Initialize collaboration tools.

        Args:
            storage: PortfolioStorage instance
        """
        self.storage = storage

    def execute_send_message_to_agent(
        self,
        agent_run_id: str,
        agent_type: str,
        message_type: str,
        message: str,
        data: dict[str, object] | None = None,
        priority: int = 5,
    ) -> dict[str, object]:
        """Execute send_message_to_agent tool for inter-agent communication.

        Args:
            agent_run_id: ID of the sending agent run
            agent_type: Target agent type (e.g., 'gemini', 'claude')
            message_type: Type of message ('question', 'data', 'consensus')
            message: Message content
            data: Optional structured data
            priority: Message priority 1-10 (default 5)

        Returns:
            Result dictionary with message_id and status
        """
        try:
            message_id = str(uuid.uuid4())

            # Build content JSONB
            content: dict[str, object] = {
                "message": message,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            if data:
                content["data"] = data

            # Insert message
            self.storage.insert_dict(
                "agent_messages",
                {
                    "id": message_id,
                    "from_agent_run_id": agent_run_id,
                    "to_agent_type": agent_type,
                    "message_type": message_type,
                    "content": json.dumps(content),
                    "status": "pending",
                    "priority": priority,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )

            logger.info(
                f"Agent {agent_run_id} sent {message_type} message to {agent_type}: {message[:100]}"
            )

            return {
                "status": "sent",
                "message_id": message_id,
                "to_agent_type": agent_type,
                "message_type": message_type,
            }

        except Exception as e:
            logger.error("send_message_failed", error=str(e), exc_info=True)
            return {
                "status": "error",
                "error": str(e),
            }

    def execute_query_agent_memory(self, workflow_id: str, key: str) -> dict[str, object]:
        """Execute query_agent_memory tool to access shared workflow context.

        Args:
            workflow_id: ID of the workflow
            key: Key to retrieve from shared context

        Returns:
            Result dictionary with value or error
        """
        try:
            # Query workflow shared context
            result = self.storage.query(
                "SELECT shared_context FROM agent_workflows WHERE id = $1",
                [workflow_id],
            )

            if result.is_empty():
                return {
                    "status": "not_found",
                    "workflow_id": workflow_id,
                    "error": f"Workflow {workflow_id} not found",
                }

            shared_context = result.get_column("shared_context")[0]

            # Extract key from context
            if key in shared_context:
                return {
                    "status": "found",
                    "workflow_id": workflow_id,
                    "key": key,
                    "value": shared_context[key],
                }
            return {
                "status": "key_not_found",
                "workflow_id": workflow_id,
                "key": key,
                "available_keys": list(shared_context.keys()),
            }

        except Exception as e:
            logger.error("workflow_memory_query_failed", error=str(e), exc_info=True)
            return {
                "status": "error",
                "error": str(e),
            }

    def execute_vote_on_decision(
        self,
        agent_run_id: str,
        workflow_id: str,
        decision_id: str,
        vote: str,
        reasoning: str,
        confidence: float | None = None,
    ) -> dict[str, object]:
        """Execute vote_on_decision tool for multi-agent consensus.

        Args:
            agent_run_id: ID of the voting agent run
            workflow_id: ID of the workflow
            decision_id: ID of the decision
            vote: Vote value ('approve', 'reject', 'abstain')
            reasoning: Explanation for vote
            confidence: Confidence level 0-1 (for weighted voting)

        Returns:
            Result dictionary with vote status
        """
        try:
            # Get current shared context
            result = self.storage.query(
                "SELECT shared_context FROM agent_workflows WHERE id = $1",
                [workflow_id],
            )

            if result.is_empty():
                return {
                    "status": "error",
                    "error": f"Workflow {workflow_id} not found",
                }

            shared_context = result.get_column("shared_context")[0]

            # Initialize votes structure if not exists
            if "votes" not in shared_context:
                shared_context["votes"] = {}

            if decision_id not in shared_context["votes"]:
                shared_context["votes"][decision_id] = []

            # Add vote
            vote_record = {
                "agent_run_id": agent_run_id,
                "vote": vote,
                "reasoning": reasoning,
                "confidence": confidence or 1.0,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            shared_context["votes"][decision_id].append(vote_record)

            # Update workflow context
            with self.storage.connection() as conn:
                conn.execute(
                    "UPDATE agent_workflows SET shared_context = $1, last_updated_at = $2 WHERE id = $3",
                    [shared_context, datetime.now(UTC), workflow_id],
                )

            logger.info(
                f"Agent {agent_run_id} voted {vote} on {decision_id} in workflow {workflow_id}"
            )

            return {
                "status": "voted",
                "workflow_id": workflow_id,
                "decision_id": decision_id,
                "vote": vote,
                "total_votes": len(shared_context["votes"][decision_id]),
            }

        except Exception as e:
            logger.error("vote_recording_failed", error=str(e), exc_info=True)
            return {
                "status": "error",
                "error": str(e),
            }

    def execute_wait_for_agent_response(
        self, message_id: str, timeout_seconds: int = 300
    ) -> dict[str, object]:
        """Execute wait_for_agent_response tool to wait for another agent's reply.

        NOTE: This is a simplified implementation that checks current status.
        A full implementation would use polling or async waiting with timeout.

        Args:
            message_id: ID of the message to wait for response to
            timeout_seconds: Maximum time to wait (default 300)

        Returns:
            Result dictionary with response status and content
        """
        try:
            # Query message status
            result = self.storage.query(
                "SELECT status, content, replied_at FROM agent_messages WHERE id = $1",
                [message_id],
            )

            if result.is_empty():
                return {
                    "status": "error",
                    "error": f"Message {message_id} not found",
                }

            status = result.get_column("status")[0]
            content = result.get_column("content")[0]
            replied_at = result.get_column("replied_at")[0]

            if status == "replied":
                return {
                    "status": "received",
                    "message_id": message_id,
                    "response": content,
                    "replied_at": replied_at.isoformat() if replied_at else None,
                }
            if status == "read":
                return {
                    "status": "waiting",
                    "message_id": message_id,
                    "message": "Message read but no reply yet",
                }
            # pending
            return {
                "status": "waiting",
                "message_id": message_id,
                "message": "Message not yet read",
            }

        except Exception as e:
            logger.error("message_response_check_failed", error=str(e), exc_info=True)
            return {
                "status": "error",
                "error": str(e),
            }


__all__ = ["CollaborationTools"]
