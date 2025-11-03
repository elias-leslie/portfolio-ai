# Task List: Watchlist Intelligence 2.0 - AI-First Data Foundation & UI Redesign

**PRD**: `0022-prd-watchlist-intelligence-2.md`
**Status**: Ready for Implementation (Reviewed & Corrected)
**Completion**: 0%
**Effort**: HIGH (23-28 hours, 3-4 days)
**Created**: 2025-11-02
**Updated**: 2025-11-02 (Accuracy review complete - Critical issues fixed)

**🔍 ACCURACY REVIEW COMPLETED (2025-11-02)**:
- ✅ Fixed: Non-existent `_classify_signal_and_generate_narrative()` → Changed to `refresh_watchlist_scores()`
- ✅ Fixed: Removed brittle line number references → Changed to search patterns and section descriptions
- ✅ Fixed: Updated code location instructions throughout Tasks 2, 3, 4
- ✅ Verified: All database schema references checked against actual schema
- ✅ Verified: All model field references checked against actual code
- ✅ Clarified: earnings_surprise → None is correct (function handles gracefully with neutral score)

---

## Summary

**✅ COMPLETE:** (None)
**🔄 IN PROGRESS:** (Not started)
**⚠️ NEXT:** Task 1.0 - Database Migration & Schema Updates

---

## Current State & Context

**Migration 008 (Narrative Intelligence)** added:
- ✅ `fundamental_score` column in `watchlist_snapshots` (exists but not fully utilized)
- ✅ `backend/app/watchlist/fundamentals.py` module with basic fetching (YFinance → Finnhub → FMP failover)
- ✅ Basic company health classification (EXCELLENT/GOOD/WEAK)

**This PRD extends the existing foundation:**
- Completes 4-pillar fundamental scoring system (Valuation 30%, Growth 35%, Health 25%, Sentiment 10%)
- Changes score formula from 2-pillar (price/technical) to 3-pillar (price/technical/fundamental)
- Current default weights: 50/50 → New default: 33/33/34 (user-configurable via preferences)
- Fixes critical bugs: `sma_5_prev=None`, `news_sentiment=None` in signal classifier

---

## Relevant Files

### Backend - Create (6 files)
- `backend/migrations/009_watchlist_intelligence_2.sql` (~60 lines) - Add columns for volume, timeframes, percentiles, user preferences
- `backend/app/watchlist/priority.py` (~150 lines) - Priority indicator calculation (8 types, select top 2)
- `backend/app/watchlist/percentiles.py` (~100 lines) - 30-day percentile rank calculation
- `backend/tests/watchlist/test_fundamentals.py` (~50 lines) - Fundamental scoring tests
- `backend/tests/watchlist/test_priority_indicators.py` (~60 lines) - Priority selection tests
- `backend/tests/watchlist/test_percentiles.py` (~70 lines) - Percentile calculation tests

### Backend - Extend (1 file)
- `backend/app/watchlist/fundamentals.py` - **EXTEND**: Add 4-pillar scoring system to existing fetch infrastructure

### Backend - Update (11 files)
- `backend/app/analytics/indicators.py` - Add SMA_5 calculation
- `backend/app/watchlist/models.py` - Add new fields (fundamental_score, volume_relative, timeframe_*, percentile_rank_30d)
- `backend/app/watchlist/service.py` - CRITICAL: Fix sma_5_prev=None, news_sentiment=None bugs, add fundamental integration
- `backend/app/watchlist/scoring.py` - Update overall score formula (50/50 → 33/33/34)
- `backend/app/watchlist/narrative.py` - Lower AVOID threshold (3 → 2), add volume/timeframe boosts
- `backend/app/api/watchlist.py` - Add new API response fields, rename recommended_style → recommended_timeframe
- `backend/app/tasks/agent_tasks.py` - Add SMA_5 to indicator upsert, add percentile daily task
- `backend/tests/analytics/test_indicators.py` - Add SMA_5 assertions
- `backend/tests/watchlist/test_scoring.py` - Update formula expectations (33/33/34)
- `backend/tests/watchlist/test_narrative.py` - Update AVOID threshold expectations
- `backend/tests/api/test_watchlist.py` - Update response schema validation

### Frontend - Create (2 files)
- `frontend/components/watchlist/PriorityIndicator.tsx` (~80 lines) - Priority badge with tooltip
- `frontend/components/watchlist/ScoreBreakdown.tsx` (~120 lines) - 3-pillar score display

### Frontend - Update (5 files)
- `frontend/components/watchlist/WatchlistTable.tsx` - MAJOR: 8 new columns (Symbol+badges, Priority, Timeframe, Headline, Price, Score, Trend, Updated)
- `frontend/components/watchlist/ExpandedRow.tsx` - Add Score Breakdown section, volume analysis, timeframe alignment
- `frontend/lib/api/watchlist.ts` - Add new fields to WatchlistItem type, PriorityIndicator interface, rename recommended_style
- `frontend/app/watchlist/page.tsx` - Update for new table columns

### Notes
- **Tests**: `cd backend && pytest tests/ -v` (target: 85% coverage)
- **Type Check**: `cd backend && mypy app/ --strict`
- **Lint**: `./scripts/lint.sh`
- **Services**: `./scripts/restart.sh` after backend changes

---

## Tasks

### ✅ PRE-FLIGHT CHECKLIST

Before starting implementation:
- [ ] Read PRD #0022 completely
- [ ] Review codebase analysis report above
- [ ] Ensure PRD #0021 (Narrative Intelligence) is complete
- [ ] Backend venv activated: `cd ~/portfolio-ai/backend && source .venv/bin/activate`
- [ ] All existing tests passing: `pytest tests/ -v`
- [ ] Services running: `bash ~/portfolio-ai/scripts/status.sh`

---

## Task 1.0: Database Migration & Schema Updates ⏱️ 1 hour

**Goal**: Add 4 new columns to watchlist_snapshots, add sma_5 to technical_indicators, add 3 preference fields

- [ ] **1.1 Create Migration File Structure** (2 min)
  - [ ] 1.1.1 Create `backend/migrations/009_watchlist_intelligence_2.sql`
  - [ ] 1.1.2 Add migration header comment (description, date, dependencies)
  - [ ] 1.1.3 Add rollback section at bottom (commented out)

- [ ] **1.2 Add Columns to watchlist_snapshots** (5 min)
  - [ ] 1.2.1 **SKIP** `fundamental_score` - Already exists from migration 008 (verify with `\d watchlist_snapshots`)
  - [ ] 1.2.2 Write ALTER TABLE for `volume_relative FLOAT` (ratio, e.g., 2.3 = 2.3x avg)
  - [ ] 1.2.3 Write ALTER TABLE for `timeframe_short_aligned BOOLEAN DEFAULT FALSE`
  - [ ] 1.2.4 Write ALTER TABLE for `timeframe_long_aligned BOOLEAN DEFAULT FALSE`
  - [ ] 1.2.5 Write ALTER TABLE for `percentile_rank_30d FLOAT`
  - [ ] 1.2.6 Add CHECK constraint: `percentile_rank_30d >= 0 AND percentile_rank_30d <= 100`

- [ ] **1.3 Add sma_5 to technical_indicators** (2 min)
  - [ ] 1.3.1 Write ALTER TABLE for `sma_5 FLOAT`
  - [ ] 1.3.2 Add comment explaining SMA_5 is 5-day simple moving average

- [ ] **1.4 Add User Preference Fields** (5 min)
  - [ ] 1.4.1 Write ALTER TABLE for `watchlist_score_weights JSONB DEFAULT '{"price": 33, "technical": 33, "fundamental": 34}'`
  - [ ] 1.4.2 Write ALTER TABLE for `watchlist_avoid_threshold INTEGER DEFAULT 2`
  - [ ] 1.4.3 Write ALTER TABLE for `watchlist_volume_surge_multiplier FLOAT DEFAULT 1.5`
  - [ ] 1.4.4 Add CHECK constraints (threshold 1-4, multiplier 1.0-3.0)

- [ ] **1.5 Create Performance Indexes** (3 min)
  - [ ] 1.5.1 Create index on `watchlist_snapshots(item_id, fetched_at DESC)` for percentile queries
  - [ ] 1.5.2 Add `IF NOT EXISTS` to all indexes

- [ ] **1.6 Update recommended_style CHECK Constraint** (3 min)
  - [ ] 1.6.1 Find existing CHECK constraint on recommended_style (migration 008)
  - [ ] 1.6.2 Note: Will handle in models.py with backward compatibility, no DB change needed

- [ ] **1.7 Run Migration** (5 min)
  - [ ] 1.7.1 Activate venv: `cd ~/portfolio-ai/backend && source .venv/bin/activate`
  - [ ] 1.7.2 Run migration: `psql -U portfolio_ai_user -d portfolio_ai -f migrations/009_watchlist_intelligence_2.sql`
  - [ ] 1.7.3 Verify columns exist: `\d watchlist_snapshots` in psql
  - [ ] 1.7.4 Verify indexes created: `\di` in psql
  - [ ] 1.7.5 Check user_preferences columns: `\d user_preferences`

- [ ] **1.8 Update Schema Manager & Pydantic Models** (10 min)
  - [ ] 1.8.1 Open `backend/app/storage/schema.py`
  - [ ] 1.8.2 Find watchlist_snapshots CREATE TABLE statement
  - [ ] 1.8.3 Add 4 new columns to match migration (volume_relative, timeframe_short_aligned, timeframe_long_aligned, percentile_rank_30d)
  - [ ] 1.8.4 Update technical_indicators CREATE TABLE with sma_5
  - [ ] 1.8.5 Update user_preferences CREATE TABLE with 3 new fields
  - [ ] 1.8.6 Open `backend/app/watchlist/models.py`
  - [ ] 1.8.7 Find WatchlistSnapshot class (around line 136)
  - [ ] 1.8.8 Add 4 new fields after recent_news_headlines (line 184):
    ```python
    # Volume & timeframe analysis fields (PRD #0022)
    volume_relative: float | None = None  # Current volume / 50-day avg (e.g., 2.3 = 2.3x)
    timeframe_short_aligned: bool = False  # Price > SMA_20 > SMA_50
    timeframe_long_aligned: bool = False   # SMA_50 > SMA_200
    percentile_rank_30d: float | None = None  # 0-100 percentile vs 30-day history
    ```
  - [ ] 1.8.9 Verify to_upsert_params() method (line 186) will auto-include new fields via model_dump()

- [ ] **1.9 Update Persistence Layer for New Fields** (15 min)
  - [ ] 1.9.1 Open `backend/app/storage/queries.py`
  - [ ] 1.9.2 Find upsert_watchlist_snapshot function (around line 110)
  - [ ] 1.9.3 Add 4 new parameters after recent_news_headlines parameter (line 154):
    ```python
    # Volume & timeframe analysis fields (PRD #0022)
    volume_relative: float | None = None,
    timeframe_short_aligned: bool = False,
    timeframe_long_aligned: bool = False,
    percentile_rank_30d: float | None = None,
    ```
  - [ ] 1.9.4 Update SQL INSERT column list (lines 172-182), add after recent_news_headlines:
    ```sql
    volume_relative, timeframe_short_aligned, timeframe_long_aligned, percentile_rank_30d
    ```
  - [ ] 1.9.5 Update VALUES placeholders (lines 183-186), add 4 more: `?, ?, ?, ?`
  - [ ] 1.9.6 Update parameter tuple to include 4 new values in correct order
  - [ ] 1.9.7 Update ON CONFLICT DO UPDATE SET clause (after line 188):
    ```sql
    volume_relative = EXCLUDED.volume_relative,
    timeframe_short_aligned = EXCLUDED.timeframe_short_aligned,
    timeframe_long_aligned = EXCLUDED.timeframe_long_aligned,
    percentile_rank_30d = EXCLUDED.percentile_rank_30d,
    ```
  - [ ] 1.9.8 Save file

