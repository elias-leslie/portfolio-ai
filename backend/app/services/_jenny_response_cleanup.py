"""Cleanup helpers for Jenny agent output."""

from __future__ import annotations

import re

# Persona protocol: [[S:completed|partial|failed:detail]] is a run-status tag
# and is dropped, like [[P:...]] narration and [[F:...]] feedback tags. But
# models sometimes misuse [[S:...]] to wrap their whole user-facing answer
# (observed live: a greeting that was nothing but one [[S:hi...]] tag) — a
# non-status [[S:...]] is unwrapped so the speech inside survives.
_STATUS_TAG_PATTERN = re.compile(
    r"\[\[S:(?:completed|partial|failed):.*?\]\]", re.DOTALL
)
_SPEECH_TAG_PATTERN = re.compile(r"\[\[S:(.*?)\]\]", re.DOTALL)
_AGENT_TAG_PATTERN = re.compile(r"\[\[(?:P|F):.*?\]\]", re.DOTALL)


def strip_agent_output_tags(text: str) -> str:
    """Remove agent narration and summary tags from a response."""
    stripped = _STATUS_TAG_PATTERN.sub("", text)
    stripped = _SPEECH_TAG_PATTERN.sub(lambda m: m.group(1), stripped)
    stripped = _AGENT_TAG_PATTERN.sub("", stripped)
    lines = [line.rstrip() for line in stripped.splitlines()]
    collapsed: list[str] = []
    last_was_blank = False
    for line in lines:
        if not line.strip():
            if collapsed and not last_was_blank:
                collapsed.append("")
            last_was_blank = True
            continue
        collapsed.append(line.strip())
        last_was_blank = False
    return "\n".join(collapsed).strip()


def extract_json_object_text(text: str) -> str | None:
    """Extract a JSON object from mixed response text after tag cleanup."""
    cleaned = strip_agent_output_tags(text)
    if "```json" in cleaned:
        return cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    if "```" in cleaned:
        return cleaned.split("```", 1)[1].split("```", 1)[0].strip()
    if "{" not in cleaned or "}" not in cleaned:
        return None
    return cleaned[cleaned.index("{") : cleaned.rindex("}") + 1].strip()
