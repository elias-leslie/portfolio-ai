"""Small encryption helper for secrets persisted in PostgreSQL."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class SecretKeyUnavailableError(RuntimeError):
    """Raised when encrypted credentials cannot be used without a secret key."""


class SecretDecryptionError(RuntimeError):
    """Raised when stored ciphertext cannot be decrypted with the configured key."""


class CredentialCipher:
    """Encrypt and decrypt credential values with the app secret key."""

    def __init__(self, secret_key: str | None = None) -> None:
        raw_key = secret_key if secret_key is not None else settings.portfolio_secret_key
        self._raw_key = raw_key.strip()

    @property
    def available(self) -> bool:
        return bool(self._raw_key)

    def _fernet(self) -> Fernet:
        if not self._raw_key:
            raise SecretKeyUnavailableError("PORTFOLIO_SECRET_KEY is required for encrypted credentials")
        digest = hashlib.sha256(self._raw_key.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, value: str) -> str:
        return self._fernet().encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise SecretDecryptionError(
                "Stored credential cannot be decrypted with PORTFOLIO_SECRET_KEY"
            ) from exc
