# Backend tests

Backend tests use pytest. Install the backend development environment first:

```bash
cd backend
uv sync --python 3.13 --frozen --extra dev
```

Run the default test suite:

```bash
uv run pytest
```

Useful focused runs:

```bash
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest tests/api/test_health_endpoints.py
```

Quality gates used by the public CI workflow:

```bash
uv run ruff check app tests
uv run ty check app
uv run pytest
```

Slow tests are marked with `slow` and are skipped by default unless explicitly requested:

```bash
uv run pytest tests --runslow
```

Prefer deterministic fixtures and fake provider payloads. Do not add tests that require real customer data, real brokerage accounts, live credentials, or private infrastructure.
