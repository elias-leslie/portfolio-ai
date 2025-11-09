# Portfolio/Watchlist Fixes - Research Findings

**Date**: 2025-11-08
**Analyzed By**: Claude (Cloud Environment)

---

## Executive Summary

The portfolio and watchlist features have a fundamental data model confusion:
- **Watchlist items are incorrectly tied to portfolio accounts** via `account_id` FK
- **Portfolio UI shows accounts and positions as separate cards** instead of nested/expandable structure
- **News page missing portfolio filter** - only has Market and Watchlist views

---

## 1. Data Model Analysis

### Current Schema (scripts/migrate-schema-to-postgres.py)

#### watchlist_items (lines 245-255) ❌ PROBLEM

```sql
CREATE TABLE IF NOT EXISTS watchlist_items (
    id                     TEXT PRIMARY KEY,
    account_id             TEXT NOT NULL,              -- ❌ SHOULD NOT EXIST
    symbol                 TEXT NOT NULL,
    metadata               JSONB,
    note                   TEXT,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    updated_at             TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (account_id, symbol),                       -- ❌ WRONG CONSTRAINT
    FOREIGN KEY (account_id) REFERENCES portfolio_accounts(id) ON DELETE CASCADE  -- ❌ CAUSES DATA LOSS
)
```

**Issues:**
- `account_id` column should NOT exist - watchlist is for monitoring stocks globally, not per-account
- `UNIQUE (account_id, symbol)` allows same symbol in different accounts - conceptually wrong
- `ON DELETE CASCADE` deletes watchlist items when deleting portfolio accounts - DATA LOSS!

**Correct Design:**
- Watchlist = stocks you're MONITORING (not owned yet, or tracking for signals)
- Should be user-level, not account-level
- No relationship to portfolio accounts

#### portfolio_positions (lines 103-113) ✅ CORRECT

```sql
CREATE TABLE IF NOT EXISTS portfolio_positions (
    id                     TEXT PRIMARY KEY,
    account_id             TEXT NOT NULL,              -- ✅ CORRECT
    symbol                 TEXT NOT NULL,
    shares                 DOUBLE PRECISION NOT NULL,
    cost_basis             DOUBLE PRECISION NOT NULL,
    position_type          TEXT NOT NULL,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    updated_at             TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (account_id) REFERENCES portfolio_accounts(id) ON DELETE CASCADE  -- ✅ CORRECT
)
```

**This is correct:**
- Positions = stocks you OWN in specific accounts
- Must be tied to accounts (IRA has different positions than Taxable)
- CASCADE delete is appropriate (deleting account should delete its positions)

---

## 2. Backend API Analysis

### Watchlist API (backend/app/api/watchlist.py)

**All endpoints require account_id - this is the root cause of confusion:**

- **Line 51**: `list_watchlist_items(account_id: str)` - takes account_id as parameter
- **Line 74**: `create_watchlist_item(data: WatchlistItemCreate)` - data.account_id required
- **Line 89-94**: Checks uniqueness with `WHERE account_id = ? AND symbol = ?`
- **Line 106-110**: Inserts with account_id
- **Line 116**: `schedule_new_ticker_tasks(symbol, data.account_id)` - passes account_id
- **Line 428-432**: `SELECT id, symbol FROM watchlist_items WHERE account_id = ?`

**Files to change:**
- `backend/app/api/watchlist.py` - Remove account_id from all endpoints
- `backend/app/watchlist/response_builders.py` - Update models (WatchlistItemCreate, etc.)
- `backend/app/watchlist/watchlist_service.py` - Update service layer
- Update all SQL queries to remove account_id filtering

### Portfolio API (backend/app/api/portfolio.py)

**Portfolio endpoint returns flat position list:**

- **Line 93-152**: `get_portfolio()` - Returns flat list of positions
- No grouping by account in response
- Frontend needs account-grouped structure for expandable UI

