"""Pydantic models for log management."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class UnifiedLogEntry(BaseModel):
    """Single log entry from unified journald stream."""

    model_config = ConfigDict(validate_assignment=True)

    timestamp: datetime = Field(description="Log entry timestamp (unified from journald)")
    service: str = Field(description="Service name (backend, celery_worker, postgresql, etc.)")
    level: str = Field(description="Log level (ERROR, WARN, INFO, DEBUG, UNKNOWN)")
    message: str = Field(description="Log message content")


class UnifiedLogsResponse(BaseModel):
    """Response model for unified logs endpoint."""

    logs: list[UnifiedLogEntry] = Field(description="Chronologically sorted log entries")
    total_entries: int = Field(description="Total number of log entries returned")
    level_counts: dict[str, int] = Field(
        description="Count of each log level in unfiltered data (for dropdown display)"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Response timestamp"
    )


class LogLevelConfigResponse(BaseModel):
    """Log level configuration information."""

    current_level: str = Field(description="Current log level (INFO, DEBUG, WARN, ERROR)")
    available_levels: list[str] = Field(description="Available log levels")
    configuration_method: str = Field(description="How to change the log level")
    restart_required: bool = Field(description="Whether restart is required after change")


class SetLogLevelRequest(BaseModel):
    """Request to set log level."""

    level: str = Field(description="Log level to set (DEBUG, INFO, WARN, ERROR, CRITICAL)")


class SetLogLevelResponse(BaseModel):
    """Response from setting log level."""

    success: bool = Field(description="Whether the operation succeeded")
    level: str = Field(description="Log level that was set")
    message: str = Field(description="Status message")
    restart_required: bool = Field(description="Whether services need restart")


class TestLoggingResponse(BaseModel):
    """Response from test logging endpoint."""

    success: bool
    message: str
    levels_tested: list[str]
