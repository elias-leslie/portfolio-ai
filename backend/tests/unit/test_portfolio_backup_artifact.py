"""Complete backup artifact integrity and safe-restore tests."""

from __future__ import annotations

import importlib.util
import io
import os
import stat
import subprocess
import tarfile
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_PATH = REPO_ROOT / "scripts" / "portfolio_backup_artifact.py"


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("portfolio_backup_artifact", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture_artifact(tmp_path: Path) -> tuple[ModuleType, Path, Path]:
    tool = _load_tool()
    database_dump = tmp_path / "database.dump"
    database_dump.write_bytes(b"PGDMP-test-database")
    uploads = tmp_path / "source_uploads"
    (uploads / "nested").mkdir(parents=True)
    (uploads / "statement.pdf").write_bytes(b"statement")
    (uploads / "nested" / "receipt.csv").write_bytes(b"merchant,total\nShop,12\n")
    artifact = tmp_path / "portfolio_ai_complete_test.tar.gz"
    tool.create_artifact(
        database_dump=database_dump,
        upload_root=uploads,
        output=artifact,
        deployment_mode="native",
        database_name="portfolio_ai_test",
    )
    return tool, artifact, uploads


def _run_compose_restore_with_fake_docker(
    *,
    tmp_path: Path,
    artifact: Path,
    fail_phase: str,
) -> tuple[subprocess.CompletedProcess[str], str]:
    fake_bin = tmp_path / f"fake-docker-{fail_phase}"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(
        """#!/usr/bin/env bash
set -eu
printf '%s\n' "$*" >> "$FAKE_DOCKER_LOG"
if [ "$1" = inspect ]; then
  printf 'true\n'
  exit 0
fi
if [ "$1" != compose ]; then exit 64; fi
shift
if [ "${1:-}" = -f ]; then shift 2; fi
command="${1:-}"
shift || true
case "$command" in
  ps)
    service="${3:-unknown}"
    printf 'container-%s\n' "$service"
    ;;
  stop)
    ;;
  exec)
    if [ "${1:-}" = -T ]; then shift; fi
    service="${1:-}"
    shift || true
    if [ "${1:-}" = printenv ]; then
      if [ "${2:-}" = POSTGRES_USER ]; then printf 'portfolio\n'; else printf 'portfolio_ai\n'; fi
    elif [ "${1:-}" = pg_restore ]; then
      cat >/dev/null
      if [ "$FAKE_RESTORE_FAILURE" = database ]; then exit 42; fi
    fi
    ;;
  run)
    cat >/dev/null
    count=0
    if [ -f "$FAKE_DOCKER_RUN_COUNT" ]; then count="$(cat "$FAKE_DOCKER_RUN_COUNT")"; fi
    count=$((count + 1))
    printf '%s' "$count" > "$FAKE_DOCKER_RUN_COUNT"
    if [ "$FAKE_RESTORE_FAILURE" = upload ] && [ "$count" -eq 1 ]; then exit 43; fi
    if [ "$FAKE_RESTORE_FAILURE" = apply ] && [ "$count" -eq 2 ]; then exit 44; fi
    ;;
  up)
    ;;
  *)
    exit 65
    ;;
esac
"""
    )
    docker.chmod(0o755)
    log = tmp_path / f"docker-{fail_phase}.log"
    run_count = tmp_path / f"docker-{fail_phase}.count"
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["FAKE_DOCKER_LOG"] = str(log)
    environment["FAKE_DOCKER_RUN_COUNT"] = str(run_count)
    environment["FAKE_RESTORE_FAILURE"] = fail_phase
    environment.pop("PORTFOLIO_DB_URL", None)
    environment.pop("PORTFOLIO_AI_DB_URL", None)

    result = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "portfolio-restore.sh"),
            str(artifact),
            "--confirm",
            "--mode",
            "compose",
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    return result, log.read_text()


