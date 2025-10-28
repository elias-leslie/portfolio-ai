"""Structured logging configuration using structlog.

This module configures structured JSON logging with proper processors,
formatters, and file rotation for production observability.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

import structlog
from pythonjsonlogger import jsonlogger


def configure_logging(log_dir: str = "logs", log_file: str = "portfolio-ai.log") -> None:
    """Configure structured logging with JSON output.

    Args:
        log_dir: Directory for log files
        log_file: Log file name
    """
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
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(json_formatter)

    # Console handler (human-readable for development)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
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
