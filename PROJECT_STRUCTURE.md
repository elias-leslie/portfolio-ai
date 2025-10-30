# Project Structure Reference

**Purpose**: This document clarifies the actual directory structure to prevent confusion when running commands or navigating the codebase.

**Last Updated**: 2025-10-29

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
│   │   ├── storage/                     ← PostgreSQL storage layer
│   │   ├── watchlist/                   ← Watchlist scoring & services
│   │   └── main.py                      ← FastAPI application entry point
│   ├── tests/                           ← Test files (ACTUAL LOCATION)
│   │   └── watchlist/                   ← Watchlist unit tests
│   ├── data/                            ← Database backups only (PostgreSQL managed externally)
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
- **Location**: `~/portfolio-ai/backend/.venv/`
- **Activate**: `source ~/portfolio-ai/backend/.venv/bin/activate`

### Tests
- **Location**: `~/portfolio-ai/backend/tests/`
- **Run tests**: `cd ~/portfolio-ai/backend && pytest tests/ -v`

### Application Code
- **Location**: `~/portfolio-ai/backend/app/`
- **Import path**: `from app.storage import ...`

### Configuration Files
- **Python config**: `~/portfolio-ai/backend/pyproject.toml`
- **Pre-commit config**: `~/portfolio-ai/.pre-commit-config.yaml`
- **Requirements**: `~/portfolio-ai/backend/requirements.txt`

---

## Common Command Patterns

All commands use absolute paths anchored to `~/portfolio-ai/` to eliminate ambiguity:

```bash
# Activate venv
source ~/portfolio-ai/backend/.venv/bin/activate

# Run tests
cd ~/portfolio-ai/backend && pytest tests/ -v

# Run linting
~/portfolio-ai/scripts/lint.sh

# Run type checking
cd ~/portfolio-ai/backend && mypy app/ --strict

# Start backend
cd ~/portfolio-ai/backend && uvicorn app.main:app --reload

# Start frontend
cd ~/portfolio-ai/frontend && npm run dev

# Git operations
cd ~/portfolio-ai && git status
```

---

## Path Standardization

**Core Rule**: All paths use `~/portfolio-ai/` prefix to eliminate ambiguity.

This prevents common issues:
- ❌ `cd backend` from wrong location → creates `backend/backend/` nesting
- ❌ Relative paths → confusion about execution context
- ✅ `cd ~/portfolio-ai/backend` → always correct location

Scripts should use absolute paths:

```bash
# Preferred: Use absolute paths
VENV="$HOME/portfolio-ai/backend/.venv"
TESTS="$HOME/portfolio-ai/backend/tests"
APP="$HOME/portfolio-ai/backend/app"

# Run commands from correct directory
cd ~/portfolio-ai/backend
source ~/portfolio-ai/backend/.venv/bin/activate
pytest tests/ -v
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
✅ **Correct**: `source ~/portfolio-ai/backend/.venv/bin/activate`

❌ **Wrong**: `./scripts/lint.sh` (relative path, context-dependent)
✅ **Correct**: `~/portfolio-ai/scripts/lint.sh` (absolute path, always works)

❌ **Wrong**: `cd backend` from unknown location
✅ **Correct**: `cd ~/portfolio-ai/backend` (always correct)

❌ **Wrong**: Looking for `tests/` in project root
✅ **Correct**: Tests are in `~/portfolio-ai/backend/tests/`

❌ **Wrong**: Expecting database at `./data/portfolio-ai.db`
✅ **Correct**: Database is at `~/portfolio-ai/backend/data/portfolio-ai.db`

❌ **Wrong**: Running tools without `cd` to backend first
✅ **Correct**: `cd ~/portfolio-ai/backend && ruff check app/`

---

## Quick Verification

Run these commands from any directory to verify paths:

```bash
# Verify virtual environment
ls ~/portfolio-ai/backend/.venv/bin/python    # Should exist

# Verify tests location
ls ~/portfolio-ai/backend/tests/              # Should list test files

# Verify app code
ls ~/portfolio-ai/backend/app/main.py         # Should exist

# Verify database location
ls ~/portfolio-ai/backend/data/portfolio-ai.db # Should exist (after setup)

# Verify scripts
ls ~/portfolio-ai/scripts/lint.sh             # Should exist
```

---

**See Also**:
- [~/portfolio-ai/CLAUDE.md](~/portfolio-ai/CLAUDE.md) - Quick reference for common commands
- [~/portfolio-ai/docs/core/DEVELOPMENT.md](~/portfolio-ai/docs/core/DEVELOPMENT.md) - Development workflows
- [~/portfolio-ai/docs/core/ARCHITECTURE.md](~/portfolio-ai/docs/core/ARCHITECTURE.md) - System architecture