def test_complete_artifact_verifies_and_restores_uploads_privately(
    tmp_path: Path,
) -> None:
    tool, artifact, uploads = _fixture_artifact(tmp_path)

    manifest = tool.verify_artifact(artifact)
    upload_manifest = manifest["uploads"]
    assert isinstance(upload_manifest, dict)
    assert upload_manifest["file_count"] == 2
    assert stat.S_IMODE(artifact.stat().st_mode) == 0o600

    restored = tmp_path / "restored_uploads"
    restored.mkdir()
    (restored / "stale.txt").write_text("remove me")
    tool.restore_uploads(artifact=artifact, target=restored)

    assert not (restored / "stale.txt").exists()
    assert (restored / "statement.pdf").read_bytes() == (
        uploads / "statement.pdf"
    ).read_bytes()
    assert (restored / "nested" / "receipt.csv").read_bytes() == (
        uploads / "nested" / "receipt.csv"
    ).read_bytes()
    assert stat.S_IMODE(restored.stat().st_mode) == 0o700
    assert stat.S_IMODE((restored / "statement.pdf").stat().st_mode) == 0o600
    assert stat.S_IMODE((restored / "nested").stat().st_mode) == 0o700


def test_artifact_verification_rejects_checksum_mismatch(tmp_path: Path) -> None:
    tool, artifact, _uploads = _fixture_artifact(tmp_path)
    tampered = tmp_path / "tampered.tar.gz"

    with (
        tarfile.open(artifact, "r:gz") as source,
        tarfile.open(tampered, "w:gz") as destination,
    ):
        for member in source.getmembers():
            stream = source.extractfile(member) if member.isfile() else None
            payload = stream.read() if stream is not None else b""
            if member.name == "uploads/statement.pdf":
                payload = b"tampered!"
                member.size = len(payload)
            destination.addfile(member, io.BytesIO(payload) if member.isfile() else None)

    with pytest.raises(tool.ArtifactError, match="checksum mismatch"):
        tool.verify_artifact(tampered)


def test_artifact_verification_rejects_path_traversal(tmp_path: Path) -> None:
    tool = _load_tool()
    malicious = tmp_path / "malicious.tar.gz"
    with tarfile.open(malicious, "w:gz") as archive:
        member = tarfile.TarInfo("uploads/../escape.txt")
        member.size = 6
        archive.addfile(member, io.BytesIO(b"escape"))

    with pytest.raises(tool.ArtifactError, match="Unsafe archive member"):
        tool.verify_artifact(malicious)


def test_artifact_creation_rejects_upload_symlinks(tmp_path: Path) -> None:
    tool = _load_tool()
    database_dump = tmp_path / "database.dump"
    database_dump.write_bytes(b"PGDMP-test-database")
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("private")
    (uploads / "linked.txt").symlink_to(outside)

    with pytest.raises(tool.ArtifactError, match="symlink"):
        tool.create_artifact(
            database_dump=database_dump,
            upload_root=uploads,
            output=tmp_path / "backup.tar.gz",
            deployment_mode="native",
            database_name="portfolio_ai_test",
        )


