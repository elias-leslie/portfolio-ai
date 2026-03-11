"""Unit-test-specific fixture overrides."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session", autouse=True)
def ensure_test_schema_up_to_date() -> None:
    """Unit tests should not depend on migrated database state."""