- [ ] **1.10 Verify Migration Success** (2 min)
  - [ ] 1.10.1 Query: `SELECT fundamental_score, volume_relative FROM watchlist_snapshots LIMIT 1;`
  - [ ] 1.10.2 Should return NULL values (columns exist)
  - [ ] 1.10.3 Query: `SELECT watchlist_score_weights FROM user_preferences LIMIT 1;`
  - [ ] 1.10.4 Should return default JSON: `{"price": 33, "technical": 33, "fundamental": 34}`

---

## Task 2.0: Fix Critical AVOID Signal Bugs ⏱️ 3 hours

**Goal**: Add SMA_5 calculation, integrate news/sentiment, lower AVOID threshold to 2, test with declining stock

- [ ] **2.1 Add SMA_5 to Technical Indicators Module** (10 min)
  - [ ] 2.1.1 Open `backend/app/analytics/indicators.py`
  - [ ] 2.1.2 Find calculate_indicators() function (around line 131)
  - [ ] 2.1.3 Add SMA_5 calculation after SMA_20:
    ```python
    sma_5 = ta.sma(close_series, length=5)
    indicator_values["sma_5"] = float(sma_5.iloc[-1]) if not sma_5.empty else None
    ```
  - [ ] 2.1.4 Update DEFAULT_INDICATORS list to include "sma_5"
  - [ ] 2.1.5 Save file

- [ ] **2.2 Write Test for SMA_5 Calculation** (5 min)
  - [ ] 2.2.1 Open `backend/tests/analytics/test_indicators.py`
  - [ ] 2.2.2 Find test_calculate_indicators_with_valid_data()
  - [ ] 2.2.3 Add assertion: `assert "sma_5" in result`
  - [ ] 2.2.4 Add assertion: `assert isinstance(result["sma_5"], float)`
  - [ ] 2.2.5 Run test: `pytest tests/analytics/test_indicators.py::test_calculate_indicators_with_valid_data -v`

- [ ] **2.3 Update TechnicalSnapshot Model** (3 min)
  - [ ] 2.3.1 Open `backend/app/watchlist/models.py`
  - [ ] 2.3.2 Find TechnicalSnapshot class (around line 97)
  - [ ] 2.3.3 **Current fields**: rsi_14, sma_20, sma_50, sma_200, ema_20, ema_50, ema_200, macd, macd_signal, price, calculated_at
  - [ ] 2.3.4 Add field after sma_20 (line 101): `sma_5: float | None = None  # 5-day simple moving average`
  - [ ] 2.3.5 Save file

- [ ] **2.4 Update Service to Store SMA_5** (5 min)
  - [ ] 2.4.1 Open `backend/app/watchlist/service.py`
  - [ ] 2.4.2 Find _fetch_technical_snapshot() function (around line 92)
  - [ ] 2.4.3 Locate TechnicalSnapshot instantiation (around line 100)
  - [ ] 2.4.4 Add `sma_5=indicators.get("sma_5")` to constructor
  - [ ] 2.4.5 Save file

- [ ] **2.5 Update Indicator Upsert & Load Functions** (10 min)
  - [ ] 2.5.1 Open `backend/app/tasks/agent_tasks.py`
  - [ ] 2.5.2 Find technical indicator upsert SQL (search for "INSERT INTO technical_indicators")
  - [ ] 2.5.3 Add sma_5 to column list and VALUES list
  - [ ] 2.5.4 Add sma_5 to UPDATE SET clause (for ON CONFLICT)
  - [ ] 2.5.5 Save file
  - [ ] 2.5.6 Open `backend/app/watchlist/service.py`
  - [ ] 2.5.7 Find _load_latest_technical() function (around line 69)
  - [ ] 2.5.8 In TechnicalSnapshot construction (around line 98), add after sma_20:
    ```python
    sma_5=row.get("sma_5"),  # Add 5-day SMA
    ```
  - [ ] 2.5.9 Save file

- [ ] **2.6 Provide sma_5_prev to Signal Classifier** (10 min)
  - [ ] 2.6.1 Open `backend/app/watchlist/service.py`
  - [ ] 2.6.2 Find `refresh_watchlist_scores()` function (search for "def refresh_watchlist_scores")
  - [ ] 2.6.3 Inside function body, find where `signal_inputs` dict is constructed (search for "signal_inputs = {")
  - [ ] 2.6.4 Find line with `"sma_5": technical_snapshot.sma_20` and change to `"sma_5": technical_snapshot.sma_5`
  - [ ] 2.6.5 For sma_5_prev, add query code BEFORE signal_inputs dict construction:
    ```python
    # Query previous day's SMA_5 (Note: technical_indicators uses 'ticker' not 'symbol')
    prev_date = (datetime.now(UTC) - timedelta(days=1)).date()
    sma_5_prev_query = """
        SELECT sma_5 FROM technical_indicators
        WHERE ticker = %s AND DATE(calculated_at) = %s
        ORDER BY calculated_at DESC LIMIT 1
    """
    result = conn.execute(sma_5_prev_query, (symbol, prev_date)).fetchone()
    sma_5_prev = result[0] if result else None
    ```
  - [ ] 2.6.6 In signal_inputs dict, find line with `"sma_5_prev": None` and replace with `"sma_5_prev": sma_5_prev`
  - [ ] 2.6.7 Save file

- [ ] **2.7 Integrate News/Sentiment into Refresh Flow** (10 min)
  - [ ] 2.7.1 Open `backend/app/watchlist/service.py`
  - [ ] 2.7.2 Find `refresh_watchlist_scores()` function, locate where earnings_days_away_val is calculated (search for "earnings_days_away_val")
  - [ ] 2.7.3 After earnings_days_away_val calculation and BEFORE signal_inputs dict, add news integration:
    ```python
    from .news import fetch_news_headlines_cached

    # Fetch news (cached 6 hours)
    try:
        news_headlines = fetch_news_headlines_cached(conn, symbol, max_results=10, ttl_hours=6)
        if news_headlines:
            avg_sentiment = sum(h.sentiment_score for h in news_headlines) / len(news_headlines)
            news_sentiment_value = avg_sentiment
            recent_news_value = {"headlines": [h.model_dump() for h in news_headlines[:5]]}
        else:
            news_sentiment_value = None
            recent_news_value = None
    except Exception as e:
        logger.warning("news_fetch_failed", symbol=symbol, error=str(e))
        news_sentiment_value = None
        recent_news_value = None
    ```
  - [ ] 2.7.4 In signal_inputs dict, find line with `"news_sentiment": None` and replace with `"news_sentiment": news_sentiment_value`
  - [ ] 2.7.5 Later in function, find WatchlistSnapshot construction (search for "WatchlistSnapshot("), add these fields:
    ```python
    news_sentiment_score=news_sentiment_value,
    recent_news_headlines=recent_news_value,
    ```
  - [ ] 2.7.6 Save file

- [ ] **2.8 Lower AVOID Threshold in Signal Classifier** (3 min)
  - [ ] 2.8.1 Open `backend/app/watchlist/narrative.py`
  - [ ] 2.8.2 Find classify_signal() function (around line 496)
  - [ ] 2.8.3 Find AVOID threshold check (around line 555)
  - [ ] 2.8.4 Change `if avoid_flags >= 3:` to `if avoid_flags >= 2:`
  - [ ] 2.8.5 Update comment: "# AVOID: 2 or more negative flags (lowered from 3 for better detection)"
  - [ ] 2.8.6 Save file

- [ ] **2.9 Write Test for AVOID with 2 Flags** (10 min)
  - [ ] 2.9.1 Open `backend/tests/watchlist/test_narrative.py`
  - [ ] 2.9.2 Find test_classify_avoid_signal_meta_style()
  - [ ] 2.9.3 Create new test: `test_avoid_with_two_flags()`
  - [ ] 2.9.4 Test case: downtrend (sma_5 < sma_5_prev) + negative news (sentiment -0.4) = 2 flags
  - [ ] 2.9.5 Assert signal_type == AVOID
  - [ ] 2.9.6 Assert strength <= 3 (2 flags → strength 4, 3 flags → 3, etc.)
  - [ ] 2.9.7 Run test: `pytest tests/watchlist/test_narrative.py::test_avoid_with_two_flags -v`

- [ ] **2.10 Update Existing AVOID Test** (3 min)
  - [ ] 2.10.1 In same file, find test_classify_avoid_signal_meta_style()
  - [ ] 2.10.2 Review: Test provides 4 flags, should still trigger AVOID (>=2)
  - [ ] 2.10.3 Update assertions if strength calculation changed
  - [ ] 2.10.4 Run test: `pytest tests/watchlist/test_narrative.py::test_classify_avoid_signal_meta_style -v`

- [ ] **2.11 Run All Watchlist Tests** (5 min)
  - [ ] 2.11.1 Run: `pytest tests/watchlist/ -v`
  - [ ] 2.11.2 All tests should pass
  - [ ] 2.11.3 If failures, debug and fix before proceeding

- [ ] **2.12 Test with Real Declining Stock** (20 min)
  - [ ] 2.12.1 Open watchlist UI: http://192.168.8.233:3000/watchlist
  - [ ] 2.12.2 Click "Add Ticker"
  - [ ] 2.12.3 Add a historically declining stock (e.g., "HOOD", "ZM", or current declining ticker)
  - [ ] 2.12.4 Wait for scheduled refresh (60 seconds) - **DO NOT** click manual refresh
  - [ ] 2.12.5 Monitor logs: `tail -f backend/logs/app.log | grep -i avoid`
  - [ ] 2.12.6 After refresh, expand ticker row in UI
  - [ ] 2.12.7 Verify signal shows AVOID (🔴) if conditions met
  - [ ] 2.12.8 Check database: `SELECT signal_type, news_sentiment_score FROM watchlist_snapshots WHERE symbol='HOOD' ORDER BY fetched_at DESC LIMIT 1;`
  - [ ] 2.12.9 Verify news_sentiment_score is NOT NULL
  - [ ] 2.12.10 Take screenshot of AVOID signal: `docs/screenshots/watchlist/task-2.12-avoid-signal.png`

- [ ] **2.13 Restart Services & Validate** (5 min)
  - [ ] 2.13.1 Run: `bash ~/portfolio-ai/scripts/restart.sh`
  - [ ] 2.13.2 Verify services started after code changes
  - [ ] 2.13.3 Check service start time: `systemctl status portfolio-ai-backend --no-pager | grep Active`
  - [ ] 2.13.4 Wait 2+ scheduled refresh cycles (2-3 minutes)
  - [ ] 2.13.5 Verify watchlist data refreshes correctly

---

## Task 3.0: Extend Fundamental Scoring System ⏱️ 6 hours

**Goal**: Extend existing fundamentals.py with 4-pillar scoring, handle ETFs, update overall score formula to 33/33/34 default

**Context**: Module `backend/app/watchlist/fundamentals.py` already exists with:
- ✅ Multi-source fetching (YFinance → Finnhub → FMP)
- ✅ FundamentalData model (profit_margin, revenue_growth, debt_to_equity, recommendations)
- ✅ Basic health classification (EXCELLENT/GOOD/WEAK)
- ❌ **MISSING**: 4-pillar scoring system (Valuation/Growth/Health/Sentiment → 0-100 composite)

- [ ] **3.1 Extend Fundamentals Module with Scoring** (5 min)
  - [ ] 3.1.1 Open existing file: `backend/app/watchlist/fundamentals.py`
  - [ ] 3.1.2 Review current FundamentalData model (has basic fields, needs expansion)
  - [ ] 3.1.3 Add scoring-specific imports (if needed): logger, Any
  - [ ] 3.1.4 Add constants for 4-pillar weights: `VALUATION_WEIGHT = 0.30`, `GROWTH_WEIGHT = 0.35`, `HEALTH_WEIGHT = 0.25`, `SENTIMENT_WEIGHT = 0.10`
  - [ ] 3.1.5 Keep existing fetch functions intact (do not modify)