def test_restore_script_verifies_before_requiring_destructive_confirmation(
    tmp_path: Path,
) -> None:
    _tool, artifact, _uploads = _fixture_artifact(tmp_path)

    result = subprocess.run(
        [str(REPO_ROOT / "scripts" / "portfolio-restore.sh"), str(artifact)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "Restore is destructive" in result.stderr


def test_compose_upload_stage_failure_never_restarts_services(tmp_path: Path) -> None:
    _tool, artifact, _uploads = _fixture_artifact(tmp_path)

    result, docker_log = _run_compose_restore_with_fake_docker(
        tmp_path=tmp_path,
        artifact=artifact,
        fail_phase="upload",
    )

    assert result.returncode != 0
    assert "services remain stopped" in result.stderr
    assert "pg_restore" not in docker_log
    assert " up -d " not in f" {docker_log} "


def test_compose_database_failure_keeps_staged_uploads_and_never_restarts(
    tmp_path: Path,
) -> None:
    _tool, artifact, _uploads = _fixture_artifact(tmp_path)

    result, docker_log = _run_compose_restore_with_fake_docker(
        tmp_path=tmp_path,
        artifact=artifact,
        fail_phase="database",
    )

    assert result.returncode != 0
    assert "services remain stopped" in result.stderr
    assert "run --rm -T --no-deps" in docker_log
    assert docker_log.index("run --rm -T --no-deps") < docker_log.index("pg_restore")
    assert " up -d " not in f" {docker_log} "


def test_compose_upload_apply_failure_after_database_never_restarts(
    tmp_path: Path,
) -> None:
    _tool, artifact, _uploads = _fixture_artifact(tmp_path)

    result, docker_log = _run_compose_restore_with_fake_docker(
        tmp_path=tmp_path,
        artifact=artifact,
        fail_phase="apply",
    )

    assert result.returncode != 0
    assert "services remain stopped" in result.stderr
    assert "pg_restore" in docker_log
    assert docker_log.count("run --rm -T --no-deps") == 2
    assert " up -d " not in f" {docker_log} "


def test_compose_restarts_services_only_after_database_and_uploads_succeed(
    tmp_path: Path,
) -> None:
    _tool, artifact, _uploads = _fixture_artifact(tmp_path)

    result, docker_log = _run_compose_restore_with_fake_docker(
        tmp_path=tmp_path,
        artifact=artifact,
        fail_phase="none",
    )

    assert result.returncode == 0, result.stderr
    assert docker_log.count("run --rm -T --no-deps") == 2
    assert "pg_restore" in docker_log
    assert "up -d portfolio-web portfolio-worker portfolio-api" in docker_log
    assert docker_log.rindex("run --rm -T --no-deps") < docker_log.index("up -d")


def test_native_backup_entry_point_builds_complete_artifact(tmp_path: Path) -> None:
    tool = _load_tool()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_pg_dump = fake_bin / "pg_dump"
    fake_pg_dump.write_text(
        """#!/usr/bin/env bash
set -eu
output=''
while [ "$#" -gt 0 ]; do
  if [ "$1" = '--file' ]; then output="$2"; shift 2; else shift; fi
done
printf 'PGDMP-fake-database' > "$output"
"""
    )
    fake_pg_dump.chmod(0o755)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "statement.pdf").write_bytes(b"statement")
    artifact = tmp_path / "complete.tar.gz"
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["PORTFOLIO_DB_URL"] = (
        "postgresql://backup:secret@localhost:5432/portfolio_drill"
    )

    result = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "portfolio-backup.sh"),
            "--mode",
            "native",
            "--upload-dir",
            str(uploads),
            "--output",
            str(artifact),
            "--no-prune",
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    manifest = tool.verify_artifact(artifact)
    assert manifest["database"]["name"] == "portfolio_drill"
    assert manifest["uploads"]["file_count"] == 1


def test_backup_entry_points_are_executable_and_document_complete_payload() -> None:
    for relative in (
        "scripts/portfolio-backup.sh",
        "scripts/portfolio-restore.sh",
        "scripts/postgres-backup.sh",
        "scripts/backup-restore-drill.sh",
    ):
        path = REPO_ROOT / relative
        assert path.stat().st_mode & stat.S_IXUSR

    backup_source = (REPO_ROOT / "scripts" / "portfolio-backup.sh").read_text()
    restore_source = (REPO_ROOT / "scripts" / "portfolio-restore.sh").read_text()
    assert "--database-dump" in backup_source
    assert "--upload-root" in backup_source
    assert "portfolio_compose pause" in backup_source
    assert "portfolio_compose unpause" in backup_source
    assert "--single-transaction" in restore_source
    assert "restore-uploads" in restore_source
