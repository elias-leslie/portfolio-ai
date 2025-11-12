# Setup Agent - Distributed Code Review System

You are the Setup Agent. Read SETUP-PROMPT.md from main and execute.

**Your mission:** Create infrastructure for 5 parallel code review agents with zero merge conflicts.

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
4. **Test each fix**:
   ```bash
   bash ~/portfolio-ai/scripts/lint.sh
   cd ~/portfolio-ai/backend && pytest tests/ -v
   ```
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

### Rules
✅ Edit ONLY your assigned files
✅ Test before every commit
✅ Small commits (one logical change)
❌ NEVER touch other agents' files
❌ NEVER skip testing
❌ NEVER use --no-verify

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

## Testing
- ✅ Lint passed
- ✅ All X tests passed
- ✅ Manual: [description]

## Notes
[Issues, blockers, recommendations]
```

---

## Example: Agent 1 starts
```bash
cd /home/user/portfolio-ai
git checkout $WORKING_BRANCH
git pull
```

Read files → Fix issues → Test → Commit → Push → Report

---

## VERIFICATION & MERGE (Local Agent)

**After all 5 agents complete:**

```
You are the Verification Agent.
Branch: $WORKING_BRANCH

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
1. Launch 5 worker agents → All push to `<WORKING_BRANCH>`
2. After all complete → Launch verification agent
3. Verification agent → Tests & merges to main

**Ready to launch!** 🚀
```

---

## Step 7: Optional Cleanup (If Tokens Available)

**If you have >80K tokens remaining**, pick a simple module and start cleaning:

```bash
# Pick module with no >800 line files (usually Market)
cd /home/user/portfolio-ai
git checkout <WORKING_BRANCH>

# Fix quick wins:
# - Remove unused imports
# - Fix obvious N+1 queries
# - Add type hints
# - Clean dead code

# Test
bash ~/portfolio-ai/scripts/lint.sh
cd backend && pytest tests/ -v

# Commit
git commit -m "chore(setup-agent): cleanup <module>"
git push origin <WORKING_BRANCH>
```

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
