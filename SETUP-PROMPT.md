You are the Setup Agent for a distributed code review system.

Repository: /home/user/portfolio-ai
Branch: claude/code-review-011CV3yYsKEbVuDcMNAiKG56

## Mission

Analyze the codebase and create ONE file (AGENT-INSTRUCTIONS.md) that contains instructions for 5 parallel agents to clean the code with zero merge conflicts.

## Step 1: Analyze Structure

```bash
cd /home/user/portfolio-ai
git checkout claude/code-review-011CV3yYsKEbVuDcMNAiKG56
```

Find:
- All modules in backend/app/ (market, watchlist, portfolio, services, tasks, utils)
- All components in frontend/components/
- Files >800 lines (need splitting)
- N+1 queries, duplicate code

## Step 2: Create Module Assignments

Divide codebase into 5 modules with ZERO file overlap:

Agent 1: Market (app/market/*, api/market.py, components/market/*)
Agent 2: Watchlist (app/watchlist/*, api/watchlist.py, components/watchlist/*)
Agent 3: Portfolio (app/portfolio/*, app/analytics/*, components/portfolio/*)
Agent 4: News (app/services/*, app/sources/*, app/ml/*)
Agent 5: Infrastructure (app/tasks/*, app/utils/*, app/storage/*, api/status.py, api/health.py)

## Step 3: Create AGENT-INSTRUCTIONS.md

Create file: /home/user/portfolio-ai/AGENT-INSTRUCTIONS.md

With this EXACT structure:

```markdown
# Code Review Agent Instructions

**USER WILL TELL YOU: "You are Cloud Agent X" - Find your section below.**

Branch: claude/code-review-011CV3yYsKEbVuDcMNAiKG56

## Cloud Agent 1: Market Intelligence

**Files YOU own:**
- backend/app/market/ (ALL files)
- backend/app/api/market.py
- frontend/components/market/ (ALL files)
- frontend/lib/hooks/useMarketIntelligence.ts

**Tasks:**
- Fix N+1 query at market.py:359 (11 queries → 1)
- Remove duplicate sector mapping at line 191
- Clean unused imports
- Optimize DB queries

**DO NOT TOUCH:** watchlist/*, portfolio/*, services/*, tasks/*, utils/*

---

## Cloud Agent 2: Watchlist

**Files YOU own:**
- backend/app/watchlist/ (ALL files)
- backend/app/api/watchlist.py
- frontend/components/watchlist/ (ALL files)

**Tasks:**
- Split refresh_processor.py (1030 lines → 3 files)
- Optimize watchlist_service.py queries
- Remove duplicate scoring logic
- Clean dead code

**DO NOT TOUCH:** market/*, portfolio/*, services/*, tasks/*, utils/*

---

## Cloud Agent 3: Portfolio & Analytics

**Files YOU own:**
- backend/app/portfolio/ (ALL files)
- backend/app/analytics/ (ALL files)
- backend/app/api/portfolio.py
- backend/app/api/analytics.py
- backend/app/api/ideas.py
- frontend/components/portfolio/ (ALL files)

**Tasks:**
- Remove SELECT * in manager.py
- Optimize analytics calculations
- Optimize paper_trading.py
- Clean dead code

**DO NOT TOUCH:** market/*, watchlist/*, services/*, tasks/*, utils/*

---

## Cloud Agent 4: News & Services

**Files YOU own:**
- backend/app/services/ (ALL files)
- backend/app/sources/ (ALL files)
- backend/app/ml/ (ALL files)
- backend/app/api/news.py
- frontend/components/shared/UnifiedNewsIntelligence*.tsx

**Tasks:**
- Refactor news_service.py (841 lines)
- Consolidate source fetchers
- Address TODOs at lines 131, 252
- Clean dead code

**DO NOT TOUCH:** market/*, watchlist/*, portfolio/*, tasks/*, utils/*

---

## Cloud Agent 5: Tasks & Infrastructure

**Files YOU own:**
- backend/app/tasks/ (ALL files)
- backend/app/utils/ (ALL files)
- backend/app/storage/ (ALL files)
- backend/app/api/health.py
- backend/app/api/status.py
- backend/app/api/maintenance.py
- backend/app/api/celery_endpoints.py
- backend/app/celery_app.py
- frontend/components/status/ (ALL files)

**Tasks:**
- Optimize Fear & Greed calc (indicator_tasks.py:286, 4 queries → 1)
- Refactor status.py (966 lines)
- Consolidate logging patterns
- Clean dead code

**DO NOT TOUCH:** market/*, watchlist/*, portfolio/*, services/*

---

## Instructions (ALL AGENTS)

### Setup
```bash
cd /home/user/portfolio-ai
git checkout claude/code-review-011CV3yYsKEbVuDcMNAiKG56
git pull
```

### Process
1. TodoWrite: Create task list
2. Read YOUR files only
3. Fix P0 → P1 → P2 issues
4. Test: bash ~/portfolio-ai/scripts/lint.sh
5. Commit: git commit -m "chore(cloud-X): summary"
6. Push: git push origin claude/code-review-011CV3yYsKEbVuDcMNAiKG56
7. Report: Generate markdown report

### Rules
✅ Edit ONLY your files
✅ Test before commit
❌ NEVER touch other agents' files

### Report Template
```
# Cloud Agent X: Module

## Summary
[2-3 sentences]

## Files Modified
- file.py - changes

## Issues Fixed
### P0: Critical
1. Issue - file:line - fix - impact

## Metrics
- Files: X
- Lines: -X
- Time: X hrs
```

BEGIN WORK
```

## Step 4: Commit

```bash
git add AGENT-INSTRUCTIONS.md
git commit -m "docs: agent instructions"
git push origin claude/code-review-011CV3yYsKEbVuDcMNAiKG56
```

## Step 5: Tell User

"✅ Created AGENT-INSTRUCTIONS.md

**File Location:**
- Branch: `claude/setup-distributed-review-011CV46RFyLxWXimzAzHFKuN`
- Path: `/home/user/portfolio-ai/AGENT-INSTRUCTIONS.md`
- Pushed to remote: ✅

**Launch Each Agent (1-5) with:**

```
You are Cloud Agent [1/2/3/4/5].

First, get the instructions:
cd /home/user/portfolio-ai
git fetch origin claude/setup-distributed-review-011CV46RFyLxWXimzAzHFKuN
git checkout origin/claude/setup-distributed-review-011CV46RFyLxWXimzAzHFKuN -- AGENT-INSTRUCTIONS.md
git checkout claude/code-review-011CV3yYsKEbVuDcMNAiKG56
git pull origin claude/code-review-011CV3yYsKEbVuDcMNAiKG56

Now read and execute:
Read /home/user/portfolio-ai/AGENT-INSTRUCTIONS.md and execute your tasks.
```

**Simplified version:**
```
You are Cloud Agent X.
Run: cd /home/user/portfolio-ai && git fetch origin claude/setup-distributed-review-011CV46RFyLxWXimzAzHFKuN && git checkout origin/claude/setup-distributed-review-011CV46RFyLxWXimzAzHFKuN -- AGENT-INSTRUCTIONS.md && git checkout claude/code-review-011CV3yYsKEbVuDcMNAiKG56 && git pull
Then read /home/user/portfolio-ai/AGENT-INSTRUCTIONS.md and execute.
```"

## BEGIN NOW