**Options:**
1. Add new endpoint `/api/portfolio/by-account` that returns nested structure
2. Modify existing endpoint to include optional grouping
3. Keep flat and group in frontend (simpler, more flexible)

**Recommendation**: Keep backend simple, group in frontend

---

## 3. Frontend Analysis

### Watchlist Page (frontend/app/watchlist/page.tsx)

**Hardcoded account_id shows data model confusion:**

- **Line 22**: `const [accountId] = useState("default"); // TODO: Get from auth context`
- **Line 25**: `useWatchlist(accountId)` - passes to API
- **Line 42**: `refreshMutation.mutate(accountId)` - passes to refresh

**This TODO comment reveals the confusion** - watchlist doesn't need auth context or account selection, it's global per user!

**Changes needed:**
- Remove accountId state and parameter passing
- Update API client hooks to not require account_id
- Clean up TODO comment

### Portfolio Page (frontend/app/portfolio/page.tsx)

**Accounts and positions shown as separate cards:**

- **Line 6**: `import { AccountsCard } from "@/components/portfolio/AccountsCard"`
- **Line 4**: `import { PositionTable } from "@/components/portfolio/PositionTable"`
- **Lines 313-316**: Accounts section (separate)
- **Lines 318-329**: Positions section (separate)

**Current structure:**
```
Portfolio Page
├── Portfolio Overview (analytics)
├── Accounts Section (list of accounts)
└── Positions Section (flat list of all positions)
```

**Expected structure:**
```
Portfolio Page
├── Portfolio Overview (analytics)
└── Accounts Section
    ├── Account 1 (expandable)
    │   ├── Position 1a
    │   ├── Position 1b
    │   └── Position 1c
    ├── Account 2 (expandable)
    │   ├── Position 2a
    │   └── Position 2b
    └── Add Account button
```

**Changes needed:**
- Create new `AccountsWithPositions` component
- Each account row is expandable (accordion/collapsible)
- Positions nested under their account
- Add position button creates under selected account
- Remove separate PositionTable or repurpose it

### News Page (frontend/app/news/page.tsx)

**Missing portfolio filter option:**

- **Line 507**: `const [view, setView] = useState<"market" | "watchlist">("market");`
- **Lines 562-581**: Toggle shows only "Market" and "My Watchlist"
- **No "portfolio" view option**

**Changes needed:**
- Add `"portfolio"` to view type: `useState<"market" | "watchlist" | "portfolio">("market")`
- Add "My Portfolio" toggle button in UI
- Create `usePortfolioNews` hook (or enhance existing)
- Fetch portfolio positions, extract unique symbols
- Filter/fetch news for those symbols
- Display in same NewsBundle format

---

## 4. Implementation Plan

### Phase 1: Database Migration

**Goal**: Remove account_id from watchlist_items

**Migration SQL** (`backend/migrations/018_watchlist_account_separation.sql`):

```sql
-- Remove FK constraint first
ALTER TABLE watchlist_items
DROP CONSTRAINT IF EXISTS watchlist_items_account_id_fkey;

-- Drop unique constraint
ALTER TABLE watchlist_items
DROP CONSTRAINT IF EXISTS watchlist_items_account_id_symbol_key;

-- Remove account_id column
ALTER TABLE watchlist_items
DROP COLUMN IF EXISTS account_id;

-- Add new unique constraint on symbol only
ALTER TABLE watchlist_items
ADD CONSTRAINT watchlist_items_symbol_key UNIQUE (symbol);
```

**Note**: This will consolidate duplicate symbols across accounts - need to handle carefully in migration.

### Phase 2: Backend API Changes

**Files to modify:**

1. **backend/app/api/watchlist.py**
   - Remove `account_id` parameter from `list_watchlist_items()`
   - Remove `account_id` from `WatchlistItemCreate` model
   - Update all SQL queries to remove account_id filtering
   - Update `schedule_new_ticker_tasks()` calls to not pass account_id

2. **backend/app/watchlist/response_builders.py**
   - Update `WatchlistItemCreate` model - remove `account_id` field
   - Update `WatchlistItemResponse` model - remove `account_id` field

