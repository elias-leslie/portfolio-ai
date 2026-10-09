from __future__ import annotations

from app.services import source_credentials
from app.services.credential_crypto import CredentialCipher
from app.services.source_credentials import (
    decrypt_source_credential_value,
    encrypt_source_credential_value,
    is_encrypted_credential_value,
    plan_plaintext_reencryption,
)


def test_source_credential_encryption_round_trips_without_plaintext() -> None:
    cipher = CredentialCipher("test-secret")
    stored = encrypt_source_credential_value("plaid-secret-value", cipher)

    assert is_encrypted_credential_value(stored)
    assert "plaid-secret-value" not in stored
    assert decrypt_source_credential_value(stored, cipher) == "plaid-secret-value"


def test_plain_source_credential_values_still_read_as_plaintext() -> None:
    assert decrypt_source_credential_value("existing-plain-value") == "existing-plain-value"


class _RecordingLogger:
    def __init__(self) -> None:
        self.warnings: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **fields: object) -> None:
        self.warnings.append((event, fields))


def test_plaintext_secret_read_warns_without_logging_the_value(monkeypatch) -> None:
    recorder = _RecordingLogger()
    monkeypatch.setattr(source_credentials, "logger", recorder)

    value = decrypt_source_credential_value("legacy-api-key", source_id="finnhub", field="token")

    assert value == "legacy-api-key"
    assert recorder.warnings == [
        ("source_credential_plaintext_legacy_value", {"source_id": "finnhub", "field": "token"})
    ]
    assert "legacy-api-key" not in repr(recorder.warnings)


def test_plaintext_config_fields_and_encrypted_values_do_not_warn(monkeypatch) -> None:
    recorder = _RecordingLogger()
    monkeypatch.setattr(source_credentials, "logger", recorder)
    cipher = CredentialCipher("test-secret")

    decrypt_source_credential_value("production", source_id="plaid", field="environment")
    decrypt_source_credential_value(
        encrypt_source_credential_value("secret", cipher), cipher, source_id="plaid", field="secret"
    )

    assert recorder.warnings == []


def test_plan_plaintext_reencryption_is_idempotent_and_skips_config_fields() -> None:
    cipher = CredentialCipher("test-secret")
    already = encrypt_source_credential_value("kept", cipher)
    rows = [
        ("finnhub", "token", "plain-token"),
        ("plaid", "environment", "production"),
        ("plaid", "secret", already),
        ("newsapi", "apiKey", None),
    ]

    updates = plan_plaintext_reencryption(rows, cipher)

    assert [(source_id, field) for source_id, field, _ in updates] == [("finnhub", "token")]
    encrypted = updates[0][2]
    assert is_encrypted_credential_value(encrypted)
    assert decrypt_source_credential_value(encrypted, cipher) == "plain-token"
    assert plan_plaintext_reencryption([("finnhub", "token", encrypted)], cipher) == []