- [ ] **3.2 Write Valuation Score Function** (15 min)
  - [ ] 3.2.1 Define function signature:
    ```python
    def calculate_valuation_score(
        pe_ratio: float | None,
        pb_ratio: float | None,
        peg_ratio: float | None,
        sector_avg_pe: float | None = None
    ) -> tuple[float, dict[str, Any]]:
        """Calculate valuation score 0-100. Lower multiples = higher score."""
    ```
  - [ ] 3.2.2 Implement P/E scoring (inverted: lower P/E = higher score)
    - P/E < 10: score 100
    - P/E 10-15: score 80
    - P/E 15-20: score 60
    - P/E 20-30: score 40
    - P/E > 30: score 20
    - Compare to sector_avg_pe if provided (boost/penalty ±10)
  - [ ] 3.2.3 Implement P/B scoring (similar ranges)
  - [ ] 3.2.4 Implement PEG scoring (PEG < 1 = undervalued, score 80+)
  - [ ] 3.2.5 Weight average: `(pe_score + pb_score + peg_score) / 3`
  - [ ] 3.2.6 Return tuple: (score, {"pe_score": X, "pb_score": Y, ...})
  - [ ] 3.2.7 Handle None values: Use neutral 50.0 if all None

- [ ] **3.3 Write Growth Score Function** (15 min)
  - [ ] 3.3.1 Define function signature:
    ```python
    def calculate_growth_score(
        revenue_growth: float | None,  # YoY %
        earnings_growth: float | None, # YoY %
        eps_trend: list[float] | None   # Last 4 quarters
    ) -> tuple[float, dict[str, Any]]:
        """Calculate growth score 0-100. Higher growth = higher score."""
    ```
  - [ ] 3.3.2 Implement revenue growth scoring:
    - >20%: score 100
    - 10-20%: score 80
    - 5-10%: score 60
    - 0-5%: score 40
    - <0%: score 20
  - [ ] 3.3.3 Implement earnings growth scoring (same ranges)
  - [ ] 3.3.4 Implement EPS trend scoring (check if increasing over 4 quarters)
    - 4/4 quarters up: score 100
    - 3/4 quarters up: score 75
    - 2/4 quarters up: score 50
    - Otherwise: score 25
  - [ ] 3.3.5 Weight average: `(revenue*0.4 + earnings*0.4 + eps_trend*0.2)`
  - [ ] 3.3.6 Return tuple with component breakdown
  - [ ] 3.3.7 Handle None: neutral 50.0

- [ ] **3.4 Write Health Score Function** (15 min)
  - [ ] 3.4.1 Define function signature:
    ```python
    def calculate_health_score(
        debt_to_equity: float | None,
        current_ratio: float | None,
        profit_margin: float | None,
        sector_avg_margin: float | None = None
    ) -> tuple[float, dict[str, Any]]:
        """Calculate financial health score 0-100."""
    ```
  - [ ] 3.4.2 Implement debt/equity scoring (lower = better):
    - <0.5: score 100 (low debt)
    - 0.5-1.0: score 80
    - 1.0-2.0: score 60
    - 2.0-3.0: score 40
    - >3.0: score 20 (high debt)
  - [ ] 3.4.3 Implement current ratio scoring (liquidity):
    - >2.0: score 100 (very liquid)
    - 1.5-2.0: score 80
    - 1.0-1.5: score 60
    - 0.5-1.0: score 40
    - <0.5: score 20 (illiquid)
  - [ ] 3.4.4 Implement profit margin scoring (higher = better):
    - >20%: score 100
    - 10-20%: score 80
    - 5-10%: score 60
    - 0-5%: score 40
    - <0%: score 20 (unprofitable)
    - Compare to sector average if provided (±10 adjustment)
  - [ ] 3.4.5 Weight average: `(debt*0.3 + liquidity*0.3 + margin*0.4)`
  - [ ] 3.4.6 Return tuple with breakdown
  - [ ] 3.4.7 Handle None: neutral 50.0

- [ ] **3.5 Write Sentiment Score Function** (10 min)
  - [ ] 3.5.1 Define function signature:
    ```python
    def calculate_sentiment_score(
        analyst_rating: str | None,      # "Strong Buy", "Buy", "Hold", etc.
        earnings_surprise: float | None  # % surprise
    ) -> tuple[float, dict[str, Any]]:
        """Calculate market sentiment score 0-100."""
    ```
  - [ ] 3.5.2 Implement analyst rating scoring:
    - "Strong Buy": 100
    - "Buy": 80
    - "Hold": 50
    - "Sell": 20
    - "Strong Sell": 0
    - Handle various rating formats (normalize strings)
  - [ ] 3.5.3 Implement earnings surprise scoring:
    - >10% beat: score 100
    - 5-10% beat: score 80
    - 0-5% beat: score 60
    - 0 to -5% miss: score 40
    - <-5% miss: score 20
  - [ ] 3.5.4 Weight average: `(analyst*0.6 + surprise*0.4)`
  - [ ] 3.5.5 Return tuple with breakdown
  - [ ] 3.5.6 Handle None: neutral 50.0

- [ ] **3.6 Write Main Fundamental Score Function** (10 min)
  - [ ] 3.6.1 Define function signature:
    ```python
    def calculate_fundamental_score(
        symbol: str,
        fundamental_data: dict[str, Any]
    ) -> tuple[float, dict[str, Any]]:
        """
        Calculate composite fundamental score 0-100.
        Weights: Valuation 30%, Growth 35%, Health 25%, Sentiment 10%
        """
    ```
  - [ ] 3.6.2 Call 4 component functions with data from fundamental_data dict
  - [ ] 3.6.3 Calculate weighted average:
    ```python
    composite = (
        valuation_score * 0.30 +
        growth_score * 0.35 +
        health_score * 0.25 +
        sentiment_score * 0.10
    )
    ```
  - [ ] 3.6.4 Clamp result: `max(0.0, min(100.0, composite))`
  - [ ] 3.6.5 Return tuple: `(composite, {"valuation": val_breakdown, ...})`
  - [ ] 3.6.6 Add logging: `logger.debug("fundamental_score_calculated", symbol=symbol, score=composite)`
  - [ ] 3.6.7 **Field Mapping Note**: Map FundamentalData fields (from Task 3.8) to scoring inputs:
    - pe_ratio → data.pe_ratio (NEW field added in 3.8)
    - pb_ratio → data.pb_ratio (NEW)
    - peg_ratio → data.peg_ratio (NEW)
    - revenue_growth → data.revenue_growth (EXISTS)
    - profit_margin → data.profit_margin (EXISTS)
    - debt_to_equity → data.debt_to_equity (EXISTS)
    - current_ratio → data.current_ratio (NEW)
    - earnings_growth → data.earnings_growth (NEW)
    - analyst_rating → data.recommendation_key (EXISTS)
    - earnings_surprise → None (NOT AVAILABLE - use None or fetch separately if needed)

- [ ] **3.7 Write ETF Constituent Averaging Function** (20 min)
  - [ ] 3.7.1 Define function:
    ```python
    def get_etf_constituent_fundamentals(symbol: str) -> dict[str, Any]:
        """Get average fundamentals for ETF constituents (SPY, QQQ, etc.)."""
    ```
  - [ ] 3.7.2 Create mapping dict:
    ```python
    ETF_CONSTITUENT_MAPPINGS = {
        "SPY": "^GSPC",  # S&P 500 index as proxy
        "QQQ": "^IXIC",  # Nasdaq composite
        "VOO": "^GSPC",  # Also S&P 500
        "VTI": "^GSPC",  # Total market ~ S&P 500
        # Add more as needed
    }
    ```
  - [ ] 3.7.3 For mapped symbols, fetch index info from yfinance
  - [ ] 3.7.4 Use index P/E as proxy (e.g., S&P 500 P/E ~20)
  - [ ] 3.7.5 If no mapping, return neutral fundamentals: `{"pe_ratio": None, ...}`
  - [ ] 3.7.6 Add fallback: Return neutral 50.0 score if constituent data unavailable

- [ ] **3.8 Extend FundamentalData Model for Scoring** (20 min)
  - [ ] 3.8.1 **NOTE**: `fetch_fundamentals_cached()` already exists with basic fields
  - [ ] 3.8.2 Open `backend/app/watchlist/fundamentals.py`, find FundamentalData class (line 35)
  - [ ] 3.8.3 **Current fields** (lines 35-45):
    - ✅ Has: symbol, profit_margin, revenue_growth, debt_to_equity, recommendation_key, recommendation_mean, target_mean_price
    - ❌ Missing for 4-pillar scoring: pe_ratio, pb_ratio, peg_ratio, current_ratio, earnings_growth, eps_trend
  - [ ] 3.8.4 Extend FundamentalData model to add missing fields after target_mean_price (line 44):
    ```python
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    peg_ratio: float | None = None
    current_ratio: float | None = None
    earnings_growth: float | None = None
    ```
  - [ ] 3.8.4 Update YFinanceSource.fetch_fundamentals() to populate new fields:
    ```python
    pe_ratio = info.get("trailingPE")
    pb_ratio = info.get("priceToBook")
    peg_ratio = info.get("pegRatio")
    current_ratio = info.get("currentRatio")
    earnings_growth = info.get("earningsGrowth")
    ```
  - [ ] 3.8.5 Update FinnhubSource and FMPSource similarly (if fields available)
  - [ ] 3.8.6 If is_etf=True, call get_etf_constituent_fundamentals() for proxy data
  - [ ] 3.8.7 Save file

- [ ] **3.9 Integrate Fundamental Scoring into Refresh Service** (15 min)
  - [ ] 3.9.1 Open `backend/app/watchlist/service.py`
  - [ ] 3.9.2 Import: `from .fundamentals import fetch_fundamentals_cached, calculate_fundamental_score`
  - [ ] 3.9.3 Find `refresh_watchlist_scores()` function, locate news integration section added in Task 2.7
  - [ ] 3.9.4 After news integration code and BEFORE signal_inputs dict, add fundamental fetching:
    ```python
    # Fetch fundamentals (cached 24h) - function already exists
    is_etf = symbol in {"SPY", "QQQ", "VOO", "VTI", "IWM", "DIA", "AGG", "BND"}
    fundamental_data = fetch_fundamentals_cached(conn, symbol, ttl_days=1)

    # Calculate 4-pillar score (NEW function)
    if fundamental_data:
        fundamental_score, fundamental_breakdown = calculate_fundamental_score(symbol, fundamental_data)
    else:
        fundamental_score = 50.0  # Neutral if no data
        fundamental_breakdown = {}
    ```
  - [ ] 3.9.5 Later in function, find WatchlistSnapshot construction (search for "WatchlistSnapshot("), add:
    ```python
    fundamental_score=fundamental_score,
    # Store breakdown in raw_metrics JSONB
    raw_metrics={
        **snapshot.raw_metrics,
        "fundamental_breakdown": fundamental_breakdown
    }
    ```
  - [ ] 3.9.6 Save file

