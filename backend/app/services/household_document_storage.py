"""Portable, root-confined paths for private household document uploads."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path, PurePosixPath

STORAGE_KEY_FIELD = "storage_key"
LEGACY_STORED_PATH_FIELD = "stored_path"
_UPLOAD_ROOT_MARKER = "household_uploads"


def household_upload_root(service: object | None = None) -> Path:
    """Return a service override when present, otherwise configured storage."""
    upload_root = getattr(service, "_upload_root", None)
    if callable(upload_root):
        resolved = upload_root()
        if isinstance(resolved, Path):
            return resolved
    from app.config import settings  # noqa: PLC0415 - avoids config import cycles

    return settings.household_upload_dir


def upload_storage_key(stored_path: Path, upload_root: Path) -> str:
    """Return a portable key for a file contained by ``upload_root``."""
    root = upload_root.resolve()
    try:
        relative = stored_path.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError("Household upload path must stay within the upload root") from exc
    if not relative.parts:
        raise ValueError("Household upload storage key must identify a file")
    return PurePosixPath(relative).as_posix()


def document_storage_reference(metadata: Mapping[str, object] | None) -> str | None:
    """Read a new storage key, falling back to the legacy path field."""
    if not isinstance(metadata, Mapping):
        return None
    for field in (STORAGE_KEY_FIELD, LEGACY_STORED_PATH_FIELD):
        value = metadata.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _legacy_relative_path(reference: Path) -> Path:
    """Rebase an absolute legacy path after moving the upload volume."""
    parts = reference.parts
    marker_indexes = [
        index for index, part in enumerate(parts) if part == _UPLOAD_ROOT_MARKER
    ]
    if marker_indexes:
        suffix = parts[marker_indexes[-1] + 1 :]
        if suffix:
            return Path(*suffix)
    return Path(reference.name)


def resolve_upload_path(
    reference: str | None,
    upload_root: Path,
    *,
    require_exists: bool = True,
    allow_legacy_absolute: bool = False,
) -> Path | None:
    """Resolve a storage key or legacy absolute path inside ``upload_root``.

    Relative keys are always confined to the configured private upload root.
    If an installation moved (for example, native to Docker), the suffix after
    ``household_uploads`` is rebased into the current root. Read-only callers
    can explicitly allow an existing legacy absolute path during migration;
    destructive callers should retain the secure default.
    """
    if not isinstance(reference, str) or not reference.strip():
        return None
    root = upload_root.resolve()
    raw_path = Path(reference.strip())
    if raw_path.is_absolute():
        try:
            relative = raw_path.resolve(strict=False).relative_to(root)
        except ValueError:
            if allow_legacy_absolute and raw_path.is_file():
                return raw_path.resolve()
            relative = _legacy_relative_path(raw_path)
    else:
        relative = raw_path
    if not relative.parts:
        return None
    try:
        candidate = (root / relative).resolve(strict=False)
        candidate.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None
    if require_exists and not candidate.is_file():
        return None
    return candidate


def resolve_document_upload(
    metadata: Mapping[str, object] | None,
    upload_root: Path,
    *,
    require_exists: bool = True,
    allow_legacy_absolute: bool = False,
) -> Path | None:
    """Resolve the upload described by document metadata."""
    return resolve_upload_path(
        document_storage_reference(metadata),
        upload_root,
        require_exists=require_exists,
        allow_legacy_absolute=allow_legacy_absolute,
    )
