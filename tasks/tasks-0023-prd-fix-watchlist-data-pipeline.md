# Task List: Fix Watchlist Data Pipeline - Unblock BUY/AVOID Signals

**PRD**: `0023-prd-fix-watchlist-data-pipeline.md`
**Status**: Ready for Implementation
**Priority**: CRITICAL
**Effort**: Medium (8-12 hours)
**Created**: 2025-11-02

---

## Summary

Fix the watchlist data pipeline to enable diverse BUY/HOLD/AVOID signals instead of all tickers showing HOLD 4/10. The narrative intelligence code is complete, but data fetching is broken.

**Current State**: All 14 tickers → HOLD 4/10 (system perceived as broken)
**Target State**: Mix of signals → BUY 8/10, HOLD 5/10, AVOID 2/10 (actionable)

**Root Causes**:
1. Fundamental data not populating (company_health = NULL)
2. Earnings data not populating (earnings_date = NULL)
3. Volume data hardcoded to None (not queried from day_bars)
4. Signal classification uses all-or-nothing logic (blocks BUY on single missing field)

---

## Tasks

### Phase 1: Investigation & Root Cause Analysis (2-3 hours)

- [ ] 1.1 Add Debug Logging to Fundamental Data Fetching
  - [ ] 1.1.1 Update `backend/app/watchlist/fundamentals.py:fetch_fundamentals_cached()`
  - [ ] 1.1.2 Add logging before/after YFinance API call: symbol, response status, field values
  - [ ] 1.1.3 Log example: "Fetching NVDA fundamentals from YFinance..." → "Response: profitMargins=0.53, revenueGrowth=1.22"
  - [ ] 1.1.4 Add logging for fallback: "YFinance failed (status 429), trying Finnhub..."
  - [ ] 1.1.5 Test with NVDA: verify logs show API response details

- [ ] 1.2 Test YFinance API Directly
  - [ ] 1.2.1 Create test script: `scripts/test_yfinance.py`
  - [ ] 1.2.2 Test NVDA fundamental data:
    ```python
    import yfinance as yf
    ticker = yf.Ticker("NVDA")
    info = ticker.info
    print("Profit Margin:", info.get("profitMargins"))
    print("Revenue Growth:", info.get("revenueGrowth"))
    print("Debt to Equity:", info.get("debtToEquity"))
    print("Recommendation Mean:", info.get("recommendationMean"))
    ```
  - [ ] 1.2.3 Document which fields are available vs NULL
  - [ ] 1.2.4 Test with AAPL, MSFT to verify consistency
  - [ ] 1.2.5 If fields NULL: Check if API response structure changed (compare to cached examples)