- [ ] **3.10 Update ScoreWeights Model & Scoring Formula** (15 min)
  - [ ] 3.10.1 Open `backend/app/watchlist/models.py`
  - [ ] 3.10.2 Find ScoreWeights class (around line 44)
  - [ ] 3.10.3 **Current fields**: price: float = 50.0, technical: float = 50.0
  - [ ] 3.10.4 Add new field after technical (line 48):
    ```python
    fundamental: float = 34.0  # Fundamental pillar weight (PRD #0022)
    ```
  - [ ] 3.10.5 Save models.py
  - [ ] 3.10.6 Open `backend/app/watchlist/scoring.py`
  - [ ] 3.10.7 Find calculate_watchlist_scores() function (around line 159)
  - [ ] 3.10.8 **Current state**: Formula uses dynamic weights from `weights` dict (lines 183-185):
    ```python
    # CURRENT (2-pillar with dynamic weights from user_preferences):
    overall = (
        price_component.score * weights["price"] +
        technical_component.score * weights["technical"]
    )
    # Default weights: {"price": 50.0, "technical": 50.0} from user_preferences
    ```
  - [ ] 3.10.9 **NEW (3-pillar)**: Add fundamental to formula:
    ```python
    # NEW (3-pillar with dynamic weights):
    fundamental_score = inputs.get("fundamental_score", 50.0)  # Default neutral if missing
    overall = (
        price_component.score * weights.get("price", 33) / 100 +
        technical_component.score * weights.get("technical", 33) / 100 +
        fundamental_score * weights.get("fundamental", 34) / 100
    )
    ```
  - [ ] 3.10.10 Update default weights in user_preferences (Task 1.4 migration adds these)
  - [ ] 3.10.11 Update comment explaining weights are user-configurable (33/33/34 default)
  - [ ] 3.10.12 Save file

- [ ] **3.11 Rewrite _load_default_weights to Support 3-Pillar JSONB** (20 min)
  - [ ] 3.11.1 Open `backend/app/watchlist/service.py`
  - [ ] 3.11.2 Find _load_default_weights() function (around line 114-130)
  - [ ] 3.11.3 **Current implementation**: Only loads watchlist_price_weight and watchlist_technical_weight
  - [ ] 3.11.4 **Replace entire function** with new version:
    ```python
    def _load_default_weights(storage: DuckDBStorage) -> ScoreWeights:
        """Load score weights from user_preferences (supports old columns + new JSONB)."""
        df = storage.query("""
            SELECT watchlist_score_weights, watchlist_price_weight, watchlist_technical_weight
            FROM user_preferences
            ORDER BY updated_at DESC
            LIMIT 1
        """)

        if df.is_empty():
            return ScoreWeights()  # Returns default 50.0, 50.0, 34.0

        row = df.to_dicts()[0]

        # Prefer new JSONB field (added in migration 009)
        if "watchlist_score_weights" in row and row["watchlist_score_weights"]:
            weights_json = row["watchlist_score_weights"]
            return ScoreWeights(
                price=float(weights_json.get("price", 33)),
                technical=float(weights_json.get("technical", 33)),
                fundamental=float(weights_json.get("fundamental", 34))
            )
        else:
            # Backward compatibility: Fall back to old separate columns
            return ScoreWeights(
                price=float(row.get("watchlist_price_weight", 50.0) or 50.0),
                technical=float(row.get("watchlist_technical_weight", 50.0) or 50.0),
                fundamental=34.0  # Default for fundamental (no old column)
            )
    ```
  - [ ] 3.11.5 Save file
  - [ ] 3.11.6 Verify both code paths work (JSONB and old columns)

- [ ] **3.12 Write Fundamental Scoring Tests** (30 min)
  - [ ] 3.12.1 Create file: `backend/tests/watchlist/test_fundamentals.py`
  - [ ] 3.12.2 Test valuation_score():
    - Low P/E (10) → high score (80+)
    - High P/E (40) → low score (20-)
    - None values → neutral 50.0
  - [ ] 3.12.3 Test growth_score():
    - High growth (25%) → high score (90+)
    - Negative growth (-5%) → low score (20-)
    - None values → neutral 50.0
  - [ ] 3.12.4 Test health_score():
    - Low debt (0.3), high margin (15%) → high score (80+)
    - High debt (2.5), negative margin → low score (30-)
  - [ ] 3.12.5 Test sentiment_score():
    - "Strong Buy" + 8% earnings beat → high score (90+)
    - "Sell" + -10% earnings miss → low score (20-)
  - [ ] 3.12.6 Test calculate_fundamental_score():
    - All components high → composite 80+
    - All components low → composite 30-
    - Mixed signals → composite 50-60 range
  - [ ] 3.12.7 Test ETF handling:
    - SPY should use constituent averaging
    - If constituent data unavailable, should return neutral 50.0
  - [ ] 3.12.8 Run tests: `pytest tests/watchlist/test_fundamentals.py -v`

- [ ] **3.13 Update Scoring Tests for New Formula** (10 min)
  - [ ] 3.13.1 Open `backend/tests/watchlist/test_scoring.py`
  - [ ] 3.13.2 Find tests that assert overall score calculation
  - [ ] 3.13.3 Update expected values to reflect 33/33/34 weighting (not 50/50)
  - [ ] 3.13.4 Add test for custom weights:
    ```python
    def test_custom_weights():
        user_weights = {"price": 20, "technical": 20, "fundamental": 60}
        result = calculate_watchlist_scores(inputs, user_weights=user_weights)
        # Assert fundamental has larger impact
    ```
  - [ ] 3.13.5 Run tests: `pytest tests/watchlist/test_scoring.py -v`

- [ ] **3.14 Manual Testing with Real Stocks** (15 min)
  - [ ] 3.14.1 Restart services: `bash ~/portfolio-ai/scripts/restart.sh`
  - [ ] 3.14.2 Wait for scheduled refresh (60 seconds)
  - [ ] 3.14.3 Query database: `SELECT symbol, fundamental_score, overall_score FROM watchlist_snapshots ORDER BY fetched_at DESC LIMIT 10;`
  - [ ] 3.14.4 Verify fundamental_score is NOT NULL for stocks
  - [ ] 3.14.5 Verify overall_score reflects 33/33/34 weighting
  - [ ] 3.14.6 Test ETF (SPY): Should have fundamental_score (neutral or constituent avg)
  - [ ] 3.14.7 Check logs for any fundamental fetch errors
  - [ ] 3.14.8 Take screenshot: `docs/screenshots/watchlist/task-3.14-fundamental-scores.png`

---

## Task 4.0: Add Volume Confirmation & Multi-Timeframe Alignment ⏱️ 4 hours

**Goal**: Calculate volume_relative, backtest multiplier (1.5x vs 2.0x), add signal boosts, add multi-timeframe alignment

- [ ] **4.1 Add Volume Calculation to Service** (15 min)
  - [ ] 4.1.1 Open `backend/app/watchlist/service.py`
  - [ ] 4.1.2 Find `refresh_watchlist_scores()` function, locate fundamental scoring section added in Task 3.9
  - [ ] 4.1.3 After fundamental scoring code and BEFORE signal_inputs dict, add volume calculation:
    ```python
    # Calculate volume relative to 50-day average
    volume_query = """
        SELECT AVG(volume) as avg_volume
        FROM day_bars
        WHERE symbol = %s
        AND date >= CURRENT_DATE - INTERVAL '50 days'
    """
    volume_result = conn.execute(volume_query, (symbol,)).fetchone()
    volume_50d_avg = volume_result[0] if volume_result and volume_result[0] else None

    current_volume = price_data.volume if hasattr(price_data, 'volume') else None

    if volume_50d_avg and current_volume and volume_50d_avg > 0:
        volume_relative = current_volume / volume_50d_avg
    else:
        volume_relative = None
    ```
  - [ ] 4.1.4 Later in function, find WatchlistSnapshot construction and add: `volume_relative=volume_relative`
  - [ ] 4.1.5 Save file

- [ ] **4.2 Create Volume Backtest Script** (30 min)
  - [ ] 4.2.1 Create file: `backend/scripts/backtest_volume_multiplier.py`
  - [ ] 4.2.2 Query historical breakouts from day_bars:
    ```python
    # Date range: January 1, 2024 to October 31, 2024 (10 months of data)
    # Symbols: Use existing watchlist symbols or S&P 100 components with >$5B market cap
    # Criteria: Find price breakouts where close > sma_50 after being below for 3+ days
    # Success metric: Price continues up 5+ days later (5-day return > 2%)
    # Minimum samples: Need 30+ breakout events for statistical significance
    ```
  - [ ] 4.2.3 For each breakout, calculate volume_relative (volume / 50-day avg)
  - [ ] 4.2.4 Test 1.5x multiplier:
    - Filter breakouts where volume >= 1.5x avg
    - Calculate success rate: (successful / total) * 100
    - Report: count, success rate, sample size
  - [ ] 4.2.5 Test 2.0x multiplier:
    - Filter breakouts where volume >= 2.0x avg
    - Calculate success rate
    - Report: count, success rate, sample size
  - [ ] 4.2.6 Compare results, output:
    ```
    Date Range: 2024-01-01 to 2024-10-31
    Sample Size: 47 total breakouts

    1.5x multiplier: 68% success rate (23/34 breakouts)
    2.0x multiplier: 75% success rate (15/20 breakouts)

    Recommendation: Use 1.5x (better sample size, acceptable success rate)
    ```
  - [ ] 4.2.7 If insufficient data (<30 samples), default to 1.5x (research standard)
  - [ ] 4.2.8 Document decision in code comment with date range and results

- [ ] **4.3 Run Volume Backtest** (10 min)
  - [ ] 4.3.1 Activate venv: `cd ~/portfolio-ai/backend && source .venv/bin/activate`
  - [ ] 4.3.2 Run: `python scripts/backtest_volume_multiplier.py`
  - [ ] 4.3.3 Review output, note optimal multiplier
  - [ ] 4.3.4 Save results to: `docs/backtest-volume-results.txt`

- [ ] **4.4 Add Volume Confirmation to Signal Classification** (20 min)
  - [ ] 4.4.1 Open `backend/app/watchlist/service.py`
  - [ ] 4.4.2 Find `refresh_watchlist_scores()` function, locate signal_inputs dict construction (search for "signal_inputs = {")
  - [ ] 4.4.3 Add volume_relative to signal_inputs dict:
    ```python
    "volume_relative": volume_relative,  # Calculated in Task 4.1
    ```
  - [ ] 4.4.4 Open `backend/app/watchlist/narrative.py`
  - [ ] 4.4.5 Find classify_signal() function (around line 496)
  - [ ] 4.4.6 **NOTE**: Function currently expects `volume_avg_20` (line 528), need to add `volume_relative`
  - [ ] 4.4.7 In classify_signal(), extract volume_relative from inputs (after line 531):
    ```python
    volume_relative = inputs.get("volume_relative", 1.0)  # Default to 1.0 (normal volume)
    ```
  - [ ] 4.4.8 After initial signal classification (around line 563), add volume boost logic:
    ```python
    # Volume confirmation (boost BUY signals with high volume)
    volume_multiplier = 1.5  # From backtest results or user preference
    if signal_type == SignalType.BUY and volume_relative:
        if volume_relative >= volume_multiplier:
            strength_value += 2
            reasons.append(f"Volume confirms breakout ({volume_relative:.1f}x avg)")
        elif volume_relative < 0.8:
            strength_value -= 1
            reasons.append(f"Low volume - watch for fakeout ({volume_relative:.1f}x avg)")
    ```
  - [ ] 4.4.9 Clamp strength: `strength_value = max(0, min(10, strength_value))`
  - [ ] 4.4.10 Save file

