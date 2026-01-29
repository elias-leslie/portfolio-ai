"""Constants and configuration for log management."""

import re

# Log level priority mapping for merging/comparison (higher = more severe)
LOG_LEVEL_PRIORITY: dict[str, int] = {
    "CRITICAL": 5,
    "ERROR": 4,
    "WARN": 3,
    "INFO": 2,
    "DEBUG": 1,
    "UNKNOWN": 0,
}

# Syslog priority to log level mapping (journald PRIORITY field)
SYSLOG_PRIORITY_TO_LEVEL: dict[int, str] = {
    0: "CRITICAL",  # Emergency
    1: "CRITICAL",  # Alert
    2: "CRITICAL",  # Critical
    3: "ERROR",  # Error
    4: "WARN",  # Warning
    5: "INFO",  # Notice
    6: "INFO",  # Informational
    7: "DEBUG",  # Debug
}

# Fetch limits
MAX_LOG_LINES = 5000
JOURNAL_FETCH_LIMIT = 10000

# Subprocess timeout constants
JOURNALCTL_TIMEOUT_SECONDS = 15
SCRIPT_EXECUTION_TIMEOUT_SECONDS = 30

# Valid 'since' patterns for journalctl (prevents command injection)
VALID_SINCE_PATTERN = re.compile(
    r"^(\d+\s+(minute|hour|day|week)s?\s+ago|today|yesterday)$", re.IGNORECASE
)

# Derive VALID_LEVELS from LOG_LEVEL_PRIORITY (excluding UNKNOWN which is internal-only)
# Include "WARNING" as an alias for "WARN" for user convenience
VALID_LEVELS = {level for level in LOG_LEVEL_PRIORITY if level != "UNKNOWN"} | {"WARNING"}
