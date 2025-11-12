# Backend Test Organization

This directory contains all backend tests for the Portfolio AI platform, organized by test type and module.

---

## 📁 Directory Structure

```
backend/tests/
├── unit/                  # Unit tests (fast, isolated)
│   ├── agents/            # Agent system tests
│   ├── analytics/         # Analytics & indicators tests
│   ├── portfolio/         # Portfolio business logic tests
│   ├── sources/           # Data source adapter tests
│   ├── storage/           # Storage layer tests
│   └── utils/             # Utility function tests
├── integration/           # Integration tests (DB, HTTP, APIs)
│   ├── api/               # API endpoint tests
│   ├── portfolio/         # Portfolio CRUD integration tests
│   ├── sources/           # Source integration tests
│   └── storage/           # Storage integration tests
├── fixtures/              # Shared test fixtures and utilities
│   └── conftest.py        # Pytest configuration and fixtures
├── api/                   # Existing API-specific tests
├── services/              # Service-level tests
├── sources/               # Source-specific integration tests
├── storage/               # Storage-specific tests
├── watchlist/             # Watchlist feature tests
└── README.md              # This file
```

---

## 🧪 Test Categories

### Unit Tests (`unit/`)

**Characteristics:**
- **Fast execution** (< 100ms per test)
- **No database connections**
- **No HTTP requests** to external APIs
- **All dependencies mocked** (using `unittest.mock` or `pytest-mock`)
- **Tests single function/class** in isolation

**When to write a unit test:**
- Testing pure functions (calculations, transformations, utilities)
- Testing business logic without external dependencies
- Testing class methods with mocked dependencies
- Fast feedback during development

**Example:**
```python
# tests/unit/sources/test_alphavantage_source.py
from unittest.mock import Mock, patch
import pytest

def test_parse_response():
    """Test data parsing logic in isolation."""
    source = AlphaVantageSource()
    mock_response = {"price": 150.0, "beta": 1.2}

    result = source._parse_price_data(mock_response)

    assert result.price == 150.0
    assert result.beta == 1.2
```

### Integration Tests (`integration/`)

**Characteristics:**
- **Realistic execution** (< 5s per test)
- **Uses test database** (`portfolio_ai_test`)
- **Makes HTTP requests** (to test server or real APIs with mocking)
- **Tests component interactions**
- **Auto-cleaned** between tests (via `clean_database` fixture)

**When to write an integration test:**
- Testing API endpoints (FastAPI TestClient)
- Testing database operations (CRUD, queries)
- Testing external API integrations (with mocking for reliability)
- Testing multi-component workflows

**Example:**
```python
# tests/integration/api/test_api_analytics.py
from fastapi.testclient import TestClient
from app.main import app

def test_get_rvol_success(client: TestClient):
    """Test RVOL API endpoint with database."""
    response = client.get("/api/analytics/rvol/AAPL?date=2025-01-15")

    assert response.status_code == 200
    data = response.json()
    assert "rvol" in data
```

---

## 🚀 Running Tests

### Recommended Workflow
- `pytest` &mdash; runs the fast suite (slow integration + watchlist suites are skipped automatically).
- `pytest --runslow` &mdash; runs everything, including slow suites.
- `pytest -m slow --runslow` &mdash; runs only the slow suites (useful before releases/infra changes).

Slow suites currently include everything under `tests/integration/` and `tests/watchlist/`. These folders are automatically marked with `@pytest.mark.slow` so they are skipped unless you pass `--runslow`.

### All Tests
```bash
cd ~/portfolio-ai/backend
source .venv/bin/activate
pytest tests/ -v --runslow
```

### Only Unit Tests (Fast)
```bash
pytest tests/unit/ -v
```

### Only Integration Tests
```bash
pytest tests/integration/ -v --runslow
```

### Specific Module
```bash
# Test specific feature
pytest tests/unit/portfolio/ -v

# Test specific file
pytest tests/unit/sources/test_alphavantage_source.py -v

# Test specific function
pytest tests/unit/sources/test_alphavantage_source.py::test_parse_response -v
```

### With Coverage
```bash
pytest tests/ --cov=app --cov-report=html
```

### Parallel Execution (Recommended for Speed)

**NEW: pytest-xdist enables parallel test execution**

```bash
# Run unit tests in parallel (4x faster)
pytest tests/unit/ -n auto -v

# Run all tests in parallel
pytest tests/ -n auto --runslow

# Specify number of workers explicitly
pytest tests/unit/ -n 4 -v
```

**Performance:**
- **Sequential**: ~3 minutes for unit tests
- **Parallel (`-n auto`)**: ~1m50s for unit tests (**39% faster**)
- Uses all available CPU cores (typically 4-8 workers)

**When to use:**
- ✅ During development (faster feedback loop)
- ✅ In CI/CD pipelines (maximize resource usage)
- ✅ When running full test suite

