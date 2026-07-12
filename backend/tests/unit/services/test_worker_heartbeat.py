"""Tests for cross-process worker heartbeat publication and interpretation."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Event
from uuid import uuid4

import polars as pl

from app.services.worker_heartbeat import (
    HEARTBEAT_STALE_AFTER_SECONDS,
    WORKER_SERVICE_NAME,
    WorkerHeartbeatPublisher,
    read_worker_heartbeat,
)


class FakeStorage:
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self.rows = rows or []
        self.executions: list[tuple[str, list[object]]] = []
        self.publish_count = 0
        self.refreshed = Event()
        self.query_error: Exception | None = None

    def execute(self, sql: str, params: list[object]) -> None:
        self.executions.append((sql, params))
        self.publish_count += 1
        if self.publish_count >= 2:
            self.refreshed.set()

    def query(self, _sql: str, _params: list[object]) -> pl.DataFrame:
        if self.query_error is not None:
            raise self.query_error
        return pl.DataFrame(self.rows, strict=False) if self.rows else pl.DataFrame()


def _heartbeat_row(age_seconds: float) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "instance_id": uuid4(),
        "hostname": "worker-host",
        "pid": 4321,
        "reported_status": "healthy",
        "started_at": now,
        "last_seen_at": now,
        "age_seconds": age_seconds,
    }


def test_publisher_writes_immediately_and_refreshes_periodically() -> None:
    storage = FakeStorage()
    publisher = WorkerHeartbeatPublisher(
        storage,
        interval_seconds=0.01,
        status_provider=lambda: "healthy",
    )

    publisher.start()
    try:
        assert storage.refreshed.wait(0.5)
    finally:
        publisher.stop()

    assert storage.publish_count >= 2
    sql, params = storage.executions[0]
    assert "ON CONFLICT (service_name) DO UPDATE" in sql
    assert params[0] == WORKER_SERVICE_NAME
    assert params[1] == str(publisher.instance_id)
    assert params[3] > 0
    assert params[4] == "healthy"


def test_current_heartbeat_is_the_only_active_state() -> None:
    storage = FakeStorage([_heartbeat_row(age_seconds=3.0)])

    heartbeat = read_worker_heartbeat(storage)

    assert heartbeat.active is True
    assert heartbeat.state == "current"
    assert heartbeat.age_seconds == 3.0
    assert heartbeat.pid == 4321


def test_stale_heartbeat_is_not_active() -> None:
    age = HEARTBEAT_STALE_AFTER_SECONDS + 1
    storage = FakeStorage([_heartbeat_row(age_seconds=age)])

    heartbeat = read_worker_heartbeat(storage)

    assert heartbeat.active is False
    assert heartbeat.state == "stale"
    assert f"{age:.0f}s old" in heartbeat.message


def test_fresh_heartbeat_requires_healthy_hatchet_state() -> None:
    for reported_status, expected_state in (
        ("starting", "starting"),
        ("unhealthy", "unhealthy"),
    ):
        row = _heartbeat_row(age_seconds=1.0)
        row["reported_status"] = reported_status

        heartbeat = read_worker_heartbeat(FakeStorage([row]))

        assert heartbeat.active is False
        assert heartbeat.state == expected_state


def test_missing_and_unavailable_heartbeats_fail_closed() -> None:
    missing = read_worker_heartbeat(FakeStorage())
    unavailable_storage = FakeStorage()
    unavailable_storage.query_error = RuntimeError("database unavailable")

    unavailable = read_worker_heartbeat(unavailable_storage)

    assert (missing.active, missing.state) == (False, "missing")
    assert (unavailable.active, unavailable.state) == (False, "unavailable")
