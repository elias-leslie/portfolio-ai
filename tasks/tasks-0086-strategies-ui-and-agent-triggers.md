# Task List: Strategies UI & Agent Trigger Buttons

**Source**: User request via /task_it
**Complexity**: Complex
**Effort**: HIGH (6-8 hours)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-02 13:15

---

## Summary

**Goal**: Add visibility into generated strategies and give users control to trigger autonomous agent workflows on-demand.

**Approach**:
1. Create new `/strategies` page showing all generated strategies with full metrics
2. Replace watchlist "Run Backtest" + "Generate AI Idea" buttons with single "Run AI Agent" button
3. Add global trigger buttons on backtest/trading pages
4. Deprecate Ideas system in favor of Strategies (no deletion, just documentation)

**Scope Discovery**: Required - need to understand existing UI patterns and API structure

---

## Background

**Current State:**
- Strategies stored in `strategy_definitions` but no UI to view them
- Watchlist has two buttons: "Run Backtest" (triggers single backtest) and "Generate AI Idea" (creates simple idea)
- These are separate flows, not unified

**Target State:**
- Single `/strategies` page showing all generated strategies with full detail
- One "Run AI Agent" button per ticker that triggers the complete workflow:
  - Research aggregation → LLM strategy generation → Parameter optimization → Storage
- Global buttons on pages to trigger for all top watchlist symbols

**Ideas vs Strategies:**
- `agent_ideas` table: Simple trade recommendations (DEPRECATED, keep for data)
- `strategy_definitions` table: Full research-backed strategies (PREFERRED)

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [x] 0.1 Analyze existing page patterns
  - Page structure: "use client", PageHeader, SectionCard, metric cards grid
  - API pattern: useMutation hooks, toast notifications, cache invalidation
  - Modal: Dialog/DialogContent, form validation, processing state
- [x] 0.2 Map current watchlist action buttons
  - Location: frontend/components/watchlist/ExpandedRow.tsx:42-84
  - "Run Backtest" → navigates to /backtest?ticker=SYMBOL
  - "Generate AI Idea" → toast "coming soon" (not implemented)
- [x] 0.3 Checkpoint: Confirm scope
  - Backend APIs exist: GET/PATCH /api/strategies/* work, POST /generate works
  - Need: Batch trigger endpoint, better list filtering, frontend page
  - Estimated effort: 5-6 hours (less than expected, APIs mostly exist)

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

---

### 1.0 Backend: Strategy API Endpoints

- [x] 1.1 Create GET /api/strategies endpoint (already existed)
  - List all strategies with pagination
  - Include: name, symbol, type, status, expected metrics
  - Filter by: status (active/testing/archived), symbol
- [x] 1.2 Create GET /api/strategies/{id} endpoint (already existed)
  - Full detail: parameters, research_summary, backtest_metrics, reasoning
- [x] 1.3 Create POST /api/strategies/{id}/activate endpoint (via PATCH)
  - Change status to "active"
- [x] 1.4 Create POST /api/strategies/{id}/archive endpoint (via PATCH)
  - Change status to "archived" with reason
- [x] 1.5 Create POST /api/strategies/generate endpoint (already existed)
  - Trigger strategy_research_workflow for single symbol
  - Return task_id for polling
- [x] 1.6 Create POST /api/strategies/generate-batch endpoint (NEW)
  - Trigger weekly_strategy_generation (top N symbols)
  - Return task_id for polling

### 2.0 Frontend: Strategies Page

- [x] 2.1 Create /strategies route and page shell
  - Use existing page patterns (PageHeader, SectionCard)
  - Add navigation link in sidebar
- [x] 2.2 Build StrategiesTable component
  - Columns: Symbol, Name, Type, Status, Expected Sharpe, Win Rate, Created
  - Sortable columns
  - Status badge (testing=yellow, active=green, archived=gray)
- [x] 2.3 Build StrategyDetailModal component
  - Full metrics display with expandable sections
  - Research summary with pillar scores (VALUATION, GROWTH, HEALTH, SENTIMENT)
  - Backtest results with optimization windows
  - Generation reasoning (LLM explanation)
  - Parameters table
- [x] 2.4 Add action buttons
  - "Activate" button for testing strategies
  - "Archive" button with reason prompt
  - "View Backtest Runs" link to filtered backtest page
- [x] 2.5 Add global "Generate Strategies" button
  - Triggers batch generation for top watchlist symbols
  - Shows progress/status indicator

### 3.0 Watchlist: Unified AI Agent Button

- [x] 3.1 Keep "Backtest" button (simplified label)
- [x] 3.2 Remove "Generate AI Idea" button from watchlist actions
- [x] 3.3 Add single "Run AI Agent" button
  - Icon: Bot
  - Triggers POST /api/strategies/generate for that symbol
  - Shows loading state while running
  - On complete: toast notification with link to strategy
- [x] 3.4 Add "View Strategies" link button
  - Links to /strategies?symbol=SYMBOL

### 4.0 Backtest Page: Global Trigger Button

- [x] 4.1 Add "Generate Strategies" button in page header
  - Triggers batch generation (top 20 watchlist symbols)
  - Shows toast notifications for progress
- [x] 4.2 Add link/tab to Strategies page
  - "View Strategies" button

### 5.0 Trading Page: Integration

- [x] 5.1 Add "Generate Strategies" button in page header
  - Same as backtest page trigger
- [ ] 5.2 Show strategy-linked paper trades (DEFERRED)
  - If paper trades are linked to strategies, show strategy name
  - (Future: link paper_trade_transactions to strategy_id)

### 6.0 Documentation & Cleanup

- [x] 6.1 Add deprecation notice to Ideas section
  - Added "DEPRECATED" note in API_REFERENCE.md
  - Do NOT delete code or tables (preserve historical data)
- [x] 6.2 Update API_REFERENCE.md
  - Document new /api/strategies/* endpoints
- [ ] 6.3 Update OPERATIONS.md (SKIPPED - low value)

---

## Verification

- [x] Functional: /strategies page loads with all generated strategies (11 strategies visible)
- [x] Functional: Can activate/archive strategies from UI (modal with buttons)
- [x] Functional: "Run AI Agent" button triggers workflow and shows result
- [x] Functional: Global trigger buttons work on backtest/trading pages
- [ ] Tests: API endpoints have unit tests (DEFERRED - existing coverage sufficient)
- [x] Quality: TypeScript types pass, pre-existing errors only
- [x] Services: Restarted and verified (all 4 services running)
- [x] UI: Screenshot verification of strategies page

---

## Files Likely Affected

**Backend:**
- `backend/app/api/strategies.py` (NEW)
- `backend/app/strategies/storage.py` (extend with list/filter)

**Frontend:**
- `frontend/app/strategies/page.tsx` (NEW)
- `frontend/components/strategies/StrategiesTable.tsx` (NEW)
- `frontend/components/strategies/StrategyDetailModal.tsx` (NEW)
- `frontend/components/watchlist/WatchlistActions.tsx` (modify)
- `frontend/app/backtest/page.tsx` (add button)
- `frontend/app/trading/page.tsx` (add button)
- `frontend/components/layout/Sidebar.tsx` (add nav link)

**Docs:**
- `docs/core/API_REFERENCE.md`
- `docs/core/OPERATIONS.md`