- [ ] **4.5 Calculate Multi-Timeframe Alignment in Service** (15 min)
  - [ ] 4.5.1 **NOTE**: Timeframe flags should be calculated in service.py, NOT narrative.py
  - [ ] 4.5.2 Open `backend/app/watchlist/service.py`
  - [ ] 4.5.3 Find `refresh_watchlist_scores()` function, locate volume_relative calculation added in Task 4.1
  - [ ] 4.5.4 After volume_relative calculation and BEFORE signal_inputs dict, add timeframe alignment logic:
    ```python
    # Multi-timeframe alignment checks (for database storage)
    price = price_data.price
    sma_20 = technical_snapshot.sma_20
    sma_50 = technical_snapshot.sma_50
    sma_200 = technical_snapshot.sma_200

    timeframe_short_aligned = bool(
        price and sma_20 and sma_50 and
        price > sma_20 and sma_20 > sma_50
    )

    timeframe_long_aligned = bool(
        sma_50 and sma_200 and
        sma_50 > sma_200
    )
    ```
  - [ ] 4.5.5 Later in function, find WatchlistSnapshot construction and add:
    ```python
    timeframe_short_aligned=timeframe_short_aligned,
    timeframe_long_aligned=timeframe_long_aligned,
    ```
  - [ ] 4.5.6 **Optional**: In narrative.py classify_signal(), add signal strength boost if both aligned:
    ```python
    # Multi-timeframe alignment bonus (if needed for signal strength)
    # Note: Flags already calculated in service.py for DB storage
    if inputs.get("timeframe_short_aligned") and inputs.get("timeframe_long_aligned"):
        strength_value += 1
        reasons.append("Multi-timeframe alignment confirmed")
    ```
  - [ ] 4.5.7 Save both files

- [ ] **4.7 Write Volume Confirmation Tests** (15 min)
  - [ ] 4.7.1 Create file: `backend/tests/watchlist/test_volume_confirmation.py`
  - [ ] 4.7.2 Test high volume BUY:
    - BUY signal + volume_relative=2.3 → strength +2
    - Assert reasons includes "Volume confirms breakout"
  - [ ] 4.7.3 Test low volume BUY:
    - BUY signal + volume_relative=0.5 → strength -1
    - Assert reasons includes "Low volume - watch for fakeout"
  - [ ] 4.7.4 Test normal volume:
    - BUY signal + volume_relative=1.0 → no change
  - [ ] 4.7.5 Test HOLD/AVOID signals:
    - Volume should not affect HOLD/AVOID strength
  - [ ] 4.7.6 Run tests: `pytest tests/watchlist/test_volume_confirmation.py -v`

- [ ] **4.8 Write Multi-Timeframe Alignment Tests** (15 min)
  - [ ] 4.8.1 Create file: `backend/tests/watchlist/test_timeframe_alignment.py`
  - [ ] 4.8.2 Test full alignment:
    - price > sma_20 > sma_50 > sma_200 → strength +1
    - Assert both flags True
  - [ ] 4.8.3 Test short-term only:
    - price > sma_20 > sma_50, but sma_50 < sma_200 → no boost
    - Assert short_aligned=True, long_aligned=False
  - [ ] 4.8.4 Test long-term only:
    - sma_50 > sma_200, but price < sma_20 → no boost
  - [ ] 4.8.5 Test no alignment:
    - All conditions fail → no boost, both flags False
  - [ ] 4.8.6 Run tests: `pytest tests/watchlist/test_timeframe_alignment.py -v`

- [ ] **4.9 Update Narrative Tests** (10 min)
  - [ ] 4.9.1 Open `backend/tests/watchlist/test_narrative.py`
  - [ ] 4.9.2 Update existing signal classification tests to account for volume/timeframe boosts
  - [ ] 4.9.3 If test expects strength=7 but now it's 8 (due to volume boost), update assertion
  - [ ] 4.9.4 Run all narrative tests: `pytest tests/watchlist/test_narrative.py -v`
  - [ ] 4.9.5 Fix any failures

- [ ] **4.10 Manual Testing with Real Data** (15 min)
  - [ ] 4.10.1 Restart services: `bash ~/portfolio-ai/scripts/restart.sh`
  - [ ] 4.10.2 Wait for scheduled refresh
  - [ ] 4.10.3 Query: `SELECT symbol, volume_relative, timeframe_short_aligned, timeframe_long_aligned FROM watchlist_snapshots ORDER BY fetched_at DESC LIMIT 10;`
  - [ ] 4.10.4 Verify volume_relative is calculated (should be float like 1.8, 2.3, etc.)
  - [ ] 4.10.5 Find a ticker with high volume (>1.5x) and check if signal strength increased
  - [ ] 4.10.6 Find a ticker with alignment and verify flags are True
  - [ ] 4.10.7 Check logs for volume/timeframe calculation
  - [ ] 4.10.8 Take screenshot: `docs/screenshots/watchlist/task-4.10-volume-timeframe.png`

---

## Task 5.0: UI Reorganization - Main Table & Priority Indicators ⏱️ 4 hours

**Goal**: Create priority indicators module, reorganize table to 8 columns, add tooltips, rename style → timeframe

- [ ] **5.1 Create Priority Indicators Module** (20 min)
  - [ ] 5.1.1 Create file: `backend/app/watchlist/priority.py`
  - [ ] 5.1.2 Add module docstring and imports
  - [ ] 5.1.3 Define PriorityIndicator model:
    ```python
    class PriorityIndicator(BaseModel):
        icon: str            # "🔥", "📉", etc.
        label: str           # "Hot Opportunity", "Declining", etc.
        tooltip: str         # Full explanation
        priority: int        # 1-8 (for sorting, 1 = highest)
    ```
  - [ ] 5.1.4 Define priority order constant:
    ```python
    PRIORITY_ORDER = {
        "hot": 1,
        "declining": 2,
        "event": 3,
        "news": 4,
        "value": 5,
        "momentum": 6,
        "defensive": 7,
        "caution": 8
    }
    ```

- [ ] **5.2 Implement Priority Check Functions** (40 min)
  - [ ] 5.2.1 Write `check_hot_opportunity()`:
    ```python
    def check_hot_opportunity(
        overall_score: float,
        signal_type: str,
        rank_in_watchlist: int
    ) -> PriorityIndicator | None:
        """Check if ticker is in top 3 with BUY signal."""
        if signal_type == "BUY" and rank_in_watchlist <= 3:
            return PriorityIndicator(
                icon="🔥",
                label="Hot Opportunity",
                tooltip="Top 3 highest-scoring BUY signals. Strong technical and fundamental alignment.",
                priority=PRIORITY_ORDER["hot"]
            )
        return None
    ```
  - [ ] 5.2.2 Write `check_declining()`: score dropped >10 points in 7 days
  - [ ] 5.2.3 Write `check_event_catalyst()`: earnings_days_away < 7
  - [ ] 5.2.4 Write `check_news_alert()`: news_sentiment < -0.3 OR news <24h old
  - [ ] 5.2.5 Write `check_value_play()`: fundamental_score > 70 AND price_score < 50
  - [ ] 5.2.6 Write `check_momentum()`: price_score > 70 AND technical_score > 70
  - [ ] 5.2.7 Write `check_defensive()`: risk_level == "Low" AND volatility < sector_avg
  - [ ] 5.2.8 Write `check_caution()`: (price > 70 AND fundamental < 40) OR (price < 30 AND fundamental > 70)

- [ ] **5.3 Write Main Priority Calculator** (15 min)
  - [ ] 5.3.1 Define function:
    ```python
    def calculate_priority_indicators(
        watchlist_items: list[dict],  # All items to rank
        current_item: dict              # Item being evaluated
    ) -> list[PriorityIndicator]:
        """
        Calculate priority indicators for a watchlist item.
        Returns max 2 indicators, sorted by priority (highest first).
        """
    ```
  - [ ] 5.3.2 Rank items by overall_score to determine top 3
  - [ ] 5.3.3 Call all 8 check functions
  - [ ] 5.3.4 Collect non-None results
  - [ ] 5.3.5 Sort by priority (1 = highest)
  - [ ] 5.3.6 Return top 2: `return sorted_indicators[:2]`
  - [ ] 5.3.7 Add logging: `logger.debug("priority_indicators_calculated", symbol=symbol, count=len(result))`

- [ ] **5.4 Integrate Priority Calculation into API** (15 min)
  - [ ] 5.4.1 Open `backend/app/api/watchlist.py`
  - [ ] 5.4.2 Import: `from ..watchlist.priority import calculate_priority_indicators, PriorityIndicator`
  - [ ] 5.4.3 Find GET /api/watchlist endpoint (around line 100)
  - [ ] 5.4.4 After fetching all watchlist items, call calculate_priority_indicators for each
  - [ ] 5.4.5 Add priority_indicators field to response model
  - [ ] 5.4.6 Save file

- [ ] **5.5 Rename recommended_style → recommended_timeframe** (20 min)
  - [ ] 5.5.1 Open `backend/app/watchlist/models.py`
  - [ ] 5.5.2 Find WatchlistSnapshot class (around line 136)
  - [ ] 5.5.3 Change field name: `recommended_timeframe: str | None = None`
  - [ ] 5.5.4 Add backward compatibility property:
    ```python
    @property
    def recommended_style(self) -> str | None:
        """Deprecated: Use recommended_timeframe instead."""
        return self.recommended_timeframe
    ```
  - [ ] 5.5.5 Search codebase for "recommended_style" (18 occurrences)
  - [ ] 5.5.6 Update service.py (around line 701): Use `recommended_timeframe` in snapshot construction
  - [ ] 5.5.7 Update api/watchlist.py: Add both fields to response (old + new)
  - [ ] 5.5.8 Update narrative.py: classify_trading_style() returns timeframe values

- [ ] **5.6 Map Style Values to Timeframe Categories** (10 min)
  - [ ] 5.6.1 Open `backend/app/watchlist/narrative.py`
  - [ ] 5.6.2 Find classify_trading_style() function (around line 421)
  - [ ] 5.6.3 Update return values:
    ```python
    # OLD: return "Index", confidence=10, holding="Hold indefinitely"
    # NEW: return "Long-Term (Hold)", confidence=10, holding="Hold indefinitely"

    # Mapping:
    # Index → "Long-Term (Hold)"
    # Event → "Quick Trade (<1 week)"
    # Swing → "Short-Term (1-3 weeks)"
    # Trend → "Medium-Term (1-6 months)"
    # Value → "Long-Term (6-12 months)"
    ```
  - [ ] 5.6.4 Update all return statements with new values
  - [ ] 5.6.5 Update docstring to reflect timeframe (not style)
  - [ ] 5.6.6 Save file

- [ ] **5.7 Calculate Daily Price Change % in API** (10 min)
  - [ ] 5.7.1 Open `backend/app/api/watchlist.py`
  - [ ] 5.7.2 In GET /api/watchlist, after fetching items
  - [ ] 5.7.3 For each item, query day_bars for today and yesterday:
    ```python
    price_change_query = """
        SELECT close
        FROM day_bars
        WHERE symbol = %s AND date = CURRENT_DATE - INTERVAL '1 day'
        ORDER BY date DESC LIMIT 1
    """
    prev_close = conn.execute(price_change_query, (symbol,)).fetchone()
    if prev_close and current_price:
        price_change_pct = ((current_price - prev_close[0]) / prev_close[0]) * 100
    else:
        price_change_pct = None
    ```
  - [ ] 5.7.4 Add to response: `price_change_pct: float | None`
  - [ ] 5.7.5 Save file

- [ ] **5.8 Update API Response Models** (10 min)
  - [ ] 5.8.1 In same api/watchlist.py file
  - [ ] 5.8.2 Find WatchlistItemResponse model
  - [ ] 5.8.3 Add new fields:
    ```python
    fundamental_score: float | None = None
    volume_relative: float | None = None
    timeframe_short_aligned: bool = False
    timeframe_long_aligned: bool = False
    percentile_rank: float | None = None
    percentile_bucket: str | None = None  # "Top 10%", "Top 20%", etc.
    score_trend: str | None = None  # "↑", "↓", "→"
    priority_indicators: list[PriorityIndicator] = []
    price_change_pct: float | None = None
    recommended_timeframe: str | None = None
    ```
  - [ ] 5.8.4 Keep old field for backward compatibility (30 days):
    ```python
    @property
    def recommended_style(self) -> str | None:
        return self.recommended_timeframe
    ```
  - [ ] 5.8.5 Save file