- [ ] 1.3 Verify API Keys and Endpoint Configuration

  **Keys Already in Database** ✅ (loaded at startup):
  ```sql
  -- Verified in source_credentials table:
  SELECT source_id, field, substring(value, 1, 10) as value_preview
  FROM source_credentials
  WHERE source_id IN ('finnhub', 'fmp');
  -- finnhub | token  | cteoh4hr01...
  -- fmp     | apikey | DQEdmFAEpN...
  ```

  - [ ] 1.3.1 Verify credential loader executed at startup:
    ```bash
    # Check backend logs for credential loading
    tail -f /tmp/portfolio-backend.log | grep "credentials_loaded_from_database"
    # Expected: "credentials_loaded_from_database loaded=14 skipped=0 total=14"
    ```

  - [ ] 1.3.2 Verify environment variables set in running process:
    ```bash
    # Check if env vars accessible in Python runtime
    cd ~/portfolio-ai/backend && source .venv/bin/activate
    python -c "import os; print('FINNHUB_API_KEY:', os.getenv('FINNHUB_API_KEY')[:10]+'...')"
    python -c "import os; print('FMP_API_KEY:', os.getenv('FMP_API_KEY')[:10]+'...')"
    ```

  - [ ] 1.3.3 Review data source YAML configs for endpoint coverage:
    **Finnhub** (`config/sources/finnhub.yaml`):
    - Capabilities: reference=true, news=true
    - Rate limit: 60 req/min (free tier)
    - **Fundamentals endpoint**: `GET /stock/metric?symbol=X&metric=all&token=KEY`
      - Fields available: `netProfitMargin`, `revenueGrowthAnnual`, `debtEquityRatio`
    - **Earnings endpoint**: `GET /calendar/earnings?symbol=X&token=KEY`
      - Fields: `earningsCalendar[].date`

    **FMP** (`config/sources/fmp.yaml`):
    - Capabilities: fundamentals=true, financial_statements=true, ratios=true
    - Rate limit: 250 req/day (free tier)
    - **Fundamentals endpoint**: `GET /api/v3/ratios/X?apikey=KEY`
      - Fields available: `netProfitMargin`, `revenueGrowth`, `debtEquityRatio`

    **YFinance** (no YAML config - library-based):
    - **Fundamentals**: `yfinance.Ticker(symbol).info` dict
      - Fields: `profitMargins`, `revenueGrowth`, `debtToEquity`, `recommendationMean`
    - **Earnings**: `yfinance.Ticker(symbol).calendar` dict
      - Fields: `Earnings Date`

  - [ ] 1.3.4 Document endpoint mapping (code vs YAML):
    | Data Type | YFinance Code | Finnhub Endpoint | FMP Endpoint |
    |-----------|---------------|------------------|--------------|
    | Fundamentals | `ticker.info` dict | `/stock/metric` ✅ | `/api/v3/ratios/X` ✅ |
    | Earnings | `ticker.calendar` dict | `/calendar/earnings` ✅ | Not available |
    | Volume | Not used (day_bars table instead) | N/A | N/A |

- [ ] 1.4 Test Finnhub API Directly (key exists ✅)
  - [ ] 1.4.1 Create test script: `scripts/test_finnhub_fundamentals.py`
  - [ ] 1.4.2 Test fundamentals fetch:
    ```python
    import requests
    import os
    # Load credentials from DB at startup (simulated)
    from app.storage.credential_loader import load_credentials_from_database
    load_credentials_from_database()

    key = os.getenv("FINNHUB_API_KEY")
    symbol = "NVDA"
    url = f"https://finnhub.io/api/v1/stock/metric?symbol={symbol}&metric=all&token={key}"
    response = requests.get(url)
    data = response.json()

    print("Status:", response.status_code)
    print("Profit Margin:", data.get("metric", {}).get("netProfitMargin"))
    print("Revenue Growth:", data.get("metric", {}).get("revenueGrowthAnnual"))
    print("Debt/Equity:", data.get("metric", {}).get("debtEquityRatio"))
    ```
  - [ ] 1.4.3 Test earnings date fetch:
    ```python
    url = f"https://finnhub.io/api/v1/calendar/earnings?symbol=AAPL&token={key}"
    response = requests.get(url)
    data = response.json()
    print("Earnings Calendar:", data.get("earningsCalendar"))
    ```
  - [ ] 1.4.4 Document response format and field availability
  - [ ] 1.4.5 Test with NVDA, AAPL, MSFT to verify consistency
  - [ ] 1.4.6 Test rate limit handling (make 61 requests, see if 429 returned)

- [ ] 1.5 Check Volume Data Availability in day_bars
  - [ ] 1.5.1 Query day_bars table for volume data:
    ```sql
    SELECT ticker, COUNT(*) as days, AVG(volume) as avg_vol
    FROM day_bars
    WHERE ticker IN ('AAPL', 'NVDA', 'MSFT', 'TSLA', 'GOOGL', 'AMZN', 'SPY', 'QQQ')
    GROUP BY ticker;
    ```
  - [ ] 1.5.2 Verify all 14 test tickers have 20+ days of data
  - [ ] 1.5.3 If insufficient: Trigger historical backfill (use existing Celery task)
  - [ ] 1.5.4 Document which tickers need backfill

- [ ] 1.6 Document Investigation Findings
  - [ ] 1.6.1 Create investigation summary in task notes
  - [ ] 1.6.2 List which data sources work vs fail
  - [ ] 1.6.3 Identify exact root causes (API field changes? Rate limits? Missing keys?)
  - [ ] 1.6.4 Propose specific fixes for each issue

---

