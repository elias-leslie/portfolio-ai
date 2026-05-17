from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import plaid_service
from app.services.plaid_service import PlaidConfigurationError, PlaidService


def _service() -> PlaidService:
    service = PlaidService.__new__(PlaidService)
    service.storage = object()
    service.cipher = SimpleNamespace(available=True)
    return service


def test_configure_keeps_saved_credentials_when_secret_inputs_are_blank(monkeypatch) -> None:
    service = _service()
    saved_fields: list[tuple[str, str, bool]] = []

    monkeypatch.setattr(service, "_ensure_source_registry", lambda: None)
    monkeypatch.setattr(service, "get_status", lambda: {"configured": True})
    monkeypatch.setattr(
        plaid_service,
        "get_source_credentials",
        lambda _storage, _source_id: {
            "client_id": "existing-client",
            "secret": "existing-secret",
        },
    )

    def fake_set_source_credential(
        storage: object,
        source_id: str,
        field: str,
        value: str,
        *,
        encrypt: bool = True,
    ) -> None:
        saved_fields.append((field, value, encrypt))

    monkeypatch.setattr(plaid_service, "set_source_credential", fake_set_source_credential)

    result = service.configure(
        client_id="",
        secret=None,
        environment="production",
        products=["transactions"],
        country_codes=["US"],
        redirect_uri="https://port.summitflow.dev/money",
    )

    assert result == {"configured": True}
    assert ("client_id", "existing-client", True) not in saved_fields
    assert ("secret", "existing-secret", True) not in saved_fields
    assert ("environment", "production", False) in saved_fields
    assert ("redirect_uri", "https://port.summitflow.dev/money", False) in saved_fields


def test_configure_still_requires_credentials_for_first_setup(monkeypatch) -> None:
    service = _service()
    monkeypatch.setattr(
        plaid_service,
        "get_source_credentials",
        lambda _storage, _source_id: {},
    )

    with pytest.raises(PlaidConfigurationError) as exc_info:
        service.configure(
            client_id=None,
            secret=None,
            environment="production",
            products=["transactions"],
            country_codes=["US"],
            redirect_uri=None,
        )

    assert str(exc_info.value) == "Plaid client_id and secret are required."