3. **backend/app/watchlist/watchlist_service.py**
   - Update `get_items_with_scores()` - remove account_id parameter
   - Update all queries to not filter by account_id

4. **backend/app/watchlist/background_tasks.py**
   - Update `schedule_new_ticker_tasks()` - remove account_id parameter

**Tests to update:**
- All watchlist integration tests
- Update test data to not use account_id

### Phase 3: Frontend - Watchlist

**Files to modify:**

1. **frontend/lib/api/watchlist.ts**
   - Remove `account_id` from API client functions
   - Update fetch URLs to not include `?account_id=...`
   - Update request/response types

2. **frontend/lib/hooks/useWatchlist.ts**
   - Remove `accountId` parameter from hooks
   - Update `useWatchlist()` to not require account parameter
   - Update `useRefreshWatchlist()` similarly

3. **frontend/app/watchlist/page.tsx**
   - Remove `const [accountId] = useState("default")`
   - Update `useWatchlist()` call - no parameter
   - Update `refreshMutation.mutate()` - no parameter
   - Remove TODO comment

4. **frontend/components/watchlist/*.tsx**
   - Update all components that accept accountId prop
   - Remove prop passing

### Phase 4: Frontend - Portfolio UI

**Goal**: Accounts with expandable positions

**Approach**: Create new component with accordion/collapsible design

**New component**: `frontend/components/portfolio/AccountsWithPositions.tsx`

**Features:**
- Fetch accounts via `useAccounts()`
- Fetch positions via `usePortfolio()`
- Group positions by account_id
- Accordion UI (react-accordion or manual with state)
- Each account shows:
  - Account name and type
  - Total value of positions in account
  - Expand/collapse button
  - When expanded: table of positions
  - Add position button (scoped to account)
- Empty state for accounts with no positions
- Delete account with confirmation

**Files to modify:**

1. **frontend/components/portfolio/AccountsWithPositions.tsx** (NEW)
   - Create full component with accordion UI
   - Use shadcn/ui Accordion component
   - Group positions by account_id
   - Show positions when account expanded

2. **frontend/app/portfolio/page.tsx**
   - Replace `<AccountsCard />` and `<PositionTable />` with `<AccountsWithPositions />`
   - Keep dialogs for add account/position
   - Update add position flow to select account first

### Phase 5: Frontend - News Portfolio Filter

**Goal**: Add "My Portfolio" filter to news page

**Files to modify:**

1. **frontend/lib/hooks/useNews.ts**
   - Add `usePortfolioNews()` hook
   - Fetch portfolio positions via `usePortfolio()`
   - Extract unique symbols from positions
   - Fetch news for those symbols (same as watchlist news logic)

2. **frontend/app/news/page.tsx**
   - Update view type: `"market" | "watchlist" | "portfolio"`
   - Add "My Portfolio" toggle button (around line 565)
   - Add portfolio query: `const portfolioQuery = usePortfolioNews()`
   - Add portfolio bundles logic (similar to watchlist)
   - Add portfolio section rendering (similar to watchlist section)

**UI placement**:
```tsx
{ key: "market", label: "Market" },
{ key: "watchlist", label: "My Watchlist" },
{ key: "portfolio", label: "My Portfolio" },  // NEW
```

---

## 5. Testing Strategy

### Database Migration Testing

**In dev environment:**
1. Create backup of portfolio_ai database
2. Run migration script
3. Verify watchlist_items schema change
4. Verify no data loss (symbols consolidated)
5. Test CASCADE delete prevention

### Backend API Testing

**Test cases:**
1. List watchlist items (no account_id needed)
2. Add watchlist item (no account_id in request)
3. Delete portfolio account (watchlist unaffected)
4. Duplicate symbol prevention (symbol unique globally)

### Frontend Testing

**Watchlist:**
1. Load watchlist page (no account selection)
2. Add ticker (no account needed)
3. Refresh watchlist (works without account)

**Portfolio:**
1. Create account
2. Add positions under account
3. Expand account (see positions)
4. Collapse account (hide positions)
5. Delete account (positions deleted, watchlist unaffected)

**News:**
1. Switch to "My Portfolio" tab
2. Verify news shows for owned symbols
3. Verify empty state when no positions

---

## 6. Files to Change Summary

### Backend (Python)

**Database:**
- `backend/migrations/018_watchlist_account_separation.sql` (NEW)

**API:**
- `backend/app/api/watchlist.py`
- `backend/app/watchlist/response_builders.py`
- `backend/app/watchlist/watchlist_service.py`
- `backend/app/watchlist/background_tasks.py`

**Models:**
- Update any Pydantic models that reference watchlist account_id

**Tests:**
- `backend/tests/integration/watchlist/` - all test files
- Update test fixtures

### Frontend (TypeScript/React)

**API Layer:**
- `frontend/lib/api/watchlist.ts`
- `frontend/lib/api/news.ts` (add portfolio news support)

**Hooks:**
- `frontend/lib/hooks/useWatchlist.ts`
- `frontend/lib/hooks/useNews.ts` (add usePortfolioNews)

**Pages:**
- `frontend/app/watchlist/page.tsx`
- `frontend/app/portfolio/page.tsx`
- `frontend/app/news/page.tsx`

**Components:**
- `frontend/components/watchlist/*.tsx` (remove accountId props)
- `frontend/components/portfolio/AccountsWithPositions.tsx` (NEW)
- Possibly remove `frontend/components/portfolio/AccountsCard.tsx` (if replaced)
- Possibly remove `frontend/components/portfolio/PositionTable.tsx` (if replaced)

---

## 7. Risk Assessment

### High Risk
- **Database migration** - Could lose data if duplicate symbols exist across accounts
  - Mitigation: Test thoroughly in dev, backup production before migration

### Medium Risk
- **Breaking API changes** - Removing account_id breaks existing frontend
  - Mitigation: Deploy backend and frontend together atomically

### Low Risk
- **UI changes** - Portfolio page redesign might confuse users initially
  - Mitigation: Clear UI with expand/collapse affordances

---

## 8. Migration Complexity Estimate

**Overall**: MEDIUM complexity

**Phase-by-phase:**
- Phase 1 (DB Migration): MEDIUM - 1 hour (requires careful SQL, testing)
- Phase 2 (Backend API): MEDIUM - 2-3 hours (multiple files, tests)
- Phase 3 (Frontend Watchlist): LOW - 1 hour (straightforward removal)
- Phase 4 (Frontend Portfolio UI): HIGH - 3-4 hours (new component, logic)
- Phase 5 (Frontend News): LOW - 1 hour (similar to watchlist implementation)

**Total Estimate**: 8-10 hours of development + testing

---

## 9. Recommended Implementation Order

1. **Backend first** (Phases 1-2)
   - Migration + API changes
   - Run tests, verify data model fix
   - Can be deployed without frontend changes (backward compatible queries fail gracefully)

2. **Frontend watchlist** (Phase 3)
   - Quick win, demonstrates account_id removal works
   - Low risk, high visibility fix

3. **Frontend portfolio UI** (Phase 4)
   - Most complex change
   - Do this separately from watchlist

4. **Frontend news** (Phase 5)
   - Final feature addition
   - Builds on working portfolio API

---

## 10. Questions for User

1. **Duplicate symbols**: If a user has AAPL in both IRA and Taxable watchlists, which note/metadata should be kept during migration?
   - Recommendation: Keep most recently updated, or concatenate notes

2. **Multi-user future**: Is multi-user support planned? If yes, watchlist_items needs `user_id`, not `account_id`
   - Current schema assumes single user

3. **Portfolio grouping**: Should portfolioendpoint return nested structure or keep flat?
   - Recommendation: Keep flat, group in frontend (more flexible)

---

**End of findings document**
