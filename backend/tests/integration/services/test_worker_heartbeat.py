"""Database contract tests for the persisted worker heartbeat."""

from __future__ import annotations

from app.services.worker_heartbeat import (
    WORKER_SERVICE_NAME,
    WorkerHeartbeatPublisher,
    read_worker_heartbeat,
)
from app.storage import PortfolioStorage, get_storage


def test_worker_heartbeat_round_trips_through_shared_database() -> None:
    storage: PortfolioStorage = get_storage()
    publisher = WorkerHeartbeatPublisher(storage, status_provider=lambda: "healthy")

    publisher.publish()

    heartbeat = read_worker_heartbeat(storage)
    assert heartbeat.active is True
    assert heartbeat.instance_id == publisher.instance_id
    assert heartbeat.pid is not None
    rows = storage.query(
        "SELECT COUNT(*) AS count FROM service_heartbeats WHERE service_name = ?",
        [WORKER_SERVICE_NAME],
    )
    assert rows.to_dicts()[0]["count"] == 1
