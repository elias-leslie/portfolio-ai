"""LLM message building and response parsing for household document review."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from agent_hub.models.content import ImageContent, MessageInput, TextContent

from app.services._household_document_text import _render_pdf_pages_to_png

_VISUAL_REVIEW_TEXT_THRESHOLD = 500
_IMAGE_MEDIA_TYPES = {
    ".bmp": "image/bmp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _visual_review_blocks(
    *,
    stored_path: Path,
    content_type: str | None,
    extracted_text: str | None,
) -> list[ImageContent]:
    if not needs_visual_review(
        stored_path=stored_path,
        content_type=content_type,
        extracted_text=extracted_text,
    ):
        return []
    suffix = stored_path.suffix.lower()
    image_payloads: list[tuple[str, bytes]] = []
    if suffix == ".pdf" or content_type == "application/pdf":
        try:
            image_payloads = [
                ("image/png", png_bytes)
                for png_bytes in _render_pdf_pages_to_png(
                    stored_path,
                    scale=2,
                    max_pages=2,
                )
            ]
        except Exception:
            image_payloads = []
    elif (content_type and content_type.startswith("image/")) or suffix in _IMAGE_MEDIA_TYPES:
        media_type = content_type if content_type and content_type.startswith("image/") else _IMAGE_MEDIA_TYPES.get(suffix, "image/png")
        image_payloads = [(media_type, stored_path.read_bytes())]

    return [
        ImageContent(
            source={
                "type": "base64",
                "media_type": media_type,
                "data": base64.b64encode(image_bytes).decode("ascii"),
            }
        )
        for media_type, image_bytes in image_payloads[:2]
        if image_bytes
    ]


def needs_visual_review(
    *,
    stored_path: Path,
    content_type: str | None,
    extracted_text: str | None,
) -> bool:
    if not stored_path.exists():
        return False
    if extracted_text and len(extracted_text) >= _VISUAL_REVIEW_TEXT_THRESHOLD:
        return False
    suffix = stored_path.suffix.lower()
    return bool(
        suffix == ".pdf"
        or content_type == "application/pdf"
        or (content_type and content_type.startswith("image/"))
        or suffix in _IMAGE_MEDIA_TYPES
    )


def _build_messages(
    *,
    payload: dict[str, Any],
    stored_path: Path,
    content_type: str | None,
    extracted_text: str | None,
    baseline_review: dict[str, Any],
    household_context: dict[str, Any] | None = None,
    prior_review: dict[str, Any] | None = None,
    reconciliation_summary: dict[str, Any] | None = None,
) -> list[MessageInput]:
    prompt_parts = [
        "Review this uploaded household finance document using your assigned Agent Hub prompts.",
        "",
        "Document metadata:",
        json.dumps(payload, indent=2),
        "",
        "Deterministic reviewer baseline:",
        json.dumps(baseline_review, indent=2),
    ]
    if household_context:
        prompt_parts.extend(
            [
                "",
                "Current canonical household context:",
                json.dumps(household_context, indent=2),
            ]
        )
    if prior_review:
        prompt_parts.extend(
            [
                "",
                "Prior review attempt:",
                json.dumps(prior_review, indent=2),
            ]
        )
    if reconciliation_summary:
        prompt_parts.extend(
            [
                "",
                "Post-apply reconciliation issues from prior attempt:",
                json.dumps(reconciliation_summary, indent=2),
            ]
        )
    prompt_parts.extend(
        [
            "",
            "Own full intake outcome, not just classification.",
            "Read upload. infer all accounts, balances, transactions, and useful facts. reconcile against household context. use related evidence examples when format drift exists, but do not copy stale values. save strong identity hints. run an internal self-check. ask the user only if ambiguity remains real after all of that.",
            "For single-account transaction activity exports, financial_accounts must describe only the uploaded account. Account names or masks mentioned inside transaction descriptions are counterparties; keep them in transaction context only, not as financial_accounts/evidence accounts.",
            "",
            "Use extracted text to improve or correct the baseline review.",
        ]
    )
    if extracted_text:
        prompt_parts.extend(["", "Extracted text preview:", extracted_text[:12000]])
    else:
        prompt_parts.extend(["", "Extracted text preview:", "[none]"])
    prompt_text = "\n".join(prompt_parts)
    image_blocks = _visual_review_blocks(
        stored_path=stored_path,
        content_type=content_type,
        extracted_text=extracted_text,
    )
    if not image_blocks:
        return [MessageInput(role="user", content=prompt_text)]
    return [
        MessageInput(
            role="user",
            content=[
                TextContent(text=prompt_text),
                *image_blocks,
            ],
        )
    ]


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
