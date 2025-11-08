# Critical Issues Found - DO NOT MERGE YET

**Date**: 2025-11-08 23:30
**Status**: 🔴 **BLOCKING ISSUES** - Need fixes before merge
**Branch**: claude/watchlist-vision-implementation-011CUw9W27dCwbxtwbECZsKT

---

## 🔴 CRITICAL ISSUES (Must Fix)

### 1. **Missing Price Column**
**Issue**: No price information showing between Symbol and Signal columns
**Expected**: Price column with actual price + daily change % (e.g., "$172.50 +1.25%")
**Current**: Column appears to be missing or empty
**Fix Location**: `frontend/components/watchlist/WatchlistTable.tsx`

### 2. **Score Breakdown Shows Identical Data**
**Issue**: All stocks showing same scores (Price 37% / Technical 37%)
**Expected**: Each stock should have unique scores based on actual data
**Current**: Scores hardcoded or using same data source for all stocks
**Fix Location**: `frontend/components/watchlist/ExpandedRow.tsx`
**Root Cause**: Likely not pulling per-stock score data correctly

### 3. **Duplicate News Sections**
**Issue**: Two news sections in expanded row:
  - "News Intelligence"
  - "News & Sentiment"
**Design Reference**: `expanded_row_-_full_intelligence_view/screen.png` shows SINGLE "News Intelligence" section
**Expected**: One consolidated news section with headline + actionable insight
**Fix Location**: `frontend/components/watchlist/ExpandedRow.tsx`

### 4. **Legacy Code in Settings**
**Issue**: "Legacy Score Weights (Deprecated)" section visible in settings panel
**Expected**: Only current weight sliders, no deprecated code
**Fix Location**: `frontend/components/settings/WatchlistPreferences.tsx`
**Action**: Remove deprecated section entirely

### 5. **News Page Broken**
**Issue**: `/news` page stuck on "Loading..." infinitely
**Expected**: News articles should load
**Fix Location**: Check `frontend/app/news/page.tsx` and API endpoint
**Possible Causes**:
  - API endpoint not responding
  - Frontend query failing
  - Network timeout

---

## 🔍 Investigation Needed

**Immediate Actions**:
1. Check `WatchlistTable.tsx` - verify Price column is rendering
2. Check `ExpandedRow.tsx` - verify scores pull from `item.current_score` not hardcoded
3. Check `ExpandedRow.tsx` - remove duplicate news section
4. Check `WatchlistPreferences.tsx` - remove deprecated section
5. Check `/api/news` endpoint - test if responding
6. Check browser console for errors (may have missed critical ones)

---

## 📋 Files to Fix

1. `frontend/components/watchlist/WatchlistTable.tsx` - Add Price column
2. `frontend/components/watchlist/ExpandedRow.tsx` - Fix scores + remove duplicate news
3. `frontend/components/settings/WatchlistPreferences.tsx` - Remove legacy section
4. `frontend/app/news/page.tsx` or backend news API - Fix infinite loading

---

## ⚠️ Status Update

**Previous Assessment**: ✅ APPROVED FOR MERGE
**Current Assessment**: 🔴 **DO NOT MERGE** - Critical bugs found

Cloud agent's implementation has **structural issues** that were masked by:
- Incomplete manual testing
- Not checking actual data display
- Not testing News page
- Not opening Settings panel

---

## 🎯 Next Steps

1. ✅ Document issues (this file)
2. ⏸️ Use /pause_it to save state
3. ⏸️ Next session: Fix all 5 issues
4. ⏸️ Re-test thoroughly
5. ⏸️ THEN merge to main

---

**Context**: 86% (172K/200K tokens)
**Recommendation**: Pause and resume in fresh session to fix issues
