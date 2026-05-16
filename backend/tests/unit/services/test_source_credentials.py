from __future__ import annotations

from app.services.credential_crypto import CredentialCipher
from app.services.source_credentials import (
    decrypt_source_credential_value,
    encrypt_source_credential_value,
    is_encrypted_credential_value,
)


def test_source_credential_encryption_round_trips_without_plaintext() -> None:
    cipher = CredentialCipher("test-secret")
    stored = encrypt_source_credential_value("plaid-secret-value", cipher)

    assert is_encrypted_credential_value(stored)
    assert "plaid-secret-value" not in stored
    assert decrypt_source_credential_value(stored, cipher) == "plaid-secret-value"


def test_plain_source_credential_values_still_read_as_plaintext() -> None:
    assert decrypt_source_credential_value("existing-plain-value") == "existing-plain-value"
