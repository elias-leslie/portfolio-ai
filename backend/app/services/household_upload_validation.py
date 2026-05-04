"""Validation and bounded reads for household evidence uploads."""

from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

MAX_HOUSEHOLD_UPLOAD_BYTES = 50 * 1024 * 1024
_MAX_MULTIPART_OVERHEAD_BYTES = 1024 * 1024
MAX_HOUSEHOLD_UPLOAD_REQUEST_BYTES = (
    MAX_HOUSEHOLD_UPLOAD_BYTES + _MAX_MULTIPART_OVERHEAD_BYTES
)
HOUSEHOLD_UPLOAD_READ_CHUNK_BYTES = 1024 * 1024

HOUSEHOLD_UPLOAD_ALLOWED_EXTENSIONS = frozenset(
    {
        ".bmp",
        ".csv",
        ".heic",
        ".htm",
        ".html",
        ".jpeg",
        ".jpg",
        ".json",
        ".ofx",
        ".pdf",
        ".png",
        ".qfx",
        ".txt",
        ".webp",
        ".xml",
    }
)

_HOUSEHOLD_UPLOAD_ALLOWED_CONTENT_TYPES = frozenset(
    {
        "application/json",
        "application/octet-stream",
        "application/ofx",
        "application/pdf",
        "application/vnd.intu.qfx",
        "application/vnd.ms-excel",
        "application/x-ofx",
        "application/xml",
    }
)


class HouseholdUploadValidationError(ValueError):
    """Upload validation failure with an HTTP-compatible status code."""

    def __init__(self, detail: str, *, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _normalized_content_type(content_type: str | None) -> str:
    return (content_type or "").split(";", maxsplit=1)[0].strip().lower()


def _content_type_is_allowed(content_type: str | None) -> bool:
    normalized = _normalized_content_type(content_type)
    return (
        not normalized
        or normalized in _HOUSEHOLD_UPLOAD_ALLOWED_CONTENT_TYPES
        or normalized.startswith("image/")
        or normalized.startswith("text/")
    )


def _parse_content_length(content_length: str | None) -> int | None:
    if content_length is None:
        return None
    try:
        parsed = int(content_length)
    except ValueError as exc:
        raise HouseholdUploadValidationError(
            "Invalid Content-Length header.",
            status_code=400,
        ) from exc
    return max(parsed, 0)


def validate_household_upload_metadata(
    upload: UploadFile,
    *,
    content_length: str | None = None,
) -> None:
    """Reject unsupported household evidence before reading the upload body."""
    filename = (upload.filename or "").strip()
    suffix = Path(filename).suffix.lower()
    if not filename or suffix not in HOUSEHOLD_UPLOAD_ALLOWED_EXTENSIONS:
        supported = ", ".join(sorted(HOUSEHOLD_UPLOAD_ALLOWED_EXTENSIONS))
        raise HouseholdUploadValidationError(
            f"Unsupported household evidence file type. Supported extensions: {supported}.",
            status_code=415,
        )

    if not _content_type_is_allowed(upload.content_type):
        raise HouseholdUploadValidationError(
            f"Unsupported household evidence media type: {upload.content_type}.",
            status_code=415,
        )

    parsed_content_length = _parse_content_length(content_length)
    if (
        parsed_content_length is not None
        and parsed_content_length > MAX_HOUSEHOLD_UPLOAD_REQUEST_BYTES
    ):
        max_mb = MAX_HOUSEHOLD_UPLOAD_BYTES // (1024 * 1024)
        raise HouseholdUploadValidationError(
            f"Household evidence uploads must be {max_mb} MB or smaller.",
            status_code=413,
        )


async def read_household_upload_limited(
    upload: UploadFile,
    *,
    max_bytes: int = MAX_HOUSEHOLD_UPLOAD_BYTES,
    chunk_bytes: int = HOUSEHOLD_UPLOAD_READ_CHUNK_BYTES,
) -> bytes:
    """Read an upload without allowing an unbounded in-memory body."""
    content = bytearray()
    while True:
        chunk = await upload.read(chunk_bytes)
        if not chunk:
            return bytes(content)
        content.extend(chunk)
        if len(content) > max_bytes:
            max_mb = max_bytes // (1024 * 1024)
            raise HouseholdUploadValidationError(
                f"Household evidence uploads must be {max_mb} MB or smaller.",
                status_code=413,
            )
