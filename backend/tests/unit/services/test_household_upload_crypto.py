"""Household uploads are encrypted at rest and read back as plaintext."""

from __future__ import annotations

import hashlib
import importlib.util
import stat
from pathlib import Path

import pytest

from app.services import household_upload_crypto as crypto
from app.services._household_document_pipeline_db import save_upload_to_disk
from app.services._household_document_text import _extract_text
from app.services.credential_crypto import SecretDecryptionError, SecretKeyUnavailableError

CSV = b"Date,Description,Amount\n2026-01-02,Test Grocer,-12.34\n"


@pytest.fixture(autouse=True)
def fixed_key(monkeypatch):
    monkeypatch.setattr(crypto, "_configured_secret", lambda: "unit-test-upload-key")


def test_round_trip_marks_ciphertext_and_hides_plaintext():
    stored = crypto.encrypt_upload_bytes(CSV)
    assert crypto.is_encrypted_upload(stored)
    assert b"Test Grocer" not in stored
    assert crypto.decrypt_upload_bytes(stored) == CSV


def test_upload_key_is_domain_separated_from_credentials():
    from app.services.credential_crypto import CredentialCipher

    token = crypto.encrypt_upload_bytes(b"secret")[len(crypto.UPLOAD_MAGIC) :]
    with pytest.raises(SecretDecryptionError):
        CredentialCipher("unit-test-upload-key").decrypt(token.decode("ascii"))


def test_legacy_plaintext_reads_unchanged(tmp_path: Path):
    legacy = tmp_path / "legacy.csv"
    legacy.write_bytes(CSV)
    assert crypto.read_upload_bytes(legacy) == CSV
    assert not crypto.upload_file_is_encrypted(legacy)


def test_saved_upload_is_encrypted_private_and_digest_stable(tmp_path: Path):
    digest = hashlib.sha256(CSV).hexdigest()
    path = save_upload_to_disk(
        CSV, document_id="doc-1", filename="Statement.CSV", upload_dir=tmp_path / "uploads"
    )
    assert path.name == "doc-1.csv"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    raw = path.read_bytes()
    assert crypto.is_encrypted_upload(raw) and b"Test Grocer" not in raw
    assert hashlib.sha256(crypto.read_upload_bytes(path)).hexdigest() == digest
    assert not list(path.parent.glob("*.tmp"))


def test_extraction_reads_plaintext_from_encrypted_upload(tmp_path: Path):
    path = save_upload_to_disk(CSV, document_id="doc-2", filename="a.csv", upload_dir=tmp_path)
    assert "Test Grocer" in (_extract_text(path, "text/csv") or "")
    with crypto.open_upload_text(path, encoding="utf-8-sig", newline="") as handle:
        assert handle.read().splitlines()[0] == "Date,Description,Amount"


def test_missing_key_refuses_to_store(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(crypto, "_configured_secret", lambda: "")
    with pytest.raises(SecretKeyUnavailableError):
        save_upload_to_disk(CSV, document_id="doc-3", filename="a.csv", upload_dir=tmp_path)
    assert not list(tmp_path.iterdir())


def test_wrong_key_fails_loudly():
    stored = crypto.encrypt_upload_bytes(CSV)
    with pytest.raises(SecretDecryptionError):
        crypto.decrypt_upload_bytes(stored, secret_key="a-different-key")


def _load_script():
    script = Path(__file__).resolve().parents[3] / "scripts" / "encrypt_household_uploads.py"
    spec = importlib.util.spec_from_file_location("encrypt_household_uploads", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_script_is_idempotent_and_preserves_content(tmp_path: Path):
    script = _load_script()
    (tmp_path / "captures").mkdir()
    legacy = tmp_path / "captures" / "c1.jpg"
    legacy.write_bytes(b"\xff\xd8\xffplain-jpeg")
    legacy.chmod(0o600)
    already = save_upload_to_disk(CSV, document_id="d1", filename="a.csv", upload_dir=tmp_path)
    (tmp_path / "inflight.pdf.tmp").write_bytes(b"partial")

    assert script.encrypt_upload_tree(tmp_path, dry_run=True)["encrypted"] == 1
    assert not crypto.upload_file_is_encrypted(legacy)

    counts = script.encrypt_upload_tree(tmp_path)
    assert counts == {"encrypted": 1, "already_encrypted": 1, "skipped": 1}
    assert crypto.upload_file_is_encrypted(legacy)
    assert crypto.read_upload_bytes(legacy) == b"\xff\xd8\xffplain-jpeg"
    assert stat.S_IMODE(legacy.stat().st_mode) == 0o600
    assert crypto.read_upload_bytes(already) == CSV

    assert script.encrypt_upload_tree(tmp_path)["encrypted"] == 0
