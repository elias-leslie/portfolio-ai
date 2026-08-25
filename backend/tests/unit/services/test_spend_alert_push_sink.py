"""The phone sink for alerts is web push now, not the shared chat (D11).

Exercised through the card producer, which is a real caller of the dispatch the
plan kinds also use (§7 3.7) — the sink behaviour is shared, so testing it once
against a producer that actually builds alerts beats testing a stub.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.models.push_alerts import PushDelivery
from app.services._alert_dispatch import ALERT_CLICK_URL
from app.services.spend_alert_service import SpendAlertService


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


@pytest.fixture
def dispatch(monkeypatch):
    """One over-cap pace alert, with every sink and store stubbed out."""

    def _run(delivery: PushDelivery) -> tuple[_FakePush, _FakeNotifier, list]:
        push = _FakePush(delivery)
        notifier = _FakeNotifier()
        dispatch_stubs: dict[str, Any] = {
            "PushService": lambda: push,
            "get_notifier": lambda: notifier,
            "upsert_notification": _noop,
            "already_sent": lambda _key, **_kwargs: False,
            "mark_sent": _noop,
            "_StorageShim": object,
        }
        for name, replacement in dispatch_stubs.items():
            monkeypatch.setattr(f"app.services._alert_dispatch.{name}", replacement)
        monkeypatch.setattr(
            "app.services.spend_alert_service.get_storage", object
        )
        methods: dict[str, Any] = {
            "refresh_welcome_progress": _no_refresh,
            "_owned_cards": _no_cards,
            # $7,000 spent against a $6,500 cap: one critical over-cap alert.
            "_month_to_date_spend": _month_to_date,
            "_monthly_cap": _cap,
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


def test_a_pass_with_nothing_new_touches_no_table(monkeypatch) -> None:
    """Every alert already sent means no routine row and no notification write."""
    calls: list[str] = []
    monkeypatch.setattr(
        "app.services._alert_dispatch.already_sent", lambda _key, **_kw: True
    )
    monkeypatch.setattr(
        "app.services._alert_dispatch._ensure_routine_row",
        lambda *_a, **_k: calls.append("routine"),
    )
    monkeypatch.setattr(
        "app.services._alert_dispatch.upsert_notification",
        lambda *_a, **_k: calls.append("notification"),
    )

    from app.services._alert_dispatch import Alert, dispatch_alerts

    dispatched = dispatch_alerts(
        [Alert(kind="k", severity="info", title="t", body="b", marker_key="m")],
        routine_id="test-routine",
        routine_type="test",
        marker_prefix="test_sent",
        trigger="test",
    )

    assert dispatched == []
    assert calls == []


def test_the_synthetic_routine_row_exists_before_a_notification_needs_it(
    monkeypatch,
) -> None:
    """``jenny_notifications.routine_id`` is a foreign key into ``jenny_routines``.

    An alert producer never runs through the coordinator that creates that row,
    so without this every write raised a foreign-key violation that each caller
    swallowed as an error status — the card alerts wrote nothing and left no
    marker from the day they shipped.
    """
    order: list[str] = []
    monkeypatch.setattr(
        "app.services._alert_dispatch.already_sent", lambda _key, **_kw: False
    )
    monkeypatch.setattr(
        "app.services._alert_dispatch.mark_sent", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        "app.services._alert_dispatch._ensure_routine_row",
        lambda *_a, **_k: order.append("routine"),
    )
    monkeypatch.setattr(
        "app.services._alert_dispatch.upsert_notification",
        lambda *_a, **_k: order.append("notification"),
    )
    monkeypatch.setattr(
        "app.services._alert_dispatch.PushService",
        lambda: _FakePush(PushDelivery(delivered=1)),
    )
    monkeypatch.setattr("app.services._alert_dispatch._StorageShim", object)

    from app.services._alert_dispatch import Alert, dispatch_alerts

    dispatch_alerts(
        [Alert(kind="k", severity="info", title="t", body="b", marker_key="m")],
        routine_id="test-routine",
        routine_type="test",
        marker_prefix="test_sent",
        trigger="test",
    )

    assert order == ["routine", "notification"]


def test_two_alerts_of_one_kind_are_two_inbox_rows(monkeypatch) -> None:
    """The UI sink keeps one open notification per category.

    Three categories over their caps collapsed into a single row until the
    subject reached the category — the inbox showed whichever was written last.
    """
    categories: list[str] = []
    monkeypatch.setattr(
        "app.services._alert_dispatch.already_sent", lambda _key, **_kw: False
    )
    monkeypatch.setattr(
        "app.services._alert_dispatch.mark_sent", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        "app.services._alert_dispatch._ensure_routine_row", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        "app.services._alert_dispatch.upsert_notification",
        lambda *_a, **kwargs: categories.append(kwargs["category"]),
    )
    monkeypatch.setattr(
        "app.services._alert_dispatch.PushService",
        lambda: _FakePush(PushDelivery(delivered=1)),
    )
    monkeypatch.setattr("app.services._alert_dispatch._StorageShim", object)

    from app.services._alert_dispatch import Alert, dispatch_alerts

    dispatch_alerts(
        [
            Alert(
                kind="category_at_cap",
                severity="warning",
                title="Travel",
                body="b",
                marker_key="m1",
                subject="Travel",
            ),
            Alert(
                kind="category_at_cap",
                severity="warning",
                title="Retail",
                body="b",
                marker_key="m2",
                subject="Retail",
            ),
            Alert(
                kind="month_over_plan",
                severity="critical",
                title="August",
                body="b",
                marker_key="m3",
            ),
        ],
        routine_id="test-routine",
        routine_type="test",
        marker_prefix="test_sent",
        trigger="test",
        category_prefix="budget_",
    )

    assert categories == [
        "budget_category_at_cap:Travel",
        "budget_category_at_cap:Retail",
        # A month-wide finding has nothing to disambiguate, so it stays one row.
        "budget_month_over_plan",
    ]
