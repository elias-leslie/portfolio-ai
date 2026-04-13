"""LLM message building and response parsing for household document review."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from agent_hub.models.content import ImageContent, MessageInput, TextContent

from app.logging_config import get_logger
from app.services._household_document_text import _render_pdf_pages_to_png

logger = get_logger(__name__)

def _pdf_image_blocks(stored_path: Path) -> list[ImageContent]:
    blocks: list[ImageContent] = []
    try:
        for png_bytes in _render_pdf_pages_to_png(stored_path, scale=1.5, max_pages=2):
            blocks.append(
                ImageContent.from_base64(
                    base64.b64encode(png_bytes).decode("utf-8"),
                    media_type="image/png",
                )
            )
    except Exception as exc:
        logger.warning("household_pdf_preview_failed", path=str(stored_path), error=str(exc))
        return []
    return blocks


def _build_messages(
    *,
    payload: dict[str, Any],
    stored_path: Path,
    content_type: str | None,
    extracted_text: str | None,
    baseline_review: dict[str, Any],
) -> list[MessageInput]:
    content_blocks: list[Any] = [
        TextContent(
            text=(
                "Review this uploaded household finance document using your assigned Agent Hub prompts.\n\n"
                "Document metadata:\n"
                f"{json.dumps(payload, indent=2)}\n\n"
                "Deterministic reviewer baseline:\n"
                f"{json.dumps(baseline_review, indent=2)}\n\n"
                "Use extracted text and visual evidence to improve or correct the baseline review."
            )
        )
    ]
    if extracted_text:
        content_blocks.append(TextContent(text=f"Extracted text preview:\n{extracted_text[:12000]}"))
    if stored_path.suffix.lower() == ".pdf" or content_type == "application/pdf":
        content_blocks.extend(_pdf_image_blocks(stored_path))
    if content_type and content_type.startswith("image/"):
        content_blocks.append(
            ImageContent.from_base64(
                base64.b64encode(stored_path.read_bytes()).decode("utf-8"),
                media_type=content_type,
            )
        )
    return [MessageInput(role="user", content=content_blocks)]


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
