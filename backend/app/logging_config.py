"""Structured logging configuration using structlog.

This module configures structured JSON logging with proper processors,
formatters, and file rotation for production observability.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

import structlog
from pythonjsonlogger import jsonlogger


def _parse_log_level(level_str: str | None) -> int:
    """Parse log level string to logging constant.

    Args:
        level_str: Log level string (DEBUG, INFO, WARN, WARNING, ERROR, CRITICAL)

    Returns:
        logging level constant (defaults to INFO if invalid)
    """
    if not level_str:
        return logging.INFO

    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARN": logging.WARNING,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    return level_map.get(level_str.upper(), logging.INFO)


def configure_logging(log_dir: str = "logs", log_file: str = "portfolio-ai.log") -> None:
    """Configure structured logging with JSON output.

    Log level can be controlled via LOG_LEVEL environment variable.
    Valid values: DEBUG, INFO, WARN, WARNING, ERROR, CRITICAL
    Default: INFO

    Args:
        log_dir: Directory for log files
        log_file: Log file name
    """
    # Get log level from environment (default: INFO)
    log_level = _parse_log_level(os.getenv("LOG_LEVEL"))

    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Configure standard library logging
    log_file_path = log_path / log_file

    # JSON formatter for file output
    json_formatter = jsonlogger.JsonFormatter(  # type: ignore[attr-defined]  # pythonjsonlogger typing incomplete
        "%(timestamp)s %(level)s %(name)s %(message)s %(pathname)s %(lineno)d",
        rename_fields={
            "levelname": "level",
            "name": "logger",
            "pathname": "file",
            "lineno": "line",
        },
    )

    # File handler with daily rotation (keep 30 days)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(log_file_path),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(json_formatter)

    # Console handler (human-readable for development)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = []  # Clear existing handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)  # type: ignore[no-any-return]  # structlog returns Any-typed logger
