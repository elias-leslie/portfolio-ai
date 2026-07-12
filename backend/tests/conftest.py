"""Root conftest that imports all shared fixtures and sets global options."""

from __future__ import annotations

from pathlib import Path

import pytest

# Import all fixtures from the centralized fixtures module
# This must come first to set up the test environment (PYTEST_RUNNING, logging, database)
from tests.fixtures.conftest import *  # noqa: F403

_TESTS_ROOT = Path(__file__).parent.resolve()
_INTEGRATION_FOLDERS = (
    (_TESTS_ROOT / "integration").resolve(),
    (_TESTS_ROOT / "watchlist").resolve(),
)
_MANUAL_FOLDER = (_TESTS_ROOT / "manual").resolve()


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom CLI flags."""
    parser.addoption(
        "--runintegration",
        action="store_true",
        default=False,
        help="Run deterministic integration/watchlist suites that require PostgreSQL.",
    )
    parser.addoption(
        "--runmanual",
        action="store_true",
        default=False,
        help="Run manual tests that may require live services or credentials.",
    )
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="Deprecated alias for --runintegration; never enables manual tests.",
    )


def _belongs_to(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def _belongs_to_integration_suite(path: Path) -> bool:
    return any(_belongs_to(path, directory) for directory in _INTEGRATION_FOLDERS)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Keep deterministic integration and live/manual execution separate.

    Integration/watchlist tests receive database isolation and run only when
    ``--runintegration`` (or the legacy ``--runslow`` alias) is supplied. Manual
    tests can contact live services and require the explicit ``--runmanual`` flag;
    neither of the integration flags can enable them accidentally.
    """
    run_integration = config.getoption("--runintegration") or config.getoption("--runslow")
    run_manual = config.getoption("--runmanual")
    skip_integration = pytest.mark.skip(
        reason="Skipped integration test. Use --runintegration to include."
    )
    skip_manual = pytest.mark.skip(
        reason="Skipped live/manual test. Use --runmanual to include."
    )

    for item in items:
        item_path = Path(str(getattr(item, "fspath", ""))).resolve()
        is_integration = _belongs_to_integration_suite(item_path)
        is_manual = _belongs_to(item_path, _MANUAL_FOLDER) or "manual" in item.keywords

        if is_integration:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.slow)

        if is_manual:
            item.add_marker(pytest.mark.manual)
            item.add_marker(pytest.mark.slow)
            if not run_manual:
                item.add_marker(skip_manual)
        elif is_integration and not run_integration:
            item.add_marker(skip_integration)
