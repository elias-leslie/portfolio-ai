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
- Run runtime tests (pytest, npm test, vitest - need running services)
- Execute database migrations (provide SQL scripts instead)
- Test API endpoints (no services running)
- Use browser automation (no services running)
- **ANY commands from these scripts**: restart.sh, start.sh, status.sh
- **ANY curl/http requests** to localhost or 192.168.8.233
- **ANY psql/database commands**
- **ANY npm/pip install or runtime commands**

✅ **You SHOULD run (static analysis - no services needed):**
- `ruff check backend/` - Python linting
- `ruff format --check backend/` - Python formatting check
- `mypy backend/app/` - Python type checking
- `npx eslint frontend/` - TypeScript/React linting (if needed)

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

# Run static analysis after making changes:
ruff check backend/                         # ✅ Check Python code quality
ruff format backend/                        # ✅ Format Python code
mypy backend/app/                           # ✅ Check Python types

# Commit your work:
git status                                  # ✅ Check changes
git add -A && git commit                   # ✅ Commit code
```

**Your Workflow:**
1. **Research thoroughly** - Read code, understand architecture, document findings
2. **Expand task list** - Add detailed subtasks based on your research
3. **Implement code changes** - Write/edit Python and TypeScript files
4. **Run static analysis** - Use ruff, mypy, eslint to catch issues early
5. **Fix any linting errors** - Clean code before committing
6. **Commit to git** - Create feature branch, commit all changes
7. **Provide handoff** - Give user git commands and testing steps for dev environment

**When Done:**
- Work on whatever branch cloud session created (check `git branch`)
- Commit all changes to that branch
- Provide: (1) branch name, (2) testing steps, (3) what's left to do
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

- [x] Research current data model relationships
  - Read backend/app/storage/ files for database schema
  - How are watchlist_items related to accounts? (currently: account_id FK)
  - How are portfolio positions related to accounts? (expected relationship)
  - What is the actual intended use case for each?
- [x] Read and analyze current UI code
  - Portfolio page: Read frontend/app/portfolio/page.tsx and components
  - Watchlist page: Read frontend/app/watchlist/page.tsx
  - News page: Read frontend/app/news/page.tsx - current filtering implementation
- [x] Identify all affected files
  - Backend: API endpoints, data models, database schema
  - Frontend: Pages, components, API clients
  - Make comprehensive list with file paths
- [x] Document findings and create detailed implementation plan
  - What currently exists vs what needs to change
  - Specific code changes per file
  - Any database migrations needed (provide SQL)
- [x] Expand this task list with specific subtasks based on findings

**Output**: ✅ COMPLETED - See `tasks/watchlist-portfolio-fixes-findings.md` for comprehensive analysis

**Key Findings**:
- watchlist_items has account_id FK with CASCADE delete (causes data loss)
- All watchlist API endpoints require account_id parameter
- Frontend hardcodes `accountId = "default"` with TODO comment
- Portfolio page shows AccountsCard + PositionTable as separate sections
- News page only has "market" and "watchlist" views (missing "portfolio")

---

### 2. Fix Portfolio Page UI

**Goal**: Accounts should contain expandable positions (not separate cards)

**Expected Behavior**:
- User adds account first (e.g., "My IRA", "Taxable Account")
- User adds positions under that account
- UI shows accounts with expand/collapse to show/hide positions
- Positions are ALWAYS associated with an account

**Current Issues**:
- Accounts and positions shown as separate cards (AccountsCard + PositionTable)
- Unclear relationship in UI
- No visual hierarchy showing positions belong to accounts

**Detailed Subtasks**:

#### 2.1 Create new AccountsWithPositions component
- [ ] Create `frontend/components/portfolio/AccountsWithPositions.tsx`
- [ ] Use shadcn/ui Accordion component for expand/collapse
- [ ] Fetch accounts via `useAccounts()` hook
- [ ] Fetch positions via `usePortfolio()` hook
- [ ] Group positions by account_id using JavaScript groupBy or reduce
- [ ] Show each account as accordion item with:
  - Account name and type in header
  - Total value of positions in that account
  - Expand/collapse icon
  - Delete account button with confirmation
- [ ] When expanded, show positions table for that account
- [ ] Handle empty state (account with no positions)
- [ ] Add position button (within expanded account context)

#### 2.2 Update Portfolio page to use new component
- [ ] Edit `frontend/app/portfolio/page.tsx`
- [ ] Replace separate `<AccountsCard />` and `<PositionTable />` with `<AccountsWithPositions />`
- [ ] Keep PortfolioOverview component (analytics at top)
- [ ] Update "Add Position" dialog to require account selection first
- [ ] Remove or repurpose old components if no longer needed

#### 2.3 Update styling and UX
- [ ] Ensure accordion has clear expand/collapse affordances
- [ ] Match existing design system colors/spacing
- [ ] Add loading states for account/position fetching
- [ ] Add error states for failed fetches
- [ ] Mobile responsive design

---

### 3. Fix Watchlist/Portfolio Data Model Separation

**Goal**: Clarify that watchlist items are INDEPENDENT of accounts

**Watchlist**:
- Stocks you're monitoring (not owned)
- Should NOT be tied to portfolio accounts
- Global list, not per-account

**Portfolio Positions**:
- Stocks you OWN in specific accounts
- MUST be tied to portfolio accounts (already correct ✅)
- Account-specific (IRA has different positions than Taxable)

**Current Issues**:
- `watchlist_items.account_id` column exists with FK constraint (should be removed)
- CASCADE delete causes data loss when deleting accounts
- All API endpoints require account_id parameter
- Frontend hardcodes `accountId = "default"`

**Detailed Subtasks**:

#### 3.1 Database migration
- [ ] Create `backend/migrations/018_watchlist_account_separation.sql`
- [ ] SQL to drop FK constraint: `watchlist_items_account_id_fkey`
- [ ] SQL to drop unique constraint: `watchlist_items_account_id_symbol_key`
- [ ] SQL to drop column: `account_id`
- [ ] SQL to add new unique constraint: `watchlist_items_symbol_key UNIQUE (symbol)`
- [ ] **NOTE**: Provide SQL script only (cloud can't run migrations)
- [ ] Handle duplicate symbols if they exist across accounts (keep most recent)

#### 3.2 Backend API - Update watchlist endpoints
- [ ] Edit `backend/app/api/watchlist.py`
  - Remove `account_id: str` parameter from `list_watchlist_items()` (line 51)
  - Remove `account_id` from CREATE endpoint (line 74)
  - Remove account_id from all SQL queries (lines 89-94, 106-110, 428-432)
  - Update `schedule_new_ticker_tasks()` calls to not pass account_id (line 116)

#### 3.3 Backend - Update data models
- [ ] Edit `backend/app/watchlist/response_builders.py`
  - Remove `account_id` field from `WatchlistItemCreate` model
  - Remove `account_id` field from `WatchlistItemResponse` model
  - Update `build_watchlist_item_responses()` if needed

#### 3.4 Backend - Update service layer
- [ ] Edit `backend/app/watchlist/watchlist_service.py`
  - Remove `account_id` parameter from `get_items_with_scores()`
  - Update all queries to not filter by account_id
  - Remove account_id from any other methods

#### 3.5 Backend - Update background tasks
- [ ] Edit `backend/app/watchlist/background_tasks.py`
  - Remove `account_id` parameter from `schedule_new_ticker_tasks()`
  - Update function signature and calls

#### 3.6 Frontend API client - Remove account_id
- [ ] Edit `frontend/lib/api/watchlist.ts`
  - Remove `account_id` from API fetch URLs
  - Remove `account_id` from request bodies
  - Update TypeScript types to remove account_id fields

#### 3.7 Frontend hooks - Remove account_id parameter
- [ ] Edit `frontend/lib/hooks/useWatchlist.ts`
  - Remove `accountId` parameter from `useWatchlist()` hook
  - Remove `accountId` parameter from `useRefreshWatchlist()` hook
  - Update all hook implementations

#### 3.8 Frontend watchlist page - Remove hardcoded account
- [ ] Edit `frontend/app/watchlist/page.tsx`
  - Remove `const [accountId] = useState("default")` (line 22)
  - Remove TODO comment
  - Update `useWatchlist()` call to not pass accountId (line 25)
  - Update `refreshMutation.mutate()` call to not pass accountId (line 42)

#### 3.9 Frontend components - Remove account_id props
- [ ] Update `frontend/components/watchlist/AddTickerModal.tsx` (remove accountId prop)
- [ ] Update `frontend/components/watchlist/WatchlistTable.tsx` (remove accountId prop)
- [ ] Update any other watchlist components that reference accountId

---

### 4. Add Portfolio Filter to News Page

**Goal**: News page should have 3 toggle options

**Expected Filters**:
- Market (current default - broad market news)
- My Watchlist (current option - news for watchlist symbols)
- My Portfolio (NEW - news for owned stocks in portfolio)

**Current Implementation**:
- Line 507: Only has "market" | "watchlist" views
- Lines 562-581: Toggle shows "Market" and "My Watchlist" buttons
- Uses `useWatchlistNews(accountId)` hook for watchlist filtering

**Detailed Subtasks**:

#### 4.1 Add portfolio news hook
- [ ] Edit `frontend/lib/hooks/useNews.ts`
- [ ] Create new hook `usePortfolioNews()`
- [ ] Inside hook:
  - Use `usePortfolio()` to fetch positions
  - Extract unique symbols: `const symbols = [...new Set(positions.map(p => p.symbol))]`
  - Use similar logic to `useWatchlistNews` but with portfolio symbols
  - Return NewsBundle[] for portfolio symbols
- [ ] Handle loading/error states
- [ ] Handle empty portfolio (no positions) gracefully

#### 4.2 Update news page state
- [ ] Edit `frontend/app/news/page.tsx`
- [ ] Update view type (line 507):
  ```typescript
  const [view, setView] = useState<"market" | "watchlist" | "portfolio">("market");
  ```
- [ ] Add portfolio query:
  ```typescript
  const portfolioQuery = usePortfolioNews();
  ```
- [ ] Update `activeQuery` logic to handle portfolio view
- [ ] Create `portfolioBundles` similar to watchlistBundles (line 531-534)

#### 4.3 Add portfolio toggle button
- [ ] Edit toggle button array (lines 562-581)
- [ ] Add third button:
  ```typescript
  { key: "portfolio", label: "My Portfolio" }
  ```
- [ ] Ensure button styling matches existing "Market" and "My Watchlist"

#### 4.4 Add portfolio news section
- [ ] Copy watchlist section structure (lines 630-672)
- [ ] Create portfolio section:
  ```typescript
  {view === "portfolio" && (
    <section className="space-y-4">
      {/* Loading, error, empty states */}
      {portfolioBundles.map((bundle) => (
        <NewsBundleCard
          key={bundle.ticker}
          bundle={bundle}
          title={`Symbol: ${bundle.ticker}`}
        />
      ))}
    </section>
  )}
  ```
- [ ] Handle loading state
- [ ] Handle error state
- [ ] Handle empty portfolio state ("Add positions to see portfolio news")

#### 4.5 Test news filtering
- [ ] Verify "Market" view shows broad market news
- [ ] Verify "My Watchlist" view shows watchlist symbol news
- [ ] Verify "My Portfolio" view shows owned position news
- [ ] Verify empty states work correctly
- [ ] Verify switching between views works smoothly

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

1. **Check your branch and commit all changes**:
   ```bash
   # Check which branch cloud session created:
   git branch

   # Commit all changes to that branch:
   git add -A
   git commit -m "feat: portfolio/watchlist UI and data model fixes

   - Portfolio UI: Accounts with expandable positions
   - Watchlist: Independent of portfolio accounts
   - News page: Add portfolio filter option
   - Data model: Separate monitoring vs owning

   See tasks/tasks-ui-portfolio-watchlist-fixes.md for details"
   ```

2. **Provide to user**:
   - **Git branch name**: (output of `git branch --show-current`)
   - Pull command: `git fetch origin && git checkout <branch-name>`
   - List of files changed (output of `git diff --name-only main`)
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
