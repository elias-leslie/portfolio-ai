"""Roundtable mode logic for multi-agent conversations."""

import json
import logging
import re
from typing import Any

from .session_bridge import SessionBridge
from .claude_process import ClaudeSession
from .gemini_process import GeminiSession
from .stream_parser import message_to_dict
from .session_utils import (
    get_or_create_gemini_session,
    get_or_create_session_with_permissions,
    build_roundtable_context,
    store_agent_message,
)

logger = logging.getLogger(__name__)


# Disagreement keywords for roundtable auto-discussion
DISAGREEMENT_KEYWORDS = [
    "disagree", "incorrect", "wrong", "mistake", "error",
    "actually", "however", "but i think", "not quite",
    "missing", "overlooked", "failed to consider",
    "inaccurate", "misleading", "contrary to",
    "i would argue", "that's not", "flaw", "omission",
    "hallucination", "incorrect assumption",
]


def detect_disagreement(response: str) -> bool:
    """Check if a response contains disagreement indicators."""
    response_lower = response.lower()
    return any(kw in response_lower for kw in DISAGREEMENT_KEYWORDS)


def parse_agent_response(response: str) -> tuple[str, str, str]:
    """Parse agent response to extract message and addressing.

    Agents should wrap responses in JSON:
    {"message": "...", "addressing": "user|claude|gemini", "action": "respond|pass|correct"}

    Returns:
        Tuple of (message_text, addressing, action)
        - addressing: "user", "claude", or "gemini"
        - action: "respond", "pass", or "correct"
    """
    # Try to parse JSON wrapper
    try:
        # Handle case where response is just JSON
        data = json.loads(response.strip())
        return (
            data.get("message", response),
            data.get("addressing", "user"),
            data.get("action", "respond"),
        )
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from end of response (agent might include message then JSON)
    json_match = re.search(r'\{[^{}]*"addressing"[^{}]*\}\s*$', response)
    if json_match:
        try:
            data = json.loads(json_match.group())
            message = response[:json_match.start()].strip()
            return (
                message or data.get("message", response),
                data.get("addressing", "user"),
                data.get("action", "respond"),
            )
        except json.JSONDecodeError:
            pass

    # No JSON found - default to addressing user
    return (response, "user", "respond")


def build_roundtable_prompt(
    agent_name: str,
    other_agent: str,
    history_context: str,
    user_message: str,
    is_review: bool = False,
    previous_response: str | None = None,
) -> str:
    """Build a prompt for roundtable mode with JSON addressing instructions."""

    json_instructions = f"""
IMPORTANT: End your response with a JSON block indicating who you're addressing next:
{{"addressing": "user"}} - if you're done and waiting for the user
{{"addressing": "{other_agent}"}} - if you're asking {other_agent.upper()} a question or passing to them
{{"addressing": "{agent_name}"}} - only if someone asked you directly

Examples:
- "Here's my answer to your question. {{"addressing": "user"}}"
- "What do you think, {other_agent.upper()}? {{"addressing": "{other_agent}"}}"
"""

    if is_review:
        # Silent review mode - only respond if correction needed
        return f"""You are {agent_name.upper()} in a roundtable with {other_agent.upper()} and a user.

{other_agent.upper()} just responded to the user:
{previous_response}

Review their response for accuracy. You have two options:
1. If the response is accurate and complete, respond ONLY with: {{"action": "pass"}}
2. If you see errors, omissions, or important additions needed, provide your correction.

If correcting, keep it brief and factual. End with {{"addressing": "user"}} or {{"addressing": "{other_agent}"}} if asking them to clarify.

DO NOT repeat what {other_agent.upper()} said correctly. Only speak up if there's something to add or correct.
"""

    # Regular response prompt
    parts = [f"You are {agent_name.upper()} in a roundtable discussion with {other_agent.upper()} and a user."]

    if history_context:
        parts.append(f"\nConversation history:\n{history_context}\n")

    if previous_response:
        parts.append(f"\n{other_agent.upper()} just said:\n{previous_response}\n")

    parts.append(f"\nUser's message: {user_message}")
    parts.append(json_instructions)

    return "\n".join(parts)


async def stream_agent_response(
    session: ClaudeSession | GeminiSession,
    content: str,
    safe_send_json,
    ws_closed_check,
    agent_name: str,
) -> str:
    """Stream a single agent's response and return the full text.

    Args:
        session: The agent session (Claude or Gemini)
        content: The prompt to send
        safe_send_json: Function to send JSON to WebSocket
        ws_closed_check: Function to check if WebSocket is closed
        agent_name: "claude" or "gemini" for attribution

    Returns:
        The complete response text
    """
    response_text_parts = []

    async for stream_msg in session.send(content):
        if ws_closed_check():
            break
        msg_dict = message_to_dict(stream_msg)
        # Add agent attribution to stream messages
        if not await safe_send_json({
            "type": "stream",
            "data": msg_dict,
            "agent": agent_name,
        }):
            break
        # Collect text
        for block in msg_dict.get("content", []):
            if block.get("type") == "text" and block.get("text"):
                response_text_parts.append(block["text"])

    return "".join(response_text_parts)


