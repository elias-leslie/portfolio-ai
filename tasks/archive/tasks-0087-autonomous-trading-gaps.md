# Task List: Autonomous Trading Pipeline Gaps

**Source**: Gap analysis from system verification (2025-12-02)
**Complexity**: Medium
**Effort**: MEDIUM (4-6 hours remaining)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-02 17:40

---

## Summary

**Goal**: Complete the autonomous trading pipeline so users can operate hands-off, only checking `/recommendations` for actionable trades.

**Approach**: Fix remaining gaps in auto-promotion, create recommendations dashboard, tune signal generation.

**Scope Discovery**: Not needed (gaps already identified via system verification)

**Status**: Gap 1 (auto-promotion) and Gap 3.1 (threshold) already implemented. Remaining: recommendations page.

---

## Tasks

### 1.0 Auto-Promotion of Validated Strategies ✅ COMPLETE

- [x] 1.1 Add `auto_promote_strategies` Celery task
  - Criteria: 3+ days old, expected Sharpe >= 1.0
  - Runs daily at 04:15 UTC
  - Auto-activates validated strategies
- [x] 1.2 Add to Celery beat schedule
  - Task registered and scheduled
- [ ] 1.3 Add `auto_promoted_at` timestamp to strategy_definitions (DEFERRED)
  - Track when/why strategy was auto-promoted
  - Migration: ALTER TABLE ADD COLUMN auto_promoted_at TIMESTAMPTZ
- [ ] 1.4 Add user preference for auto-promotion threshold (DEFERRED)
  - Default: Sharpe >= 1.0, min 3 days
  - Store in user_preferences table

### 2.0 Top Trades Recommendations Dashboard ✅ COMPLETE

- [x] 2.1 Create GET `/api/recommendations` endpoint
  - Returns top trades from active strategies with BUY signals
  - Includes: symbol, signal_strength, entry_price, stop_loss, target, position_size, reasoning
  - Sorted by signal_strength DESC
  - Filter: Only signals from today, strength >= 5
- [x] 2.2 Add position sizing calculation
  - Fixed percentage method: 5% of $100K = $5,000 per trade
  - Calculate shares: position_size / entry_price
  - Include in response
- [x] 2.3 Create `/recommendations` page in frontend
  - Card-based layout with trade details
  - Show: symbol, strategy name, signal strength, entry/stop/target
  - Show: position size (shares and dollars), reasoning bullets
- [x] 2.4 Add navigation link in sidebar
  - Icon: Target
  - Label: "Recs"
- [x] 2.5 Add "Track in Portfolio" action button
  - Creates portfolio position with strategy_id link
  - POST /api/recommendations/track/{symbol}

### 3.0 Signal Strength Tuning ✅ PARTIAL

- [x] 3.1 Lower auto-trade threshold from 7 to 5
  - Updated default in `auto_paper_trade_from_signals()`
  - More trades will be created automatically
- [ ] 3.2 Improve signal data coverage (DEFERRED)
  - Ensure technicals populated for all watchlist symbols
  - Backfill missing fundamental data
- [ ] 3.3 Add strategy-specific signal boost (DEFERRED)
  - Strategies with Sharpe > 2.0 get +1 strength boost
  - Market regime bonus

---

## Verification

- [x] Functional: Strategies auto-promote after 3 days with Sharpe >= 1.0
- [x] Functional: Auto paper trades created from strength >= 5 signals
- [x] Functional: `/recommendations` page shows top trades with full details
- [x] Tests: API endpoint returns correct data structure (AMD signal)
- [x] Quality: ruff passes (pre-existing TypeScript test errors only)
- [x] Services: Restarted and verified
- [x] UI: Screenshot verification of recommendations page

---

## Files Affected

**Backend:**
- `backend/app/api/recommendations.py` (NEW)
- `backend/app/tasks/strategy_monitoring_tasks.py` (DONE - auto_promote added)
- `backend/app/tasks/strategy_signal_tasks.py` (DONE - threshold lowered)
- `backend/app/celery_schedules.py` (DONE - schedule added)

**Frontend:**
- `frontend/app/recommendations/page.tsx` (NEW)
- `frontend/components/recommendations/TradeCard.tsx` (NEW)
- `frontend/lib/api/recommendations.ts` (NEW)
- `frontend/components/layout/Sidebar.tsx` (add nav link)

**Docs:**
- `docs/core/AUTONOMOUS_TRADING.md` (DONE - updated)
