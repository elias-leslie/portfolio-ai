"""Private on-disk storage controls for household uploads."""

from __future__ import annotations

import stat
from pathlib import Path

from app.services._household_document_pipeline_db import save_upload_to_disk


def test_save_upload_to_disk_uses_private_permissions_and_atomic_name(
    tmp_path: Path,
) -> None:
    upload_dir = tmp_path / "household_uploads"

    stored_path = save_upload_to_disk(
        b"private financial data",
        document_id="document-1",
        filename="statement.PDF",
        upload_dir=upload_dir,
    )

    assert stored_path == upload_dir / "document-1.pdf"
    assert stored_path.read_bytes() == b"private financial data"
    assert stat.S_IMODE(upload_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(stored_path.stat().st_mode) == 0o600
    assert list(upload_dir.glob("*.tmp")) == []