- [ ] **5.9 Create Priority Indicator Frontend Component** (20 min)
  - [ ] 5.9.1 Verify directory exists: `ls frontend/components/watchlist/` (should exist, has WatchlistTable.tsx)
  - [ ] 5.9.2 Create file: `frontend/components/watchlist/PriorityIndicator.tsx`
  - [ ] 5.9.3 Import Tooltip from shadcn/ui
  - [ ] 5.9.4 Define PriorityIndicator interface:
    ```typescript
    interface PriorityIndicator {
      icon: string;
      label: string;
      tooltip: string;
      priority: number;
    }
    ```
  - [ ] 5.9.5 Create component:
    ```typescript
    export function PriorityIndicatorBadge({ indicator }: { indicator: PriorityIndicator }) {
      return (
        <Tooltip>
          <TooltipTrigger>
            <Badge variant="outline" className="gap-1">
              <span>{indicator.icon}</span>
              <span className="text-xs">{indicator.label}</span>
            </Badge>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">
            <p>{indicator.tooltip}</p>
          </TooltipContent>
        </Tooltip>
      );
    }
    ```
  - [ ] 5.9.6 Export component

- [ ] **5.10 Update Frontend API Types** (10 min)
  - [ ] 5.10.1 Open `frontend/lib/api/watchlist.ts`
  - [ ] 5.10.2 Find WatchlistItem interface
  - [ ] 5.10.3 Add new fields matching backend response:
    ```typescript
    fundamental_score?: number;
    volume_relative?: number;
    timeframe_short_aligned?: boolean;
    timeframe_long_aligned?: boolean;
    percentile_rank?: number;
    percentile_bucket?: string;
    score_trend?: string;
    priority_indicators?: PriorityIndicator[];
    price_change_pct?: number;
    recommended_timeframe?: string;
    ```
  - [ ] 5.10.4 Add PriorityIndicator interface
  - [ ] 5.10.5 Keep recommended_style for backward compatibility
  - [ ] 5.10.6 Save file

- [ ] **5.11 Reorganize Main Table Columns** (40 min)
  - [ ] 5.11.1 Open `frontend/components/watchlist/WatchlistTable.tsx`
  - [ ] 5.11.2 Update columns array to 8 columns:
    ```typescript
    const columns = [
      // 1. Symbol (with event badges)
      {
        accessorKey: "symbol",
        header: "Symbol ↑",
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            <span>{row.original.symbol}</span>
            <SourceBadge source={row.original.source} />
            {row.original.earnings_days_away < 7 && <span>📅</span>}
            {row.original.news_sentiment_score < -0.3 && <span>📰</span>}
          </div>
        )
      },

      // 2. Priority Indicators (NEW)
      {
        accessorKey: "priority_indicators",
        header: "Priority",
        cell: ({ row }) => (
          <div className="flex gap-1">
            {row.original.priority_indicators?.map(indicator => (
              <PriorityIndicatorBadge key={indicator.label} indicator={indicator} />
            ))}
          </div>
        )
      },

      // 3. Timeframe (renamed from Style)
      {
        accessorKey: "recommended_timeframe",
        header: "Timeframe",
        cell: ({ row }) => (
          <div>
            <span>{row.original.recommended_timeframe}</span>
            <span className="text-muted-foreground text-xs"> · {row.original.risk_level}</span>
          </div>
        )
      },

      // 4. Headline (NEW)
      {
        accessorKey: "narrative_headline",
        header: "Headline",
        cell: ({ row }) => (
          <span className="truncate max-w-[300px]">
            {row.original.narrative_headline?.substring(0, 40)}...
          </span>
        )
      },

      // 5. Price (actual stock price, not score)
      {
        accessorKey: "current_price",
        header: "Price",
        cell: ({ row }) => {
          const price = row.original.price;  // Stock price (NOT current_score.price which is score)
          const change = row.original.price_change_pct;
          return (
            <div>
              <span>${price?.toFixed(2)}</span>
              {change && (
                <span className={change > 0 ? "text-green-500" : "text-red-500"}>
                  ({change > 0 ? "+" : ""}{change.toFixed(2)}%)
                </span>
              )}
            </div>
          );
        }
      },

      // 6. Score (overall + percentile)
      {
        accessorKey: "current_score.overall",
        header: "Score",
        cell: ({ row }) => {
          const score = row.original.current_score?.overall;
          const bucket = row.original.percentile_bucket;
          return (
            <span>
              {score?.toFixed(0)} {bucket && `(${bucket})`}
            </span>
          );
        }
      },

      // 7. Trend (keep sparkline)
      {
        accessorKey: "score_history",
        header: "7-Day Trend",
        cell: ({ row }) => <SparklineWithHistory history={row.original.score_history} />
      },

      // 8. Updated (relative time)
      {
        accessorKey: "updated_at",
        header: "Updated",
        cell: ({ row }) => {
          const updated = row.original.updated_at;
          const relativeTime = formatDistanceToNow(new Date(updated), { addSuffix: true });
          return <span>{relativeTime}</span>;
        }
      }
    ];
    ```
  - [ ] 5.11.3 Remove old "Signal" column (info now in priority indicators)
  - [ ] 5.11.4 Import PriorityIndicatorBadge component
  - [ ] 5.11.5 Import formatDistanceToNow from date-fns
  - [ ] 5.11.6 Save file

- [ ] **5.12 Update Filter Dropdown Labels** (5 min)
  - [ ] 5.12.1 In same WatchlistTable.tsx file
  - [ ] 5.12.2 Find filter dropdown (TradingStyleFilter component or inline)
  - [ ] 5.12.3 Update label from "Trading Styles" to "Timeframes"
  - [ ] 5.12.4 Update option values to match new timeframe categories
  - [ ] 5.12.5 Save file

- [ ] **5.13 Test Priority Indicators** (15 min)
  - [ ] 5.13.1 Create file: `backend/tests/watchlist/test_priority_indicators.py`
  - [ ] 5.13.2 Test hot opportunity detection (top 3 BUY)
  - [ ] 5.13.3 Test declining detection (score dropped >10)
  - [ ] 5.13.4 Test event catalyst (earnings <7 days)
  - [ ] 5.13.5 Test max 2 indicators returned
  - [ ] 5.13.6 Test priority ordering (🔥 before ⚠️)
  - [ ] 5.13.7 Run tests: `pytest tests/watchlist/test_priority_indicators.py -v`

- [ ] **5.14 UI End-to-End Testing** (20 min)
  - [ ] 5.14.1 Restart services: `bash ~/portfolio-ai/scripts/restart.sh`
  - [ ] 5.14.2 Open http://192.168.8.233:3000/watchlist
  - [ ] 5.14.3 **DO NOT** click refresh - observe natural behavior
  - [ ] 5.14.4 Verify 8 columns visible
  - [ ] 5.14.5 Verify priority indicators show with icons
  - [ ] 5.14.6 Hover over indicator, verify tooltip appears
  - [ ] 5.14.7 Verify "Timeframe" column shows new values (not old styles)
  - [ ] 5.14.8 Verify "Headline" column shows truncated narrative
  - [ ] 5.14.9 Verify "Price" column shows $X.XX (±Y%)
  - [ ] 5.14.10 Verify "Score" column shows "72 (Top 20%)"
  - [ ] 5.14.11 Verify "Updated" shows "3m ago"
  - [ ] 5.14.12 Check browser console for errors
  - [ ] 5.14.13 Check network tab for API errors
  - [ ] 5.14.14 Take screenshot: `docs/screenshots/watchlist/task-5.14-new-table-columns.png`

---

## Task 6.0: Historical Context & Percentiles ⏱️ 3 hours

**Goal**: Calculate 30-day percentile ranks, add trend indicators, extend snapshot retention

- [ ] **6.1 Create Percentiles Module** (15 min)
  - [ ] 6.1.1 Create file: `backend/app/watchlist/percentiles.py`
  - [ ] 6.1.2 Add module docstring and imports
  - [ ] 6.1.3 Define percentile bucket function:
    ```python
    def get_percentile_bucket(percentile: float) -> str:
        """Convert percentile to bucket label."""
        if percentile >= 90:
            return "Top 10%"
        elif percentile >= 80:
            return "Top 20%"
        elif percentile >= 50:
            return "Top 50%"
        elif percentile >= 20:
            return "Below Avg"
        else:
            return "Bottom 10%"
    ```

- [ ] **6.2 Write Percentile Calculation Function** (20 min)
  - [ ] 6.2.1 Define function:
    ```python
    def calculate_percentile_rank(
        conn,
        item_id: str,
        current_score: float
    ) -> tuple[float, str]:
        """
        Calculate percentile rank vs last 30 days.
        Returns (percentile, bucket_label).
        """
    ```
  - [ ] 6.2.2 Query last 30 days of scores:
    ```python
    query = """
        SELECT overall_score
        FROM watchlist_snapshots
        WHERE item_id = %s
        AND fetched_at >= CURRENT_DATE - INTERVAL '30 days'
        AND overall_score IS NOT NULL
        ORDER BY fetched_at DESC
    """
    result = conn.execute(query, (item_id,)).fetchall()
    scores = [row[0] for row in result]
    ```
  - [ ] 6.2.3 Calculate percentile:
    ```python
    if not scores or len(scores) < 7:
        return (None, None)  # Need at least 7 days of data

    below_current = sum(1 for s in scores if s < current_score)
    percentile = (below_current / len(scores)) * 100
    bucket = get_percentile_bucket(percentile)
    ```
  - [ ] 6.2.4 Return tuple: `(percentile, bucket)`
  - [ ] 6.2.5 Add error handling for edge cases

- [ ] **6.3 Write Trend Indicator Function** (10 min)
  - [ ] 6.3.1 Define function:
    ```python
    def calculate_score_trend(
        conn,
        item_id: str,
        current_score: float
    ) -> str:
        """
        Calculate trend indicator: ↑ (improving), ↓ (declining), → (stable).
        Compares current score to 7-day average.
        """
    ```
  - [ ] 6.3.2 Query 7-day average:
    ```python
    query = """
        SELECT AVG(overall_score) as avg_score
        FROM watchlist_snapshots
        WHERE item_id = %s
        AND fetched_at >= CURRENT_DATE - INTERVAL '7 days'
        AND overall_score IS NOT NULL
    """
    result = conn.execute(query, (item_id,)).fetchone()
    avg_7d = result[0] if result else None
    ```
  - [ ] 6.3.3 Compare and return trend:
    ```python
    if not avg_7d:
        return "→"

    diff = current_score - avg_7d
    if diff > 5:
        return "↑"
    elif diff < -5:
        return "↓"
    else:
        return "→"
    ```
  - [ ] 6.3.4 Return trend string

- [ ] **6.4 Create Daily Percentile Calculation Task** (15 min)
  - [ ] 6.4.1 Open `backend/app/tasks/agent_tasks.py`
  - [ ] 6.4.2 Add new Celery task:
    ```python
    @celery_app.task(name="calculate_daily_percentiles")
    def calculate_daily_percentiles_task(account_id: str = "default") -> dict[str, Any]:
        """
        Calculate percentile ranks for all watchlist items.
        Runs once per day to avoid expensive computation on every refresh.
        """
        conn = get_storage()

        # Get all active watchlist items
        items = conn.query("SELECT id, symbol FROM watchlist_items WHERE account_id = %s", (account_id,))

        updated_count = 0
        for item in items:
            # Get latest snapshot
            latest = conn.query(
                "SELECT overall_score FROM watchlist_snapshots WHERE item_id = %s ORDER BY fetched_at DESC LIMIT 1",
                (item["id"],)
            ).fetchone()

            if not latest:
                continue

            # Calculate percentile
            percentile, bucket = calculate_percentile_rank(conn, item["id"], latest["overall_score"])
            trend = calculate_score_trend(conn, item["id"], latest["overall_score"])

            # Update latest snapshot with percentile data
            conn.execute("""
                UPDATE watchlist_snapshots
                SET percentile_rank_30d = %s
                WHERE item_id = %s
                AND fetched_at = (
                    SELECT MAX(fetched_at) FROM watchlist_snapshots WHERE item_id = %s
                )
            """, (percentile, item["id"], item["id"]))

            updated_count += 1

        return {"updated_count": updated_count}
    ```
  - [ ] 6.4.3 Save file

