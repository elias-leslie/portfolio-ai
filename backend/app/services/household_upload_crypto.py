"""At-rest encryption for private household uploads (statements, receipts, evidence).

Stored format: ``UPLOAD_MAGIC`` followed by one Fernet token (AES-128-CBC +
HMAC-SHA256) over the original bytes. The Fernet key is derived from
``PORTFOLIO_SECRET_KEY`` with a dedicated domain label, so upload ciphertext
and source-credential ciphertext never share a key.

Files without the marker are legacy plaintext uploads and are returned as-is,
so existing stores keep working until ``scripts/encrypt_household_uploads.py``
rewrites them. New writes fail closed when no secret key is configured,
matching how encrypted credentials behave.
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings
from app.services.credential_crypto import SecretDecryptionError, SecretKeyUnavailableError

UPLOAD_MAGIC = b"PAIENC\x00household-upload\x00v1\n"
_KEY_DOMAIN = b"portfolio-ai/household-upload/v1\x00"


def _configured_secret() -> str:
    raw = settings.portfolio_secret_key
    value = raw.get_secret_value() if hasattr(raw, "get_secret_value") else raw
    return str(value or "").strip()


def _fernet(secret_key: str | None = None) -> Fernet:
    secret = (secret_key if secret_key is not None else _configured_secret()).strip()
    if not secret:
        raise SecretKeyUnavailableError(
            "PORTFOLIO_SECRET_KEY is required to store or read encrypted household uploads"
        )
    digest = hashlib.sha256(_KEY_DOMAIN + secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def is_encrypted_upload(data: bytes) -> bool:
    return data.startswith(UPLOAD_MAGIC)


def encrypt_upload_bytes(plaintext: bytes, *, secret_key: str | None = None) -> bytes:
    return UPLOAD_MAGIC + _fernet(secret_key).encrypt(plaintext)


def decrypt_upload_bytes(stored: bytes, *, secret_key: str | None = None) -> bytes:
    """Return plaintext; legacy unmarked files pass through unchanged."""
    if not is_encrypted_upload(stored):
        return stored
    try:
        return _fernet(secret_key).decrypt(stored[len(UPLOAD_MAGIC) :])
    except InvalidToken as exc:
        raise SecretDecryptionError(
            "Stored household upload cannot be decrypted with PORTFOLIO_SECRET_KEY"
        ) from exc


def upload_file_is_encrypted(path: Path) -> bool:
    with path.open("rb") as handle:
        return is_encrypted_upload(handle.read(len(UPLOAD_MAGIC)))


def read_upload_bytes(path: Path) -> bytes:
    """Read an upload's plaintext bytes, decrypting when it carries the marker."""
    return decrypt_upload_bytes(path.read_bytes())


def open_upload_text(
    path: Path, *, encoding: str = "utf-8", errors: str = "strict", newline: str | None = None
) -> io.TextIOWrapper:
    """Text handle over an upload's plaintext (decrypted in memory, never on disk)."""
    return io.TextIOWrapper(
        io.BytesIO(read_upload_bytes(path)), encoding=encoding, errors=errors, newline=newline
    )


def write_private_file_atomic(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` via an fsynced 0600 temp file and atomic rename."""
    temporary_path = path.with_name(f"{path.name}.tmp")
    file_descriptor = os.open(temporary_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
        path.chmod(0o600)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def write_encrypted_upload(path: Path, plaintext: bytes) -> None:
    """Encrypt and atomically store an upload; refuses to write without a key."""
    ciphertext = encrypt_upload_bytes(plaintext)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    write_private_file_atomic(path, ciphertext)
