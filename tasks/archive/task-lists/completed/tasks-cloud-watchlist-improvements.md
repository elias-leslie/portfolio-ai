# Task List: Watchlist Improvements - Cloud Implementation

**Created**: 2025-11-08
**Status**: Pending Research
**Priority**: HIGH
**Environment**: Cloud Claude Code (sandbox, limited runtime)
**Estimated Effort**: 18-24 hours of implementation (cloud agent does code, dev environment does testing)

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
- Use code analysis tools (ruff, mypy, eslint - static only)

❌ **You CANNOT (or should avoid):**
- Run Python venv commands (they hang in sandbox)
- Start backend/frontend services
- Run runtime tests (pytest, npm test, vitest - need running services)
- Execute database migrations (provide SQL scripts instead)
- Test API endpoints (no services running)
- Use browser automation (no services running)
- **ANY commands from project scripts** (restart.sh, start.sh, status.sh, etc.)
- **ANY curl/http requests** to localhost or specific IPs
- **ANY database commands** (psql, migrations, queries)
- **ANY package installation** (npm install, pip install during runtime)

✅ **You SHOULD run (static analysis - no services needed):**
- `ruff check backend/` - Python linting
- `ruff format backend/` - Python formatting
- `mypy backend/app/` - Python type checking
- `npx eslint frontend/` - TypeScript/React linting (if project configured)

**❌ DO NOT RUN THESE COMMANDS:**
```bash
source backend/.venv/bin/activate          # ❌ Hangs
bash ~/portfolio-ai/scripts/restart.sh     # ❌ No dev environment
pytest tests/                               # ❌ No runtime
curl http://localhost:8000                 # ❌ No services
psql -U portfolio_ai_user -d portfolio_ai  # ❌ No database access
npm test                                    # ❌ No runtime
```

**✅ USE THESE COMMANDS:**
```bash
# Code reading and analysis:
cat/grep/find/rg                           # ✅ Read and search files
ls/pwd                                      # ✅ Basic navigation

# Static analysis (IMPORTANT - run after changes):
ruff check backend/                         # ✅ Python linting
ruff format backend/                        # ✅ Python formatting
mypy backend/app/                           # ✅ Python type checking

# Git operations:
git status/add/commit/checkout/branch      # ✅ Git operations
```

**Your Workflow:**
1. **Research thoroughly** - Read code, understand architecture, document findings in Task 1
2. **Expand task list** - Add detailed subtasks based on your research
3. **Implement code changes** - Write/edit Python and TypeScript files
4. **Run static analysis** - Use ruff, mypy to catch issues early
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

Implement comprehensive watchlist improvements based on user requirements:

**User Requirements** (ALL 5 confirmed):
1. ✅ Show price/technical/fundamental score breakdowns with ALL sub-metrics
2. ✅ Add weight sliders in settings for ALL sub-metrics (RSI, MACD, trend, valuation, growth, health, sentiment)
3. ✅ Priority indicators - NO arbitrary cap (show all 8 relevant ones)
4. ✅ Automated scheduled task for sparkline backfill (not manual)
5. ✅ All tiers: Quick Wins + Foundation + Polish

**Features to Implement**:
- **Priority Indicators**: 8 types (🔥 Hot, 📋 Earnings, 📰 News, 📈 Insider, 📉 Negative, 💎 Value, ⚡ Momentum, ⚠️ Caution)
- **Actionable Insights**: Display existing backend field in UI
- **Sparkline Backfill**: Automated Celery task (not manual)
- **4-Pillar Fundamental**: Valuation/Growth/Health/Sentiment scoring
- **3-Pillar Formula**: Price 33% / Technical 33% / Fundamental 34%
- **Volume/Timeframe/Percentile**: Calculate and populate existing DB columns
- **AVOID Signal Bugs**: Fix sma_5_prev=None and news_sentiment=None
- **Settings Sliders**: Weight configuration for ALL sub-metrics

---

## Tasks

### Task 1: Research & Analysis (DO THIS FIRST - Cloud Agent)