### Phase 2: Fix Data Fetching (3-4 hours)

- [ ] 2.1 Fix Fundamental Data Fetching
  - [ ] 2.1.1 Update field mappings if YFinance API changed:
    - Check if `profitMargins` → `profit_margin` or similar
    - Update `fundamentals.py` field extraction logic
  - [ ] 2.1.2 Add retry logic with exponential backoff for rate limits:
    ```python
    for attempt in range(3):
        try:
            data = fetch_yfinance(symbol)
            return data
        except RateLimitError:
            time.sleep(2 ** attempt)  # 1s, 2s, 4s
    ```
  - [ ] 2.1.3 Improve error handling - catch specific exceptions:
    - `KeyError` → field missing in response
    - `HTTPError` → API request failed
    - `ValueError` → data parsing error
  - [ ] 2.1.4 Update `classify_company_health()` to handle partial data:
    - If profit_margin NULL: skip that check (don't fail entire classification)
    - Return "GOOD" with confidence score if 2 of 3 metrics available
  - [ ] 2.1.5 Test with NVDA - verify company_health = "EXCELLENT"
  - [ ] 2.1.6 Test with 14 tickers - verify 80%+ success rate

- [ ] 2.2 Fix Earnings Data Fetching
  - [ ] 2.2.1 Verify Finnhub API call format matches documentation
  - [ ] 2.2.2 Update date parsing if response format changed
  - [ ] 2.2.3 Add fallback to YFinance if Finnhub fails:
    ```python
    ticker = yf.Ticker("AAPL")
    calendar = ticker.calendar
    earnings_date = calendar.get("Earnings Date")
    ```
  - [ ] 2.2.4 Handle ETFs gracefully (no earnings → return None, not error)
  - [ ] 2.2.5 Calculate days_away correctly:
    ```python
    days_away = (earnings_date.date() - datetime.now(UTC).date()).days
    # Only store if >= 0 (future earnings)
    ```
  - [ ] 2.2.6 Test with AAPL - verify earnings_date and days_away populated
  - [ ] 2.2.7 Test with SPY (ETF) - verify NULL handled gracefully
  - [ ] 2.2.8 Test with 14 tickers - verify 70%+ stock tickers have earnings

- [ ] 2.3 Add Volume Data Query from day_bars
  - [ ] 2.3.1 Update `backend/app/watchlist/service.py:refresh_watchlist_scores()`
  - [ ] 2.3.2 Add volume query after price data fetch (around line 380):
    ```python
    # Query latest volume + 20-day average
    volume_df = storage.query("""
        SELECT volume
        FROM day_bars
        WHERE ticker = ?
        ORDER BY date DESC
        LIMIT 20
    """, [symbol])

    if volume_df.height >= 20:
        volumes = volume_df["volume"].to_list()
        current_volume = volumes[0]
        avg_volume_20d = sum(volumes) / len(volumes)
        volume_ratio = current_volume / avg_volume_20d
    else:
        current_volume = None
        avg_volume_20d = None
        volume_ratio = None
    ```
  - [ ] 2.3.3 Update signal_inputs dict (line 474):
    ```python
    signal_inputs = {
        "price": price_data.price,
        "ema_20": technical_snapshot.price,
        "rsi_14": technical_snapshot.rsi_14,
        "macd": technical_snapshot.macd,
        "volume": current_volume,  # ✅ FIXED
        "volume_avg_20d": avg_volume_20d,
        "company_health": company_health_str,
        "news_sentiment": None,  # Still deferred
        "earnings_days_away": earnings_days_away_val,
    }
    ```
  - [ ] 2.3.4 Add logging: "NVDA volume: 45M (95% of 20d avg 47M)"
  - [ ] 2.3.5 Handle tickers with <20 days data: log warning, skip volume check
  - [ ] 2.3.6 Test with NVDA - verify volume ratio calculated correctly

- [ ] 2.4 Write Unit Tests for Data Fetching Fixes
  - [ ] 2.4.1 Test fundamental field mapping: `test_fundamental_field_extraction()`
  - [ ] 2.4.2 Test retry logic: `test_fundamental_fetch_with_retry()`
  - [ ] 2.4.3 Test partial data handling: `test_company_health_with_missing_fields()`
  - [ ] 2.4.4 Test earnings date parsing: `test_earnings_date_calculation()`
  - [ ] 2.4.5 Test ETF earnings handling: `test_earnings_for_etf_returns_none()`
  - [ ] 2.4.6 Test volume calculation: `test_volume_20day_average()`
  - [ ] 2.4.7 Run tests: `pytest tests/watchlist/ -v`

---

### Phase 3: Update Signal Classification Logic (2-3 hours)

- [ ] 3.1 Refactor Signal Classification to Use Scoring
  - [ ] 3.1.1 Update `backend/app/watchlist/narrative.py:classify_signal()`
  - [ ] 3.1.2 Replace all-or-nothing logic with factor counting:
    ```python
    def classify_signal(inputs: dict) -> SignalClassification:
        confirmations = []

        # Technical factors (always available)
        if inputs.get("price") and inputs.get("ema_20"):
            if inputs["price"] > inputs["ema_20"]:
                confirmations.append("uptrend")

        if inputs.get("rsi_14"):
            if 30 <= inputs["rsi_14"] <= 70:
                confirmations.append("healthy_rsi")

        if inputs.get("macd"):
            if inputs["macd"] > 0:
                confirmations.append("positive_momentum")

        # Optional factors (may be NULL)
        if inputs.get("volume") and inputs.get("volume_avg_20d"):
            if inputs["volume"] >= 0.7 * inputs["volume_avg_20d"]:
                confirmations.append("strong_volume")

        if inputs.get("company_health") in ["EXCELLENT", "GOOD"]:
            confirmations.append("good_fundamentals")

        if inputs.get("news_sentiment") and inputs["news_sentiment"] >= 0.2:
            confirmations.append("positive_news")

        # Calculate signal type and strength
        total_checks = 5  # Always check 3 technical + volume + fundamentals
        if inputs.get("news_sentiment") is not None:
            total_checks += 1

        score = len(confirmations)
        strength = min(10, int((score / total_checks) * 10))

        # Determine signal type
        if score >= 3:
            signal_type = SignalType.BUY
        elif score <= 1:
            signal_type = SignalType.AVOID
        else:
            signal_type = SignalType.HOLD

        # Check for critical AVOID triggers
        if inputs.get("earnings_days_away") and inputs["earnings_days_away"] <= 5:
            signal_type = SignalType.AVOID
            strength = 2

        if inputs.get("company_health") == "WEAK":
            signal_type = SignalType.AVOID
            strength = 3

        return SignalClassification(
            signal_type=signal_type,
            strength=SignalStrength(strength),
            confirmations=confirmations
        )
    ```
  - [ ] 3.1.3 Update `SignalStrength` to store score 1-10 (not just HIGH/MEDIUM/LOW)
  - [ ] 3.1.4 Update `SignalClassification` to include `confirmations` list

- [ ] 3.2 Update Signal Classification Tests
  - [ ] 3.2.1 Test BUY with 5 confirmations → strength 10/10
  - [ ] 3.2.2 Test BUY with 3 confirmations → strength 6/10
  - [ ] 3.2.3 Test HOLD with 2 confirmations → strength 4/10
  - [ ] 3.2.4 Test AVOID with 0 confirmations → strength 1/10
  - [ ] 3.2.5 Test AVOID override (earnings in 2 days) → strength 2/10
  - [ ] 3.2.6 Test BUY without news_sentiment (NULL) → still possible
  - [ ] 3.2.7 Run tests: `pytest tests/watchlist/test_narrative.py -v`

- [ ] 3.3 Update Narrative Generation for New Scoring
  - [ ] 3.3.1 Update `generate_headline()` to include strength:
    - "STRONG BUY (9/10)" vs "WEAK BUY (6/10)"
  - [ ] 3.3.2 Update templates to reflect confirmations:
    - "BUY - 4 of 5 conditions met (missing volume)"
  - [ ] 3.3.3 Test headline generation with various strengths

---

### Phase 4: Integration Testing & Validation (2-3 hours)

- [ ] 4.1 Create Integration Test Suite
  - [ ] 4.1.1 Create `backend/tests/integration/test_watchlist_data_pipeline.py`
  - [ ] 4.1.2 Test: `test_fundamentals_fetch_nvda_yfinance()`
    - Fetch NVDA fundamentals from YFinance
    - Verify profit_margin ~0.53, revenue_growth ~1.22
    - Verify company_health = "EXCELLENT"
  - [ ] 4.1.3 Test: `test_fundamentals_fallback_to_finnhub()`
    - Mock YFinance to fail (status 429)
    - Verify Finnhub called as fallback
    - Verify fundamentals still returned
  - [ ] 4.1.4 Test: `test_earnings_fetch_aapl_finnhub()`
    - Fetch AAPL earnings from Finnhub
    - Verify earnings_date is datetime object
    - Verify days_away calculated correctly
  - [ ] 4.1.5 Test: `test_volume_calculation_from_day_bars()`
    - Insert 20 days of test volume data
    - Calculate 20-day average
    - Verify ratio calculation (current / avg)
  - [ ] 4.1.6 Test: `test_signal_classification_nvda_real_data()`
    - Fetch all data for NVDA (fundamentals, earnings, volume)
    - Run classify_signal()
    - Verify signal_type = BUY, strength >= 8
  - [ ] 4.1.7 Mark tests as skip if API keys not configured
  - [ ] 4.1.8 Run integration tests: `pytest tests/integration/ -v`

- [ ] 4.2 Fix History Endpoint Test
  - [ ] 4.2.1 Update `backend/tests/test_api_watchlist.py:test_get_score_history_extracts_price_score_from_raw_metrics`
  - [ ] 4.2.2 Change assertion:
    ```python
    # OLD: assert len(data["history"]) == 7
    # NEW:
    assert len(data["history"]) >= 7, "Should have at least 7 trading days"
    assert len(data["history"]) <= 15, "Should not exceed 15 calendar days"
    ```
  - [ ] 4.2.3 Run test to verify it passes: `pytest tests/test_api_watchlist.py::test_get_score_history_extracts_price_score_from_raw_metrics -v`

- [ ] 4.3 Run Full Test Suite
  - [ ] 4.3.1 Run all tests: `pytest tests/ -v`
  - [ ] 4.3.2 Verify 150/150 tests passing (145 existing + 5 new)
  - [ ] 4.3.3 Run coverage: `pytest tests/ --cov=app/watchlist --cov-report=term-missing`
  - [ ] 4.3.4 Verify 85%+ coverage maintained
  - [ ] 4.3.5 Fix any failing tests

- [ ] 4.4 Manual Refresh Test (Production Data)
  - [ ] 4.4.1 Restart services to load code changes:
    ```bash
    bash ~/portfolio-ai/scripts/restart.sh
    ```
  - [ ] 4.4.2 Navigate to watchlist UI: http://localhost:3000/watchlist
  - [ ] 4.4.3 Click "Refresh" button
  - [ ] 4.4.4 Monitor backend logs:
    ```bash
    tail -f /tmp/portfolio-backend.log | grep -i "watchlist\|fundamental\|earnings\|volume"
    ```
  - [ ] 4.4.5 Verify logs show:
    - "Fetched NVDA fundamentals from YFinance: profitMargins=0.53"
    - "Fetched AAPL earnings from Finnhub: 2025-11-21 (19 days away)"
    - "NVDA volume: 45M (95% of 20d avg 47M)"
    - "NVDA signal: BUY 9/10 (5 of 6 confirmations)"

- [ ] 4.5 E2E UI Validation with Browser Automation
  - [ ] 4.5.1 Take screenshot of watchlist table:
    ```bash
    node ~/.claude/skills/browser-automation/scripts/screenshot.js \
      http://localhost:3000/watchlist \
      ~/portfolio-ai/docs/screenshots/prd-0023-signals-fixed.png \
      true
    ```
  - [ ] 4.5.2 Verify screenshot shows mixed signals (not all HOLD)
  - [ ] 4.5.3 Verify NVDA has green BUY badge
  - [ ] 4.5.4 Verify signal strengths vary (not all 4/10)
  - [ ] 4.5.5 Expand NVDA row (click chevron)
  - [ ] 4.5.6 Take screenshot of expanded view:
    ```bash
    # Click expand first, then screenshot
    node ~/.claude/skills/browser-automation/scripts/screenshot.js \
      http://localhost:3000/watchlist \
      ~/portfolio-ai/docs/screenshots/prd-0023-nvda-expanded.png \
      true
    ```
  - [ ] 4.5.7 Verify company health section shows bullets
  - [ ] 4.5.8 Verify earnings warnings appear (if applicable)
  - [ ] 4.5.9 Check console for errors:
    ```bash
    node ~/.claude/skills/browser-automation/scripts/console.js \
      http://localhost:3000/watchlist \
      10000
    ```
  - [ ] 4.5.10 Verify no JavaScript errors

---

### Phase 5: Documentation & Cleanup (1 hour)

- [ ] 5.1 Update Code Comments
  - [ ] 5.1.1 Update `service.py:refresh_watchlist_scores()` docstring:
    - Document volume calculation logic
    - Document signal scoring system (3+ confirmations = BUY)
  - [ ] 5.1.2 Update `narrative.py:classify_signal()` docstring:
    - Document scoring algorithm
    - Document confirmation factors
    - Provide examples: "3/5 confirmations = BUY 6/10"

- [ ] 5.2 Update watchlist_review.md
  - [ ] 5.2.1 Add "Resolution Status" section
  - [ ] 5.2.2 Mark Priority 1 (Fix Signal Classification) as COMPLETE
  - [ ] 5.2.3 Document final outcome:
    - "After fixes: NVDA shows BUY 9/10, AAPL shows HOLD 5/10, diverse signals achieved"
  - [ ] 5.2.4 Update success metrics:
    - Company health: 85% populated (12 of 14 tickers)
    - Earnings dates: 75% populated (9 of 12 stocks)
    - Volume data: 100% for tickers with day_bars history

- [ ] 5.3 Update REFACTOR_STATUS.md
  - [ ] 5.3.1 Mark PRD #0023 as "100% Complete"
  - [ ] 5.3.2 Add completion date and summary
  - [ ] 5.3.3 Document remaining work (if any):
    - News sentiment integration (defer to PRD #0024)
    - Backtesting framework (defer to PRD #0025)

- [ ] 5.4 Create PR Summary (if using Git PR workflow)
  - [ ] 5.4.1 Summary: "Fix watchlist data pipeline to enable diverse BUY/HOLD/AVOID signals"
  - [ ] 5.4.2 Before/After screenshots showing HOLD-only vs mixed signals
  - [ ] 5.4.3 Test results: "145/145 tests passing, 85% coverage"
  - [ ] 5.4.4 Validation: "E2E tested with 14 tickers, scheduled refreshes generate narrative data"

---

### Phase 6: Service Restart & Scheduled Verification (CRITICAL - 30 min)

**IMPORTANT**: Code changes only take effect after services are restarted!

- [ ] 6.1 Restart All Services to Load New Code
  - [ ] 6.1.1 Restart backend, Celery workers, and Celery beat:
    ```bash
    bash ~/portfolio-ai/scripts/restart.sh
    ```
  - [ ] 6.1.2 Verify all services running:
    ```bash
    bash ~/portfolio-ai/scripts/status.sh
    ```
  - [ ] 6.1.3 Expected output:
    - Backend: ✓ Running (http://localhost:8000)
    - Celery Worker: ✓ Running (4 workers)
    - Celery Beat: ✓ Running
    - Frontend: ✓ Running (http://localhost:3000)

- [ ] 6.2 Verify Scheduled Refresh Configuration
  - [ ] 6.2.1 Check Celery beat schedule (should poll every 60 seconds):
    ```bash
    grep -A 10 "refresh-watchlist-scores" ~/portfolio-ai/backend/app/celery_app.py
    ```
  - [ ] 6.2.2 Check user refresh interval preference:
    ```sql
    SELECT watchlist_refresh_override, default_refresh_minutes
    FROM user_preferences WHERE id = 'default';
    ```
  - [ ] 6.2.3 Expected: watchlist_refresh_override = 15 minutes (or NULL to use default 60 min)
  - [ ] 6.2.4 For testing, can temporarily set to 5 minutes:
    ```sql
    UPDATE user_preferences
    SET watchlist_refresh_override = 5
    WHERE id = 'default';
    ```

- [ ] 6.3 Monitor First Scheduled Refresh After Restart
  - [ ] 6.3.1 Monitor Celery worker logs in real-time:
    ```bash
    tail -f /tmp/portfolio-celery-worker.log | grep "watchlist_refresh"
    ```
  - [ ] 6.3.2 Wait for next scheduled refresh (check every 60 seconds, executes every N minutes)
  - [ ] 6.3.3 Verify logs show:
    - "watchlist_refresh_task_started" with refresh_interval_minutes
    - "watchlist_refresh_completed" with processed=14, success_count=14
    - NO "watchlist_refresh_skipped" (unless interval not met)
  - [ ] 6.3.4 Check snapshot was created:
    ```sql
    SELECT fetched_at, COUNT(*) FROM watchlist_snapshots
    WHERE fetched_at > NOW() - INTERVAL '10 minutes'
    GROUP BY fetched_at ORDER BY fetched_at DESC LIMIT 3;
    ```

- [ ] 6.4 Verify Scheduled Refresh Generates Narrative Data
  - [ ] 6.4.1 Check most recent snapshot has narrative fields populated:
    ```sql
    SELECT
        symbol,
        signal_strength,
        company_health,
        LENGTH(COALESCE(narrative_action_plan, '')) as action_plan_len,
        LENGTH(COALESCE(narrative_special_notes, '')) as special_notes_len
    FROM watchlist_snapshots ws
    JOIN watchlist_items wi ON ws.item_id = wi.id
    WHERE ws.fetched_at = (SELECT MAX(fetched_at) FROM watchlist_snapshots)
    AND symbol IN ('NVDA', 'AAPL', 'PLTR')
    ORDER BY symbol;
    ```
  - [ ] 6.4.2 Expected results for ALL tickers:
    - company_health: "EXCELLENT" or "GOOD" (not NULL)
    - action_plan_len: >100 characters (not 0)
    - special_notes_len: >100 characters (not 0)
    - signal_strength: varies (5-9, not all 3-4)
  - [ ] 6.4.3 If ANY ticker shows NULL narrative data:
    - ❌ FAIL: Investigate Celery logs for errors
    - Check fundamentals cache: `SELECT * FROM reference_cache WHERE ticker='NVDA'`
    - Check service logs: `grep "fundamentals_fetch_failed" /tmp/portfolio-celery-worker.log`

- [ ] 6.5 Verify API Returns Complete Data
  - [ ] 6.5.1 Query watchlist API:
    ```bash
    curl -s 'http://localhost:8000/api/watchlist?account_id=default' | \
      jq '.items[] | select(.symbol == "NVDA") |
      {symbol, signal_strength, company_health, has_action: (.narrative_action_plan != null)}'
    ```
  - [ ] 6.5.2 Expected response:
    ```json
    {
      "symbol": "NVDA",
      "signal_strength": 7,
      "company_health": "EXCELLENT",
      "has_action": true
    }
    ```
  - [ ] 6.5.3 If company_health is NULL or has_action is false:
    - ❌ FAIL: API returning old snapshot data
    - Check if frontend/backend caching issue
    - Force refresh via UI and recheck

- [ ] 6.6 Wait for Second Scheduled Refresh (Continuous Verification)
  - [ ] 6.6.1 Wait for the NEXT scheduled refresh (another N minutes)
  - [ ] 6.6.2 Verify it also generates complete narrative data
  - [ ] 6.6.3 Confirm pattern: EVERY scheduled refresh should populate narrative
  - [ ] 6.6.4 If second refresh fails:
    - ❌ FAIL: Regression or race condition
    - Check if credentials expired
    - Check if API rate limits hit

- [ ] 6.7 Reset Refresh Interval to Production Value
  - [ ] 6.7.1 If you set interval to 5 minutes for testing, reset it:
    ```sql
    UPDATE user_preferences
    SET watchlist_refresh_override = 15
    WHERE id = 'default';
    ```
  - [ ] 6.7.2 Or use NULL to inherit default (60 minutes):
    ```sql
    UPDATE user_preferences
    SET watchlist_refresh_override = NULL
    WHERE id = 'default';
    ```

**Success Criteria for Phase 6**:
- ✅ Services restarted successfully
- ✅ Scheduled refresh executes automatically (no manual trigger needed)
- ✅ First scheduled refresh generates narrative data (100% of tickers)
- ✅ Second scheduled refresh also generates narrative data (continuous operation)
- ✅ API returns complete data with company_health and narrative fields
- ✅ No errors in Celery logs related to fundamentals/narrative generation

**Critical Notes**:
- This phase is MANDATORY - code changes require service restart
- Must verify AUTOMATIC scheduled refreshes, not just manual API calls
- If scheduled refreshes fail but manual refreshes succeed → credential/environment issue
- Monitor at least TWO consecutive scheduled refreshes to ensure stability

---

## Validation Checklist

**Before marking COMPLETE, verify ALL items:**

### Quantitative Validation
- [ ] Signal strengths vary (not all 3-4/10): see strengths of 5-9/10
- [ ] Company health populated for 100% of tickers (14 of 14)
- [ ] Earnings dates populated for eligible stock tickers (ETFs expected to be NULL)
- [ ] Volume data queried from day_bars for 100% of tickers
- [ ] All tickers have 200+ days of historical data in day_bars
- [ ] 145/145 tests passing (no new tests added, no regressions)
- [ ] Test coverage maintained at 85%+
- [ ] Scheduled refreshes execute automatically every N minutes

### Qualitative Validation
- [ ] NVDA shows signal strength 7/10 with EXCELLENT company health
- [ ] All tickers show diverse signal strengths (not uniform 3-4/10)
- [ ] Narrative action plans generated for all tickers (>100 chars each)
- [ ] Special notes generated for all tickers (>100 chars each)
- [ ] Company health bullets displayed in expanded UI rows
- [ ] API returns complete narrative data (not NULL fields)
- [ ] No console errors during E2E testing
- [ ] Celery logs show successful scheduled refreshes with narrative generation

### Scheduled Operation Validation (CRITICAL)
- [ ] Celery beat polling every 60 seconds (confirmed in logs)
- [ ] Scheduled refreshes execute when interval met (not skipped)
- [ ] First scheduled refresh after restart generates complete narrative data
- [ ] Second scheduled refresh also generates complete narrative data
- [ ] Pattern confirmed: EVERY scheduled refresh populates narrative fields
- [ ] No manual API triggers needed - system operates autonomously

### User Experience Validation
- [ ] Watchlist shows actionable diversity (varied signal strengths and health)
- [ ] Clear narrative reasoning visible in expanded rows
- [ ] System operates automatically without manual intervention

---

## Known Issues & Future Work

### Known Limitations
1. **ETF Handling**: ETFs (SPY, QQQ, VOO) have NULL earnings (expected behavior, not a bug)
2. **New Tickers**: Newly added tickers with <20 days history will skip volume check
3. **News Sentiment**: Still NULL (explicitly deferred to Phase 3 per PRD)

### Future Enhancements (Separate PRDs)
1. **PRD #0024**: News Sentiment Integration (8-12 hours)
2. **PRD #0025**: Backtesting Framework (8-12 hours)
3. **PRD #0026**: Price Alerts (6-8 hours)
4. **PRD #0027**: Mobile Responsive Testing (2-3 hours)

---

## Effort Breakdown

- **Phase 1**: Investigation (2-3 hours) - 25% of work
- **Phase 2**: Fix Data Fetching (3-4 hours) - 35% of work
- **Phase 3**: Update Signal Logic (2-3 hours) - 25% of work
- **Phase 4**: Testing & Validation (2-3 hours) - 15% of work
- **Phase 5**: Documentation (1 hour) - 5% of work

**Total Estimated Effort**: 10-14 hours (Medium complexity)

**Risk Level**: Low
- No new architecture (fixing existing code)
- Clear root causes identified
- Existing tests provide safety net

---

**END OF TASK LIST**
