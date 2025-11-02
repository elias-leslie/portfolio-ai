# PRD #0023: Fix Watchlist Data Pipeline - Unblock BUY/AVOID Signals

**Status**: Draft
**Created**: 2025-11-02
**Priority**: CRITICAL
**Effort**: Medium (8-12 hours)
**Risk**: Low (fixing existing code, no new architecture)
**Dependencies**: PRD #0021 (narrative intelligence code exists)

---

## Introduction

The watchlist narrative intelligence system (PRD #0021) was implemented and marked "100% complete" with all code in place. However, **production testing reveals ALL 14 tickers generate identical HOLD 4/10 signals**, rendering the system useless for actual trading decisions.

**Root Cause**: Missing data prevents signal classification from working:
- Fundamental data not populating (company_health = NULL)
- Earnings data not populating (earnings_date = NULL)
- Volume data hardcoded to None instead of queried from database
- Signal classification uses all-or-nothing logic (requires ALL conditions for BUY)

**Business Impact**: Users perceive system as "not working" because every ticker looks identical. The comprehensive narrative intelligence framework (signal classification, trading styles, position sizing) cannot deliver value without the underlying data.

---

## Problem Statement

**Current Behavior** (Verified Nov 2, 2025 via live UI testing):
- All 14 tickers: HOLD 4/10 signal (no variation)
- Price scores: 50.0 (static, no real calculation)
- Company health: NULL for all tickers
- Earnings dates: NULL for all tickers
- Technical scores: 67.4-89.0 (working correctly - only field with real data)

**Expected Behavior**:
- Mix of BUY (🟢), HOLD (🟡), AVOID (🔴) signals across tickers
- Signal strength varies 1-10 based on number of confirming factors
- NVDA (strong fundamentals + uptrend) → BUY 8/10
- AAPL (sideways consolidation) → HOLD 5/10
- Tickers with earnings <5 days → AVOID 2/10

**Impact**: System value drops from potential 7/10 to actual 2/10 due to data pipeline failures.

---

## Goals

### Primary Goals
1. **Generate diverse signals**: See BUY, HOLD, AVOID signals across 14-ticker test watchlist
2. **Populate fundamental data**: Achieve 80%+ success rate for company_health classification
3. **Populate earnings data**: Achieve 70%+ success rate for earnings_date fetching
4. **Integrate volume data**: Query from day_bars table, calculate 20-day average
5. **Fix signal scoring**: Replace all-or-nothing logic with strength-based scoring (1-10)

### Secondary Goals
6. Fix history endpoint test failure (expects 7 items, gets 10)
7. Maintain 85%+ test coverage
8. Add integration tests for fundamentals/earnings fetching
9. E2E UI validation of mixed signals

---

## User Stories

### US-1: Actionable Buy Signals
**As a** trader
**I want** to see BUY signals for stocks with strong fundamentals and good technical setups
**So that** I can identify high-probability entry opportunities

**Acceptance Criteria**:
- NVDA (profit margin 53%, revenue +122% YoY, uptrend, RSI 58) → BUY 8/10 or 9/10
- BUY signal shows: entry price, stop loss, target, position size
- Signal strength reflects number of confirming factors (8/10 = 4 of 5 conditions met)

### US-2: Protective Avoid Signals
**As a** trader
**I want** to see AVOID signals for stocks approaching earnings or with weak fundamentals
**So that** I can stay out of high-risk setups

**Acceptance Criteria**:
- Stock with earnings in 3 days → AVOID with "⚠️ Earnings in 3 days" warning
- Stock with profit margin <0% → AVOID with "Unprofitable company" note
- AVOID signals prevent capital loss from predictable volatility

### US-3: Informed Hold Signals
**As a** trader
**I want** to see HOLD signals with clear reasoning for quality companies in poor timing
**So that** I can wait for better entry points

**Acceptance Criteria**:
- AAPL (good fundamentals but RSI 72 overbought) → HOLD 5/10 with "Overbought - wait for pullback"
- HOLD signals show what's missing: "Good company, but already extended +8% this week"

### US-4: Data Pipeline Reliability
**As a** system operator
**I want** fundamental/earnings data to fetch reliably with multi-source failover
**So that** signals remain accurate even when primary data source fails

**Acceptance Criteria**:
- YFinance primary source fetches successfully for 80%+ of tickers
- Finnhub fallback activates when YFinance fails
- Errors logged with clear source attribution (e.g., "YFinance failed: rate limit, falling back to Finnhub")

---

## Functional Requirements

### FR-1: Fix Signal Classification Scoring Logic

**Current Implementation** (`backend/app/watchlist/narrative.py:classify_signal()`):
```python
# BUY requires ALL conditions (all-or-nothing):
if (price > ema_20 AND rsi in 30-70 AND macd > 0 AND
    volume >= 70% AND company_health in ["EXCELLENT", "GOOD"] AND
    news_sentiment >= 0.2):
    return BUY
else:
    return HOLD
```

**Problem**: Single missing data point (e.g., news_sentiment = NULL) blocks BUY signal.

**Required Change**: Scoring system where BUY strength = count of confirming factors:

```python
# Score each factor independently
confirmations = []
if price > ema_20: confirmations.append("uptrend")
if rsi in 30-70: confirmations.append("healthy_rsi")
if macd > 0: confirmations.append("positive_momentum")
if volume >= 70% of 20d_avg: confirmations.append("strong_volume")
if company_health in ["EXCELLENT", "GOOD"]: confirmations.append("good_fundamentals")
if news_sentiment >= 0.2: confirmations.append("positive_news")  # optional

# BUY if >= 3 confirmations, strength = count / total_checked
if len(confirmations) >= 3:
    signal_type = BUY
    signal_strength = min(10, int((len(confirmations) / 5) * 10))
```

**Acceptance Criteria**:
- BUY signals possible with 3+ confirmations (not requiring all 6)
- Signal strength 1-10 reflects confidence (3/5 = 6/10, 5/5 = 10/10)
- News sentiment optional (doesn't block BUY if NULL)
- AVOID triggers on ANY critical factor (earnings <5 days, company_health = WEAK)

### FR-2: Debug and Fix Fundamental Data Fetching

**Current Behavior**: `fetch_fundamentals_cached()` returns None for all tickers

**Investigation Steps**:
1. Add debug logging to `backend/app/watchlist/fundamentals.py:fetch_fundamentals_cached()`
2. Test YFinance API directly with NVDA:
   ```python
   import yfinance as yf
   ticker = yf.Ticker("NVDA")
   print(ticker.info.get("profitMargins"))  # Should return 0.53
   print(ticker.info.get("revenueGrowth"))  # Should return 1.22
   ```
3. Check if API keys exist for Finnhub/FMP:
   ```bash
   echo $FINNHUB_API_KEY
   echo $FMP_API_KEY
   ```
4. If keys missing, verify free tier signup and add to `.env`

**Required Fixes**:
- If YFinance rate-limited: Add retry logic with exponential backoff
- If API response structure changed: Update field mappings (e.g., `profitMargins` → `profit_margin`)
- If parsing errors: Add try/except with specific error logging
- Ensure `reference_cache` TTL (24 hours) respects to avoid excessive refetching

**Acceptance Criteria**:
- NVDA fundamental data fetches successfully:
  - `profit_margin`: 0.53 (53%)
  - `revenue_growth`: 1.22 (122% YoY)
  - `company_health`: "EXCELLENT"
- Logs show clear source attribution: "Fetched NVDA fundamentals from YFinance (200 OK)"
- Fallback activates on failure: "YFinance failed (429 rate limit), trying Finnhub..."
- 80%+ of 14 test tickers have company_health populated

### FR-3: Debug and Fix Earnings Data Fetching

**Current Behavior**: `fetch_earnings_date_cached()` returns None for all tickers

**Investigation Steps**:
1. Add debug logging to `backend/app/watchlist/earnings.py:fetch_earnings_date_cached()`
2. Test Finnhub API directly (requires API key):
   ```python
   import requests
   url = f"https://finnhub.io/api/v1/calendar/earnings?from=2025-11-01&to=2025-12-31&symbol=AAPL&token={FINNHUB_API_KEY}"
   response = requests.get(url)
   print(response.json())
   ```
3. Test YFinance fallback:
   ```python
   ticker = yf.Ticker("AAPL")
   print(ticker.calendar)  # Should show earnings date
   ```

**Required Fixes**:
- Verify Finnhub API key exists and is valid (free tier: 60 req/min)
- If Finnhub requires paid tier for earnings: Switch to YFinance primary
- Update date parsing if API response format changed
- Handle tickers without scheduled earnings (e.g., ETFs) gracefully

**Acceptance Criteria**:
- AAPL earnings date fetches successfully with days_away calculation
- ETFs (SPY, QQQ, VOO) handle missing earnings gracefully (NULL, not error)
- Logs show: "Fetched AAPL earnings from Finnhub: 2025-11-21 (19 days away)"
- 70%+ of stock tickers (excluding ETFs) have earnings_date populated

### FR-4: Integrate Volume Data from day_bars

**Current Code** (`backend/app/watchlist/service.py:474`):
```python
signal_inputs = {
    "volume": None,  # Not available in current data ❌
}
```

**Reality**: Volume IS available in `day_bars` table:
```sql
SELECT volume FROM day_bars WHERE ticker = 'NVDA' ORDER BY date DESC LIMIT 20;
```

**Required Implementation**:
1. Query latest 20 days of volume from `day_bars`
2. Calculate 20-day average: `avg_volume = sum(volumes) / 20`
3. Check if current volume >= 70% of average
4. Pass to signal classifier: `"volume": current_volume` and `"volume_avg_20d": avg_volume`

**Acceptance Criteria**:
- Volume data populated for all tickers with day_bars history
- Signal inputs include: `volume`, `volume_avg_20d`, `volume_ratio` (current/avg)
- Logs show: "NVDA volume: 45M (95% of 20d avg 47M) - strong conviction"
- Tickers without 20 days of data handle gracefully (volume check skipped, not failed)

### FR-5: Fix History Endpoint Test Failure

**Current Test**:
```python
def test_get_score_history_extracts_price_score_from_raw_metrics():
    # ... setup ...
    assert len(data["history"]) == 7  # FAILS: actual = 10
```

**Root Cause**: Test assumes yfinance returns exactly 7 trading days for 15 calendar days request, but market may have more trading days depending on holidays.

**Required Fix**:
```python
assert len(data["history"]) >= 7  # At least 7 days
assert len(data["history"]) <= 15  # No more than 15 calendar days
```

**Acceptance Criteria**:
- Test passes with flexible assertion
- History endpoint returns 7-10 trading days (varies by market calendar)
- Test validates correct fields present (timestamp, overall, price_score, technical_score)

### FR-6: Add Integration Tests for Data Fetching

**New Test File**: `backend/tests/integration/test_watchlist_data_pipeline.py`

**Test Cases**:
1. `test_fundamentals_fetch_with_yfinance_success()` - Verify YFinance returns data for NVDA
2. `test_fundamentals_fallback_to_finnhub()` - Mock YFinance failure, verify Finnhub called
3. `test_earnings_fetch_with_finnhub()` - Verify Finnhub returns earnings date for AAPL
4. `test_volume_calculation_from_day_bars()` - Verify 20-day average calculated correctly
5. `test_signal_classification_with_real_data()` - End-to-end test with NVDA (should be BUY 8+/10)

**Acceptance Criteria**:
- All 5 integration tests pass
- Tests use real API calls (not mocked) to validate actual data pipeline
- Tests skip if API keys not configured (mark as skipped, not failed)
- Total test suite: 145 + 5 = 150 tests passing

### FR-7: E2E UI Validation with Browser Automation

**Validation Steps** (using browser automation skill):
1. Navigate to http://localhost:3000/watchlist
2. Take screenshot: verify mixed signals visible (not all HOLD)
3. Verify NVDA shows BUY with green badge
4. Expand NVDA row: verify company health bullets appear
5. Verify earnings warnings for tickers with upcoming earnings
6. Check console: no JavaScript errors

**Acceptance Criteria**:
- Screenshot shows at least 3 different signal types (BUY, HOLD, AVOID)
- Signal strengths vary (not all 4/10)
- Company health section populated for 80%+ of tickers
- Earnings warnings appear when applicable
- No console errors during navigation/interaction

---

## Non-Goals (Out of Scope)

1. **News Sentiment Integration** - Explicitly deferred to Phase 3 per watchlist_review.md
2. **AI Regenerate Button** - Templates work fine, defer indefinitely
3. **Sector Fundamental Metric Map** - Too complex (246-line appendix), not needed for individual investors
4. **Competitor Scores** - Adds clutter, focus on absolute signals not relative ranking
5. **Multi-Scenario Guidance** - "Breakout vs Pullback" scenarios add complexity without proportional value
6. **Backtesting Framework** - Defer to separate PRD (8-12 hours effort)
7. **Mobile Responsive Testing** - Defer to separate PRD (focus on data pipeline first)

---

## Technical Considerations

### Existing Infrastructure (Reuse, Don't Rebuild)

**Multi-Source Failover Pattern** (already implemented in `backend/app/portfolio/price_fetcher.py`):
```python
class MultiSourceDataFetcher:
    def fetch_with_failover(self, symbol):
        for source in [YFinanceSource, FinnhubSource, FMPSource]:
            try:
                data = source.fetch(symbol)
                if data:
                    return data
            except Exception as e:
                logger.warning(f"{source} failed: {e}, trying next...")
        return None
```

**Apply same pattern to**:
- `fundamentals.py:fetch_fundamentals_cached()`
- `earnings.py:fetch_earnings_date_cached()`

**Caching Strategy** (already implemented in `reference_cache` table):
- Fundamentals: 24-hour TTL (low volatility)
- Earnings: 30-day TTL (infrequent updates)
- Volume: No caching (query day_bars directly)

### API Key Configuration

**Keys Already Configured** ✅

API keys are stored in the database (`source_credentials` table) and loaded into environment variables at startup via `credential_loader.py`:

**Verified Keys in Database**:
```sql
SELECT source_id, field FROM source_credentials;
-- finnhub | token  → FINNHUB_API_KEY (cteoh4hr01qngidcae3g...)
-- fmp     | apikey → FMP_API_KEY (DQEdmFAEpNT1ZeTsm9Rs...)
```

**Credential Loading Flow**:
1. Application starts → `main.py:lifespan()` executes
2. `load_credentials_from_database()` called (line 62)
3. Queries `source_credentials` table
4. Maps database entries to env vars:
   - `finnhub.token` → `os.environ["FINNHUB_API_KEY"]`
   - `fmp.apikey` → `os.environ["FMP_API_KEY"]`
5. Code uses `os.getenv("FINNHUB_API_KEY")` successfully

**Mapping Reference** (`backend/app/storage/credential_loader.py:47-62`):
- `(finnhub, token)` → `FINNHUB_API_KEY`
- `(fmp, apikey)` → `FMP_API_KEY`
- `(alphavantage, apikey)` → `ALPHAVANTAGE_API_KEY`
- `(twelvedata, apikey)` → `TWELVEDATA_API_KEY`
- `(polygon, apiKey)` → `POLYGON_API_KEY`

**Free Tier Quotas** (Already Active):
- YFinance: Unlimited (primary source, no key needed)
- Finnhub: 60 req/min (sufficient for watchlist refresh)
- FMP: 250 req/day (sufficient as tertiary fallback)

**Conclusion**: Keys are configured correctly. Problem is NOT missing keys - it's data fetching logic or API response parsing.

### Data Source Endpoint Verification

**Code vs YAML Configuration**:

| Data Type | YFinance Code | Finnhub Endpoint | FMP Endpoint | Coverage |
|-----------|---------------|------------------|--------------|----------|
| Fundamentals | `ticker.info` dict | `/stock/metric` | `/api/v3/ratios/X` | 3 sources ✅ |
| Earnings | `ticker.calendar` dict | `/calendar/earnings` | ❌ Not available | 2 sources ✅ |
| Volume | ❌ Not used (from day_bars table) | N/A | N/A | Database only |

**Potential Root Causes**:
1. YFinance API field names changed (e.g., `profitMargins` → `profit_margin`)
2. Silent failures - all exceptions return `None` without logging
3. No retry logic for rate limits
4. Caching not integrated in fetch functions

### Database Schema (No Changes Needed)

All columns already exist from migration 008:
- `watchlist_snapshots.company_health TEXT`
- `watchlist_snapshots.earnings_date DATE`
- `watchlist_snapshots.earnings_days_away INTEGER`
- `day_bars.volume BIGINT` (existing historical data table)

### Signal Classification Logic Changes

**Old Logic** (all-or-nothing):
```python
if all_conditions_met:
    return BUY
else:
    return HOLD
```

**New Logic** (scoring-based):
```python
score = 0
max_score = 0

# Technical factors (always available)
max_score += 3
if price > ema_20: score += 1
if rsi in 30-70: score += 1
if macd > 0: score += 1

# Optional factors (may be NULL)
if volume is not None:
    max_score += 1
    if volume >= 70% of avg: score += 1

if company_health is not None:
    max_score += 1
    if company_health in ["EXCELLENT", "GOOD"]: score += 1

if news_sentiment is not None:
    max_score += 1
    if news_sentiment >= 0.2: score += 1

# Calculate signal
strength = int((score / max_score) * 10)
if score >= 3:
    return BUY, strength
elif score <= 1:
    return AVOID, (10 - strength)
else:
    return HOLD, 5
```

---

## Success Metrics

### Quantitative Metrics

1. **Signal Diversity**: At least 3 different signal types across 14-ticker test watchlist (not all HOLD)
2. **Data Population Rate**:
   - Company health: 80%+ tickers (11 of 14)
   - Earnings dates: 70%+ stocks (8 of 12, excluding ETFs)
   - Volume data: 100% tickers with day_bars history
3. **Test Coverage**: Maintain 85%+ coverage (currently 85%, add 5 integration tests)
4. **Test Pass Rate**: 150/150 tests passing (145 existing + 5 new)

### Qualitative Metrics

1. **NVDA Validation**: Generates BUY 8/10 or 9/10 (strong fundamentals + uptrend)
2. **Signal Reasoning Transparency**: Logs show which conditions met/failed for each ticker
3. **Error Attribution**: Logs clearly identify which data source failed and why
4. **User Experience**: Watchlist shows actionable diversity (not perceived as "broken")

### Validation Checklist

- [ ] See BUY signal with green badge (🟢)
- [ ] See HOLD signal with yellow badge (🟡)
- [ ] See AVOID signal with red badge (🔴) OR earnings warning
- [ ] Signal strengths vary (1/10, 5/10, 8/10, etc.)
- [ ] Company health section shows bullets for 80%+ tickers
- [ ] Earnings warnings appear when date < 14 days
- [ ] Volume ratio shown in logs (e.g., "95% of average")
- [ ] All 150 tests passing
- [ ] No console errors during E2E testing

---

## Open Questions

### Q1: API Key Availability
**Question**: Are Finnhub and FMP API keys already configured in production environment?

**Resolution Path**:
- Check `.env` file for `FINNHUB_API_KEY` and `FMP_API_KEY`
- If missing: Sign up for free tiers and add keys
- If YFinance sufficient (>80% success): Skip secondary sources for now

### Q2: Volume Data Availability
**Question**: Do all 14 test tickers have 20+ days of volume data in day_bars table?

**Resolution Path**:
- Query: `SELECT ticker, COUNT(*) FROM day_bars WHERE ticker IN ('AAPL', 'NVDA', ...) GROUP BY ticker`
- If insufficient: Trigger historical backfill (existing task: `ingest_historical_ohlcv.delay()`)
- Handle gracefully: Skip volume check if <20 days (don't fail signal)

### Q3: Signal Strength Calibration
**Question**: Should BUY 3/10 be called HOLD instead (weak buy = hold)?

**Proposed Thresholds**:
- Score >= 70% (4+ of 6 factors) → BUY (strength 7-10)
- Score 40-69% (2-3 factors) → HOLD (strength 4-6)
- Score <= 39% (0-1 factors) → AVOID (strength 1-3)

**Decision**: Start with 50% threshold (3+ factors = BUY), adjust based on production data

---

## Implementation Notes

### Development Workflow

1. **Phase 1: Investigation** (2-3 hours)
   - Add debug logging to fundamentals.py, earnings.py
   - Test API calls directly with NVDA, AAPL
   - Identify root cause of data failures
   - Document findings in task list

2. **Phase 2: Fix Data Fetching** (3-4 hours)
   - Fix fundamental data fetching (YFinance API changes?)
   - Fix earnings data fetching (Finnhub key config?)
   - Add volume query from day_bars (20-day average)
   - Test with 14 tickers, verify 80%+ success

3. **Phase 3: Update Signal Logic** (2-3 hours)
   - Refactor `classify_signal()` to use scoring
   - Make news_sentiment optional
   - Update tests to reflect new logic
   - Verify NVDA generates BUY 8+/10

4. **Phase 4: Testing & Validation** (2-3 hours)
   - Add 5 integration tests
   - Fix history endpoint test
   - Run full test suite (150 tests)
   - E2E UI validation with browser automation
   - Screenshot verification

### Risk Mitigation

**Risk 1**: YFinance API changed field names (e.g., `profitMargins` → `profit_margin`)
- Mitigation: Test directly with NVDA, update mappings
- Fallback: Use Finnhub/FMP if YFinance unreliable

**Risk 2**: Finnhub API key not configured or expired
- Mitigation: Verify key in `.env`, test with direct API call
- Fallback: Use YFinance only (accept lower success rate)

**Risk 3**: Volume data missing in day_bars (new tickers)
- Mitigation: Skip volume check gracefully (log warning, don't fail signal)
- Fallback: Trigger historical backfill automatically on ticker creation

**Risk 4**: Signal scoring produces too many BUY signals (false positives)
- Mitigation: Start conservative (require 4+ of 6 factors for BUY)
- Fallback: Add backtesting validation in separate PRD to tune thresholds

### Commit Strategy

- Commit 1: "debug: add logging to fundamentals and earnings fetching"
- Commit 2: "fix: update fundamental data fetching for YFinance API changes"
- Commit 3: "fix: add volume data from day_bars with 20-day average"
- Commit 4: "refactor: signal classification to use strength-based scoring"
- Commit 5: "test: add integration tests for data pipeline"
- Commit 6: "test: fix history endpoint test assertion"
- Commit 7: "docs: update watchlist_review.md with resolution status"

---

## Appendix: Root Cause Evidence

**Live Production Screenshot Analysis** (Nov 2, 2025):
- All 14 tickers: HOLD 4/10 (identical)
- Price scores: 50.0 (no variation)
- Technical scores: 67.4-89.0 (working correctly)
- Company health: NULL for all
- Earnings dates: NULL for all

**Code Investigation Findings**:
1. `service.py:474` - volume hardcoded to None
2. `service.py:442-444` - fundamentals fetch in try/except, returns None
3. `service.py:454` - earnings fetch in try/except, returns None
4. `narrative.py:classify_signal()` - all-or-nothing logic (requires ALL conditions)

**Test Results**:
- 21/22 tests passing (95.5% pass rate)
- 1 failure: history endpoint expects 7 items, gets 10 (yfinance variance)

**Conclusion**: Code architecture is sound, data pipeline is broken. Fix data fetching + signal logic to unlock value.

---

**END OF PRD #0023**
