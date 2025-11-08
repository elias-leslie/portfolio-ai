# Task List: Portfolio/Watchlist UI & Data Model Fixes

**Created**: 2025-11-07
**Updated**: 2025-11-07 (Corrected cloud capabilities - DOES have full source access)
**Status**: Pending Research
**Priority**: HIGH
**Environment**: Cloud Claude Code (sandbox, limited runtime environment)

---

## ⚠️ IMPORTANT: Cloud Environment Constraints

**This task is for a cloud Claude Code instance with limited environment access:**

✅ **You CAN:**
- **Read ALL source code** (full access to backend/, frontend/, docs/, all files)
- Search, grep, and analyze complete codebase structure
- Plan and design solutions
- Write/edit code files (frontend TypeScript/React, backend Python/FastAPI)
- Create git commits and branches
- Provide detailed implementation plans
- Use code analysis tools (ruff, mypy, eslint)

❌ **You CANNOT (or should avoid):**
- Run Python venv commands (they hang in sandbox)
- Start backend/frontend services
- Run tests (pytest, npm test, vitest)
- Execute database migrations
- Test API endpoints
- Use browser automation
- **ANY commands from these scripts**: restart.sh, start.sh, status.sh
- **ANY curl/http requests** to localhost or 192.168.8.233
- **ANY psql/database commands**
- **ANY npm/pip install or runtime commands**

**❌ EXAMPLES OF WHAT NOT TO RUN:**
```bash
# DON'T run these - they only work in dev environment:
source backend/.venv/bin/activate          # ❌ Hangs in sandbox
bash ~/portfolio-ai/scripts/restart.sh     # ❌ No dev environment access
pytest tests/                               # ❌ No venv in sandbox
npm test                                    # ❌ No runtime environment
curl http://localhost:8000/api/health      # ❌ No services running
psql -U portfolio_ai_user -d portfolio_ai  # ❌ No database access
python backend/app/main.py                 # ❌ No runtime execution
```

**✅ INSTEAD, DO THIS:**
```bash
# Read code to understand what to change:
cat backend/app/api/portfolio.py           # ✅ Read files
grep -r "account_id" frontend/             # ✅ Search code
git status                                  # ✅ Check changes
git add -A && git commit                   # ✅ Commit code
```

**Your Workflow:**
1. **Research thoroughly** - Read code, understand architecture, document findings
2. **Expand task list** - Add detailed subtasks based on your research
3. **Implement what you can** - Write code changes (no need to test)
4. **Commit to git** - Create feature branch, commit all changes
5. **Provide handoff** - Give user git commands and testing steps for dev environment

**When Done:**
- Commit all changes to a new branch: `git checkout -b feature/portfolio-watchlist-fixes`
- Provide: (1) git pull command, (2) testing steps, (3) what's left to do
- User will pull your branch and continue in dev environment with full testing

---

## Overview

Fix data model confusion and UI issues with portfolio accounts, watchlist items, and news filtering.

**Key Issues**:
- Watchlist items accidentally tied to portfolio accounts (should be independent)
- Portfolio UI shows accounts and positions separately (should be nested/expandable)
- News page missing portfolio filter option
- CASCADE delete caused watchlist data loss

---

## Tasks

### 1. Research & Analysis (DO THIS FIRST)

**Objective**: Fully understand current implementation and flesh out detailed task list

- [ ] Research current data model relationships
  - How are watchlist_items related to accounts? (currently: account_id FK)
  - How are portfolio positions related to accounts? (expected relationship)
  - What is the actual intended use case for each?
- [ ] Test current UI behavior
  - Portfolio page: How do accounts and positions display?
  - Watchlist page: How does it use account_id?
  - News page: Current filtering options
- [ ] Identify all affected files
  - Backend: API endpoints, data models, database schema
  - Frontend: Pages, components, API clients
- [ ] Document findings and create detailed implementation plan
- [ ] Expand this task list with specific subtasks based on findings

**Output**: Updated task list with detailed subtasks for items 2-4 below

---

### 2. Fix Portfolio Page UI

**Goal**: Accounts should contain expandable positions (not separate cards)

**Expected Behavior**:
- User adds account first (e.g., "My IRA", "Taxable Account")
- User adds positions under that account
- UI shows accounts with expand/collapse to show/hide positions
- Positions are ALWAYS associated with an account

**Current Issues**:
- Accounts and positions shown as separate cards
- Unclear relationship in UI

