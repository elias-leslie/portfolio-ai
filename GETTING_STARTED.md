# Getting Started with Portfolio AI Platform

**Welcome!** This guide helps you start a new Claude Code session in this project.

---

## ✅ Pre-Flight Checklist

Before you start coding, verify these critical components are present:

### 1. **Slash Commands** (Most Important!)

```bash
ls .claude/commands/
```

**Expected output:**
```
do_it.md
doc_it.md
next_it.md
plan_it.md
task_it.md
```

These files enable slash commands like `/do_it`, `/plan_it`, etc. in Claude Code.

**If missing:** The `.claude/commands/` folder is the most critical piece. Without it, slash commands won't work!

### 2. **Task Files**

```bash
ls tasks/
```

**Expected output:**
```
0009-prd-portfolio-ai-platform.md          # The PRD (specification)
tasks-0009-prd-portfolio-ai-platform.md    # Task list with progress
```

### 3. **Virtual Environment**

```bash
ls backend/.venv/
```

Should show `bin/`, `lib/`, etc. If missing, recreate with:
```bash
cd backend
python3 -m venv --without-pip .venv
source .venv/bin/activate
curl -sS https://bootstrap.pypa.io/get-pip.py | python
pip install -r requirements.txt
```

---

## 🚀 Starting a New Session

### Option 1: Continue with Tasks (Recommended)

```bash
# This will pick up where you left off
/do_it tasks/tasks-0009-prd-portfolio-ai-platform.md
```

The `/do_it` command will:
- Read the task list
- Find the next incomplete task
- Ask permission to start
- Implement the task
- Run tests and commit when parent task completes

### Option 2: Check What's Next

```bash
/next_it
```

This will scan the task list and identify the highest priority incomplete task.

### Option 3: Start New Feature

```bash
/plan_it "Add user authentication to the platform"
```

This will create a new PRD in the `tasks/` folder.

---

## 📋 Current Project Status

**Completed:** Task 0.0 - Project Bootstrap & Infrastructure Setup (20/20 subtasks)

**Next Task:** 1.0 - Storage Layer & Database Schema (0/18 subtasks)

**Next Subtask:** 1.1 - Copy `app/storage/connection.py` from market-sim

---

## 🔍 Useful Commands

### Check Project Health
```bash
# Validate slash commands work
./scripts/validate-commands.sh

# Check git status
git status

# View recent commits
git log --oneline -5
```

### Backend Development
```bash
cd backend
source .venv/bin/activate       # Always activate first!
uvicorn app.main:app --reload   # Start backend (port 8000)
pytest tests/ -v                # Run tests
```

### Frontend Development
```bash
cd frontend
npm run dev                     # Start frontend (port 3000)
```

### Code Quality
```bash
# Run from repo root
./scripts/lint.sh               # Linting + type checking
```

---

## 📖 Key Documentation Files

1. **[CLAUDE.md](CLAUDE.md)** - Quick reference for Claude Code (auto-read on session start)
2. **[README.md](README.md)** - Project overview and features
3. **[PROJECT_STATUS.md](PROJECT_STATUS.md)** - Detailed status and verification
4. **[tasks/tasks-0009-prd-portfolio-ai-platform.md](tasks/tasks-0009-prd-portfolio-ai-platform.md)** - Full task list with checkboxes

---

## ⚠️ Important Notes

### Critical Components
- **`.claude/commands/`** - DO NOT DELETE! Contains slash command definitions
- **`tasks/`** - Contains PRD and task list for continuity
- **`backend/.venv/`** - Python environment with all dependencies

### Git Workflow
- Slash commands handle commits automatically
- Follow conventional commit format (feat:, fix:, docs:, etc.)
- Test before committing (handled by `/do_it`)

### Native Execution (No Docker)
- Backend: Python venv (activate with `source backend/.venv/bin/activate`)
- Frontend: npm (run with `npm run dev` from frontend/)
- No Docker Compose needed for this project

---

## 🆘 Troubleshooting

### Slash commands don't work
**Problem:** `/do_it` or other commands not recognized

**Solution:** Verify `.claude/commands/*.md` files exist:
```bash
ls -la .claude/commands/
```

If missing, they need to be restored from market-sim project.

### Python virtual environment issues
**Problem:** `pip` or `pytest` commands fail

**Solution:** Make sure venv is activated:
```bash
cd backend
source .venv/bin/activate
pip --version  # Should show path in .venv
```

### Task list out of sync
**Problem:** Task list doesn't reflect your current work

**Solution:** Manually update `tasks/tasks-0009-prd-portfolio-ai-platform.md` to mark tasks complete with `[x]`.

---

## 🎯 Quick Start Command

For immediate continuation of work:

```bash
/do_it tasks/tasks-0009-prd-portfolio-ai-platform.md
```

This single command will:
1. Load the task list
2. Find Task 1.1 (next incomplete task)
3. Ask permission to start
4. Execute the task
5. Test and commit when ready

**That's it! You're ready to code.** 🚀
