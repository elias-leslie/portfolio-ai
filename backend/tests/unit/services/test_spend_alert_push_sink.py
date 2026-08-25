"""The phone sink for card alerts is web push now, not the shared chat (D11)."""

from __future__ import annotations

from typing import Any

import pytest

from app.models.push_alerts import PushDelivery
from app.services.spend_alert_service import ALERT_CLICK_URL, SpendAlertService


class _FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def send(self, *, title: str, body: str, severity: str = "info") -> bool:
        self.sent.append({"title": title, "body": body, "severity": severity})
        return True


class _FakePush:
    def __init__(self, delivery: PushDelivery) -> None:
        self._delivery = delivery
        self.sent: list[dict[str, Any]] = []

    def send(self, **kwargs: Any) -> PushDelivery:
        self.sent.append(kwargs)
        return self._delivery


def _noop(*_args: Any, **_kwargs: Any) -> None:
    return None


def _no_refresh(_self: SpendAlertService) -> int:
    return 0


def _no_cards(_self: SpendAlertService) -> list[dict[str, Any]]:
    return []


def _month_to_date(_self: SpendAlertService) -> float:
    return 7000.0


def _cap(_self: SpendAlertService, _cards: list[dict[str, Any]]) -> float:
    return 6500.0


def _never_sent(_self: SpendAlertService, _marker_key: str) -> bool:
    return False


def _no_mark(_self: SpendAlertService, _marker_key: str) -> None:
    return None


@pytest.fixture
def dispatch(monkeypatch):
    """One over-cap pace alert, with every sink and store stubbed out."""

    def _run(delivery: PushDelivery) -> tuple[_FakePush, _FakeNotifier, list]:
        push = _FakePush(delivery)
        notifier = _FakeNotifier()
        stubs: dict[str, Any] = {
            "get_storage": object,
            "PushService": lambda: push,
            "get_notifier": lambda: notifier,
            "upsert_notification": _noop,
        }
        for name, replacement in stubs.items():
            monkeypatch.setattr(f"app.services.spend_alert_service.{name}", replacement)
        methods: dict[str, Any] = {
            "refresh_welcome_progress": _no_refresh,
            "_owned_cards": _no_cards,
            # $7,000 spent against a $6,500 cap: one critical over-cap alert.
            "_month_to_date_spend": _month_to_date,
            "_monthly_cap": _cap,
            "_already_sent": _never_sent,
            "_mark_sent": _no_mark,
        }
        for name, replacement in methods.items():
            monkeypatch.setattr(SpendAlertService, name, replacement)
        dispatched = SpendAlertService().evaluate_and_dispatch(trigger="test")
        return push, notifier, dispatched

    return _run


def test_a_delivered_push_is_the_whole_phone_sink(dispatch) -> None:
    """The shared chat does not also fire — that is what D11 replaced."""
    push, notifier, dispatched = dispatch(PushDelivery(delivered=2))

    assert [alert.kind for alert in dispatched] == ["spend_over_cap"]
    assert len(push.sent) == 1
    assert notifier.sent == []


def test_the_shared_chat_still_carries_an_alert_no_phone_took(dispatch) -> None:
    """Before any device registers there is nothing to push to.

    Swapping the transport must not open a window where a finding reaches
    nobody: the month can go over the cap the day before the first phone
    subscribes.
    """
    push, notifier, dispatched = dispatch(PushDelivery(delivered=0))

    assert len(push.sent) == 1
    assert [sent["title"] for sent in notifier.sent] == [
        alert.title for alert in dispatched
    ]


def test_the_push_carries_the_crossing_marker_as_its_tray_tag(dispatch) -> None:
    """A repeat of one crossing replaces its own notification, not stacks."""
    push, _notifier, dispatched = dispatch(PushDelivery(delivered=1))

    sent = push.sent[0]
    assert sent["tag"] == dispatched[0].marker_key
    assert sent["url"] == ALERT_CLICK_URL
    assert sent["severity"] == "critical"
