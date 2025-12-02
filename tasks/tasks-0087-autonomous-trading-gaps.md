# Task List: Autonomous Trading Pipeline Gaps

**Source**: Gap analysis from system verification (2025-12-02)
**Complexity**: Medium
**Effort**: 6-8 hours
**Created**: 2025-12-02 17:40

---

## Summary

Gap analysis of the autonomous trading pipeline revealed 3 critical issues preventing true hands-off operation:

1. **No Auto-Promotion**: Strategies remain in "testing" status forever until manually activated
2. **No Top Trades Dashboard**: User has no single view showing actionable trade recommendations
3. **Signal Thresholds**: Auto-trading requires strength >= 7, but signals averaging 4-5

---

## Gap 1: Auto-Promotion of Validated Strategies

**Current State:**
- New strategies created with `status='testing'`
- Never change to `status='active'` automatically
- User must manually click "Activate" in UI

**Expected State:**
- Strategies auto-promote to `active` after validation period
- Criteria: 5+ days of paper trading, no major drawdowns, expected Sharpe confirmed

**Tasks:**

- [ ] 1.1 Add auto-promotion logic to `evaluate_strategy_performance` task
  - Criteria: `days_since_creation >= 5` AND `expected_sharpe >= 1.0` AND `no_blocking_issues`
  - Call `storage.activate_strategy()` automatically
  - Log promotion reason

- [ ] 1.2 Add `auto_promoted_at` timestamp to strategy_definitions
  - Track when/why strategy was auto-promoted
  - Migration: ALTER TABLE strategy_definitions ADD COLUMN auto_promoted_at TIMESTAMPTZ

- [ ] 1.3 Add user preference for auto-promotion threshold
  - Default: Sharpe >= 1.0, min 5 days
  - Store in user_preferences table

**Files:**
- `backend/app/tasks/strategy_monitoring_tasks.py`
- `backend/app/strategies/storage.py`
- `backend/migrations/053_auto_promotion.sql`

---

## Gap 2: Top Trades Dashboard

**Current State:**
- Paper trades visible at `/trading` but mixed with all trades
- No prioritized view of "what should I trade today"
- No consolidated reasoning/sizing/entry/exit display

**Expected State:**
- Dashboard showing top N actionable trades ranked by confidence
- Each trade shows: symbol, signal, entry, stop, target, position size, reasoning
- Filterable by strategy type, signal strength

**Tasks:**

- [ ] 2.1 Create GET `/api/recommendations` endpoint
  - Returns top trades from active strategies with BUY signals
  - Includes: symbol, signal_strength, entry_price, stop_loss, target, position_size, reasoning
  - Sorted by signal_strength DESC

- [ ] 2.2 Create `/recommendations` page in frontend
  - Card-based layout with trade details
  - "Execute" button links to brokerage (future)
  - "Track" button adds to portfolio with strategy_id

- [ ] 2.3 Add position sizing calculation
  - Based on account size, risk tolerance
  - Kelly criterion or fixed percentage (2-5% of portfolio)

**Files:**
- `backend/app/api/recommendations.py` (NEW)
- `frontend/app/recommendations/page.tsx` (NEW)
- `frontend/components/recommendations/TradeCard.tsx` (NEW)

---

## Gap 3: Signal Strength Tuning

**Current State:**
- Auto paper trading threshold: strength >= 7
- Current signals averaging 4-5 strength
- Result: Very few auto-trades created

**Root Cause:**
- Signal classifier designed for watchlist (conservative)
- Many data points returning None (fundamentals, technicals)
- Missing data treated as neutral (strength 5)

**Tasks:**

- [ ] 3.1 Lower auto-trade threshold to strength >= 5 (configurable)
  - Add `min_signal_strength` to user_preferences
  - Default: 5 (was 7)

- [ ] 3.2 Improve signal data coverage
  - Ensure technicals populated for all watchlist symbols
  - Backfill missing fundamental data from reference_cache

- [ ] 3.3 Add strategy-specific signal boost
  - Strategies with Sharpe > 2.0 get +1 strength boost
  - Strategies in favorable market regime get +1 boost

**Files:**
- `backend/app/tasks/strategy_signal_tasks.py`
- `backend/app/watchlist/signal_classifier.py`

---

## Verification

After implementing:

- [ ] Strategy auto-promotes after 5 days with Sharpe >= 1.0
- [ ] `/recommendations` page shows top trades with full details
- [ ] Auto paper trades created daily from strength >= 5 signals
- [ ] User can view all recommendations without manual intervention

---

## Priority Order

1. **Gap 1 (Auto-Promotion)** - Critical for hands-off operation
2. **Gap 2 (Top Trades Dashboard)** - Critical for user visibility
3. **Gap 3 (Signal Tuning)** - Important for trade volume

---

## Quick Wins (Can Do Now)

1. Lower signal threshold from 7 to 5 in celery_schedules.py
2. Auto-activate strategies with Sharpe >= 2.0 immediately
3. Add "Recommendations" section to /trading page showing BUY signals
