"""Root conftest that imports all shared fixtures.

Pytest automatically loads conftest.py from the tests/ directory.
This file imports all fixtures from tests/fixtures/conftest.py to make
them available to all tests.
"""

# Import all fixtures from the centralized fixtures module
# This must come first to set up the test environment (PYTEST_RUNNING, logging, database)
from tests.fixtures.conftest import *  # noqa: F403
