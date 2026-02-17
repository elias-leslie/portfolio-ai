"""Root conftest that imports all shared fixtures and sets global options."""

from __future__ import annotations

from pathlib import Path

import pytest

# Import all fixtures from the centralized fixtures module
# This must come first to set up the test environment (PYTEST_RUNNING, logging, database)
from tests.fixtures.conftest import *  # noqa: F403

_TESTS_ROOT = Path(__file__).parent.resolve()
_SLOW_FOLDERS = (
    (_TESTS_ROOT / "integration").resolve(),
    (_TESTS_ROOT / "watchlist").resolve(),
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom CLI flags."""
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="Run tests marked as slow (integration/watchlist suites).",
    )


def _belongs_to_slow_suite(path: Path) -> bool:
    for slow_dir in _SLOW_FOLDERS:
        try:
            path.relative_to(slow_dir)
            return True
        except ValueError:
            continue
    return False


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip slow tests unless --runslow specified.

    Also automatically applies clean_database fixture to integration/watchlist tests
    to ensure database isolation, while skipping it for unit tests (for speed).
    """
    runslow = config.getoption("--runslow")
    skip_slow = pytest.mark.skip(reason="Skipped slow test. Use --runslow to include.")

    for item in items:
        item_path = Path(str(getattr(item, "fspath", ""))).resolve()
        if _belongs_to_slow_suite(item_path):
            item.add_marker(pytest.mark.slow)
            # Auto-apply clean_database fixture to integration/watchlist tests
            # pytest.Item subclasses (Function) have fixturenames attribute
            raw_fixturenames = getattr(item, "fixturenames", None)
            if isinstance(raw_fixturenames, list):
                raw_fixturenames.append("clean_database")

        if not runslow and "slow" in item.keywords:
            item.add_marker(skip_slow)
