"""Agent spec definitions for Jenny operator routines."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JennyAgentSpec:
    agent_slug: str
    system_prompt: str
    prompt_mode: str


AGENT_SPECS: tuple[JennyAgentSpec, ...] = (
    JennyAgentSpec(
        agent_slug="equity-analyst",
        prompt_mode="thesis",
        system_prompt=(
            "You are Jenny's thesis guardian. Return strict JSON only. "
            "Focus on whether the thesis still holds for a solo long-only investor."
        ),
    ),
    JennyAgentSpec(
        agent_slug="risk-manager",
        prompt_mode="risk",
        system_prompt=(
            "You are Jenny's risk manager. Return strict JSON only. "
            "Focus on concentration, downside, and position-sizing discipline."
        ),
    ),
    JennyAgentSpec(
        agent_slug="trade-manager",
        prompt_mode="exit",
        system_prompt=(
            "You are Jenny. Return strict JSON only. "
            "Focus on whether to hold, trim, review, or exit based on the current facts."
        ),
    ),
    JennyAgentSpec(
        agent_slug="investment-committee",
        prompt_mode="synthesis",
        system_prompt=(
            "You are Jenny's decision synthesizer. Return strict JSON only. "
            "Weigh the thesis, risks, and catalysts to produce the clearest next action."
        ),
    ),
)
