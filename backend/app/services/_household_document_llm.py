"""LLM message building and response parsing for household document review."""

from __future__ import annotations

import base64
import io
import json
import re
from pathlib import Path
from typing import Any

from agent_hub.models.content import ImageContent, MessageInput, TextContent
from PIL import Image, ImageOps

_IMAGE_REVIEW_MAX_BYTES = 4_000_000
_IMAGE_REVIEW_MAX_DIMENSION = 3200
_IMAGE_REVIEW_MIN_DIMENSION = 1400
_PROMPT_STRING_LIMIT = 2000
_PROMPT_LIST_LIMIT = 80
_RECEIPT_CROP_THRESHOLD = 110
_RECEIPT_CROP_PADDING_RATIO = 0.04


def _compact_prompt_value(value: Any) -> Any:
    if isinstance(value, str):
        if len(value) <= _PROMPT_STRING_LIMIT:
            return value
        return f"{value[:_PROMPT_STRING_LIMIT]}\n[truncated]"
    if isinstance(value, list):
        compacted = [_compact_prompt_value(item) for item in value[:_PROMPT_LIST_LIMIT]]
        if len(value) > _PROMPT_LIST_LIMIT:
            compacted.append({"truncated_count": len(value) - _PROMPT_LIST_LIMIT})
        return compacted
    if isinstance(value, dict):
        return {str(key): _compact_prompt_value(item) for key, item in value.items()}
    return value


def _prompt_json(value: Any) -> str:
    return json.dumps(_compact_prompt_value(value), indent=2, default=str)


def _crop_receipt_region(image: Image.Image) -> Image.Image:
    grayscale = ImageOps.grayscale(image)
    mask = grayscale.point(lambda pixel: 255 if pixel >= _RECEIPT_CROP_THRESHOLD else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return image
    left, top, right, bottom = bbox
    width, height = image.size
    bbox_width = right - left
    bbox_height = bottom - top
    image_area = width * height
    bbox_area = bbox_width * bbox_height
    if bbox_area < image_area * 0.05 or bbox_area > image_area * 0.96:
        return image

    pad_x = int(bbox_width * _RECEIPT_CROP_PADDING_RATIO)
    pad_y = int(bbox_height * _RECEIPT_CROP_PADDING_RATIO)
    crop_box = (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(width, right + pad_x),
        min(height, bottom + pad_y),
    )
    return image.crop(crop_box)


def _build_review_image_content(stored_path: Path) -> ImageContent | None:
    try:
        with Image.open(stored_path) as raw_image:
            image = ImageOps.exif_transpose(raw_image).convert("RGB")
    except Exception:
        return None

    image = _crop_receipt_region(image)
    width, height = image.size
    largest_dimension = max(width, height)
    if largest_dimension > _IMAGE_REVIEW_MAX_DIMENSION:
        ratio = _IMAGE_REVIEW_MAX_DIMENSION / largest_dimension
        image = image.resize((int(width * ratio), int(height * ratio)), Image.Resampling.LANCZOS)

    data = b""
    for quality in (92, 88, 84, 80, 76):
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True)
        data = buffer.getvalue()
        if len(data) <= _IMAGE_REVIEW_MAX_BYTES:
            break

    while len(data) > _IMAGE_REVIEW_MAX_BYTES and max(image.size) > _IMAGE_REVIEW_MIN_DIMENSION:
        next_size = (int(image.size[0] * 0.85), int(image.size[1] * 0.85))
        image = image.resize(next_size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=82, optimize=True)
        data = buffer.getvalue()

    if not data:
        return None
    encoded = base64.b64encode(data).decode("ascii")
    return ImageContent.from_base64(encoded, media_type="image/jpeg")


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
    include_image: bool = False,
) -> list[MessageInput]:
    prompt_parts = [
        "Review this uploaded household finance document using your assigned Agent Hub prompts.",
        "",
        "Document metadata:",
        _prompt_json(payload),
        "",
        "Deterministic reviewer baseline:",
        _prompt_json(baseline_review),
    ]
    if household_context:
        prompt_parts.extend(
            [
                "",
                "Current canonical household context:",
                _prompt_json(household_context),
            ]
        )
    if prior_review:
        prompt_parts.extend(
            [
                "",
                "Prior review attempt:",
                _prompt_json(prior_review),
            ]
        )
    if reconciliation_summary:
        prompt_parts.extend(
            [
                "",
                "Post-apply reconciliation issues from prior attempt:",
                _prompt_json(reconciliation_summary),
            ]
        )
    prompt_parts.extend(
        [
            "",
            "Own full intake outcome, not just classification.",
            "Read upload. infer all accounts, balances, transactions, and useful facts. reconcile against household context. use related evidence examples when format drift exists, but do not copy stale values. save strong identity hints. run an internal self-check. ask the user only if ambiguity remains real after all of that.",
            "For receipts, extract itemized purchases when visible. Put them under structured_data.transactions[].line_items with description, amount, quantity when known, and keep the transaction total separate.",
            "For receipt line_items, do not guess. Include only items whose description and amount are directly readable. Do not invent rows to make totals match.",
            "When itemizing receipts, set review_checks.itemization with line_item_count, declared_items_sold when visible, line_item_total, subtotal, tax, total, reconciles, and itemization_incomplete_reason when any expected line cannot be read.",
            "",
            "Use extracted text to improve or correct the baseline review.",
        ]
    )
    if include_image:
        prompt_parts.extend(
            [
                "",
                "Image review mode:",
                "The receipt image is attached. Use image pixels as source of truth; OCR text is only a rough aid.",
                "If the image is not legible enough for accurate item rows, leave line_items empty or partial only for readable rows and explain why in review_checks.itemization_incomplete_reason.",
            ]
        )
    if extracted_text:
        prompt_parts.extend(["", "Extracted text preview:", extracted_text[:12000]])
    else:
        prompt_parts.extend(["", "Extracted text preview:", "[none]"])
    prompt = "\n".join(prompt_parts)
    if include_image:
        image_content = _build_review_image_content(stored_path)
        if image_content is not None:
            return [MessageInput(role="user", content=[TextContent(text=prompt), image_content])]
    return [MessageInput(role="user", content=prompt)]


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