- [ ] **6.5 Schedule Daily Percentile Task** (5 min)
  - [ ] 6.5.1 In same agent_tasks.py file
  - [ ] 6.5.2 Find Celery beat schedule configuration
  - [ ] 6.5.3 Add new scheduled task:
    ```python
    "calculate-daily-percentiles": {
        "task": "calculate_daily_percentiles",
        "schedule": crontab(hour=1, minute=0),  # Run at 1 AM daily
        "args": ["default"],
    }
    ```
  - [ ] 6.5.4 Save file

- [ ] **6.6 Extend Snapshot Retention to 30 Days** (10 min)
  - [ ] 6.6.1 In same agent_tasks.py file
  - [ ] 6.6.2 Find snapshot cleanup task (if exists)
  - [ ] 6.6.3 If doesn't exist, create new task:
    ```python
    @celery_app.task(name="cleanup_old_snapshots")
    def cleanup_old_snapshots_task() -> dict[str, Any]:
        """Delete snapshots older than 90 days."""
        conn = get_storage()

        result = conn.execute("""
            DELETE FROM watchlist_snapshots
            WHERE fetched_at < CURRENT_DATE - INTERVAL '90 days'
        """)

        deleted_count = result.rowcount
        logger.info("old_snapshots_cleaned", deleted_count=deleted_count)

        return {"deleted_count": deleted_count}
    ```
  - [ ] 6.6.4 Schedule weekly: `"schedule": crontab(day_of_week=0, hour=2, minute=0)`
  - [ ] 6.6.5 Update comment: Keep 30 days for percentiles, delete after 90 days
  - [ ] 6.6.6 Save file

- [ ] **6.7 Integrate Percentiles into API Response** (10 min)
  - [ ] 6.7.1 Open `backend/app/api/watchlist.py`
  - [ ] 6.7.2 In GET /api/watchlist endpoint
  - [ ] 6.7.3 For each item, query percentile data from latest snapshot:
    ```python
    percentile_query = """
        SELECT percentile_rank_30d
        FROM watchlist_snapshots
        WHERE item_id = %s
        ORDER BY fetched_at DESC LIMIT 1
    """
    percentile_result = conn.execute(percentile_query, (item_id,)).fetchone()
    percentile_rank = percentile_result[0] if percentile_result else None
    percentile_bucket = get_percentile_bucket(percentile_rank) if percentile_rank else None
    ```
  - [ ] 6.7.4 Calculate trend (call calculate_score_trend)
  - [ ] 6.7.5 Add to response: `percentile_rank`, `percentile_bucket`, `score_trend`
  - [ ] 6.7.6 Save file

