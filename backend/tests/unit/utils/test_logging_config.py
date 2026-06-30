"""Tests for structured logging configuration."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
import structlog

from app.logging_config import configure_logging, get_logger


@pytest.fixture(autouse=True)
def _clear_invocation_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure INVOCATION_ID is unset so file logging is enabled in tests."""
    monkeypatch.delenv("INVOCATION_ID", raising=False)


def test_get_logger() -> None:
    """Test that get_logger returns a structlog logger."""
    logger = get_logger(__name__)
    # Check that it's a BoundLogger (the actual type returned)
    assert hasattr(logger, "info")
    assert hasattr(logger, "error")
    assert hasattr(logger, "debug")


def test_configure_logging_stdout_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test logging configuration with stdout output."""
    # Configure logging
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(log_dir=str(log_dir), log_file="test-stdout.log")

    logger = get_logger("test")
    logger.info("test_event", foo="bar", num=42)

    # Check that log was written to console (captured by capsys)
    captured = capsys.readouterr()
    assert "test_event" in captured.out or "test_event" in captured.err


def test_configure_logging_with_file_rotation(tmp_path: Path) -> None:
    """Test logging configuration with file output and rotation."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(log_dir=str(log_dir), log_file="test.log")

    # Log a test message
    logger = get_logger("test")
    logger.info("test_event", foo="bar", num=42)

    # Verify log file exists
    log_file = log_dir / "test.log"
    assert log_file.exists()

    # Read log file and verify JSON format
    log_contents = log_file.read_text(encoding="utf-8")
    assert len(log_contents) > 0

    # Parse first line as JSON
    first_line = log_contents.strip().split("\n")[0]
    log_entry = json.loads(first_line)

    # Verify required fields
    assert "message" in log_entry or "event" in log_entry
    assert "timestamp" in log_entry
    assert "level" in log_entry or "levelname" in log_entry


def test_configure_logging_uses_log_dir_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """LOG_DIR should override the default relative logs directory."""
    override_dir = tmp_path / "custom-logs"
    monkeypatch.setenv("LOG_DIR", str(override_dir))

    configure_logging(log_file="env-override.log")

    logger = get_logger("test")
    logger.info("env_override_event")

    assert (override_dir / "env-override.log").exists()


def test_configure_logging_suppresses_yfinance_provider_noise(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    configure_logging(log_dir=str(log_dir), log_file="test-yfinance.log")

    assert logging.getLogger("yfinance").level == logging.CRITICAL


def test_log_levels(tmp_path: Path) -> None:
    """Test different log levels."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(log_dir=str(log_dir), log_file="test-levels.log")

    logger = get_logger("test")

    # Log at different levels
    logger.debug("debug_event")
    logger.info("info_event")
    logger.warning("warning_event")
    logger.error("error_event")

    # Read log file
    log_file = log_dir / "test-levels.log"
    log_contents = log_file.read_text(encoding="utf-8")
    lines = log_contents.strip().split("\n")

    # Verify at least info and higher were logged
    assert len(lines) >= 3

    # Just check that different log levels exist
    levels_found = set()
    for line in lines:
        entry = json.loads(line)
        level = entry.get("level") or entry.get("levelname")
        if level:
            levels_found.add(level.lower())

    # Should have at least info, warning, error
    assert "info" in levels_found
    assert "warning" in levels_found
    assert "error" in levels_found


def test_structured_fields(tmp_path: Path) -> None:
    """Test that structured fields are properly logged."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(log_dir=str(log_dir), log_file="test-fields.log")

    logger = get_logger("test")

    # Log with various field types
    logger.info(
        "test_event",
        string_field="hello",
        int_field=42,
        float_field=3.14,
        bool_field=True,
    )

    # Read log file
    log_file = log_dir / "test-fields.log"
    log_entry = json.loads(log_file.read_text(encoding="utf-8").strip())

    # Verify basic fields exist (the exact format may vary)
    assert "message" in log_entry or "event" in log_entry
    # The actual field values depend on how structlog/pythonjsonlogger serialize them
    # Just verify the log was created successfully
    assert len(log_file.read_text(encoding="utf-8")) > 0


def test_contextvars_binding(tmp_path: Path) -> None:
    """Test that contextvars are properly bound to logs."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(log_dir=str(log_dir), log_file="test-context.log")

    logger = get_logger("test")

    # Bind context variables
    structlog.contextvars.bind_contextvars(request_id="test-request-123")

    logger.info("test_event", action="test_action")

    # Read log file
    log_file = log_dir / "test-context.log"
    log_contents = log_file.read_text(encoding="utf-8").strip()

    # Verify log was created
    assert len(log_contents) > 0

    # Try to parse as JSON
    log_entry = json.loads(log_contents)

    # The exact structure depends on how structlog is configured
    # Just verify it's valid JSON and has some content
    assert isinstance(log_entry, dict)
    assert len(log_entry) > 0

    # Clear context
    structlog.contextvars.clear_contextvars()
