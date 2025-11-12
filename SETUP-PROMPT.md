# Setup Agent Instructions - Distributed Code Review System

You are the Setup Agent. Your job is to create the infrastructure for a distributed code review system where 5 agents work in parallel with zero merge conflicts.

## Prerequisites

**TWO branches required:**
1. **Setup Branch**: Your current session branch (e.g., `claude/setup-distributed-review-XXXX`)
   - Used to store AGENT-INSTRUCTIONS.md
   - You can push to this branch (matches your session ID)
2. **Working Branch**: The agent working branch (e.g., `claude/code-review-YYYY`)
   - Where all 5 agents will do their work
   - You cannot push to this branch (different session ID)

**The user should tell you both branch names.**

---

## Step 1: Analyze Codebase Structure

```bash
cd /home/user/portfolio-ai
git checkout <WORKING_BRANCH>
git pull origin <WORKING_BRANCH>
```

Analyze and document:

### Backend Files
```bash
find backend/app -type f -name "*.py" -exec wc -l {} + | sort -rn | head -20
```

**Look for:**
- Files >800 lines (P0: must split)
- Files 500-800 lines (P1: should optimize)
- N+1 queries (grep for loops with db queries)
- SELECT * statements
- Duplicate code patterns
- Missing type hints

### Frontend Files
```bash
find frontend/components -type f \( -name "*.tsx" -o -name "*.ts" \) -exec wc -l {} + | sort -rn | head -20
```

**Look for:**
- Components >800 lines (P0: must split)
- Duplicate JSX patterns
- Unused imports

---

## Step 2: Create Module Assignments (Zero Overlap)

Divide codebase into 5 modules with **ZERO file overlap**:

