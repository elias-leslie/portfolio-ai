"""Response parsing and normalization helpers for Jenny review agents."""

from __future__ import annotations

import json
from typing import Any

from app.logging_config import get_logger

logger = get_logger(__name__)


def normalize_confidence(raw_confidence: float | int | str | bool | None) -> float | None:
    if raw_confidence is None:
        return None
    if isinstance(raw_confidence, bool):
        return 1.0 if raw_confidence else 0.0
    if isinstance(raw_confidence, int | float):
        value = float(raw_confidence)
        normalized_value = value / 100.0 if value > 1.0 else value
        return max(0.0, min(1.0, normalized_value))
    if isinstance(raw_confidence, str):
        normalized = raw_confidence.strip().lower()
        qualitative_map = {"low": 0.35, "medium": 0.6, "med": 0.6, "high": 0.8}
        if normalized in qualitative_map:
            return qualitative_map[normalized]
        if normalized.endswith("%"):
            normalized = normalized[:-1].strip()
        value = float(normalized)
        normalized_value = value / 100.0 if value > 1.0 else value
        return max(0.0, min(1.0, normalized_value))
    raise ValueError(f"Unsupported confidence value: {raw_confidence!r}")


def normalize_verdict(raw_verdict: str | None) -> str:
    verdict = str(raw_verdict or "review").strip().lower()
    compact = verdict.split("—", 1)[0].split("-", 1)[0].strip()
    prefix_map = (
        (("buy",), "buy"),
        (("hold",), "hold"),
        (("trim",), "trim"),
        (("exit", "sell"), "exit"),
        (("avoid", "pass", "skip"), "avoid"),
    )
    for prefixes, normalized in prefix_map:
        if compact.startswith(prefixes):
            return normalized
    if compact in {"wait", "watch", "review", "reassess"}:
        return "review"
    return "review"


_FALLBACK_CONFIDENCE = 0.45

def _extract_json(content: str) -> dict[str, Any]:
    try:
        if "```json" in content:
            content = content.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in content:
            content = content.split("```", 1)[1].split("```", 1)[0].strip()
        elif "{" in content and "}" in content:
            content = content[content.index("{") : content.rindex("}") + 1]
        return dict(json.loads(content))
    except (json.JSONDecodeError, ValueError):
        logger.warning("jenny_review_json_parse_failed", content_length=len(content))
        return {
            "verdict": "review",
            "confidence": _FALLBACK_CONFIDENCE,
            "rationale": content.strip(),
            "recommendation": "Manual review required.",
            "strengths": [],
            "weaknesses": ["Response was not valid JSON."],
        }


def parse_agent_response(content: str, agent_name: str) -> dict[str, Any]:
    parsed = _extract_json(content)

    strengths = parsed.get("strengths", [])
    if not isinstance(strengths, list):
        strengths = []
    weaknesses = parsed.get("weaknesses", [])
    if not isinstance(weaknesses, list):
        weaknesses = []

    return {
        "agent_name": agent_name,
        "verdict": normalize_verdict(parsed.get("verdict", "review")),
        "confidence": normalize_confidence(parsed.get("confidence", 0.5)),
        "rationale": str(parsed.get("rationale") or "No rationale provided."),
        "recommendation": str(parsed.get("recommendation")) if parsed.get("recommendation") else None,
        "strengths": [str(item) for item in strengths][:5],
        "weaknesses": [str(item) for item in weaknesses][:5],
        "metadata": {"raw_response": parsed},
    }


_VALID_MODES = {"thesis", "risk", "exit", "synthesis"}

def build_agent_prompt(mode: str, payload: dict[str, Any]) -> str:
    mode_map = {
        "thesis": "Decide whether the thesis still supports owning or buying the symbol.",
        "risk": "Decide whether current risk justifies trimming, reviewing, or holding.",
        "exit": "Focus on the next action for the position: hold, trim, review, exit, or avoid.",
        "synthesis": "Combine the prior evidence into the clearest plain-English next step.",
    }
    if mode not in mode_map:
        raise ValueError(
            f"Unknown mode {mode!r}. Valid modes are: {sorted(_VALID_MODES)}"
        )
    mode_instruction = mode_map[mode]

    review_instruction = ""
    if payload.get("review_mode") == "allocation":
        review_instruction = (
            " This symbol is a passive fund or index-style holding. "
            "Do not complain about a missing single-company thesis. "
            "Focus on allocation fit, concentration, market regime, and whether to hold, trim, or avoid adding."
        )
    elif payload.get("evidence_status") == "thin":
        review_instruction = (
            " Fresh evidence is limited. "
            "Do not invent precision or hidden conviction. "
            "If the facts are too thin, prefer review or avoid and explain the missing evidence plainly."
        )

    return (
        f"{mode_instruction}{review_instruction}\n"
        "Return JSON with keys: verdict, confidence, rationale, recommendation, strengths, weaknesses.\n"
        "Set confidence as a number from 0.0 to 1.0.\n"
        f"Context:\n{json.dumps(payload, default=str)}"
    )
