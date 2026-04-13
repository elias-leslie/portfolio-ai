"""Agent spec definitions for Jenny operator routines."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JennyAgentSpec:
    agent_slug: str
    prompt_mode: str


AGENT_SPECS: tuple[JennyAgentSpec, ...] = (
    JennyAgentSpec(
        agent_slug="equity-analyst",
        prompt_mode="thesis",
    ),
    JennyAgentSpec(
        agent_slug="risk-manager",
        prompt_mode="risk",
    ),
    JennyAgentSpec(
        agent_slug="trade-manager",
        prompt_mode="exit",
    ),
    JennyAgentSpec(
        agent_slug="investment-committee",
        prompt_mode="synthesis",
    ),
)
