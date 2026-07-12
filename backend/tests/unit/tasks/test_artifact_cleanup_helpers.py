"""Backup-retention coverage for complete and legacy artifacts."""

from __future__ import annotations

import os
from pathlib import Path

from app.tasks.cleanup.artifact_cleanup_helpers import collect_backup_files


def test_collect_backup_files_includes_complete_artifacts_and_legacy_dumps(
    tmp_path: Path,
) -> None:
    complete = tmp_path / "portfolio_ai_complete_20260712T120000Z.tar.gz"
    legacy = tmp_path / "legacy.sql.gz"
    unrelated = tmp_path / "untrusted.tar.gz"
    complete.write_bytes(b"complete")
    legacy.write_bytes(b"legacy")
    unrelated.write_bytes(b"unrelated")
    os.utime(legacy, (1, 1))
    os.utime(complete, (2, 2))

    files = collect_backup_files(tmp_path)

    assert [row[0] for row in files] == [complete, legacy]

