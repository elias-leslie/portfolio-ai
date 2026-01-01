"""URL manipulation utilities.

This module provides common URL manipulation functions used across
the application, including path parameter substitution.
"""

from __future__ import annotations

import re


def substitute_path_params(path: str, value: str = "test-probe-value") -> str:
    """Substitute path parameter placeholders with a test value.

    Commonly used for probing endpoints that contain dynamic parameters
    like {symbol} or {id}.

    Args:
        path: Path that may contain {param} placeholders
        value: Value to substitute for each placeholder (default: "test-probe-value")

    Returns:
        Path with all {param} replaced by value

    Example:
        >>> substitute_path_params("/api/symbols/{symbol}/details")
        "/api/symbols/test-probe-value/details"
    """
    return re.sub(r"\{[^}]+\}", value, path)
