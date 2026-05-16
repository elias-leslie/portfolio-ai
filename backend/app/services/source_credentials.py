"""Canonical source credential access for API providers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.credential_crypto import CredentialCipher

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

_ENCRYPTED_PREFIX = "enc:v1:"


def is_encrypted_credential_value(value: str | None) -> bool:
    """Return whether a stored source credential value is encrypted."""
    return bool(value and value.startswith(_ENCRYPTED_PREFIX))


def encrypt_source_credential_value(value: str, cipher: CredentialCipher | None = None) -> str:
    """Encrypt a source credential for storage in source_credentials.value."""
    active_cipher = cipher or CredentialCipher()
    return f"{_ENCRYPTED_PREFIX}{active_cipher.encrypt(value)}"


def decrypt_source_credential_value(value: str, cipher: CredentialCipher | None = None) -> str:
    """Decrypt a source credential if it uses the canonical encrypted prefix."""
    if not is_encrypted_credential_value(value):
        return value
    active_cipher = cipher or CredentialCipher()
    return active_cipher.decrypt(value.removeprefix(_ENCRYPTED_PREFIX))


def get_source_credential(
    storage: PortfolioStorage,
    source_id: str,
    field: str,
) -> str | None:
    """Read one credential from the canonical source_credentials table."""
    df = storage.query(
        "SELECT value FROM source_credentials WHERE source_id = ? AND field = ?",
        [source_id, field],
    )
    if df.is_empty():
        return None
    raw_value = df.to_dicts()[0].get("value")
    if raw_value is None:
        return None
    return decrypt_source_credential_value(str(raw_value))


def get_source_credentials(
    storage: PortfolioStorage,
    source_id: str,
) -> dict[str, str]:
    """Read all credentials for one source from source_credentials."""
    df = storage.query(
        "SELECT field, value FROM source_credentials WHERE source_id = ?",
        [source_id],
    )
    if df.is_empty():
        return {}
    credentials: dict[str, str] = {}
    for row in df.to_dicts():
        field = str(row.get("field") or "")
        raw_value = row.get("value")
        if not field or raw_value is None:
            continue
        credentials[field] = decrypt_source_credential_value(str(raw_value))
    return credentials


def set_source_credential(
    storage: PortfolioStorage,
    source_id: str,
    field: str,
    value: str,
    *,
    encrypt: bool = True,
) -> None:
    """Upsert one credential into source_credentials."""
    stored_value = encrypt_source_credential_value(value) if encrypt else value
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO source_credentials (source_id, field, value, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (source_id, field) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            [source_id, field, stored_value],
        )
        conn.commit()
