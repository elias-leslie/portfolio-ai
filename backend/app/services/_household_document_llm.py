"""LLM message building and response parsing for household document review."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agent_hub.models.content import MessageInput


def _build_messages(
    *,
    payload: dict[str, Any],
    stored_path: Path,
    content_type: str | None,
    extracted_text: str | None,
    baseline_review: dict[str, Any],
) -> list[MessageInput]:
    prompt_parts = [
        "Review this uploaded household finance document using your assigned Agent Hub prompts.",
        "",
        "Document metadata:",
        json.dumps(payload, indent=2),
        "",
        "Deterministic reviewer baseline:",
        json.dumps(baseline_review, indent=2),
        "",
        "Use extracted text to improve or correct the baseline review.",
    ]
    if extracted_text:
        prompt_parts.extend(["", "Extracted text preview:", extracted_text[:12000]])
    else:
        prompt_parts.extend(["", "Extracted text preview:", "[none]"])
    return [MessageInput(role="user", content="\n".join(prompt_parts))]


def _parse_review_payload(content: Any) -> dict[str, Any]:
    """Coerce LLM response content to text and extract the first valid JSON object."""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        chunks = [item if isinstance(item, str) else getattr(item, "text", None) for item in content]
        text = "\n".join(c for c in chunks if isinstance(c, str) and c)
    else:
        text = str(content)

    candidates: list[str] = []
    for pattern in [r"```json\s*(\{.*?\})\s*```", r"```\s*(\{.*?\})\s*```"]:
        candidates.extend(re.findall(pattern, text, flags=re.DOTALL | re.IGNORECASE))
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)
    first, last = text.find("{"), text.rfind("}")
    if first != -1 and last > first:
        candidates.append(text[first : last + 1].strip())

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    raise ValueError("No valid JSON object found in review payload")
