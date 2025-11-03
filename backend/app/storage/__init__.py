"""PostgreSQL storage layer for portfolio-ai.

This module provides database access and management functionality.
"""

from .facade import DuckDBStorage, get_storage
from .types import DatabaseConnection

__all__ = ["DatabaseConnection", "DuckDBStorage", "get_storage"]
