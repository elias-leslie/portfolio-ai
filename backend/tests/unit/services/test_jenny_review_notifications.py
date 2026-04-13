"""Unit tests for Jenny notification lifecycle helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services._jenny_review_notifications import resolve_superseded_notifications


def test_resolve_superseded_notifications_closes_only_managed_stale_alerts() -> None:
    service = MagicMock()
    connection = service.storage.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = [
        ("note-exit", "position_exit"),
        ("note-thesis", "thesis_invalidation"),
        ("note-manual", "manual_followup"),
    ]

    resolve_superseded_notifications(service, "NVDA", active_categories=set())

    update_calls = [
        call
        for call in connection.execute.call_args_list
        if "UPDATE jenny_notifications" in call.args[0]
    ]

    assert [call.args[1] for call in update_calls] == [
        ["resolved", "note-exit"],
        ["resolved", "note-thesis"],
    ]
    connection.commit.assert_called_once()


def test_resolve_superseded_notifications_keeps_current_category_open() -> None:
    service = MagicMock()
    connection = service.storage.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = [
        ("note-trim", "position_trim"),
        ("note-review", "position_review"),
    ]

    resolve_superseded_notifications(service, "VTI", active_categories={"position_trim"})

    update_calls = [
        call
        for call in connection.execute.call_args_list
        if "UPDATE jenny_notifications" in call.args[0]
    ]

    assert [call.args[1] for call in update_calls] == [["resolved", "note-review"]]
    connection.commit.assert_called_once()


def test_resolve_superseded_notifications_manages_household_inbox_categories() -> None:
    service = MagicMock()
    connection = service.storage.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = [
        ("note-money", "household_inbox:refresh-cma"),
        ("note-manual", "manual_followup"),
    ]

    resolve_superseded_notifications(service, None, active_categories=set())

    update_calls = [
        call
        for call in connection.execute.call_args_list
        if "UPDATE jenny_notifications" in call.args[0]
    ]

    assert [call.args[1] for call in update_calls] == [["resolved", "note-money"]]
    connection.commit.assert_called_once()
