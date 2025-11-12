# Setup Agent - Distributed Code Review System

You are the Setup Agent. Read SETUP-PROMPT.md from main and execute.

**Your mission:** Create infrastructure for 5 parallel code review agents with zero merge conflicts.

---

## ⚠️ CRITICAL: Cloud Agent Constraints

**YOU (Setup Agent) and ALL Worker Agents (1-5) are Cloud Agents with LIMITED capabilities:**

### ✅ Cloud Agents CAN:
- Read files (Read, Glob, Grep tools)
- Edit files (Edit, Write tools)
- Static analysis (code review, pattern detection)
- Git operations (checkout, commit, push, pull, log, diff, status)
- Create documentation and reports

### ❌ Cloud Agents CANNOT:
- **Run tests** (`pytest`, `npm test`, etc.) - No test execution
- **Start/restart services** (`bash ~/portfolio-ai/scripts/restart.sh`) - No service management
- **Run database migrations** - No database access
- **Execute application code** (`python`, `node`, etc.) - No runtime execution
- **Check service status** (except via git log/status) - No system inspection
- **Access .venv/** - Virtual environment not available
- **Run linters/formatters** (`ruff`, `mypy`, `eslint`) - Tools not installed

### 🎯 Cloud Agent Workflow:
1. **Read** code to understand issues
2. **Edit** code to fix issues (based on static analysis)
3. **Commit** changes with clear messages
4. **Trust** that fixes are correct (no local verification possible)
5. **Report** what you did for local verification agent

### 🖥️ Local Verification Agent (Step 7):
- **ONLY the Verification Agent** can run tests, restart services, and verify changes
- Verification Agent runs on local dev machine with full capabilities
- All 5 worker agents submit code blindly, verification agent validates

**IMPORTANT:** Do NOT attempt to run tests or services. Focus on code quality through reading and editing only.

---

## Step 1: Create Working Branch

All worker agents need a shared branch to collaborate on:

```bash
cd /home/user/portfolio-ai
git checkout main
git pull origin main

# Create working branch for the 5 worker agents
WORKING_BRANCH="claude/code-review-$(date +%Y%m%d-%H%M%S)"
git checkout -b "$WORKING_BRANCH"
git push -u origin "$WORKING_BRANCH"

echo "Working branch created: $WORKING_BRANCH"
```

**Save this branch name** - you'll tell users to launch agents with it.

---

## Step 2: Analyze Codebase

Find issues to assign to agents:

### Backend
```bash
find backend/app -type f -name "*.py" -exec wc -l {} + | sort -rn | head -20
```

**Look for:**
- Files >800 lines (P0: must split)
- Files 500-800 lines (P1: optimize)
- N+1 queries, SELECT *, duplicate code

### Frontend
```bash
find frontend/components -type f \( -name "*.tsx" -o -name "*.ts" \) -exec wc -l {} + | sort -rn | head -20
```

**Look for:**
- Components >800 lines (P0: must split)
- Duplicate patterns, unused imports

---

## Step 3: Create Module Assignments (Zero Overlap)

Divide into 5 modules with **ZERO file overlap**:

**Agent 1: Market Intelligence**
- backend/app/market/*
- backend/app/api/market.py
- frontend/components/market/*

**Agent 2: Watchlist**
- backend/app/watchlist/*
- backend/app/api/watchlist.py
- frontend/components/watchlist/*
- frontend/components/settings/*WatchlistSettings*.tsx

**Agent 3: Portfolio & Analytics**
- backend/app/portfolio/*
- backend/app/analytics/*
- backend/app/api/portfolio.py
- backend/app/api/analytics.py
- backend/app/api/ideas.py
- frontend/components/portfolio/*

**Agent 4: News & Services**
- backend/app/services/*
- backend/app/sources/*
- backend/app/ml/*
- backend/app/api/news.py
- frontend/components/shared/UnifiedNewsIntelligence*.tsx

**Agent 5: Tasks & Infrastructure**
- backend/app/tasks/*
- backend/app/utils/*
- backend/app/storage/*
- backend/app/api/health.py
- backend/app/api/status.py
- backend/app/api/maintenance.py
- backend/app/celery_app.py
- frontend/components/status/*

---

## Step 4: Create AGENT-INSTRUCTIONS.md

Create detailed instructions with your findings:

```markdown
# Code Review Agent Instructions

**USER WILL TELL YOU: "You are Cloud Agent X" - Find your section below.**

Working Branch: $WORKING_BRANCH
Setup Branch: <YOUR_CURRENT_BRANCH>

## Cloud Agent 1: Market Intelligence

**Files YOU own:**
- backend/app/market/* (ALL files)
- backend/app/api/market.py (<XXX> lines)
- frontend/components/market/* (ALL files)

**Tasks:**
- P0: [Critical issues you found]
- P1: [Important issues you found]
- P2: [Nice-to-have cleanups]

**DO NOT TOUCH:** watchlist/*, portfolio/*, services/*, tasks/*, utils/*

---

[Repeat for Agents 2-5 with actual findings from Step 2]

---

## Instructions (ALL AGENTS)

### Setup
```bash
cd /home/user/portfolio-ai
git checkout $WORKING_BRANCH
git pull origin $WORKING_BRANCH
```

### Process
1. **TodoWrite**: Create task list from P0/P1/P2 above
2. **Read YOUR files only**: Don't touch other agents' files
3. **Fix in order**: P0 → P1 → P2
4. **Review your changes**: Use static analysis (read the code, check logic)
5. **Commit frequently**:
   ```bash
   git add <files>
   git commit -m "chore(agent-X): brief description"
   ```
6. **Push when done**:
   ```bash
   git push origin $WORKING_BRANCH
   ```
7. **Generate report** (see template below)

### Rules (Cloud Agent Constraints)
✅ Edit ONLY your assigned files
✅ Review changes carefully (no testing available)
✅ Small commits (one logical change)
✅ Trust your static analysis
❌ NEVER touch other agents' files
❌ NEVER attempt to run tests (you can't)
❌ NEVER attempt to restart services (you can't)
❌ NEVER use runtime verification (Verification Agent will test)

### Priority Levels
- **P0 (Critical)**: Files >800 lines, N+1 queries, SELECT *, security issues
- **P1 (Important)**: Files 500-800 lines, duplicate code, missing types
- **P2 (Nice-to-have)**: Dead code, TODOs, unused imports

### Report Template
```markdown
# Agent X: [Module Name]

## Summary
[2-3 sentences]

## Files Modified
- `file.py` - [changes]

## Issues Fixed
### P0: Critical
1. **Issue**: [description]
   - **Location**: file.py:123
   - **Fix**: [what you did]
   - **Impact**: [measurable improvement]

### P1: Important
[same format]

### P2: Nice-to-have
[same format]

## Metrics
- Files Modified: X
- Lines Added: +X
- Lines Removed: -X
- Net Change: -X lines (Y% reduction)

## Testing (Cloud Agent - Static Analysis Only)
- ✅ Code reviewed for correctness
- ✅ Logic verified through static analysis
- ⏳ Awaiting Verification Agent for runtime testing

## Notes
[Issues, blockers, recommendations for Verification Agent]
```

---

## Example: Agent 1 starts (Cloud Agent)
```bash
cd /home/user/portfolio-ai
git checkout $WORKING_BRANCH
git pull
```

Read files → Fix issues → Review changes → Commit → Push → Report

**Note:** No testing step - Cloud agents rely on static analysis only.

---

## VERIFICATION & MERGE (Local Agent ONLY)

**⚠️ CRITICAL: This step requires a LOCAL agent with full capabilities (tests, services, database).**

**After all 5 agents complete:**

```
You are the Verification Agent running on LOCAL dev machine.
Branch: $WORKING_BRANCH
Environment: Local Dev (full capabilities)

1. Pull and review:
   cd /home/user/portfolio-ai
   git checkout $WORKING_BRANCH
   git pull origin $WORKING_BRANCH
   git log --oneline -20
   git diff main...HEAD --stat

2. Test everything:
   bash ~/portfolio-ai/scripts/lint.sh
   cd ~/portfolio-ai/backend && source .venv/bin/activate && pytest tests/ -v

3. Verify services:
   bash ~/portfolio-ai/scripts/restart.sh
   sleep 10
   bash ~/portfolio-ai/scripts/status.sh

4. Manual smoke test:
   http://192.168.8.233:3000
   Test: market, watchlist, portfolio, news, status pages

5. If all pass:
   git checkout main
   git merge $WORKING_BRANCH
   git push origin main

6. Report:
   - Total commits
   - Lines changed
   - Test results
   - Issues found
```

**Good luck!** 🚀
```

**Important:** Replace `$WORKING_BRANCH` with actual branch name from Step 1.

---

## Step 5: Commit AGENT-INSTRUCTIONS.md

Commit to YOUR branch (the setup branch):

```bash
git add AGENT-INSTRUCTIONS.md
git commit -m "docs: distributed code review instructions"
git push origin HEAD
```

---

## Step 6: Tell User

Report completion:

```
✅ Setup Complete - Distributed Code Review Ready

**Working Branch:** `<WORKING_BRANCH>`
**Setup Branch:** `<YOUR_BRANCH>`
**Instructions:** AGENT-INSTRUCTIONS.md (committed to setup branch)

**Launch Each Worker Agent (1-5):**

```
You are Cloud Agent X.

cd /home/user/portfolio-ai
git fetch origin <YOUR_SETUP_BRANCH>
git checkout origin/<YOUR_SETUP_BRANCH> -- AGENT-INSTRUCTIONS.md
git checkout <WORKING_BRANCH>
git pull origin <WORKING_BRANCH>

Read /home/user/portfolio-ai/AGENT-INSTRUCTIONS.md and execute.
```

**Module Summary:**
- Agent 1: Market (<size>L market.py)
- Agent 2: Watchlist (<size>L refresh_processor.py - NEEDS SPLIT)
- Agent 3: Portfolio (<size>L paper_trading.py)
- Agent 4: News (<size>L news_service.py - NEEDS SPLIT)
- Agent 5: Infrastructure (<size>L status.py - NEEDS SPLIT)

**Workflow:**
1. Launch 5 **Cloud** worker agents (1-5) → All push to `<WORKING_BRANCH>`
   - Cloud agents: Code review and editing only (no tests/services)
   - Work in parallel on isolated modules
2. After all complete → Launch **Local** verification agent
   - Local agent: Full testing, service restart, validation
3. Verification agent → Tests & merges to main

**Agent Environment Summary:**
- **Setup Agent (You)**: Cloud - Creates infrastructure, no testing
- **Worker Agents (1-5)**: Cloud - Code fixes only, no testing
- **Verification Agent**: Local - Full testing and merge

**Ready to launch!** 🚀
```

---

## Step 7: Optional Cleanup (If Tokens Available)

**If you have >80K tokens remaining**, pick a simple module and start cleaning:

```bash
# Pick module with no >800 line files (usually Market)
cd /home/user/portfolio-ai
git checkout <WORKING_BRANCH>

# Fix quick wins (static analysis only):
# - Remove unused imports
# - Fix obvious N+1 queries
# - Add type hints
# - Clean dead code

# Review your changes carefully (no testing available)
# Commit with confidence based on static analysis
git add <files>
git commit -m "chore(setup-agent): cleanup <module>"
git push origin <WORKING_BRANCH>
```

**Note:** As a Cloud Agent, you can't run tests. Trust your static analysis. The Verification Agent will test everything.

This gives agents a head start!

---

## Repeatable Process

**Future code reviews:**

1. Start new Claude session (auto-creates setup branch)
2. Say: "Read SETUP-PROMPT.md from main and execute"
3. Setup agent creates working branch + instructions
4. Launch 5 worker agents
5. Launch verification agent
6. Merge to main

**Estimated time:** ~4 hours parallel (vs 20+ sequential)

---

## BEGIN NOW

Execute steps 1-6 above. Be thorough in analysis (Step 2) so agents have clear tasks.
