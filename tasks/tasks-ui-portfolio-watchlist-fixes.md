# Task List: Portfolio/Watchlist UI & Data Model Fixes

**Created**: 2025-11-07
**Status**: Pending Research
**Priority**: HIGH

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
- [ ] All changes documented and tested
