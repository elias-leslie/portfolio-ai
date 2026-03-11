"""Repository layer for database operations.

Repositories handle all database queries, separating data access from business logic.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


def __getattr__(name: str) -> Any:
    """Lazily resolve repository exports to avoid circular imports."""
    exports = {
        "AgentRunRepository": (".agent_repository", "AgentRunRepository"),
        "MarketRepository": (".market_repository", "MarketRepository"),
        "ReferenceRepository": (".reference_repository", "ReferenceRepository"),
    }
    export = exports.get(name)
    if export is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)

    module_name, attribute_name = export
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value

__all__ = ["AgentRunRepository", "MarketRepository", "ReferenceRepository"]
