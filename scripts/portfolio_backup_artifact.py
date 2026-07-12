#!/usr/bin/env python3
"""Create, verify, and safely unpack complete Portfolio AI backup artifacts."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import tarfile
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import BinaryIO

SCHEMA_VERSION = 1
MANIFEST_NAME = "manifest.json"
DATABASE_ARCHIVE_PATH = "database.dump"
UPLOADS_PREFIX = "uploads"
_COPY_BUFFER_BYTES = 1024 * 1024
_MAX_MANIFEST_BYTES = 1024 * 1024
_POSTGRES_CUSTOM_MAGIC = b"PGDMP"


class ArtifactError(RuntimeError):
    """Raised when a backup artifact is incomplete or unsafe."""


def _sha256_stream(stream: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(_COPY_BUFFER_BYTES):
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def _sha256_file(path: Path) -> tuple[str, int]:
    with path.open("rb") as stream:
        return _sha256_stream(stream)


def _safe_storage_key(value: str) -> str:
    pure = PurePosixPath(value)
    if (
        not value
        or pure.is_absolute()
        or value != pure.as_posix()
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise ArtifactError(f"Unsafe upload storage key: {value!r}")
    return value


def _upload_files(upload_root: Path) -> Iterable[tuple[str, Path]]:
    if not upload_root.exists():
        return
    if not upload_root.is_dir() or upload_root.is_symlink():
        raise ArtifactError(f"Upload root is not a real directory: {upload_root}")
    for path in sorted(upload_root.rglob("*")):
        if path.is_symlink():
            raise ArtifactError(f"Refusing to archive upload symlink: {path}")
        if not path.is_file():
            continue
        key = PurePosixPath(path.relative_to(upload_root)).as_posix()
        yield _safe_storage_key(key), path


def _normalized_tar_info(
    name: str,
    *,
    size: int,
    created_at: int,
    mode: int = 0o600,
) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mode = mode
    info.mtime = created_at
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def create_artifact(
    *,
    database_dump: Path,
    upload_root: Path,
    output: Path,
    deployment_mode: str,
    database_name: str,
) -> dict[str, object]:
    """Build one atomic, checksummed archive containing the DB and uploads."""
    if not database_dump.is_file() or database_dump.is_symlink():
        raise ArtifactError(f"Database dump is missing or unsafe: {database_dump}")
    with database_dump.open("rb") as stream:
        if stream.read(len(_POSTGRES_CUSTOM_MAGIC)) != _POSTGRES_CUSTOM_MAGIC:
            raise ArtifactError("Database payload is not a PostgreSQL custom-format dump")
    created = datetime.now(UTC)
    created_epoch = int(created.timestamp())
    db_sha, db_size = _sha256_file(database_dump)
    upload_rows: list[dict[str, object]] = []
    upload_paths: list[tuple[str, Path]] = []
    for key, path in _upload_files(upload_root):
        sha256, size = _sha256_file(path)
        upload_rows.append({"storage_key": key, "size_bytes": size, "sha256": sha256})
        upload_paths.append((key, path))

    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "application": "portfolio-ai",
        "created_at": created.isoformat(),
        "deployment_mode": deployment_mode,
        "database": {
            "name": database_name,
            "format": "postgresql-custom",
            "archive_path": DATABASE_ARCHIVE_PATH,
            "size_bytes": db_size,
            "sha256": db_sha,
        },
        "uploads": {
            "archive_prefix": f"{UPLOADS_PREFIX}/",
            "file_count": len(upload_rows),
            "total_size_bytes": sum(int(row["size_bytes"]) for row in upload_rows),
            "files": upload_rows,
        },
    }
    manifest_bytes = (
        json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    )

    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    previous_umask = os.umask(0o077)
    try:
        with tarfile.open(temporary, mode="w:gz", compresslevel=6) as archive:
            archive.addfile(
                _normalized_tar_info(
                    MANIFEST_NAME,
                    size=len(manifest_bytes),
                    created_at=created_epoch,
                ),
                io.BytesIO(manifest_bytes),
            )
            with database_dump.open("rb") as stream:
                archive.addfile(
                    _normalized_tar_info(
                        DATABASE_ARCHIVE_PATH,
                        size=db_size,
                        created_at=created_epoch,
                    ),
                    stream,
                )
            for key, path in upload_paths:
                size = path.stat().st_size
                with path.open("rb") as stream:
                    archive.addfile(
                        _normalized_tar_info(
                            f"{UPLOADS_PREFIX}/{key}",
                            size=size,
                            created_at=created_epoch,
                        ),
                        stream,
                    )
        temporary.chmod(0o600)
        verify_artifact(temporary)
        temporary.replace(output)
        output.chmod(0o600)
        directory_fd = os.open(output.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        os.umask(previous_umask)
        temporary.unlink(missing_ok=True)
    return manifest


def _validated_member_name(member: tarfile.TarInfo) -> str:
    pure = PurePosixPath(member.name)
    normalized = pure.as_posix()
    if (
        pure.is_absolute()
        or normalized != member.name
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise ArtifactError(f"Unsafe archive member: {member.name!r}")
    if not member.isfile() and not member.isdir():
        raise ArtifactError(f"Unsupported archive member type: {member.name!r}")
    if normalized not in {MANIFEST_NAME, DATABASE_ARCHIVE_PATH} and not normalized.startswith(
        f"{UPLOADS_PREFIX}/"
    ):
        raise ArtifactError(f"Unexpected archive member: {member.name!r}")
    return normalized


def _manifest_from_archive(archive: tarfile.TarFile) -> dict[str, object]:
    try:
        member = archive.getmember(MANIFEST_NAME)
    except KeyError as exc:
        raise ArtifactError("Backup artifact has no manifest") from exc
    if not member.isfile() or member.size > _MAX_MANIFEST_BYTES:
        raise ArtifactError("Backup manifest is invalid or too large")
    stream = archive.extractfile(member)
    if stream is None:
        raise ArtifactError("Backup manifest could not be read")
    try:
        manifest = json.loads(stream.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactError("Backup manifest is not valid JSON") from exc
    if not isinstance(manifest, dict):
        raise ArtifactError("Backup manifest must be a JSON object")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ArtifactError(
            f"Unsupported backup schema version: {manifest.get('schema_version')!r}"
        )
    if manifest.get("application") != "portfolio-ai":
        raise ArtifactError("Backup artifact is not for Portfolio AI")
    return manifest


def _checked_payload(
    archive: tarfile.TarFile,
    *,
    member_name: str,
    expected_sha256: object,
    expected_size: object,
) -> None:
    try:
        member = archive.getmember(member_name)
    except KeyError as exc:
        raise ArtifactError(f"Backup payload is missing: {member_name}") from exc
    if not member.isfile():
        raise ArtifactError(f"Backup payload is not a regular file: {member_name}")
    stream = archive.extractfile(member)
    if stream is None:
        raise ArtifactError(f"Backup payload could not be read: {member_name}")
    actual_sha256, actual_size = _sha256_stream(stream)
    if expected_size != actual_size or expected_sha256 != actual_sha256:
        raise ArtifactError(f"Backup payload checksum mismatch: {member_name}")


def verify_artifact(path: Path) -> dict[str, object]:
    """Validate structure, types, declared counts, sizes, and SHA-256 hashes."""
    if not path.is_file() or path.is_symlink():
        raise ArtifactError(f"Backup artifact is missing or unsafe: {path}")
    try:
        with tarfile.open(path, mode="r:*") as archive:
            seen: set[str] = set()
            for member in archive.getmembers():
                name = _validated_member_name(member)
                if name in seen:
                    raise ArtifactError(f"Duplicate archive member: {name}")
                seen.add(name)
            manifest = _manifest_from_archive(archive)
            database = manifest.get("database")
            uploads = manifest.get("uploads")
            if not isinstance(database, dict) or not isinstance(uploads, dict):
                raise ArtifactError("Backup manifest is missing payload metadata")
            if database.get("format") != "postgresql-custom":
                raise ArtifactError("Backup database format is unsupported")
            if database.get("archive_path") != DATABASE_ARCHIVE_PATH:
                raise ArtifactError("Backup database archive path is invalid")
            database_stream = archive.extractfile(DATABASE_ARCHIVE_PATH)
            if (
                database_stream is None
                or database_stream.read(len(_POSTGRES_CUSTOM_MAGIC))
                != _POSTGRES_CUSTOM_MAGIC
            ):
                raise ArtifactError(
                    "Database payload is not a PostgreSQL custom-format dump"
                )
            _checked_payload(
                archive,
                member_name=DATABASE_ARCHIVE_PATH,
                expected_sha256=database.get("sha256"),
                expected_size=database.get("size_bytes"),
            )

            file_rows = uploads.get("files")
            if not isinstance(file_rows, list):
                raise ArtifactError("Backup upload manifest is invalid")
            expected_upload_members: set[str] = set()
            total_size = 0
            for row in file_rows:
                if not isinstance(row, dict):
                    raise ArtifactError("Backup upload entry is invalid")
                key = _safe_storage_key(str(row.get("storage_key") or ""))
                member_name = f"{UPLOADS_PREFIX}/{key}"
                if member_name in expected_upload_members:
                    raise ArtifactError(f"Duplicate upload storage key: {key}")
                expected_upload_members.add(member_name)
                _checked_payload(
                    archive,
                    member_name=member_name,
                    expected_sha256=row.get("sha256"),
                    expected_size=row.get("size_bytes"),
                )
                if not isinstance(row.get("size_bytes"), int):
                    raise ArtifactError(f"Invalid upload size for: {key}")
                total_size += int(row["size_bytes"])
            actual_upload_members = {
                name
                for name in seen
                if name.startswith(f"{UPLOADS_PREFIX}/")
                and archive.getmember(name).isfile()
            }
            if expected_upload_members != actual_upload_members:
                raise ArtifactError("Backup upload payload does not match its manifest")
            if uploads.get("file_count") != len(file_rows):
                raise ArtifactError("Backup upload file count does not match its manifest")
            if uploads.get("total_size_bytes") != total_size:
                raise ArtifactError("Backup upload byte count does not match its manifest")
            return manifest
    except (tarfile.TarError, OSError) as exc:
        if isinstance(exc, ArtifactError):
            raise
        raise ArtifactError(f"Backup artifact could not be read: {exc}") from exc


def extract_database(*, artifact: Path, output: Path) -> None:
    """Verify and extract the PostgreSQL custom dump with private permissions."""
    verify_artifact(artifact)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tarfile.open(artifact, mode="r:*") as archive:
        stream = archive.extractfile(DATABASE_ARCHIVE_PATH)
        if stream is None:
            raise ArtifactError("Backup database payload could not be read")
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "wb") as destination:
            shutil.copyfileobj(stream, destination, _COPY_BUFFER_BYTES)
            destination.flush()
            os.fsync(destination.fileno())
    output.chmod(0o600)


def _extract_uploads(*, artifact: Path, target: Path) -> None:
    manifest = verify_artifact(artifact)
    uploads = manifest["uploads"]
    if not isinstance(uploads, dict) or not isinstance(uploads.get("files"), list):
        raise ArtifactError("Backup upload manifest is invalid")
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    target.chmod(0o700)
    with tarfile.open(artifact, mode="r:*") as archive:
        for row in uploads["files"]:
            if not isinstance(row, dict):
                raise ArtifactError("Backup upload entry is invalid")
            key = _safe_storage_key(str(row.get("storage_key") or ""))
            destination = target.joinpath(*PurePosixPath(key).parts)
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            destination.parent.chmod(0o700)
            stream = archive.extractfile(f"{UPLOADS_PREFIX}/{key}")
            if stream is None:
                raise ArtifactError(f"Backup upload could not be read: {key}")
            descriptor = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(descriptor, "wb") as output:
                shutil.copyfileobj(stream, output, _COPY_BUFFER_BYTES)
                output.flush()
                os.fsync(output.fileno())
            destination.chmod(0o600)


def restore_uploads(*, artifact: Path, target: Path) -> None:
    """Atomically replace an upload directory from a verified artifact."""
    target_parent = target.parent
    target_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    staging = target_parent / f".{target.name}.restore-{uuid.uuid4().hex}"
    try:
        _extract_uploads(artifact=artifact, target=staging)
        install_staged_uploads(source=staging, target=target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def install_staged_uploads(*, source: Path, target: Path) -> None:
    """Atomically install an already-extracted upload tree on one filesystem."""
    if source.is_symlink() or not source.is_dir():
        raise ArtifactError(f"Staged upload directory is unsafe: {source}")
    target_parent = target.parent
    target_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    target_parent.chmod(0o700)
    if source.parent.resolve() != target_parent.resolve():
        raise ArtifactError("Staged uploads must share the restore target filesystem")
    for path in source.rglob("*"):
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise ArtifactError(f"Staged upload entry is unsafe: {path}")
        path.chmod(0o700 if path.is_dir() else 0o600)
    source.chmod(0o700)

    previous = target_parent / f".{target.name}.previous-{uuid.uuid4().hex}"
    if target.exists():
        if target.is_symlink() or not target.is_dir():
            raise ArtifactError(f"Upload restore target is unsafe: {target}")
        target.rename(previous)
    try:
        source.rename(target)
    except BaseException:
        if previous.exists() and not target.exists():
            previous.rename(target)
        raise
    if previous.exists():
        shutil.rmtree(previous)
    directory_fd = os.open(target_parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a complete backup artifact")
    create.add_argument("--database-dump", type=Path, required=True)
    create.add_argument("--upload-root", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--deployment-mode", choices=("native", "compose"), required=True)
    create.add_argument("--database-name", required=True)

    verify = subparsers.add_parser("verify", help="Verify manifest and every payload checksum")
    verify.add_argument("--artifact", type=Path, required=True)
    verify.add_argument("--json", action="store_true")

    extract_db = subparsers.add_parser("extract-database", help="Extract the PostgreSQL dump")
    extract_db.add_argument("--artifact", type=Path, required=True)
    extract_db.add_argument("--output", type=Path, required=True)

    restore = subparsers.add_parser("restore-uploads", help="Atomically restore private uploads")
    restore.add_argument("--artifact", type=Path, required=True)
    restore.add_argument("--target", type=Path, required=True)
    install = subparsers.add_parser(
        "install-staged-uploads",
        help="Atomically install a pre-staged private-upload directory",
    )
    install.add_argument("--source", type=Path, required=True)
    install.add_argument("--target", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "create":
            manifest = create_artifact(
                database_dump=args.database_dump,
                upload_root=args.upload_root,
                output=args.output,
                deployment_mode=args.deployment_mode,
                database_name=args.database_name,
            )
            print(json.dumps(manifest, sort_keys=True))
        elif args.command == "verify":
            manifest = verify_artifact(args.artifact)
            if args.json:
                print(json.dumps(manifest, sort_keys=True))
            else:
                uploads = manifest["uploads"]
                assert isinstance(uploads, dict)
                print(
                    "Backup verified: "
                    f"database + {uploads.get('file_count', 0)} upload file(s)"
                )
        elif args.command == "extract-database":
            extract_database(artifact=args.artifact, output=args.output)
        elif args.command == "restore-uploads":
            restore_uploads(artifact=args.artifact, target=args.target)
        elif args.command == "install-staged-uploads":
            install_staged_uploads(source=args.source, target=args.target)
    except ArtifactError as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
