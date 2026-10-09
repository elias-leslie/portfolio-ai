"""Root conftest that imports all shared fixtures and sets global options."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, tzinfo
from pathlib import Path
from types import ModuleType

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


@pytest.fixture(autouse=True)
def testclient_local_transport(monkeypatch):
    """Starlette's in-process transport represents this suite's local operator.

    Real IPs and signed assertions still exercise the actual access checks.
    Production never accepts the non-IP 'testclient' transport name.
    """
    from pydantic import SecretStr

    from app.services import household_identity

    monkeypatch.setattr(household_identity.settings, "household_member_emails", SecretStr(""))

    original = household_identity.is_local_connection
    monkeypatch.setattr(
        household_identity,
        "is_local_connection",
        lambda request: (
            bool(request.client and request.client.host == "testclient") or original(request)
        ),
    )


@pytest.fixture
def freeze_today(monkeypatch: pytest.MonkeyPatch) -> Callable[..., date]:
    """Pin the calendar inside the given modules to a fixed day.

    Calendar-sensitive code (month windows, ``add_months``) must not depend on
    the day the suite runs. Each module's ``date`` name is replaced with a
    subclass whose ``today()`` returns ``today``, and its ``datetime`` name (if
    any) with one whose ``now()`` returns noon UTC on ``today`` (converted to
    the requested tz). ``isinstance`` checks and all other behavior are
    unchanged. Usage: ``today = freeze_today(date(2026, 3, 31), some_module)``.
    """

    class _RealInstances(type):
        # Keep ``isinstance(value, date)`` / ``datetime`` true for real values.
        def __instancecheck__(cls, instance: object) -> bool:
            return isinstance(instance, cls.__mro__[1])

        def __subclasscheck__(cls, subclass: type) -> bool:
            return issubclass(subclass, cls.__mro__[1])

    def _freeze(today: date, *modules: ModuleType) -> date:
        frozen = date(today.year, today.month, today.day)
        frozen_now = datetime(today.year, today.month, today.day, 12, tzinfo=UTC)

        class _FrozenDate(date, metaclass=_RealInstances):
            _frozen_clock = True

            @classmethod
            def today(cls) -> date:
                return frozen

        class _FrozenDatetime(datetime, metaclass=_RealInstances):
            _frozen_clock = True

            @classmethod
            def now(cls, tz: tzinfo | None = None) -> datetime:
                if tz is None:
                    return frozen_now.replace(tzinfo=None)
                return frozen_now.astimezone(tz)

        for module in modules:
            for name, real, frozen_cls in (
                ("date", date, _FrozenDate),
                ("datetime", datetime, _FrozenDatetime),
            ):
                current = getattr(module, name, None)
                # Re-freezing (e.g. autouse default + parametrized day) is allowed.
                if current is real or getattr(current, "_frozen_clock", False):
                    monkeypatch.setattr(module, name, frozen_cls)
        return frozen

    return _freeze


@pytest.fixture(autouse=True)
def household_upload_test_key(monkeypatch):
    """Uploads are encrypted at rest and fail closed without a key.

    Environments without PORTFOLIO_SECRET_KEY (CI) get a throwaway test key so
    upload flows remain testable; tests of the unset-key path patch it back.
    """
    from app.services import household_upload_crypto

    if not household_upload_crypto._configured_secret():
        monkeypatch.setattr(
            household_upload_crypto, "_configured_secret", lambda: "pytest-only-upload-key"
        )


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
    skip_manual = pytest.mark.skip(reason="Skipped live/manual test. Use --runmanual to include.")

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
