"""JSON serialization utilities.

Provides consistent JSON serialization across the application,
handling non-standard types like datetime and Decimal.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any


def json_serializer(obj: Any) -> Any:
    """Serialize objects not natively JSON-compatible.

    Handles:
    - datetime: Converted to ISO format with UTC timezone
    - date: Converted to ISO format
    - Decimal: Converted to float

    Args:
        obj: Object to serialize

    Returns:
        JSON-compatible representation

    Raises:
        TypeError: If object type is not supported
    """
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=UTC)
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