**Research Needed** (Task 1 above):
- Current component structure
- How positions are currently displayed
- What data is being fetched

---

### 3. Fix Watchlist/Portfolio Data Model Separation

**Goal**: Clarify that watchlist items are INDEPENDENT of accounts

**Watchlist**:
- Stocks you're monitoring (not owned)
- Should NOT be tied to portfolio accounts
- Global list, not per-account

**Portfolio Positions**:
- Stocks you OWN in specific accounts
- MUST be tied to portfolio accounts
- Account-specific (IRA has different positions than Taxable)

**Current Issues**:
- `watchlist_items.account_id` exists but shouldn't (OR should be nullable/ignored)
- CASCADE delete removed watchlist when deleting accounts
- Confusion between "monitoring" vs "owning"

**Research Needed** (Task 1 above):
- Check if positions table has proper account relationship
- Determine best approach: remove watchlist.account_id OR make it nullable/default
- Create migration to fix schema

---

### 4. Add Portfolio Filter to News Page

**Goal**: News page should have 3 toggle options

**Expected Filters**:
- [ ] Market (current default)
- [ ] My Watchlist (current option)
- [ ] My Portfolio (NEW - show news for owned stocks)

**Implementation**:
- Fetch portfolio positions
- Get unique symbols from positions
- Filter news by those symbols
- Add toggle/tab UI component

**Research Needed** (Task 1 above):
- Current news filtering implementation
- How to fetch portfolio symbols efficiently
- UI component design (tabs vs toggle vs dropdown)

---

## Current State (Fixed Temporarily)

**What Was Fixed This Session**:
- ✅ Changed CASCADE delete to RESTRICT (prevents future data loss)
- ✅ Restored 24 watchlist items from news cache
- ✅ Recreated "default" account

**What Still Needs Work**:
- ❌ Portfolio UI still shows accounts/positions separately
- ❌ Watchlist still has account_id (shouldn't, or should be ignored)
- ❌ News page missing portfolio filter
- ❌ Data model confusion not fully resolved

---

## Notes

- CASCADE delete was ON DELETE CASCADE - changed to RESTRICT
- Frontend hardcodes `accountId = "default"` with TODO comment
- Watchlist items don't actually need account_id (remnant of planned multi-user feature)
- Portfolio positions DO need account_id (core feature)

---

## Success Criteria

- [ ] Portfolio page shows accounts with nested expandable positions
- [ ] Watchlist is independent of portfolio accounts
- [ ] Deleting portfolio accounts doesn't affect watchlist
- [ ] News page has Market/Watchlist/Portfolio filters
- [ ] Data model clearly separates "monitoring" (watchlist) from "owning" (positions)
- [ ] All code changes committed to feature branch
- [ ] Testing steps documented for dev environment

---

## Handoff Instructions (When Complete)

**Before finishing, do this:**

1. **Commit all changes**:
   ```bash
   git checkout -b feature/portfolio-watchlist-fixes
   git add -A
   git commit -m "feat: portfolio/watchlist UI and data model fixes

   - Portfolio UI: Accounts with expandable positions
   - Watchlist: Independent of portfolio accounts
   - News page: Add portfolio filter option
   - Data model: Separate monitoring vs owning

   See tasks/tasks-ui-portfolio-watchlist-fixes.md for details"
   ```

2. **Provide to user**:
   - Git branch name: `feature/portfolio-watchlist-fixes`
   - Pull command: `git fetch origin && git checkout feature/portfolio-watchlist-fixes`
   - List of files changed
   - Testing steps (what to test in dev environment)
   - What's implemented vs what needs dev environment to complete

3. **Testing Steps Template**:
   ```
   Testing in Dev Environment:
   1. Start services: bash ~/portfolio-ai/scripts/restart.sh
   2. Test portfolio page: http://192.168.8.233:3000/portfolio
      - Verify accounts show with expand/collapse
      - Add position under account, verify nesting
   3. Test watchlist: http://192.168.8.233:3000/watchlist
      - Delete portfolio account, verify watchlist unchanged
   4. Test news page: http://192.168.8.233:3000/news
      - Verify Market/Watchlist/Portfolio toggle exists
   5. Database verification:
      - Check FK constraint (should be RESTRICT or removed)
      - Verify positions.account_id exists and working
   ```

**What Cannot Be Done in Cloud**:
- Database migrations (provide SQL script instead)
- Running tests (provide test commands to run)
- Service verification (describe expected behavior)
- Browser testing (describe UI changes made)
