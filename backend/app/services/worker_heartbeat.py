"""Persisted liveness for the Hatchet worker process.

The API and worker may run in separate containers or systemd services, so process
inspection cannot establish worker liveness. A small database heartbeat provides the
same truthful signal in both deployment modes.
"""

from __future__ import annotations

import os
import socket
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from threading import Event, Thread
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)

WORKER_SERVICE_NAME = "portfolio-hatchet-worker"
HEARTBEAT_INTERVAL_SECONDS = 10.0
HEARTBEAT_STALE_AFTER_SECONDS = 45.0

HeartbeatState = Literal[
    "current",
    "starting",
    "unhealthy",
    "stale",
    "missing",
    "unavailable",
]
WorkerReportedStatus = Literal["starting", "healthy", "unhealthy"]


@dataclass(frozen=True)
class WorkerHeartbeatSnapshot:
    """Latest persisted worker liveness observation."""

    state: HeartbeatState
    message: str
    instance_id: UUID | None = None
    hostname: str | None = None
    pid: int | None = None
    started_at: datetime | None = None
    last_seen_at: datetime | None = None
    age_seconds: float | None = None

    @property
    def active(self) -> bool:
        """Only a current heartbeat is evidence that the worker is active."""
        return self.state == "current"


class WorkerHeartbeatPublisher:
    """Publish worker liveness from a lightweight daemon thread."""

    def __init__(
        self,
        storage: PortfolioStorage,
        *,
        status_provider: Callable[[], WorkerReportedStatus],
        interval_seconds: float = HEARTBEAT_INTERVAL_SECONDS,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("Heartbeat interval must be positive")
        self._storage = storage
        self._interval_seconds = interval_seconds
        self._status_provider = status_provider
        self._instance_id = uuid4()
        self._hostname = socket.gethostname()
        self._pid = os.getpid()
        self._stop_event = Event()
        self._thread: Thread | None = None

    @property
    def instance_id(self) -> UUID:
        """Stable identifier for this worker process."""
        return self._instance_id

    def publish(self) -> None:
        """Atomically create or refresh this worker's heartbeat."""
        self._storage.execute(
            """
            INSERT INTO service_heartbeats (
                service_name, instance_id, hostname, pid, reported_status,
                started_at, last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (service_name) DO UPDATE SET
                instance_id = EXCLUDED.instance_id,
                hostname = EXCLUDED.hostname,
                pid = EXCLUDED.pid,
                reported_status = EXCLUDED.reported_status,
                started_at = CASE
                    WHEN service_heartbeats.instance_id = EXCLUDED.instance_id
                    THEN service_heartbeats.started_at
                    ELSE CURRENT_TIMESTAMP
                END,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            [
                WORKER_SERVICE_NAME,
                str(self._instance_id),
                self._hostname,
                self._pid,
                self._status_provider(),
            ],
        )

    def start(self) -> None:
        """Publish immediately, then refresh at the configured cadence."""
        if self._thread is not None:
            return
        # Fail worker startup when the durable liveness contract is unavailable.
        # Otherwise the worker could run indefinitely while every observer correctly
        # reports it missing.
        self.publish()
        self._thread = Thread(
            target=self._run,
            name="portfolio-worker-heartbeat",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop periodic publication and wait for the publisher thread to exit."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=self._interval_seconds + 1)

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval_seconds):
            try:
                self.publish()
            except Exception as exc:
                # A transient database failure naturally turns the last heartbeat
                # stale. Keep the publisher alive so it recovers with the database.
                logger.error("worker_heartbeat_publish_failed", error=str(exc), exc_info=True)


def _snapshot_from_row(row: dict[str, object]) -> WorkerHeartbeatSnapshot:
    raw_age = row.get("age_seconds")
    age_seconds = max(0.0, float(raw_age)) if raw_age is not None else None
    reported_status = str(row.get("reported_status") or "unhealthy")
    if age_seconds is None or age_seconds > HEARTBEAT_STALE_AFTER_SECONDS:
        state: HeartbeatState = "stale"
    elif reported_status == "healthy":
        state = "current"
    elif reported_status == "starting":
        state = "starting"
    else:
        state = "unhealthy"
    if state == "current":
        message = f"Worker heartbeat current ({age_seconds:.0f}s ago)"
    elif state == "starting":
        message = "Worker heartbeat current, but Hatchet is still starting"
    elif state == "unhealthy":
        message = "Worker heartbeat current, but Hatchet reports unhealthy"
    elif age_seconds is None:
        message = "Worker heartbeat timestamp is unavailable"
    else:
        message = (
            f"Worker heartbeat stale ({age_seconds:.0f}s old; "
            f"expected within {HEARTBEAT_STALE_AFTER_SECONDS:.0f}s)"
        )

    raw_instance_id = row.get("instance_id")
    instance_id = raw_instance_id if isinstance(raw_instance_id, UUID) else UUID(str(raw_instance_id))
    raw_pid = row.get("pid")
    return WorkerHeartbeatSnapshot(
        state=state,
        message=message,
        instance_id=instance_id,
        hostname=str(row["hostname"]),
        pid=int(raw_pid) if raw_pid is not None else None,
        started_at=row.get("started_at") if isinstance(row.get("started_at"), datetime) else None,
        last_seen_at=(
            row.get("last_seen_at") if isinstance(row.get("last_seen_at"), datetime) else None
        ),
        age_seconds=age_seconds,
    )


def read_worker_heartbeat(storage: PortfolioStorage) -> WorkerHeartbeatSnapshot:
    """Read the latest persisted Hatchet worker heartbeat without raising."""
    try:
        result = storage.query(
            """
            SELECT
                instance_id,
                hostname,
                pid,
                reported_status,
                started_at,
                last_seen_at,
                GREATEST(
                    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_seen_at)),
                    0
                ) AS age_seconds
            FROM service_heartbeats
            WHERE service_name = ?
            """,
            [WORKER_SERVICE_NAME],
        )
        rows = result.to_dicts()
        if not rows:
            return WorkerHeartbeatSnapshot(
                state="missing",
                message="No worker heartbeat has been recorded",
            )
        return _snapshot_from_row(rows[0])
    except Exception as exc:
        logger.error("worker_heartbeat_read_failed", error=str(exc), exc_info=True)
        return WorkerHeartbeatSnapshot(
            state="unavailable",
            message="Worker heartbeat unavailable",
        )