**Objective**: Fully understand current implementation, verify all file paths, and flesh out detailed subtasks

**Research Tasks** (read code, analyze structure, NO runtime execution):

#### 1.1 Backend Structure Analysis
- [ ] **Read watchlist modules**:
  - `backend/app/watchlist/models.py` - Verify ScoreWeights, ScoreBreakdown, WatchlistSnapshot models
  - `backend/app/watchlist/scoring.py` - Check calculate_watchlist_scores() formula (currently 2-pillar)
  - `backend/app/watchlist/fundamentals.py` - Check existing functions (fetch_fundamentals, classify_company_health)
  - `backend/app/watchlist/response_builders.py` - Check WatchlistItemResponse model
  - `backend/app/watchlist/watchlist_service.py` - Check get_items_with_scores() method
  - `backend/app/watchlist/refresh_processor.py` - Check snapshot creation logic
  - `backend/app/watchlist/signal_classifier.py` - Check classify_signal() parameters

- [ ] **Read task scheduling**:
  - `backend/app/celery_app.py` - Check beat_schedule structure (line ~83)
  - `backend/app/tasks/watchlist_tasks.py` - Check existing watchlist tasks

- [ ] **Read user preferences**:
  - `backend/app/storage/schema.py` - Check user_preferences table schema
  - Check migrations directory for latest migration number

#### 1.2 Frontend Structure Analysis
- [ ] **Read watchlist components**:
  - `frontend/components/watchlist/WatchlistTable.tsx` - Check Signal column rendering, verify SparklineWithHistory import commented
  - `frontend/components/watchlist/NewsIntelligenceCard.tsx` - Check if actionable_insight is displayed (should be TypeScript interface only, not rendered)
  - `frontend/components/watchlist/ExpandedRow.tsx` - Check score display section
  - `frontend/lib/api/watchlist.ts` - Check WatchlistItem interface

- [ ] **Read settings page**:
  - `frontend/app/settings/page.tsx` - Check structure and imports
  - `frontend/components/settings/WatchlistPreferences.tsx` - Check existing score weight sliders (price/technical only, no fundamental)