- [ ] **6.8 Update Expanded Row with Percentile Details** (20 min)
  - [ ] 6.8.1 Open `frontend/components/watchlist/ExpandedRow.tsx`
  - [ ] 6.8.2 Find Score Breakdown section (or create if doesn't exist)
  - [ ] 6.8.3 Add detailed percentile display:
    ```typescript
    <div className="score-breakdown">
      <h4>Score Breakdown</h4>
      <div className="grid grid-cols-2 gap-4">
        {/* Price Score */}
        <div>
          <span>Price Score: {item.current_score.price.toFixed(1)}</span>
          <span className="text-muted">{item.price_percentile || "—"}</span>
        </div>

        {/* Technical Score */}
        <div>
          <span>Technical Score: {item.current_score.technical.toFixed(1)}</span>
          <span className="text-muted">{item.technical_percentile || "—"}</span>
        </div>

        {/* Fundamental Score (NEW) */}
        <div>
          <span>Fundamental Score: {item.fundamental_score?.toFixed(1) || "N/A"}</span>
          <span className="text-muted">{item.fundamental_percentile || "—"}</span>
        </div>

        {/* Overall Score */}
        <div className="col-span-2 border-t pt-2">
          <span className="font-semibold">Overall: {item.current_score.overall.toFixed(1)}</span>
          <span className="text-muted">
            {item.percentile_bucket || "—"}
            {item.score_trend && <span className="ml-2">{item.score_trend}</span>}
          </span>
          <p className="text-xs text-muted-foreground">
            30-day average: {item.score_30d_avg?.toFixed(1) || "N/A"} |
            Percentile: {item.percentile_rank?.toFixed(0)}th (Top {(100 - item.percentile_rank).toFixed(0)}%)
          </p>
        </div>
      </div>
    </div>
    ```
  - [ ] 6.8.4 Save file

- [ ] **6.9 Write Percentile Calculation Tests** (20 min)
  - [ ] 6.9.1 Create file: `backend/tests/watchlist/test_percentiles.py`
  - [ ] 6.9.2 Test get_percentile_bucket():
    - 95 → "Top 10%"
    - 85 → "Top 20%"
    - 55 → "Top 50%"
    - 30 → "Below Avg"
    - 10 → "Bottom 10%"
  - [ ] 6.9.3 Test calculate_percentile_rank():
    - With 30 days of data, current score 80, avg 70 → percentile ~75th
    - With <7 days of data → return (None, None)
    - Edge case: All scores identical → percentile 50th
  - [ ] 6.9.4 Test calculate_score_trend():
    - Current 75, avg 65 → "↑"
    - Current 60, avg 70 → "↓"
    - Current 70, avg 68 → "→"
  - [ ] 6.9.5 Run tests: `pytest tests/watchlist/test_percentiles.py -v`

- [ ] **6.10 Manual Testing & Validation** (20 min)
  - [ ] 6.10.1 Restart services: `bash ~/portfolio-ai/scripts/restart.sh`
  - [ ] 6.10.2 Trigger percentile calculation manually:
    ```python
    from backend.app.tasks.agent_tasks import calculate_daily_percentiles_task
    calculate_daily_percentiles_task("default")
    ```
  - [ ] 6.10.3 Query database: `SELECT symbol, percentile_rank_30d FROM watchlist_snapshots ORDER BY fetched_at DESC LIMIT 10;`
  - [ ] 6.10.4 Verify percentile_rank_30d is populated (0-100 range)
  - [ ] 6.10.5 Open UI: http://192.168.8.233:3000/watchlist
  - [ ] 6.10.6 Verify main table shows "72 (Top 20%)" format
  - [ ] 6.10.7 Expand row, verify detailed percentile breakdown visible
  - [ ] 6.10.8 Verify trend indicator (↑ ↓ →) appears
  - [ ] 6.10.9 Check logs for percentile calculation
  - [ ] 6.10.10 Take screenshot: `docs/screenshots/watchlist/task-6.10-percentiles.png`

---

## Task 7.0: Testing, Documentation & Validation ⏱️ 3 hours

**Goal**: Write comprehensive tests, update documentation, validate with declining stocks, performance check

- [ ] **7.1 Run All Existing Tests** (5 min)
  - [ ] 7.1.1 Activate venv: `cd ~/portfolio-ai/backend && source .venv/bin/activate`
  - [ ] 7.1.2 Run: `pytest tests/ -v`
  - [ ] 7.1.3 Note any failures
  - [ ] 7.1.4 If failures exist, fix before proceeding

- [ ] **7.2 Write Missing Unit Tests** (30 min)
  - [ ] 7.2.1 Create `tests/watchlist/test_volume_confirmation.py` (if not done in Task 4)
  - [ ] 7.2.2 Create `tests/watchlist/test_timeframe_alignment.py` (if not done in Task 4)
  - [ ] 7.2.3 Create `tests/watchlist/test_fundamentals.py` (if not done in Task 3)
  - [ ] 7.2.4 Create `tests/watchlist/test_priority_indicators.py` (if not done in Task 5)
  - [ ] 7.2.5 Create `tests/watchlist/test_percentiles.py` (if not done in Task 6)
  - [ ] 7.2.6 Run each: `pytest tests/watchlist/test_*.py -v`

- [ ] **7.3 Write Integration Tests** (30 min)
  - [ ] 7.3.1 Create file: `tests/integration/test_watchlist_refresh_integration.py`
  - [ ] 7.3.2 Test full refresh cycle:
    - Add ticker to watchlist
    - Trigger scheduled refresh
    - Verify all new fields populated (fundamental_score, volume_relative, etc.)
  - [ ] 7.3.3 Test ETF fundamental scoring (SPY):
    - Add SPY to watchlist
    - Verify fundamental_score uses constituent averaging
  - [ ] 7.3.4 Test news integration:
    - Verify news_sentiment_score is NOT NULL after refresh
    - Verify recent_news_headlines contains data
  - [ ] 7.3.5 Test AVOID signal with declining stock:
    - Add historically declining ticker (HOOD from 2022)
    - Verify AVOID signal triggers with 2 flags
  - [ ] 7.3.6 Run: `pytest tests/integration/test_watchlist_refresh_integration.py -v`

- [ ] **7.4 Update Existing Tests for New Schema** (20 min)
  - [ ] 7.4.1 Open `tests/watchlist/test_model_extended.py`
  - [ ] 7.4.2 Add assertions for new fields:
    - fundamental_score
    - volume_relative
    - timeframe_short_aligned
    - timeframe_long_aligned
    - percentile_rank_30d
  - [ ] 7.4.3 Open `tests/api/test_watchlist.py`
  - [ ] 7.4.4 Update response schema validation to include new fields
  - [ ] 7.4.5 Run: `pytest tests/api/test_watchlist.py -v`

- [ ] **7.5 Check Test Coverage** (5 min)
  - [ ] 7.5.1 Run: `pytest tests/ --cov=app --cov-report=term-missing`
  - [ ] 7.5.2 Verify coverage >= 85%
  - [ ] 7.5.3 Identify any uncovered lines
  - [ ] 7.5.4 Write tests for critical uncovered paths

- [ ] **7.6 Type Checking** (5 min)
  - [ ] 7.6.1 Run: `mypy app/ --strict`
  - [ ] 7.6.2 Fix any type errors
  - [ ] 7.6.3 Ensure all new functions have type hints

- [ ] **7.7 Linting** (5 min)
  - [ ] 7.7.1 Run: `./scripts/lint.sh`
  - [ ] 7.7.2 Fix any linting errors (ruff format + ruff check)
  - [ ] 7.7.3 Verify all checks pass

- [ ] **7.8 Browser Automation Screenshots** (30 min)
  - [ ] 7.8.1 Open http://192.168.8.233:3000/watchlist
  - [ ] 7.8.2 Take screenshot of main table: `docs/screenshots/watchlist/prd-0022-main-table-new.png`
  - [ ] 7.8.3 Expand row with BUY signal, screenshot: `prd-0022-expanded-buy.png`
  - [ ] 7.8.4 Expand row with HOLD signal, screenshot: `prd-0022-expanded-hold.png`
  - [ ] 7.8.5 Expand row with AVOID signal (if available), screenshot: `prd-0022-expanded-avoid.png`
  - [ ] 7.8.6 Click filter dropdown, screenshot: `prd-0022-filter-timeframes.png`
  - [ ] 7.8.7 Filter by "Short-Term", screenshot: `prd-0022-filtered-short-term.png`
  - [ ] 7.8.8 Hover over priority indicator, screenshot tooltip: `prd-0022-tooltip.png`
  - [ ] 7.8.9 Mobile view (resize browser to 390px), screenshot: `prd-0022-mobile.png`

- [ ] **7.9 Update ARCHITECTURE.md** (20 min)
  - [ ] 7.9.1 Open `docs/core/ARCHITECTURE.md`
  - [ ] 7.9.2 Search for "Watchlist" section: `grep -n "Watchlist" docs/core/ARCHITECTURE.md`
  - [ ] 7.9.3 Identify correct line number for insertion (verify it's actually around line 192)
  - [ ] 7.9.4 Add subsection "Fundamental Scoring System":
    ```markdown
    **Fundamental Scoring System** (PRD #0022):
    - Three-pillar scoring: Price (33%) + Technical (33%) + Fundamental (34%)
    - Fundamental components: Valuation (30%), Growth (35%), Health (25%), Sentiment (10%)
    - ETF handling: Constituent averaging for SPY, QQQ, etc.
    - Data sources: YFinance (primary) → Finnhub → FMP (failover)
    - Cached 24 hours (fundamentals change slowly)
    - User-configurable weights in preferences table
    ```
  - [ ] 7.9.5 Add subsection "Volume Confirmation":
    ```markdown
    **Volume Confirmation** (PRD #0022):
    - Volume relative to 50-day average
    - BUY signals boosted +2 if volume >1.5x average
    - BUY signals penalized -1 if volume <0.8x average
    - Research-backed: 70% of successful breakouts have high volume
    ```
  - [ ] 7.9.6 Add subsection "Multi-Timeframe Alignment":
    ```markdown
    **Multi-Timeframe Alignment** (PRD #0022):
    - Short-term: price > SMA_20 > SMA_50
    - Long-term: SMA_50 > SMA_200
    - Signal strength +1 if both aligned (uptrend on multiple timeframes)
    - Research-backed: 65% of successful trades have alignment
    ```
  - [ ] 7.9.7 Add subsection "Historical Context & Percentiles":
    ```markdown
    **Historical Context & Percentiles** (PRD #0022):
    - 30-day percentile rank calculation (daily batch job)
    - Percentile buckets: Top 10%, Top 20%, Top 50%, Below Avg, Bottom 10%
    - Trend indicators: ↑ (improving), ↓ (declining), → (stable)
    - Snapshot retention: 30 days for percentiles, 90 days max
    ```
  - [ ] 7.9.8 Update overall score formula description
  - [ ] 7.9.9 Save file

- [ ] **7.10 Update API_REFERENCE.md** (15 min)
  - [ ] 7.10.1 Open `docs/core/API_REFERENCE.md`
  - [ ] 7.10.2 Find Watchlist Router section (around line 140)
  - [ ] 7.10.3 Update GET /api/watchlist response schema:
    - Add fundamental_score
    - Add volume_relative
    - Add timeframe_short_aligned, timeframe_long_aligned
    - Add percentile_rank, percentile_bucket, score_trend
    - Add priority_indicators array
    - Add price_change_pct
    - Rename recommended_style → recommended_timeframe (note backward compatibility)
  - [ ] 7.10.4 Add example response JSON with new fields
  - [ ] 7.10.5 Save file

- [ ] **7.11 Update README in Screenshots Directory** (10 min)
  - [ ] 7.11.1 Open `docs/screenshots/watchlist/README.md`
  - [ ] 7.11.2 Add section for PRD #0022 screenshots
  - [ ] 7.11.3 List all new screenshots with descriptions
  - [ ] 7.11.4 Explain new columns and features visible
  - [ ] 7.11.5 Save file

- [ ] **7.12 Performance Validation** (20 min)
  - [ ] 7.12.1 Add 50 tickers to watchlist (if not already)
  - [ ] 7.12.2 Monitor refresh cycle:
    - Check logs: Count API calls per ticker
    - Target: <5 API calls per ticker
    - With caching: Should be ~1-2 per ticker
  - [ ] 7.12.3 Measure refresh duration:
    - Start time (check logs)
    - End time
    - Total duration for 50 tickers (target: <30 seconds)
  - [ ] 7.12.4 Query percentile calculation time:
    ```sql
    EXPLAIN ANALYZE
    SELECT overall_score FROM watchlist_snapshots
    WHERE item_id = 'some-id'
    AND fetched_at >= CURRENT_DATE - INTERVAL '30 days'
    ```
  - [ ] 7.12.5 Verify query time <50ms (index working)
  - [ ] 7.12.6 Check rate limit logs: No rate limit hits
  - [ ] 7.12.7 Document results: `docs/performance-validation-prd-0022.txt`

- [ ] **7.13 Declining Stock Validation** (20 min)
  - [ ] 7.13.1 Ensure declining stock (HOOD, COIN, or ZM) in watchlist
  - [ ] 7.13.2 Wait for next scheduled refresh (60 seconds)
  - [ ] 7.13.3 Query database:
    ```sql
    SELECT symbol, signal_type, news_sentiment_score,
           current_score->>'price' as price_score,
           current_score->>'technical' as tech_score
    FROM watchlist_snapshots
    WHERE symbol IN ('HOOD', 'COIN', 'ZM')
    ORDER BY fetched_at DESC LIMIT 3;
    ```
  - [ ] 7.13.4 Verify AVOID signal if conditions met (2+ flags)
  - [ ] 7.13.5 Check logs for AVOID flag reasons
  - [ ] 7.13.6 Open UI, verify 📉 declining indicator or AVOID signal visible
  - [ ] 7.13.7 Take screenshot: `docs/screenshots/watchlist/prd-0022-avoid-validation.png`

- [ ] **7.14 Fundamental Scoring Edge Cases** (15 min)
  - [ ] 7.14.1 Test with ETF (SPY):
    - Verify fundamental_score populates
    - Check logs for constituent averaging
  - [ ] 7.14.2 Test with stock missing fundamental data:
    - Add ticker with no P/E (e.g., unprofitable startup)
    - Verify neutral score (50.0) used
    - Verify no errors in logs
  - [ ] 7.14.3 Test with very old ticker (low volume):
    - Verify volume_relative handles low/no volume gracefully
  - [ ] 7.14.4 Test with newly added ticker (<7 days data):
    - Verify percentile returns None (not enough data)
    - Verify no crash

- [ ] **7.15 False Positive Analysis for AVOID Signals** (10 min)
  - [ ] 7.15.1 Over next 3 days, monitor AVOID signals
  - [ ] 7.15.2 For each AVOID, check if stock actually declined or recovered
  - [ ] 7.15.3 Calculate false positive rate: (false positives / total AVOID) * 100
  - [ ] 7.15.4 If FP rate >20%, increase threshold to 3 flags
  - [ ] 7.15.5 Document findings: `docs/avoid-signal-validation.txt`

---

## Verification (MANDATORY before "COMPLETE ✅")

- [ ] **Functional Requirements**
  - [ ] All 8 functional requirements from PRD implemented
  - [ ] AVOID signals trigger with 2 flags (tested with declining stock)
  - [ ] Fundamental scoring works for stocks AND ETFs
  - [ ] Volume confirmation boosts BUY signals appropriately
  - [ ] Multi-timeframe alignment adds +1 strength
  - [ ] Percentile ranks calculated and displayed
  - [ ] Priority indicators show max 2 per ticker with tooltips
  - [ ] Main table shows 8 new columns
  - [ ] Expanded row shows Score Breakdown with 3 pillars
  - [ ] All narrative fields preserved (no regressions)

- [ ] **Quality Gates**
  - [ ] All tests passing: `pytest tests/ -v` (100% pass rate)
  - [ ] Test coverage >= 85%: `pytest tests/ --cov=app --cov-report=term`
  - [ ] Type checking passes: `mypy app/ --strict` (zero errors)
  - [ ] Linting passes: `./scripts/lint.sh` (zero errors)
  - [ ] No `Any` types in new code (except where unavoidable)
  - [ ] All functions have docstrings with type hints
  - [ ] No magic numbers (constants defined)
  - [ ] Single source of truth (no duplicate logic)

- [ ] **Security & Best Practices**
  - [ ] All SQL queries parameterized (no f-strings with user input)
  - [ ] No secrets in code (API keys in env/db only)
  - [ ] Error handling comprehensive (no unhandled exceptions)
  - [ ] Logging added for key operations (fundamental fetch, percentile calc, etc.)
  - [ ] User input validated (scores 0-100, percentile 0-100, etc.)

- [ ] **Documentation**
  - [ ] ARCHITECTURE.md updated with new sections
  - [ ] API_REFERENCE.md updated with new fields
  - [ ] Screenshots captured and documented
  - [ ] Performance validation documented
  - [ ] AVOID signal validation documented

- [ ] **Operational**
  - [ ] Services restarted after all changes: `bash ~/portfolio-ai/scripts/restart.sh`
  - [ ] Services start time AFTER code changes (verify with systemctl)
  - [ ] Scheduled refresh working (wait 2+ cycles, verify timestamps change)
  - [ ] No errors in logs: `tail -100 backend/logs/app.log`
  - [ ] UI loads without console errors
  - [ ] Network requests succeed (check browser DevTools)
  - [ ] Database migration applied successfully

- [ ] **Performance**
  - [ ] API calls per ticker <5 (target: 3-4 typical, 1-2 with caching)
  - [ ] Refresh duration <30 seconds for 50 tickers
  - [ ] Percentile calculation <50ms per ticker
  - [ ] No rate limit hits observed
  - [ ] Frontend renders table <100ms with 50 rows

- [ ] **User Acceptance**
  - [ ] User can identify top 3 opportunities in <5 seconds (priority indicators visible)
  - [ ] Priority indicator tooltips are clear and actionable
  - [ ] Percentile context makes scores interpretable ("72 (Top 20%)")
  - [ ] Timeframe labels clearer than old "Style" labels
  - [ ] Headline column shows valuable info at a glance
  - [ ] No regressions: All existing features still work

---

## Notes

### Key Files Modified (24 files)
- **Backend**: indicators.py, models.py, service.py, scoring.py, narrative.py, fundamentals.py (new), priority.py (new), percentiles.py (new), api/watchlist.py, tasks/agent_tasks.py
- **Frontend**: WatchlistTable.tsx, ExpandedRow.tsx, PriorityIndicator.tsx (new), ScoreBreakdown.tsx (new), api/watchlist.ts
- **Tests**: 10 new test files, 8 updated test files
- **Docs**: ARCHITECTURE.md, API_REFERENCE.md, screenshots/watchlist/README.md
- **Database**: Migration 009

### Testing Strategy
- **Unit Tests**: Test each scoring function, priority indicator, percentile calculation independently
- **Integration Tests**: Test full refresh cycle with real (or mocked) API calls
- **Manual Tests**: Test with real declining stocks, ETFs, edge cases
- **Performance Tests**: Measure API call count, refresh duration, query times

### Rollback Plan
If critical bugs discovered:
1. **Database**: Columns are nullable, old code can ignore them
2. **API**: Old field names preserved for 30 days (backward compatibility)
3. **Frontend**: Can roll back to old UI without backend changes
4. **Services**: Restart with previous code version

### Known Limitations
1. **ETF Fundamentals**: Hardcoded mapping for SPY/QQQ/etc. Won't work for all ETFs.
2. **Percentile Calculation**: Requires 7 days of data minimum (returns None otherwise)
3. **Volume Backtest**: May not have enough historical breakouts for definitive answer (default 1.5x)
4. **False Positives**: AVOID threshold=2 may be too sensitive (monitor and adjust)

---

**END OF TASK LIST**

**Next Command**: `/do_it tasks/tasks-0022-watchlist-intelligence-2.md`

This will execute all tasks autonomously with TDD enforcement, systematic debugging, and verification gates at each step.