**Note:** Parallel execution will be even faster once unit tests are properly isolated (currently some tests hit the database)

---

## 🔧 Test Fixtures and Utilities

### Shared Fixtures (`fixtures/conftest.py`)

**Auto-cleanup Fixture:**
```python
@pytest.fixture(autouse=True)
def clean_database():
    """Automatically cleans database before each test."""
    # Truncates all tables to ensure test isolation
```

**Database Fixtures:**
```python
@pytest.fixture
def storage() -> PortfolioStorage:
    """Get storage instance (uses test database)."""
    return get_storage()
```

**Mock Fixtures:**
```python
@pytest.fixture
def mock_http_client():
    """Mock HTTP client for testing external APIs."""
    with patch('httpx.Client') as mock:
        yield mock
```

### Test Database

**Database:** `portfolio_ai_test` (separate from production `portfolio_ai`)

**Auto-cleanup:** All tests automatically truncate tables before running (via `clean_database` fixture)

**Connection:** Configured in `fixtures/conftest.py`
```python
TEST_DB_URL = "postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai_test"
```

---

## ✍️ Writing New Tests

### Unit Test Pattern

```python
"""Unit tests for MyModule."""
from __future__ import annotations

from unittest.mock import Mock, patch
import pytest

from app.my_module import MyClass

@pytest.fixture
def mock_dependency() -> Mock:
    """Mock external dependency."""
    return Mock(spec=ExternalDependency)

@pytest.fixture
def my_class(mock_dependency: Mock) -> MyClass:
    """Create MyClass instance with mocked dependencies."""
    return MyClass(dependency=mock_dependency)

def test_my_function_success(my_class: MyClass):
    """Test function succeeds with valid input."""
    result = my_class.my_function("valid_input")

    assert result == "expected_output"
    # Verify mock interactions if needed
    my_class.dependency.some_method.assert_called_once()

def test_my_function_error_handling(my_class: MyClass):
    """Test function handles errors gracefully."""
    with pytest.raises(ValueError, match="Invalid input"):
        my_class.my_function("invalid_input")
```

### Integration Test Pattern

```python
"""Integration tests for MyAPI."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import get_storage

@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)

@pytest.fixture
def storage():
    """Get storage (uses test database with auto-cleanup)."""
    return get_storage()

def test_api_endpoint_success(client: TestClient, storage):
    """Test API endpoint returns expected data."""
    # Setup test data in database
    storage.create_item({"name": "test"})

    # Make API request
    response = client.get("/api/items")

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "test"
```

---

## 🐛 Debugging Tests

### Run Single Test with Output
```bash
pytest tests/unit/sources/test_alphavantage_source.py::test_parse_response -v -s
```

### Drop into Debugger on Failure
```bash
pytest tests/unit/sources/test_alphavantage_source.py --pdb
```

### Show Local Variables on Failure
```bash
pytest tests/ -l
```

### Verbose Output with Captured Logs
```bash
pytest tests/ -v --log-cli-level=DEBUG
```

---

## 📊 Test Metrics

**Total Tests:** 582 (304 unit, 117 integration, 161 feature)
**Test Discovery:** Automatic via pytest
**Isolation:** Auto-cleanup via `clean_database` fixture
**Execution Time:**
- Unit tests: ~1m50s (parallel with `-n auto`), ~3min (sequential)
- Full suite: ~2-3min (parallel), ~6-7min (sequential)
**Coverage Target:** 80%+ (currently 85%)
**Parallel Execution:** Enabled via `pytest-xdist` (installed 2025-11-12)

---

## 🔍 Troubleshooting

### "No module named app"
**Solution:** Activate virtual environment first
```bash
cd ~/portfolio-ai/backend
source .venv/bin/activate
pytest tests/
```

### "Database connection refused"
**Solution:** Ensure PostgreSQL is running
```bash
sudo systemctl status postgresql
```

### "Test database doesn't exist"
**Solution:** Create test database
```bash
sudo -u postgres psql -c "CREATE DATABASE portfolio_ai_test OWNER portfolio_ai_user;"
```

### Tests Pass Individually but Fail Together
**Cause:** Test isolation issue (data leaking between tests)
**Solution:** Verify `clean_database` fixture is running (check `autouse=True` in conftest.py)

### Slow Test Execution
**Solution:** Run only unit tests for fast feedback
```bash
pytest tests/unit/ -v  # Much faster than full suite
```

---

## 📚 Additional Resources

- **Testing Guide:** `docs/reference/testing-strategy.md`
- **Architecture:** `docs/core/ARCHITECTURE.md` (Testing Strategy section)
- **Development Workflows:** `docs/core/DEVELOPMENT.md`
- **Pytest Documentation:** https://docs.pytest.org/

---

**Last Updated:** 2025-11-12
**Test Count:** 582 tests
**Organization:** Unit/Integration split completed
**Latest Enhancement:** Parallel test execution enabled (pytest-xdist)
