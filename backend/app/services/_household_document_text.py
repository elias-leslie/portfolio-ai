"""Text and OCR extraction helpers for household document review."""

from __future__ import annotations

import csv
import io
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageOps
from pypdf import PdfReader

from app.logging_config import get_logger

logger = get_logger(__name__)

_PDF_PAGE_LIMIT = 6
_MAX_EXTRACTED_TEXT_CHARS = 30000

# Signal terms that indicate the PDF has usable financial content (skip OCR if present).
_FINANCIAL_SIGNAL_TERMS = (
    "$", "order total", "total", "subtotal", "amount due",
    "item", "qty", "payment", "transaction",
)


# ---------------------------------------------------------------------------
# OCR helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _build_image_ocr_engine():  # -> RapidOCR
    from rapidocr_onnxruntime import RapidOCR  # noqa: PLC0415

    return RapidOCR()


def _prepare_and_ocr(image: Image.Image) -> str | None:
    """Grayscale + autocontrast + optional upscale, then OCR. Returns text or None."""
    grayscale = ImageOps.grayscale(image)
    contrast = ImageOps.autocontrast(grayscale)
    w, h = contrast.size
    if max(w, h) < 2200:
        contrast = contrast.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
    result, _ = _build_image_ocr_engine()(np.array(contrast))
    if not result:
        return None
    text = "\n".join(
        line[1]
        for line in result
        if isinstance(line, (list, tuple)) and len(line) > 1 and isinstance(line[1], str)
    ).strip()
    return text[:_MAX_EXTRACTED_TEXT_CHARS] if text else None


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _merge_text_fragments(*fragments: str) -> str:
    """Merge text fragments, deduplicating lines while preserving order."""
    seen: set[str] = set()
    lines: list[str] = []
    for fragment in fragments:
        for line in fragment.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            key = re.sub(r"\s+", " ", cleaned).lower()
            if key not in seen:
                seen.add(key)
                lines.append(cleaned)
    return "\n".join(lines).strip()


def _render_pdf_pages_to_png(stored_path: Path, *, scale: float, max_pages: int) -> list[bytes]:
    png_pages: list[bytes] = []
    pdf = pdfium.PdfDocument(str(stored_path))
    try:
        for page_index in range(min(len(pdf), max_pages)):
            page = pdf.get_page(page_index)
            bitmap = None
            try:
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil()
                with io.BytesIO() as buffer:
                    image.save(buffer, format="PNG")
                    png_pages.append(buffer.getvalue())
            finally:
                if bitmap is not None:
                    bitmap.close()
                page.close()
    finally:
        pdf.close()
    return png_pages


def _extract_pdf_image_text(stored_path: Path) -> str | None:
    try:
        png_pages = _render_pdf_pages_to_png(stored_path, scale=2, max_pages=_PDF_PAGE_LIMIT)
    except Exception as exc:
        logger.warning("household_pdf_ocr_failed", path=str(stored_path), error=str(exc))
        return None

    ocr_chunks: list[str] = []
    for png_bytes in png_pages:
        page_text = _prepare_and_ocr(Image.open(io.BytesIO(png_bytes)))
        if page_text:
            ocr_chunks.append(page_text)
    merged = "\n\n".join(ocr_chunks).strip()
    return merged[:_MAX_EXTRACTED_TEXT_CHARS] if merged else None


def _extract_pdf_text(stored_path: Path) -> str | None:
    try:
        reader = PdfReader(str(stored_path))
        chunks: list[str] = []
        for page in reader.pages[:_PDF_PAGE_LIMIT]:
            text = page.extract_text() or ""
            if text.strip():
                chunks.append(text.strip())
        merged = "\n\n".join(chunks).strip()
        needs_ocr = not merged or len(merged) < 180 or not any(
            t in merged.lower() for t in _FINANCIAL_SIGNAL_TERMS
        )
        if needs_ocr:
            ocr_text = _extract_pdf_image_text(stored_path)
            if ocr_text:
                merged = _merge_text_fragments(merged, ocr_text)
        return merged[:_MAX_EXTRACTED_TEXT_CHARS] if merged else None
    except Exception as exc:
        logger.warning("household_pdf_extract_failed", path=str(stored_path), error=str(exc))
        return None


def _extract_image_text(stored_path: Path) -> str | None:
    try:
        return _prepare_and_ocr(Image.open(stored_path))
    except Exception as exc:
        logger.warning("household_image_ocr_failed", path=str(stored_path), error=str(exc))
        return None


def _extract_csv_text(stored_path: Path) -> str:
    with stored_path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.reader(handle)
        rows = [
            ", ".join(cell.strip() for cell in row[:32])
            for idx, row in enumerate(reader)
            if idx <= 20
        ]
    return "\n".join(rows)


def _extract_plain_text(stored_path: Path) -> str | None:
    text = stored_path.read_text(encoding="utf-8", errors="ignore")
    cleaned = text.strip()
    return cleaned[:12000] if cleaned else None


def _extract_financial_markup_text(stored_path: Path) -> str | None:
    text = _extract_plain_text(stored_path)
    if not text:
        return None
    normalized = re.sub(r">\s*<", ">\n<", text)
    normalized = re.sub(r"(?i)<(stmttrn|banktranlist|creditcardmsgsrsv1|ccstmttrnrs|invstmtmsgsrsv1|invtranlist)", r"\n<\1", normalized)
    return normalized[:12000]


def _extract_text(stored_path: Path, content_type: str | None) -> str | None:
    suffix = stored_path.suffix.lower()
    extracted: str | None = None

    if suffix == ".csv":
        extracted = _extract_csv_text(stored_path)
    elif suffix in {".ofx", ".qfx"}:
        extracted = _extract_financial_markup_text(stored_path)
    elif suffix == ".pdf" or content_type == "application/pdf":
        extracted = _extract_pdf_text(stored_path)
    elif (content_type and content_type.startswith("image/")) or suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        extracted = _extract_image_text(stored_path)
    elif suffix in {".txt", ".json", ".xml", ".html", ".htm"} or (
        content_type and (content_type.startswith("text/") or "xml" in content_type or "ofx" in content_type)
    ):
        extracted = _extract_plain_text(stored_path)

    return extracted
