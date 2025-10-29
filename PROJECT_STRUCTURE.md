# Project Structure Reference

**Purpose**: This document clarifies the actual directory structure to prevent confusion when running commands or navigating the codebase.

**Last Updated**: 2025-10-28

---

## Directory Layout

```
/home/kasadis/portfolio-ai/              ← PROJECT ROOT
│
├── backend/                              ← Backend application root
│   ├── .venv/                           ← Python virtual environment (ACTUAL LOCATION)
│   ├── app/                             ← Python application code
│   │   ├── agents/                      ← AI agent system
│   │   ├── analytics/                   ← Analytics & indicators
│   │   ├── api/                         ← FastAPI routers
│   │   ├── portfolio/                   ← Portfolio CRUD & analytics
│   │   ├── sources/                     ← Data source adapters
│   │   ├── storage/                     ← DuckDB storage layer
│   │   └── main.py                      ← FastAPI application entry point
│   ├── tests/                           ← Test files (ACTUAL LOCATION)
│   ├── data/                            ← DuckDB database files
│   ├── logs/                            ← Application logs
│   ├── migrations/                      ← Database migrations
│   ├── pyproject.toml                   ← Project config (ruff, mypy, pytest)
│   └── requirements.txt                 ← Pip dependencies
│
├── frontend/                             ← Next.js dashboard
│   ├── app/                             ← App router pages
│   ├── components/                      ← React components
│   └── lib/                             ← API clients & hooks
│
├── docs/                                 ← Core documentation
│   └── core/                            ← System documentation
│       ├── ARCHITECTURE.md              ← System design & philosophy
│       ├── DEVELOPMENT.md               ← Development workflows
│       ├── API_REFERENCE.md             ← API endpoint reference
│       └── ...
│
├── tasks/                                ← PRD and task lists
│   ├── 0012-prd-solution-alignment-fixes.md
│   ├── tasks-0012-prd-solution-alignment-fixes.md
│   └── ...
│
├── scripts/                              ← Build & validation scripts
│   ├── lint.sh                          ← Full linting suite
│   ├── validate-versions.sh             ← Tool version sync check
│   └── ...
│
├── config/                               ← YAML seed data
├── data/                                 ← Database backups only (app uses backend/data/)
│
├── CLAUDE.md                             ← Quick reference for AI agents
├── .pre-commit-config.yaml              ← Pre-commit hook configuration
├── .env                                  ← Environment variables
└── ...
```

---

## Critical Paths

### Virtual Environment
- **Location**: `/home/kasadis/portfolio-ai/backend/.venv/`
- **Activate from project root**: `source backend/.venv/bin/activate`
- **Activate from backend dir**: `source .venv/bin/activate`

### Tests
- **Location**: `/home/kasadis/portfolio-ai/backend/tests/`
- **Run from project root**: `backend/.venv/bin/pytest backend/tests/ -v`
- **Run from backend dir**: `.venv/bin/pytest tests/ -v`

### Application Code
- **Location**: `/home/kasadis/portfolio-ai/backend/app/`
- **Import path**: `from app.storage import ...`

### Configuration Files
- **Python config**: `/home/kasadis/portfolio-ai/backend/pyproject.toml`
- **Pre-commit config**: `/home/kasadis/portfolio-ai/.pre-commit-config.yaml` (project root!)
- **Requirements**: `/home/kasadis/portfolio-ai/backend/requirements.txt`

---

## Common Command Patterns

### From Project Root (`/home/kasadis/portfolio-ai/`)

```bash
# Activate venv
source backend/.venv/bin/activate

# Run tests
backend/.venv/bin/pytest backend/tests/ -v

# Run linting
./scripts/lint.sh

# Run type checking
backend/.venv/bin/mypy backend/app/ --strict

# Start backend
cd backend && .venv/bin/uvicorn app.main:app --reload
```

### From Backend Dir (`/home/kasadis/portfolio-ai/backend/`)

```bash
# Activate venv
source .venv/bin/activate

# Run tests
.venv/bin/pytest tests/ -v

# Run linting (script is in parent dir)
../scripts/lint.sh

# Run type checking
.venv/bin/mypy app/ --strict

# Start backend
.venv/bin/uvicorn app.main:app --reload
```

---

## Working Directory Detection

When writing scripts or commands, detect the current working directory:

```bash
# Check if we're in project root or backend dir
if [ -d "backend/.venv" ]; then
  # We're in project root
  VENV="backend/.venv"
  TESTS="backend/tests"
  APP="backend/app"
elif [ -d ".venv" ] && [ -d "app" ]; then
  # We're in backend dir
  VENV=".venv"
  TESTS="tests"
  APP="app"
else
  echo "Error: Run from project root or backend dir"
  exit 1
fi
```

---

## Why This Structure?

This structure emerged from the project evolution:

1. **Backend isolation**: All Python code, tests, and venv are self-contained in `backend/`
2. **Consistent imports**: Python code uses `from app.* import ...` (no `backend.app` prefix)
3. **Root-level coordination**: Scripts, docs, and configs at project root coordinate across frontend/backend
4. **Native execution**: No Docker, so venv location matters for reproducibility

---

## Common Mistakes to Avoid

❌ **Wrong**: `cd backend && source backend/.venv/bin/activate`
✅ **Correct**: `cd backend && source .venv/bin/activate`

❌ **Wrong**: `cd backend && ./../scripts/lint.sh` (works but ugly)
✅ **Correct**: `./scripts/lint.sh` (from project root)

❌ **Wrong**: Looking for `tests/` in project root
✅ **Correct**: Tests are in `backend/tests/`

❌ **Wrong**: Expecting database at `./data/portfolio-ai.db` when running from project root
✅ **Correct**: Database is at `backend/data/portfolio-ai.db` (app uses relative path from backend dir)

❌ **Wrong**: Running tools from project root (creates duplicate caches in root)
✅ **Correct**: Always `cd backend` first, then run `ruff`, `mypy`, `pytest`

---

## Quick Verification

Run these commands to verify your understanding:

```bash
# From project root
ls backend/.venv/bin/python    # Should exist
ls backend/tests/              # Should list test files
ls backend/app/main.py         # Should exist

# From backend dir
ls .venv/bin/python            # Should exist
ls tests/                      # Should list test files
ls app/main.py                 # Should exist
```

---

**See Also**:
- [CLAUDE.md](CLAUDE.md) - Quick reference for common commands
- [docs/core/DEVELOPMENT.md](docs/core/DEVELOPMENT.md) - Development workflows
- [docs/core/ARCHITECTURE.md](docs/core/ARCHITECTURE.md) - System architecture
