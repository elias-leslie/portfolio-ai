"""Web push transport for household alerts (plan §7 3.6, D11)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.models.push_alerts import PushSubscriptionInput
from app.services.push_service import PushService


class _Cursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._rows[0] if self._rows else None


class _Connection:
    """Routes SQL to canned rows by the table and verb it names."""

    def __init__(self, rows_for: dict[str, list[tuple[Any, ...]]]) -> None:
        self._rows_for = rows_for
        self.calls: list[tuple[str, Any]] = []
        self.commits = 0

    def __enter__(self) -> _Connection:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False

    def execute(self, sql: str, params: Any = None) -> _Cursor:
        self.calls.append((sql, params))
        for key, rows in self._rows_for.items():
            if key in sql:
                return _Cursor(rows)
        return _Cursor([])

    def commit(self) -> None:
        self.commits += 1


class _Storage:
    def __init__(self, connection: _Connection) -> None:
        self._connection = connection

    def connection(self) -> _Connection:
        return self._connection


def _service(monkeypatch, connection: _Connection) -> PushService:
    monkeypatch.setattr(
        "app.services.push_service.get_storage", lambda: _Storage(connection)
    )
    return PushService()


def _configure(monkeypatch, *, private: str = "priv", public: str = "pub") -> None:
    monkeypatch.setattr("app.config.settings.vapid_private_key", private)
    monkeypatch.setattr("app.config.settings.vapid_public_key", public)


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def _target_rows(*ids: str) -> list[tuple[Any, ...]]:
    return [(i, f"https://push.example/{i}", f"key-{i}", f"auth-{i}") for i in ids]


# -- configuration -----------------------------------------------------------


def test_push_is_disabled_until_both_vapid_keys_are_set(monkeypatch) -> None:
    """A public key with no private key cannot sign, so it is not configured."""
    _configure(monkeypatch, private="", public="pub")
    service = _service(monkeypatch, _Connection({}))

    assert service.is_configured() is False
    assert service.config().enabled is False


def test_unconfigured_send_is_a_no_op_not_a_failure(monkeypatch) -> None:
    """Nothing is dispatched and nothing is counted as failed."""
    _configure(monkeypatch, private="", public="")
    connection = _Connection({"FROM household_push_subscriptions": _target_rows("a")})
    service = _service(monkeypatch, connection)

    delivery = service.send(title="t", body="b")

    assert (delivery.delivered, delivery.failed, delivery.expired) == (0, 0, 0)
    assert connection.calls == []


# -- sending -----------------------------------------------------------------


def test_send_delivers_to_every_registered_device(monkeypatch) -> None:
    _configure(monkeypatch)
    connection = _Connection(
        {"SELECT id, endpoint": _target_rows("one", "two")}
    )
    service = _service(monkeypatch, connection)
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "app.services.push_service.webpush", lambda **kwargs: sent.append(kwargs) or _Response(201)
    )

    delivery = service.send(title="Over the cap", body="details", tag="marker")

    assert delivery.delivered == 2
    assert [call["subscription_info"]["endpoint"] for call in sent] == [
        "https://push.example/one",
        "https://push.example/two",
    ]
    assert sent[0]["subscription_info"]["keys"] == {
        "p256dh": "key-one",
        "auth": "auth-one",
    }


def test_each_send_gets_its_own_vapid_claims(monkeypatch) -> None:
    """pywebpush writes `aud` into the claims dict in place.

    A dict shared across devices would keep the first endpoint's audience, and
    every later push would be rejected by a push service it was not addressed
    to — a failure that only shows up once a second phone registers.
    """
    _configure(monkeypatch)
    connection = _Connection({"SELECT id, endpoint": _target_rows("one", "two")})
    service = _service(monkeypatch, connection)
    claims: list[dict[str, Any]] = []

    def _webpush(**kwargs: Any) -> _Response:
        seen = kwargs["vapid_claims"]
        claims.append(seen)
        seen["aud"] = kwargs["subscription_info"]["endpoint"]
        return _Response(201)

    monkeypatch.setattr("app.services.push_service.webpush", _webpush)
    service.send(title="t", body="b")

    assert claims[0] is not claims[1]
    assert "aud" not in claims[1] or claims[1]["aud"] != claims[0]["aud"]


def test_payload_carries_the_click_target_and_tag(monkeypatch) -> None:
    import json

    _configure(monkeypatch)
    connection = _Connection({"SELECT id, endpoint": _target_rows("one")})
    service = _service(monkeypatch, connection)
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "app.services.push_service.webpush", lambda **kwargs: sent.append(kwargs) or _Response(201)
    )

    service.send(
        title="Over the cap",
        body="details",
        severity="critical",
        url="/money?tab=spending",
        tag="spend_over_cap:2026-08",
    )

    payload = json.loads(sent[0]["data"])
    assert payload["url"] == "/money?tab=spending"
    assert payload["tag"] == "spend_over_cap:2026-08"
    assert payload["severity"] == "critical"


@pytest.mark.parametrize("status", [404, 410])
def test_a_gone_endpoint_is_deleted_not_retried_forever(monkeypatch, status) -> None:
    """The browser replaced this subscription; the row can never deliver again."""
    from pywebpush import WebPushException

    _configure(monkeypatch)
    connection = _Connection({"SELECT id, endpoint": _target_rows("stale")})
    service = _service(monkeypatch, connection)

    def _webpush(**_kwargs: Any) -> None:
        error = WebPushException("gone")
        error.response = _Response(status)
        raise error

    monkeypatch.setattr("app.services.push_service.webpush", _webpush)
    delivery = service.send(title="t", body="b")

    assert (delivery.expired, delivery.delivered, delivery.failed) == (1, 0, 0)
    assert any("DELETE FROM household_push_subscriptions" in sql for sql, _ in connection.calls)


def test_a_transient_failure_records_the_error_and_keeps_the_device(monkeypatch) -> None:
    from pywebpush import WebPushException

    _configure(monkeypatch)
    connection = _Connection({"SELECT id, endpoint": _target_rows("flaky")})
    service = _service(monkeypatch, connection)

    def _webpush(**_kwargs: Any) -> None:
        error = WebPushException("service unavailable")
        error.response = _Response(503)
        raise error

    monkeypatch.setattr("app.services.push_service.webpush", _webpush)
    delivery = service.send(title="t", body="b")

    assert (delivery.failed, delivery.expired) == (1, 0)
    assert not any("DELETE FROM" in sql for sql, _ in connection.calls)
    assert any("last_failure_at" in sql for sql, _ in connection.calls)


def test_one_dead_device_does_not_stop_the_others(monkeypatch) -> None:
    _configure(monkeypatch)
    connection = _Connection({"SELECT id, endpoint": _target_rows("bad", "good")})
    service = _service(monkeypatch, connection)

    def _webpush(**kwargs: Any) -> _Response:
        if kwargs["subscription_info"]["endpoint"].endswith("bad"):
            raise RuntimeError("socket exploded")
        return _Response(201)

    monkeypatch.setattr("app.services.push_service.webpush", _webpush)
    delivery = service.send(title="t", body="b")

    assert (delivery.delivered, delivery.failed) == (1, 1)


def test_send_can_be_routed_to_one_person(monkeypatch) -> None:
    """The routing the shared chat could not do: one adult, not both."""
    _configure(monkeypatch)
    connection = _Connection({"SELECT id, endpoint": _target_rows("mariana-phone")})
    service = _service(monkeypatch, connection)
    monkeypatch.setattr("app.services.push_service.webpush", lambda **_k: _Response(201))

    service.send(title="t", body="b", household_member_ids=["member-1"])

    select_sql, params = connection.calls[0]
    assert "household_member_id = ANY(%s)" in select_sql
    assert params == [["member-1"]]


# -- subscriptions -----------------------------------------------------------


def test_register_upserts_on_the_endpoint(monkeypatch) -> None:
    """Re-granting permission must not leave two rows pushing to one handset."""
    connection = _Connection(
        {
            "INSERT INTO household_push_subscriptions": [("row-1",)],
            "LEFT JOIN household_members": [
                (
                    "row-1",
                    "member-1",
                    "Elias",
                    "Pixel 7 Pro",
                    datetime(2026, 8, 25, tzinfo=UTC),
                    None,
                    None,
                    None,
                )
            ],
        }
    )
    service = _service(monkeypatch, connection)

    view = service.register(
        PushSubscriptionInput(
            endpoint="https://push.example/one",
            keys={"encryption_key": "k", "auth_secret": "a"},
            household_member_id="member-1",
            device_label="Pixel 7 Pro",
        )
    )

    insert_sql, params = connection.calls[0]
    assert "ON CONFLICT (endpoint) DO UPDATE" in insert_sql
    assert params[2:5] == ["https://push.example/one", "k", "a"]
    assert view.id == "row-1"
    assert view.member_name == "Elias"


def test_listing_devices_never_returns_the_endpoint(monkeypatch) -> None:
    """The endpoint is a bearer capability — holding it is permission to push."""
    connection = _Connection(
        {
            "LEFT JOIN household_members": [
                (
                    "row-1",
                    "member-1",
                    "Mariana",
                    "SM-S908U",
                    datetime(2026, 8, 25, tzinfo=UTC),
                    datetime(2026, 8, 25, tzinfo=UTC),
                    None,
                    None,
                )
            ]
        }
    )
    service = _service(monkeypatch, connection)

    [view] = service.list_subscriptions()

    assert "endpoint" not in view.model_dump()
    assert view.device_label == "SM-S908U"
    assert view.last_success_at == "2026-08-25T00:00:00+00:00"


def test_only_the_adults_are_offered_as_recipients(monkeypatch) -> None:
    """The girls capture receipts; a cap they cannot act on must not buzz them."""
    connection = _Connection(
        {"FROM household_members": [("m1", "Elias"), ("m2", "Mariana")]}
    )
    service = _service(monkeypatch, connection)

    recipients = service.recipients()

    sql, _ = connection.calls[0]
    assert "role IN ('primary', 'spouse')" in sql
    assert [r.name for r in recipients] == ["Elias", "Mariana"]