**Agent 1: Market Intelligence**
- backend/app/market/* (ALL files)
- backend/app/api/market.py
- frontend/components/market/* (ALL files)
- frontend/lib/hooks/useMarketIntelligence.ts

**Agent 2: Watchlist**
- backend/app/watchlist/* (ALL files)
- backend/app/api/watchlist.py
- frontend/components/watchlist/* (ALL files)
- frontend/components/settings/WatchlistPreferences.tsx
- frontend/components/settings/sections/WatchlistSettingsSection.tsx

**Agent 3: Portfolio & Analytics**
- backend/app/portfolio/* (ALL files)
- backend/app/analytics/* (ALL files)
- backend/app/api/portfolio.py
- backend/app/api/analytics.py
- backend/app/api/ideas.py
- frontend/components/portfolio/* (ALL files)

**Agent 4: News & Services**
- backend/app/services/* (ALL files)
- backend/app/sources/* (ALL files)
- backend/app/ml/* (ALL files)
- backend/app/api/news.py
- frontend/components/shared/UnifiedNewsIntelligence*.tsx

**Agent 5: Tasks & Infrastructure**
- backend/app/tasks/* (ALL files)
- backend/app/utils/* (ALL files)
- backend/app/storage/* (ALL files)
- backend/app/api/health.py
- backend/app/api/status.py
- backend/app/api/maintenance.py
- backend/app/api/celery_endpoints.py
- backend/app/celery_app.py
- frontend/components/status/* (ALL files)

---

## Step 3: Create AGENT-INSTRUCTIONS.md

Create this file with detailed instructions for all agents.

**Template structure:**

```markdown
# Code Review Agent Instructions

**USER WILL TELL YOU: "You are Cloud Agent X" - Find your section below.**

Branch: <WORKING_BRANCH>

## Cloud Agent 1: Market Intelligence

**Files YOU own:**
[List from Step 2]

**Tasks:**
- P0: [Files >800 lines, N+1 queries, SELECT *]
- P1: [Files 500-800, duplicate code, missing types]
- P2: [Dead code, TODOs, unused imports]

**DO NOT TOUCH:** watchlist/*, portfolio/*, services/*, tasks/*, utils/*

---

[Repeat for Agents 2-5]

---

## Instructions (ALL AGENTS)

### Setup
```bash
# Step 1: Go to repo
cd /home/user/portfolio-ai

# Step 2: Fetch the AGENT-INSTRUCTIONS.md file from setup branch
git fetch origin <SETUP_BRANCH>
git checkout origin/<SETUP_BRANCH> -- AGENT-INSTRUCTIONS.md

# Step 3: Switch to working branch
git checkout <WORKING_BRANCH>
git pull origin <WORKING_BRANCH>

# Step 4: Verify you have the file
ls -la AGENT-INSTRUCTIONS.md
```

### Process
1. **TodoWrite**: Create task list from your P0/P1/P2 tasks above
2. **Read YOUR files only**: Use Read tool on files you own
3. **Fix issues in order**: P0 (critical) → P1 (important) → P2 (nice-to-have)
4. **Test after each fix**:
   ```bash
   bash ~/portfolio-ai/scripts/lint.sh
   cd ~/portfolio-ai/backend && pytest tests/ -v
   ```
5. **Commit frequently**:
   ```bash
   git add <files>
   git commit -m "chore(cloud-X): <summary>"
   ```
6. **Push when done**:
   ```bash
   git push origin <WORKING_BRANCH>
   ```
7. **Generate report**: Use template below

### Rules
✅ **Edit ONLY your files** - Zero overlap ensures zero conflicts
✅ **Test before commit** - All lint and tests must pass
✅ **Small commits** - One logical change per commit
✅ **Follow patterns** - Match existing code style
❌ **NEVER touch other agents' files** - This prevents merge conflicts
❌ **NEVER skip testing** - Broken code blocks other agents
❌ **NEVER use `--no-verify`** - Pre-commit hooks must pass

### Priority Definitions
- **P0 (Critical)**: Files >800 lines, N+1 queries, SELECT *, performance issues
- **P1 (Important)**: Files 500-800 lines, duplicate code, missing types
- **P2 (Nice-to-have)**: Dead code, TODOs, unused imports, documentation

### Report Template
```markdown
# Cloud Agent X: [Module Name]

## Summary
[2-3 sentences describing what you accomplished]

## Files Modified
- `path/to/file.py` - [description of changes]

## Issues Fixed

### P0: Critical
1. **Issue**: [description]
   - **Location**: `file.py:123`
   - **Fix**: [what you did]
   - **Impact**: [measurable improvement]

### P1: Important
[Same format]

### P2: Nice-to-have
[Same format]

## Metrics
- **Files Modified**: X
- **Lines Added**: +X
- **Lines Removed**: -X
- **Net Change**: -X lines (Y% reduction)
- **Time Spent**: X hours

## Testing
- ✅ Linting: `bash ~/portfolio-ai/scripts/lint.sh` passed
- ✅ Tests: All X tests passed
- ✅ Manual: [brief description]

## Notes
[Any issues, blockers, or recommendations]
```

---

## Example Workflow

### Agent 1 starts:
```bash
cd /home/user/portfolio-ai
git fetch origin <SETUP_BRANCH>
git checkout origin/<SETUP_BRANCH> -- AGENT-INSTRUCTIONS.md
git checkout <WORKING_BRANCH>
git pull origin <WORKING_BRANCH>
```

Read files → Fix issues → Test → Commit → Push → Report

### All 5 agents can work in parallel with ZERO conflicts because:
- Each agent owns different files
- No file overlap between agents
- Each pushes to same branch (git handles auto-merge)

---

## BEGIN WORK

When user says: **"You are Cloud Agent X"**
1. Find your section above (1-5)
2. Use TodoWrite to create task list
3. Follow the Process steps
4. Generate report when done
5. Push to branch

---

## VERIFICATION & MERGE (Local Agent)

**After all 5 agents complete**, hand off to local agent with:

```
You are the Verification Agent.

Pull the distributed code review branch and verify all work:

1. Pull branch:
   cd /home/user/portfolio-ai
   git checkout <WORKING_BRANCH>
   git pull origin <WORKING_BRANCH>

2. Review commits:
   git log --oneline -20
   git diff main...HEAD --stat

3. Run full test suite:
   bash ~/portfolio-ai/scripts/lint.sh
   cd ~/portfolio-ai/backend && source .venv/bin/activate && pytest tests/ -v

4. Restart and verify services:
   bash ~/portfolio-ai/scripts/restart.sh
   sleep 10
   bash ~/portfolio-ai/scripts/status.sh

5. Manual smoke test:
   - Visit http://192.168.8.233:3000
   - Test each module (market, watchlist, portfolio, news, status)

6. If all pass, merge to main:
   git checkout main
   git merge <WORKING_BRANCH>
   git push origin main

7. Generate final report with:
   - Total commits from all agents
   - Lines changed (added/removed)
   - Test results
   - Any issues found
```

**Expected outcome:**
- All 508+ tests passing
- All linting/mypy checks passing
- Services healthy
- Clean merge to main

**Good luck!** 🚀
```

**IMPORTANT:** Replace `<SETUP_BRANCH>` and `<WORKING_BRANCH>` with actual branch names throughout the file.

---

## Step 4: Commit and Push AGENT-INSTRUCTIONS.md

**Switch to YOUR setup branch** (you can push here):

```bash
git checkout <SETUP_BRANCH>
git add AGENT-INSTRUCTIONS.md
git commit -m "docs: add distributed code review agent instructions"
git push origin <SETUP_BRANCH>
```

**Verify the file is accessible:**
```bash
git fetch origin <SETUP_BRANCH>
git checkout origin/<SETUP_BRANCH> -- AGENT-INSTRUCTIONS.md
ls -la AGENT-INSTRUCTIONS.md
```

---

## Step 5: Tell User

Report to user:

```
✅ Setup Complete - Distributed Code Review System Ready

**File Location:**
- Branch: `<SETUP_BRANCH>`
- Path: `/home/user/portfolio-ai/AGENT-INSTRUCTIONS.md`
- Pushed to remote: ✅

**Launch Each Agent (1-5) with this prompt:**

```
You are Cloud Agent [1/2/3/4/5].

First, get the instructions:
cd /home/user/portfolio-ai
git fetch origin <SETUP_BRANCH>
git checkout origin/<SETUP_BRANCH> -- AGENT-INSTRUCTIONS.md
git checkout <WORKING_BRANCH>
git pull origin <WORKING_BRANCH>

Now read and execute:
Read /home/user/portfolio-ai/AGENT-INSTRUCTIONS.md and execute your tasks.
```

**Simplified one-liner:**
```
You are Cloud Agent X.
Run: cd /home/user/portfolio-ai && git fetch origin <SETUP_BRANCH> && git checkout origin/<SETUP_BRANCH> -- AGENT-INSTRUCTIONS.md && git checkout <WORKING_BRANCH> && git pull
Then read /home/user/portfolio-ai/AGENT-INSTRUCTIONS.md and execute.
```

**Module Summary:**
- Agent 1: Market Intelligence (market/*, api/market.py)
- Agent 2: Watchlist (watchlist/*, api/watchlist.py) [Has 1030-line file]
- Agent 3: Portfolio & Analytics (portfolio/*, analytics/*)
- Agent 4: News & Services (services/*, sources/*, ml/*, api/news.py) [Has 841-line file]
- Agent 5: Tasks & Infrastructure (tasks/*, utils/*, api/status.py) [Has 966-line file]

**Workflow:**
1. Launch 5 agents in parallel → All push to `<WORKING_BRANCH>`
2. After all complete → Launch verification agent → Tests & merge to main

Ready to launch! 🚀
```

---

## Step 6: Optional - Do Cleanup Work (If Tokens Available)

**If you have >50K tokens remaining after setup**, you can start working on code cleanup yourself!

Check your token usage, then:

```bash
# Pick the SIMPLEST module (usually Market or Portfolio)
# DO NOT pick modules with >800 line files (those need splitting)

# Example: Work on Market module
cd /home/user/portfolio-ai
git checkout <WORKING_BRANCH>
git pull origin <WORKING_BRANCH>

# Read the files
Read backend/app/api/market.py

# Fix issues:
# - Remove unused imports
# - Fix obvious N+1 queries
# - Add type hints
# - Clean dead code

# Test
bash ~/portfolio-ai/scripts/lint.sh
cd ~/portfolio-ai/backend && pytest tests/ -v

# Commit
git add <files>
git commit -m "chore(setup-agent): optimize market module"
git push origin <WORKING_BRANCH>
```

**Guidelines for optional work:**
- ✅ Only if >50K tokens remaining
- ✅ Pick simplest module (no >800 line files)
- ✅ Focus on quick wins (unused imports, dead code, obvious fixes)
- ✅ Test before committing
- ✅ Push to `<WORKING_BRANCH>` (same branch as other agents)
- ❌ Don't start if <50K tokens (save for agents)
- ❌ Don't tackle file splitting (leave for dedicated agents)

This gives you a head start on the cleanup! Other agents will handle the heavy lifting.

---

## Repeatable Process

For future code reviews, just:
1. Create two branches (setup branch + working branch)
2. Start new session with this prompt
3. Tell setup agent the branch names
4. Setup agent creates AGENT-INSTRUCTIONS.md
5. Launch 5 worker agents
6. Launch 1 verification agent
7. Merge to main

**Time estimate:**
- Setup: 15-30 min
- 5 agents in parallel: 2-4 hours each
- Verification: 30-60 min
- **Total wall time: ~4 hours (vs 20+ hours sequential)**

---

## BEGIN NOW

The user has given you this prompt. Follow the steps above to set up the distributed code review system.