#### 1.3 Database Schema Analysis
- [ ] **Check existing columns** (read migration files, don't execute):
  - Migration 009: Verify volume_relative, timeframe_short_aligned, timeframe_long_aligned, percentile_rank_30d columns
  - Migration 009: Verify sma_5 column in technical_indicators table
  - Check if watchlist_score_weights JSONB column exists in user_preferences

#### 1.4 Document Findings
- [ ] **Create implementation map**:
  - List all files to create (NEW files)
  - List all files to modify (EXISTING files with specific changes)
  - Document current vs desired state for each component
  - Identify dependencies between tasks
  - Note any missing database columns (provide SQL for dev environment)

#### 1.5 Expand Subtasks
- [ ] **Update Task 2** with specific file changes for priority indicators
- [ ] **Update Task 3** with specific file changes for actionable insights
- [ ] **Update Task 4** with specific file changes for sparkline backfill
- [ ] **Update Task 5** with specific file changes for fundamental scoring
- [ ] **Update Task 6** with specific file changes for volume/timeframe/percentile
- [ ] **Update Task 7** with specific file changes for AVOID bugs
- [ ] **Update Task 8** with specific file changes for settings sliders

**Output**:
- Detailed notes in this section about current state
- All subtasks below expanded with specific implementation steps
- SQL migration scripts if new columns needed
- Clear understanding of what cloud agent will implement vs what needs dev testing

---

### Task 2: Priority Indicators Backend

**Goal**: Create priority indicator calculation system (ALL 8 indicators, no cap on display)

**Files to Create** (expand after research):
- [ ] `backend/app/watchlist/priority.py` (~200 lines)
  - TBD: PriorityIndicator model
  - TBD: 8 check functions (hot_opportunity, earnings_alert, breaking_news, insider_buying, negative_catalyst, value_play, momentum, caution)
  - TBD: calculate_priority_indicators() main function

**Files to Modify** (expand after research):
- [ ] `backend/app/watchlist/response_builders.py`
  - TBD: Add priority_indicators field to WatchlistItemResponse
  - TBD: Add to from_service_dict() method

- [ ] `backend/app/watchlist/watchlist_service.py`
  - TBD: Import calculate_priority_indicators
  - TBD: Calculate indicators in get_items_with_scores() method
  - TBD: Add to item dict before return

**Static Analysis**:
```bash
# After implementing, run:
ruff check backend/app/watchlist/priority.py
ruff format backend/app/watchlist/priority.py
mypy backend/app/watchlist/priority.py
```

---

### Task 3: Priority Indicators Frontend

**Goal**: Display priority indicators in watchlist table (no cap - show all relevant)

**Files to Modify** (expand after research):
- [ ] `frontend/lib/api/watchlist.ts`
  - TBD: Add PriorityIndicator interface
  - TBD: Add priority_indicators field to WatchlistItem

- [ ] `frontend/components/watchlist/WatchlistTable.tsx`
  - TBD: Update Signal column to show indicators alongside badge
  - TBD: Map through indicators array (no length cap)
  - TBD: Add tooltips on hover

---

### Task 4: Display Actionable Insights

**Goal**: Show existing actionable_insight field from backend in NewsIntelligenceCard

**Files to Modify** (expand after research):
- [ ] `frontend/components/watchlist/NewsIntelligenceCard.tsx`
  - TBD: Add rendering of article.actionable_insight field
  - TBD: Location: After impact_summary display (around line 204)
  - TBD: Style as primary color with 💡 icon

**Note**: Backend already generates this field - just needs UI display

---

### Task 5: Sparkline Backfill - Automated Task

**Goal**: Create scheduled Celery task to automatically backfill watchlist snapshot history

**Files to Create** (expand after research):
- [ ] None - task added to existing file

**Files to Modify** (expand after research):
- [ ] `backend/app/tasks/watchlist_tasks.py`
  - TBD: Add backfill_watchlist_snapshots_task() function
  - TBD: Logic: Check each watchlist item for days of history, backfill up to 30 days
  - TBD: Return results dict with counts

- [ ] `backend/app/celery_app.py`
  - TBD: Add "backfill-watchlist-history-daily" to beat_schedule
  - TBD: Schedule: 86400.0 (daily)
  - TBD: Runs at ~03:00 UTC after other tasks

- [ ] `frontend/components/watchlist/WatchlistTable.tsx`
  - TBD: Uncomment SparklineWithHistory import (line 14)
  - TBD: Verify sparkline usage is uncommented

**Static Analysis**:
```bash
ruff check backend/app/tasks/watchlist_tasks.py
mypy backend/app/tasks/watchlist_tasks.py
```

---

### Task 6: 4-Pillar Fundamental Scoring

**Goal**: Implement valuation/growth/health/sentiment scoring with 3-pillar overall formula

**Files to Modify** (expand after research):
- [ ] `backend/app/watchlist/fundamentals.py`
  - TBD: Add FundamentalData fields (valuation_score, growth_score, health_score, sentiment_score, fundamental_score)
  - TBD: Add calculate_valuation_score() function
  - TBD: Add calculate_growth_score() function
  - TBD: Add calculate_health_score() function
  - TBD: Add calculate_sentiment_score() function
  - TBD: Add calculate_fundamental_score() function (weighted average)

- [ ] `backend/app/watchlist/models.py`
  - TBD: Update ScoreWeights to include fundamental field (33/33/34)
  - TBD: Update ScoreBreakdown to include fundamental: ScoreComponent | None
  - TBD: Add sub_scores: dict field to ScoreComponent

- [ ] `backend/app/watchlist/scoring.py`
  - TBD: Add _compute_fundamental_component() function
  - TBD: Update calculate_watchlist_scores() to handle 3-pillar formula
  - TBD: Add sub_scores to price and technical components

- [ ] `backend/app/watchlist/refresh_processor.py`
  - TBD: Calculate fundamental sub-scores after fetching fundamental data
  - TBD: Pass fundamental data to scoring function

**Static Analysis**:
```bash
ruff check backend/app/watchlist/fundamentals.py backend/app/watchlist/models.py backend/app/watchlist/scoring.py
mypy backend/app/watchlist/fundamentals.py backend/app/watchlist/models.py backend/app/watchlist/scoring.py
```

---

### Task 7: Volume, Timeframe, Percentile Calculations

**Goal**: Calculate and populate volume_relative, timeframe_short_aligned, timeframe_long_aligned, percentile_rank_30d

**Files to Create** (expand after research):
- [ ] `backend/app/watchlist/timeframe.py` (~60 lines)
  - TBD: calculate_timeframe_alignment() function
  - TBD: calculate_volume_relative() function

- [ ] `backend/app/watchlist/percentiles.py` (~30 lines)
  - TBD: calculate_percentile_rank() function

**Files to Modify** (expand after research):
- [ ] `backend/app/watchlist/refresh_processor.py`
  - TBD: Import timeframe and percentile functions
  - TBD: Calculate all 4 values before snapshot creation
  - TBD: Assign to snapshot fields
  - TBD: Note: May need to query historical snapshots for percentile

**Static Analysis**:
```bash
ruff check backend/app/watchlist/timeframe.py backend/app/watchlist/percentiles.py
mypy backend/app/watchlist/timeframe.py backend/app/watchlist/percentiles.py
```

---

### Task 8: Fix AVOID Signal Bugs

**Goal**: Ensure sma_5_prev and news_sentiment are passed to signal classifier

**Files to Modify** (expand after research):
- [ ] `backend/app/watchlist/signal_classifier.py`
  - TBD: Verify classify_signal() has sma_5_prev and news_sentiment parameters
  - TBD: Verify AVOID detection uses these values
  - TBD: Verify AVOID threshold is 2+ flags (not 3)

- [ ] `backend/app/watchlist/refresh_processor.py` (or wherever classify_signal is called)
  - TBD: Fetch previous SMA_5 value from technical_indicators
  - TBD: Pass news_sentiment from news data
  - TBD: Update classify_signal() call with both parameters

**Static Analysis**:
```bash
ruff check backend/app/watchlist/signal_classifier.py
mypy backend/app/watchlist/signal_classifier.py
```

---

### Task 9: Settings Page - Weight Sliders for ALL Sub-Metrics

**Goal**: Add weight configuration UI for price/technical/fundamental and ALL their sub-metrics

**SQL Migration** (provide script, don't execute):
- [ ] Create migration file `backend/migrations/019_score_weight_sliders.sql`
  - TBD: Add watchlist_score_weights JSONB (if not exists)
  - TBD: Add price_sub_weights JSONB
  - TBD: Add technical_sub_weights JSONB
  - TBD: Add fundamental_sub_weights JSONB
  - TBD: Defaults: price/technical/fundamental weights, RSI/MACD/trend weights, valuation/growth/health/sentiment weights

**Files to Modify** (expand after research):
- [ ] `frontend/components/settings/WatchlistPreferences.tsx`
  - TBD: Add state for fundamental weight (currently missing)
  - TBD: Add state for all sub-metric weights
  - TBD: Replace score weights section with 3-pillar + sub-metric sliders
  - TBD: Price sub-metrics: change_pct (100%), beta (0%), volatility (0%) - informational for now
  - TBD: Technical sub-metrics: rsi_14, trend, macd - interactive sliders
  - TBD: Fundamental sub-metrics: valuation, growth, health, sentiment - interactive sliders
  - TBD: Validation: Each group must sum to 100%

**Static Analysis**:
```bash
# No eslint needed for TypeScript in this project based on research
# Just verify no syntax errors when reading file
```

---

### Task 10: Score Breakdown Display in UI

**Goal**: Show 3-pillar breakdown with sub-metrics in ExpandedRow

**Files to Modify** (expand after research):
- [ ] `frontend/components/watchlist/ExpandedRow.tsx`
  - TBD: Add "Score Breakdown" section
  - TBD: Display Overall score with progress bar
  - TBD: Display Price component with weight and sub-scores
  - TBD: Display Technical component with weight and sub-scores
  - TBD: Display Fundamental component with weight and sub-scores
  - TBD: Format: Component name, percentage, score, progress bar, sub-metric list

---

### Task 11: Static Analysis & Code Quality

**Goal**: Ensure all code passes linting and type checking before commit

**Steps**:
- [ ] Run ruff on all modified backend files
  ```bash
  ruff check backend/app/watchlist/
  ruff format backend/app/watchlist/
  ```

- [ ] Run mypy on all modified backend files
  ```bash
  mypy backend/app/watchlist/ --strict
  ```

- [ ] Fix ALL linting and type errors
  - Document any exceptions needed
  - Do not commit code with errors

- [ ] Verify TypeScript files have no syntax errors
  - Read files to check for obvious issues
  - No runtime TypeScript checking available in cloud

---

### Task 12: Git Commit & Handoff

**Goal**: Commit all changes and provide handoff instructions

**Steps**:
- [ ] Check current branch
  ```bash
  git branch --show-current
  ```

- [ ] Stage all changes
  ```bash
  git add -A
  git status  # Review what's being committed
  ```

- [ ] Commit with descriptive message
  ```bash
  git commit -m "feat: watchlist improvements - priority indicators, fundamental scoring, settings sliders

  Backend Changes:
  - Priority indicators: 8 types, no display cap
  - 4-pillar fundamental scoring (valuation/growth/health/sentiment)
  - 3-pillar overall formula (price 33%, technical 33%, fundamental 34%)
  - Volume/timeframe/percentile calculations
  - Sparkline backfill automated task
  - AVOID signal bug fixes (sma_5_prev, news_sentiment)
  - Sub-metric weight models

  Frontend Changes:
  - Priority indicators in watchlist table with tooltips
  - Actionable insights display in news card
  - Sparkline re-enabled
  - 3-pillar score breakdown in expanded row
  - Settings sliders for ALL sub-metrics (12 total)

  Database:
  - Migration 019 provided (needs execution in dev environment)

  See tasks/tasks-cloud-watchlist-improvements.md for details"
  ```

- [ ] Verify commit
  ```bash
  git log -1 --stat
  git diff main --name-only
  ```

- [ ] Provide handoff information (see Handoff section below)

---

## Success Criteria

**Code Implementation** (Cloud Agent):
- [ ] All 8 priority indicator check functions implemented
- [ ] Priority indicators displayed in UI (no cap)
- [ ] Actionable insights shown in news card
- [ ] Sparkline backfill task created and scheduled
- [ ] 4-pillar fundamental scoring functions implemented
- [ ] 3-pillar score formula implemented
- [ ] Volume/timeframe/percentile calculation functions implemented
- [ ] AVOID signal bugs fixed
- [ ] Settings sliders for ALL sub-metrics implemented
- [ ] Score breakdown UI shows 3 pillars + sub-metrics
- [ ] All code passes ruff + mypy static analysis
- [ ] All changes committed to feature branch

**Handoff to Dev Environment** (User + Local Claude):
- [ ] Migration 019 SQL script provided
- [ ] Testing steps documented
- [ ] Expected behavior described
- [ ] Files changed listed

---

## Handoff Instructions (When Complete)

**Cloud Agent - Provide This Information:**

### 1. Git Branch
```bash
# Your branch name:
git branch --show-current

# User pull command:
git fetch origin && git checkout <your-branch-name>
```

### 2. Files Changed
```bash
# List all changed files:
git diff main --name-only
```

### 3. SQL Migration to Execute

**File**: `backend/migrations/019_score_weight_sliders.sql`

User must execute in dev environment:
```bash
cd ~/portfolio-ai/backend
psql -U portfolio_ai_user -d portfolio_ai -f migrations/019_score_weight_sliders.sql
```

**Migration adds**:
- `watchlist_score_weights` JSONB column (price 33%, technical 33%, fundamental 34%)
- `price_sub_weights` JSONB column (future: change_pct, beta, volatility)
- `technical_sub_weights` JSONB column (rsi_14 33%, trend 34%, macd 33%)
- `fundamental_sub_weights` JSONB column (valuation 30%, growth 35%, health 25%, sentiment 10%)

### 4. Testing Steps for Dev Environment

**Prerequisites**:
```bash
# Activate venv
cd ~/portfolio-ai/backend && source .venv/bin/activate

# Run migration (if not done)
psql -U portfolio_ai_user -d portfolio_ai -f migrations/019_score_weight_sliders.sql

# Restart services
bash ~/portfolio-ai/scripts/restart.sh

# Verify services started
bash ~/portfolio-ai/scripts/status.sh
```

**Backend Testing**:
```bash
# 1. Test priority indicators API
curl http://localhost:8000/api/watchlist | jq '.[0].priority_indicators'
# Expected: Array of indicator objects (icon, label, tooltip, priority, category)

# 2. Test fundamental scoring
# Add a watchlist item and trigger refresh, check fundamental_score populated
curl -X POST http://localhost:8000/api/watchlist -H "Content-Type: application/json" -d '{"symbol": "AAPL"}'
# Wait for refresh task to run (~60 seconds)
curl http://localhost:8000/api/watchlist | jq '.[] | select(.symbol == "AAPL") | .current_score.fundamental'
# Expected: Non-null fundamental score component

# 3. Verify sparkline backfill task is scheduled
curl http://localhost:8000/api/status | jq '.celery_beat_schedule'
# Expected: "backfill-watchlist-history-daily" task present

# 4. Check score weights in preferences
curl http://localhost:8000/api/preferences | jq '.watchlist_score_weights'
# Expected: {"price": 33, "technical": 33, "fundamental": 34}
```

**Frontend Testing**:
```bash
# Open in browser:
open http://192.168.8.233:3000/watchlist
```

**Manual UI Verification**:
1. **Priority Indicators**:
   - Navigate to watchlist page
   - Check Signal column for emoji indicators (🔥📋📰📈📉💎⚡⚠️)
   - Hover over indicators to see tooltips
   - Verify multiple indicators shown (no cap at 2)

2. **Actionable Insights**:
   - Expand a watchlist item with news
   - Check News Intelligence card
   - Verify actionable insights shown with 💡 icon

3. **Sparklines**:
   - Check if sparklines appear in table
   - If not visible: Wait 24h for backfill task to accumulate data
   - Or manually trigger backfill: `curl -X POST http://localhost:8000/api/admin/backfill-snapshots`

4. **Score Breakdown**:
   - Expand a watchlist item
   - Look for "Score Breakdown" section
   - Verify 3 pillars shown: Price, Technical, Fundamental
   - Verify sub-scores listed under each pillar

5. **Settings Sliders**:
   - Navigate to Settings page
   - Scroll to Score Weights section
   - Verify 3 top-level sliders (Price, Technical, Fundamental)
   - Expand each to see sub-metric sliders:
     - Price: change_pct (informational)
     - Technical: RSI, Trend, MACD (interactive)
     - Fundamental: Valuation, Growth, Health, Sentiment (interactive)
   - Adjust sliders and save
   - Refresh watchlist and verify scores recalculated

**Run Tests**:
```bash
# Backend unit tests
cd ~/portfolio-ai/backend && source .venv/bin/activate
pytest tests/unit/watchlist/test_priority.py -v  # (if created)
pytest tests/unit/watchlist/test_fundamentals.py -v
pytest tests/unit/watchlist/test_scoring.py -v
pytest tests/ -v  # All tests

# Frontend tests (if applicable)
cd ~/portfolio-ai/frontend
npm test
```

**Expected Results**:
- All backend tests pass
- All frontend tests pass
- UI shows priority indicators correctly
- Score breakdown displays 3 pillars
- Settings sliders save and apply weights
- Fundamental scores non-null for stocks

### 5. What Cloud Agent Implemented

**✅ Completed in Cloud**:
- Backend priority indicator logic (all 8 types)
- Backend fundamental scoring (4-pillar system)
- Backend 3-pillar formula
- Backend volume/timeframe/percentile calculations
- Backend AVOID signal bug fixes
- Frontend priority indicator display
- Frontend actionable insights display
- Frontend sparkline re-enable
- Frontend score breakdown UI
- Frontend settings sliders (all sub-metrics)
- SQL migration script (provided, not executed)
- Static analysis (ruff + mypy)

**⏳ Needs Dev Environment Testing**:
- Database migration execution
- Service restart verification
- API endpoint testing
- Browser UI testing
- Integration test suite
- Sparkline data accumulation (24h+ wait for automated backfill)

**❓ Potential Issues to Check**:
- Fundamental data availability (some stocks may have NULL values)
- Sparklines may not appear immediately (need 7+ days of snapshot data)
- Volume calculations need OHLCV data in day_bars table
- Percentile calculations need 30 days of historical snapshots

### 6. Next Steps for User

1. **Pull branch** from cloud agent
2. **Execute migration 019**
3. **Restart services**
4. **Test manually** per steps above
5. **Run test suites**
6. **If tests pass**: Merge to main
7. **If issues found**: Share with local Claude for fixes

---

## Implementation Notes

**Key Design Decisions**:
1. **No cap on priority indicators** - Show all relevant ones (user requirement)
2. **Automated sparkline backfill** - Daily scheduled task, not manual (user requirement)
3. **All sub-metric sliders** - Expose full weight configuration (user requirement)
4. **3-pillar formula** - Even split 33/33/34 by default
5. **4-pillar fundamental** - Industry-standard weights (30/35/25/10)

**Dependencies**:
- Priority indicators need overall_score for ranking (Task 2 depends on current scoring working)
- Fundamental scoring needs FundamentalData fetching (already exists)
- Volume calculations need day_bars OHLCV data (should exist)
- Percentile calculations need watchlist_snapshots history (accumulates over time)

**Known Limitations**:
- Fundamental data may be NULL for some stocks (API limitations)
- Sparklines need 7-30 days of data to be useful
- Volume surge detection needs 50-day average (cold start issue)
- Percentile ranking needs 30-day history (cold start issue)

**Backward Compatibility**:
- 2-pillar systems continue to work if fundamental_score is NULL
- Existing user preferences unaffected (new fields have defaults)
- Frontend gracefully handles missing data (shows N/A or hides sections)

---

## Files Summary

**New Backend Files** (5):
1. `backend/app/watchlist/priority.py` (~200 lines)
2. `backend/app/watchlist/timeframe.py` (~60 lines)
3. `backend/app/watchlist/percentiles.py` (~30 lines)
4. `backend/migrations/019_score_weight_sliders.sql` (~25 lines)
5. Task added to `backend/app/tasks/watchlist_tasks.py` (backfill function ~80 lines)

**Modified Backend Files** (8):
1. `backend/app/watchlist/models.py` - ScoreWeights, ScoreBreakdown, ScoreComponent updates
2. `backend/app/watchlist/scoring.py` - 3-pillar formula, fundamental component
3. `backend/app/watchlist/fundamentals.py` - 4-pillar scoring functions
4. `backend/app/watchlist/response_builders.py` - priority_indicators field
5. `backend/app/watchlist/watchlist_service.py` - calculate priority indicators
6. `backend/app/watchlist/refresh_processor.py` - volume/timeframe/percentile, fundamental scoring
7. `backend/app/watchlist/signal_classifier.py` - AVOID bug fixes
8. `backend/app/celery_app.py` - backfill task schedule

**Modified Frontend Files** (5):
1. `frontend/lib/api/watchlist.ts` - PriorityIndicator type, priority_indicators field
2. `frontend/components/watchlist/WatchlistTable.tsx` - priority indicators, sparkline uncomment
3. `frontend/components/watchlist/NewsIntelligenceCard.tsx` - actionable_insight display
4. `frontend/components/watchlist/ExpandedRow.tsx` - 3-pillar score breakdown
5. `frontend/components/settings/WatchlistPreferences.tsx` - all sub-metric sliders

**Total**: 5 new files, 13 modified files

---

**END OF TASK LIST - Ready for Cloud Claude Agent**
