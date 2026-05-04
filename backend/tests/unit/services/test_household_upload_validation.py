"""Tests for household evidence upload validation."""

from __future__ import annotations

import pytest

from app.services.household_upload_validation import (
    MAX_HOUSEHOLD_UPLOAD_REQUEST_BYTES,
    HouseholdUploadValidationError,
    read_household_upload_limited,
    validate_household_upload_metadata,
)


class _UploadStub:
    def __init__(
        self,
        *,
        chunks: list[bytes] | None = None,
        filename: str = "statement.pdf",
        content_type: str | None = "application/pdf",
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        self._chunks = list(chunks or [])

    async def read(self, _size: int = -1) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


def test_validate_household_upload_metadata_accepts_supported_financial_exports() -> None:
    validate_household_upload_metadata(
        _UploadStub(filename="transactions.qfx", content_type="application/octet-stream")
    )
    validate_household_upload_metadata(_UploadStub(filename="receipt.heic", content_type="image/heic"))


def test_validate_household_upload_metadata_rejects_unsupported_extension() -> None:
    with pytest.raises(HouseholdUploadValidationError) as exc:
        validate_household_upload_metadata(
            _UploadStub(filename="archive.zip", content_type="application/zip")
        )

    assert exc.value.status_code == 415
    assert "Supported extensions" in exc.value.detail


def test_validate_household_upload_metadata_rejects_unsupported_media_type() -> None:
    with pytest.raises(HouseholdUploadValidationError) as exc:
        validate_household_upload_metadata(
            _UploadStub(filename="statement.pdf", content_type="application/x-msdownload")
        )

    assert exc.value.status_code == 415
    assert "Unsupported household evidence media type" in exc.value.detail


def test_validate_household_upload_metadata_rejects_large_content_length() -> None:
    with pytest.raises(HouseholdUploadValidationError) as exc:
        validate_household_upload_metadata(
            _UploadStub(),
            content_length=str(MAX_HOUSEHOLD_UPLOAD_REQUEST_BYTES + 1),
        )

    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_read_household_upload_limited_joins_chunks_under_limit() -> None:
    content = await read_household_upload_limited(
        _UploadStub(chunks=[b"abc", b"def"]),
        max_bytes=6,
        chunk_bytes=3,
    )

    assert content == b"abcdef"


@pytest.mark.asyncio
async def test_read_household_upload_limited_rejects_oversized_body() -> None:
    with pytest.raises(HouseholdUploadValidationError) as exc:
        await read_household_upload_limited(
            _UploadStub(chunks=[b"abc", b"def"]),
            max_bytes=5,
            chunk_bytes=3,
        )

    assert exc.value.status_code == 413