async def handle_roundtable_message(
    bridge: SessionBridge,
    session_id: str,
    content: str,
    order: str,
    safe_send_json,
    permission_callback,
    ws_closed_check,
    max_turns: int = 10,
) -> None:
    """Handle a roundtable message with shared-channel model.

    Features:
    - JSON addressing: agents indicate who they're talking to
    - Silent review: second agent only speaks if they have corrections
    - Automatic continuation: agents can address each other directly
    """
    # Determine agent order
    if order == "gemini-first":
        first_agent = "gemini"
        second_agent = "claude"
    else:
        first_agent = "claude"
        second_agent = "gemini"

    logger.info(f"Roundtable: {first_agent} first, {second_agent} reviews")

    try:
        # Build conversation history
        history_context = await build_roundtable_context(bridge.db, session_id)
        if history_context:
            logger.info(f"Roundtable: Loaded {len(history_context)} chars of history")

        # Get sessions for both agents
        sessions = {}
        for agent in [first_agent, second_agent]:
            if agent == "gemini":
                sessions[agent] = await get_or_create_gemini_session(bridge, session_id)
            else:
                sessions[agent] = await get_or_create_session_with_permissions(
                    bridge, session_id, permission_callback
                )
            if not sessions[agent]:
                await safe_send_json({
                    "type": "error",
                    "message": f"Failed to start {agent} session",
                })
                return

        # Set original_provider for roundtable
        await bridge.db.set_original_provider(session_id, "both")

        # First agent responds
        first_prompt = build_roundtable_prompt(
            agent_name=first_agent,
            other_agent=second_agent,
            history_context=history_context,
            user_message=content,
        )

        await safe_send_json({"type": "agent_start", "agent": first_agent})
        first_response_raw = await stream_agent_response(
            sessions[first_agent], first_prompt, safe_send_json, ws_closed_check, first_agent
        )
        await safe_send_json({"type": "agent_done", "agent": first_agent})

        if ws_closed_check():
            return

        # Parse first response
        first_message, addressing, _ = parse_agent_response(first_response_raw)

        # Store first response (use clean message for display)
        await store_agent_message(bridge.db, session_id, first_message, first_agent)

        logger.info(f"Roundtable: {first_agent} addressing: {addressing}")

        # Track current state
        current_agent = first_agent
        current_response = first_message
        turn_count = 1

        # Conversation loop
        while turn_count < max_turns and not ws_closed_check():
            other_agent = second_agent if current_agent == first_agent else first_agent

            # Determine next action based on addressing
            if addressing == other_agent:
                # Agent addressed the other agent - they should respond
                next_agent = other_agent
                is_review = False
                logger.info(f"Roundtable: {current_agent} addressed {other_agent}")
            elif addressing == "user":
                # Agent addressed user - other agent does silent review
                next_agent = other_agent
                is_review = True
                logger.info(f"Roundtable: {other_agent} doing silent review")
            else:
                # Addressed self or unknown - end turn
                logger.info(f"Roundtable: Ending, addressing={addressing}")
                break

            # Build prompt for next agent
            next_prompt = build_roundtable_prompt(
                agent_name=next_agent,
                other_agent=current_agent,
                history_context=history_context,
                user_message=content,
                is_review=is_review,
                previous_response=current_response,
            )

            await safe_send_json({"type": "agent_start", "agent": next_agent})
            next_response_raw = await stream_agent_response(
                sessions[next_agent], next_prompt, safe_send_json, ws_closed_check, next_agent
            )
            await safe_send_json({"type": "agent_done", "agent": next_agent})

            if ws_closed_check():
                return

            # Parse response
            next_message, next_addressing, action = parse_agent_response(next_response_raw)

            # Handle silent review pass
            if is_review and action == "pass":
                logger.info(f"Roundtable: {next_agent} passed (no corrections)")
                # Send a signal that review passed (no visible message)
                await safe_send_json({"type": "review_pass", "agent": next_agent})
                break

            # Store response if not a pass
            if action != "pass":
                await store_agent_message(bridge.db, session_id, next_message, next_agent)

            # If review resulted in correction, end (user got both perspectives)
            if is_review and action == "correct":
                logger.info(f"Roundtable: {next_agent} provided correction")
                break

            # Update state for next iteration
            current_agent = next_agent
            current_response = next_message
            addressing = next_addressing
            turn_count += 1

            # If now addressing user, end
            if addressing == "user":
                logger.info(f"Roundtable: {current_agent} addressing user, ending")
                break

        await safe_send_json({"type": "done"})

    except Exception as e:
        logger.error(f"Roundtable error: {e}")
        await safe_send_json({
            "type": "error",
            "message": f"Roundtable error: {str(e)}",
        })
