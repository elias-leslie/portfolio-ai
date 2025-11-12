"""Source performance metrics tracking and database persistence."""

from __future__ import annotations

import dataclasses
import datetime as dt
from typing import TYPE_CHECKING

from httpx import HTTPStatusError

from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)

# Rate limit cooldown duration (60 seconds)
RATE_LIMIT_COOLDOWN_SECONDS = 60


@dataclasses.dataclass
class SourceMetrics:
    """Performance metrics for a data source."""

    source_name: str
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: int = 0
    rate_limit_hits: int = 0
    last_success_at: dt.datetime | None = None
    last_failure_at: dt.datetime | None = None
    last_rate_limit_at: dt.datetime | None = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        total = self.success_count + self.failure_count
        return (self.success_count / total * 100) if total > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency in milliseconds."""
        return self.total_latency_ms / self.success_count if self.success_count > 0 else 0.0

    def is_in_cooldown(self) -> bool:
        """Check if source is in rate limit cooldown."""
        if self.last_rate_limit_at is None:
            return False

        cooldown_until = self.last_rate_limit_at + dt.timedelta(seconds=RATE_LIMIT_COOLDOWN_SECONDS)
        return dt.datetime.now(dt.UTC) < cooldown_until

    def cooldown_remaining_seconds(self) -> int:
        """Calculate remaining cooldown time in seconds."""
        if not self.is_in_cooldown() or self.last_rate_limit_at is None:
            return 0

        cooldown_until = self.last_rate_limit_at + dt.timedelta(seconds=RATE_LIMIT_COOLDOWN_SECONDS)
        remaining = (cooldown_until - dt.datetime.now(dt.UTC)).total_seconds()
        return max(0, int(remaining))


class SourceMetricsManager:
    """Manages source performance metrics with database persistence."""

    def __init__(self, storage: PortfolioStorage | None = None) -> None:
        """Initialize metrics manager.

        Args:
            storage: PortfolioStorage instance for metrics persistence (optional)
        """
        self.storage = storage
        self._metrics: dict[str, SourceMetrics] = {}

    def initialize_metric(self, source_name: str) -> None:
        """Initialize metric tracking for a source.

        Args:
            source_name: Name of source to track
        """
        if source_name not in self._metrics:
            self._metrics[source_name] = SourceMetrics(source_name=source_name)

    def load_all_from_db(self) -> None:
        """Load source performance metrics from database.

        Reads from source_performance table if it exists.
        Silently skips if table doesn't exist (not created yet).
        """
        if not self.storage:
            return

        try:
            df = self.storage.query(
                """
                SELECT source_name, success_count, failure_count,
                       total_latency_ms, rate_limit_hits, last_success_at
                FROM source_performance
                """,
                [],
            )

            if df.is_empty():
                return

            for row in df.iter_rows(named=True):
                source_name = row["source_name"]
                if source_name in self._metrics:
                    self._metrics[source_name].success_count = row["success_count"] or 0
                    self._metrics[source_name].failure_count = row["failure_count"] or 0
                    self._metrics[source_name].total_latency_ms = row["total_latency_ms"] or 0
                    self._metrics[source_name].rate_limit_hits = row["rate_limit_hits"] or 0
                    self._metrics[source_name].last_success_at = row.get("last_success_at")

            logger.info(
                "metrics_loaded_from_db", num_sources=len(self._metrics), table="source_performance"
            )

        except Exception as e:
            # Table might not exist yet
            logger.debug("metrics_load_skipped", error=str(e), reason="table_not_ready")

    def save_to_db(self, source_name: str) -> None:
        """Save source performance metrics to database using UPSERT.

        Args:
            source_name: Name of source to save metrics for
        """
        if not self.storage or source_name not in self._metrics:
            return

        metrics = self._metrics[source_name]

        try:
            with self.storage.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO source_performance (
                        source_name, success_count, failure_count,
                        total_latency_ms, rate_limit_hits, last_success_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_name)
                    DO UPDATE SET
                        success_count = EXCLUDED.success_count,
                        failure_count = EXCLUDED.failure_count,
                        total_latency_ms = EXCLUDED.total_latency_ms,
                        rate_limit_hits = EXCLUDED.rate_limit_hits,
                        last_success_at = EXCLUDED.last_success_at
                    """,
                    [
                        source_name,
                        metrics.success_count,
                        metrics.failure_count,
                        metrics.total_latency_ms,
                        metrics.rate_limit_hits,
                        metrics.last_success_at,
                    ],
                )
                conn.commit()

            logger.debug("metrics_saved_to_db", source=source_name)

        except Exception as e:
            # Non-fatal - metrics still tracked in memory
            logger.debug("metrics_save_failed", source=source_name, error=str(e))

    def record_success(self, source_name: str, latency_ms: int) -> None:
        """Record successful fetch.

        Args:
            source_name: Name of source
            latency_ms: Request latency in milliseconds
        """
        if source_name not in self._metrics:
            self.initialize_metric(source_name)

        metrics = self._metrics[source_name]
        metrics.success_count += 1
        metrics.total_latency_ms += latency_ms
        metrics.last_success_at = dt.datetime.now(dt.UTC)

        logger.info(
            "source_success",
            source=source_name,
            latency_ms=latency_ms,
            success_rate=f"{metrics.success_rate:.1f}%",
            avg_latency_ms=int(metrics.avg_latency_ms),
        )

        # Persist to database
        if self.storage:
            self.save_to_db(source_name)

    def record_failure(self, source_name: str, error: Exception) -> None:
        """Record failed fetch.

        Args:
            source_name: Name of source
            error: Exception that occurred
        """
        if source_name not in self._metrics:
            self.initialize_metric(source_name)

        metrics = self._metrics[source_name]
        metrics.failure_count += 1
        metrics.last_failure_at = dt.datetime.now(dt.UTC)

        # Check if rate limit error (HTTP 429)
        is_rate_limit = False
        if isinstance(error, HTTPStatusError) and error.response.status_code == 429:
            is_rate_limit = True
            metrics.rate_limit_hits += 1
            metrics.last_rate_limit_at = dt.datetime.now(dt.UTC)

            logger.warning(
                "source_rate_limit_hit",
                source=source_name,
                cooldown_seconds=RATE_LIMIT_COOLDOWN_SECONDS,
                total_rate_limit_hits=metrics.rate_limit_hits,
            )

        if not is_rate_limit:
            logger.warning(
                "source_failure",
                source=source_name,
                error=str(error),
                error_type=type(error).__name__,
                success_rate=f"{metrics.success_rate:.1f}%",
            )

        # Persist to database
        if self.storage:
            self.save_to_db(source_name)

    def get_metric(self, source_name: str) -> SourceMetrics | None:
        """Get metrics for a specific source.

        Args:
            source_name: Name of source

        Returns:
            SourceMetrics or None if not found
        """
        return self._metrics.get(source_name)

    def get_all_metrics(self) -> dict[str, SourceMetrics]:
        """Get metrics for all sources.

        Returns:
            Dictionary mapping source name to SourceMetrics
        """
        return dict(self._metrics)

    def is_in_cooldown(self, source_name: str) -> bool:
        """Check if source is in rate limit cooldown.

        Args:
            source_name: Name of source to check

        Returns:
            True if source is in cooldown, False otherwise
        """
        metrics = self._metrics.get(source_name)
        return metrics.is_in_cooldown() if metrics else False

    def cooldown_remaining(self, source_name: str) -> int:
        """Get remaining cooldown time in seconds.

        Args:
            source_name: Name of source to check

        Returns:
            Remaining cooldown time in seconds, or 0 if not in cooldown
        """
        metrics = self._metrics.get(source_name)
        return metrics.cooldown_remaining_seconds() if metrics else 0
