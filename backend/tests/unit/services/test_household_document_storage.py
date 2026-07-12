"""Private on-disk storage controls for household uploads."""

from __future__ import annotations

import stat
from pathlib import Path

from app.services._household_document_pipeline_db import save_upload_to_disk
from app.services.household_document_storage import (
    document_storage_reference,
    resolve_document_upload,
    resolve_upload_path,
    upload_storage_key,
)


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


def test_storage_key_survives_upload_root_move(tmp_path: Path) -> None:
    old_root = tmp_path / "old" / "household_uploads"
    old_root.mkdir(parents=True)
    old_path = old_root / "nested" / "statement.pdf"
    old_path.parent.mkdir()
    old_path.write_bytes(b"statement")

    storage_key = upload_storage_key(old_path, old_root)
    assert storage_key == "nested/statement.pdf"

    new_root = tmp_path / "new" / "household_uploads"
    new_path = new_root / storage_key
    new_path.parent.mkdir(parents=True)
    new_path.write_bytes(b"statement")

    assert resolve_document_upload({"storage_key": storage_key}, new_root) == new_path
    assert document_storage_reference(
        {"storage_key": storage_key, "stored_path": "/stale/path"}
    ) == storage_key


def test_legacy_absolute_path_rebases_after_volume_move(tmp_path: Path) -> None:
    new_root = tmp_path / "current" / "household_uploads"
    current = new_root / "nested" / "statement.pdf"
    current.parent.mkdir(parents=True)
    current.write_bytes(b"statement")

    legacy = "/app/data/household_uploads/nested/statement.pdf"
    assert resolve_document_upload({"stored_path": legacy}, new_root) == current


def test_relative_storage_key_cannot_escape_upload_root(tmp_path: Path) -> None:
    upload_root = tmp_path / "household_uploads"
    upload_root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")

    assert resolve_upload_path("../secret.txt", upload_root) is None
    assert resolve_upload_path("/etc/passwd", upload_root) is None


def test_existing_legacy_absolute_path_requires_explicit_read_compatibility(
    tmp_path: Path,
) -> None:
    upload_root = tmp_path / "configured" / "household_uploads"
    upload_root.mkdir(parents=True)
    legacy = tmp_path / "legacy-statement.pdf"
    legacy.write_bytes(b"statement")

    assert resolve_upload_path(str(legacy), upload_root) is None
    assert resolve_document_upload({"stored_path": str(legacy)}, upload_root) is None
    assert (
        resolve_upload_path(
            str(legacy),
            upload_root,
            allow_legacy_absolute=True,
        )
        == legacy
    )
