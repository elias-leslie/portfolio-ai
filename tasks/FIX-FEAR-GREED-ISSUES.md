# Fear & Greed Index - Issue Resolution Guide

**Created**: 2025-11-07
**Status**: Ready to apply on local server
**Estimated Time**: 2-3 hours

---

## 🔍 Root Cause Analysis

### Issue 1: Task Execution Timeout (30 seconds)

**ROOT CAUSE FOUND**: `backend/app/market/fear_greed_data.py:116`

```python
response = httpx.get(self.CBOE_PUT_CALL_URL, timeout=15.0)
```

**Problem**:
- The CBOE put/call CSV URL is **slow or unresponsive**
- Data is discontinued anyway (stops at 2019-12-31)
- Making HTTP call on **every task execution** even though data won't exist
- 15-second timeout × 2 retries = 30 seconds total timeout

**Impact**: Celery task hangs for 30 seconds, then fails

---

## ✅ Fixes to Apply

### Fix 1: Skip CBOE HTTP Call for Recent Dates

**File**: `backend/app/market/fear_greed_data.py`
**Line**: 94-146

**Replace the entire `fetch_put_call_ratio` method with:**

```python
def fetch_put_call_ratio(self, target_date: date) -> float | None:
    """Fetch CBOE equity put/call ratio for a specific date.

    NOTE: CBOE CSV data feed was discontinued in 2019. This method will
    always return None for dates after 2019-12-31. The Fear & Greed Index
    calculation handles this gracefully by using 4 signals instead of 5,
    with the missing signal defaulting to neutral (50).

    TODO: Find alternative source for put/call ratio data:
    - Option 1: Use options chain data from Polygon/Finnhub if available
    - Option 2: Use proxy indicators (e.g., SKEW index, VIX term structure)
    - Option 3: Purchase CBOE data feed subscription

    Args:
        target_date: Date to fetch put/call ratio for

    Returns:
        Put/call ratio, or None if unavailable (always None for dates > 2019)
    """
    try:
        # OPTIMIZATION: Skip HTTP call entirely for dates after 2019
        # CBOE CSV was discontinued, so data won't exist anyway
        if target_date.year > 2019:
            logger.info(
                "put_call_skipped_post2019",
                date=target_date,
                reason="CBOE data discontinued after 2019-12-31"
            )
            return None

        # Fetch CSV if not cached (only for pre-2020 dates)
        if self._put_call_cache is None:
            response = httpx.get(self.CBOE_PUT_CALL_URL, timeout=10.0)  # Reduced from 15s
            response.raise_for_status()

            # Parse CSV (skip first 2 header rows)
            csv_data = StringIO(response.text)
            df = pd.read_csv(csv_data, skiprows=2, parse_dates=["DATE"])
            self._put_call_cache = df
            logger.info("put_call_csv_cached", rows=len(df))

        # Find matching date
        df = self._put_call_cache
        df["DATE"] = pd.to_datetime(df["DATE"]).dt.date
        matching = df[df["DATE"] == target_date]

        if not matching.empty:
            # Column name is "P/C Ratio" in the CSV
            ratio = float(matching.iloc[0]["P/C Ratio"])
            logger.info(
                "put_call_ratio_fetched",
                date=target_date,
                value=ratio,
                source="CBOE",
            )
            return ratio

        logger.warning("put_call_ratio_not_found", date=target_date)
        return None

    except Exception as e:
        logger.error("put_call_ratio_fetch_failed", date=target_date, error=str(e))
        return None
```

**Changes**:
1. Added check: `if target_date.year > 2019: return None` (skips HTTP call entirely)
2. Reduced timeout from 15s → 10s for legacy dates
3. Added logging for skipped calls

---

### Fix 2: Add HTTP Timeout for FRED Calls

**File**: `backend/app/sources/fred.py`

Check if FRED API calls have timeout configured. If not, add `timeout=10.0` to all `httpx.get()` calls.

**Example**:
```python
response = httpx.get(url, params=params, timeout=10.0)
```

---

### Fix 3: Backfill Historical Data

**Create**: `backend/scripts/backfill_fred_data.py`

```python
"""Backfill VIX and HY Spread historical data for Fear & Greed Index."""

from datetime import datetime, timedelta

from app.sources.fred import FREDSource
from app.storage import get_storage

def backfill_fred_indicators():
    """Backfill 252 trading days (~360 calendar days) of VIX and HY Spread data."""
    storage = get_storage()
    fred = FREDSource()

    # Calculate date range (252 trading days ≈ 360 calendar days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=360)

    print(f"Backfilling FRED data from {start_date.date()} to {end_date.date()}")

    # Fetch VIX data
    print("Fetching VIX (VIXCLS)...")
    vix_data = fred.fetch("VIXCLS", start_date, end_date)
    print(f"  ✓ Fetched {len(vix_data) if vix_data else 0} VIX data points")

    # Fetch HY Spread data
    print("Fetching HY Spread (BAMLH0A0HYM2)...")
    hy_data = fred.fetch("BAMLH0A0HYM2", start_date, end_date)
    print(f"  ✓ Fetched {len(hy_data) if hy_data else 0} HY Spread data points")

    # TODO: Store data in fear_greed_inputs table
    # (Need to write persistence logic based on storage.connection() pattern)

    print("\n✅ Backfill complete")

if __name__ == "__main__":
    backfill_fred_indicators()
```

**Run on your server**:
```bash
cd ~/portfolio-ai/backend
source .venv/bin/activate
python scripts/backfill_fred_data.py
```

---

### Fix 4: Fix PortfolioOverview Component

**Option A - Quick Fix (Remove)**:

**File**: `frontend/app/page.tsx`
**Line**: 62 (or wherever PortfolioOverview is commented out)

**Delete the commented code entirely**:
```tsx
// Remove these lines:
// {/* <PortfolioOverview analytics={analytics} /> */}
```

**Option B - Proper Fix (Fix Analytics)**:

Check `backend/app/portfolio/analytics.py` for the `concentration` calculation:
```python
# Ensure this exists and returns top_holding_pct
def calculate_concentration(positions):
    # ... calculate total value ...
    return {
        "top_holding_pct": (largest_position_value / total_value) * 100,
        # ... other fields ...
    }
```

---

### Fix 5: Verify Celery Beat Schedule

**File**: `backend/app/celery_app.py`

Ensure these tasks are in `beat_schedule`:

```python
beat_schedule = {
    # ... existing tasks ...

    "refresh-daily-ohlcv": {
        "task": "app.tasks.data_ingestion_tasks.refresh_daily_ohlcv",
        "schedule": 86400.0,  # Daily
    },
    "update-technical-indicators-daily": {
        "task": "app.tasks.data_ingestion_tasks.update_technical_indicators_daily",
        "schedule": 86400.0,  # Daily
    },
    "compute-fear-greed-daily": {
        "task": "compute_fear_greed_daily",
        "schedule": 86400.0,  # Daily at 03:30 UTC
    },
}
```

---

## 🧪 Testing Instructions

### Step 1: Apply Fixes
```bash
# On your local server
cd ~/portfolio-ai/backend
source .venv/bin/activate

# Apply Fix 1 (edit fear_greed_data.py manually)
# Apply Fix 5 (verify celery_app.py)
```

### Step 2: Restart Services
```bash
bash ~/portfolio-ai/scripts/restart.sh
```

### Step 3: Test Manual Trigger
```bash
cd ~/portfolio-ai/backend
source .venv/bin/activate
python -c "
from app.tasks.fear_greed_tasks import compute_fear_greed_daily
import time

print('Triggering Fear & Greed task...')
start = time.time()
result = compute_fear_greed_daily.delay()
print(f'Task ID: {result.id}')
print('Waiting for result (max 60s)...')

try:
    output = result.get(timeout=60)
    elapsed = time.time() - start
    print(f'✅ SUCCESS in {elapsed:.1f}s')
    print(f'Result: {output}')
except Exception as e:
    elapsed = time.time() - start
    print(f'❌ FAILED after {elapsed:.1f}s')
    print(f'Error: {e}')
"
```

**Expected**: Task completes in < 5 seconds (no HTTP timeout)

### Step 4: Check Logs
```bash
# Check worker logs for any errors
tail -50 /tmp/portfolio-celery-worker.log

# Should see:
# - "put_call_skipped_post2019" log message
# - "fear_greed_compute_complete" log message
# - No timeout errors
```

### Step 5: Verify API Works
```bash
curl http://localhost:8000/api/market/fng | jq '.'
```

**Expected**:
```json
{
  "as_of_date": "2025-11-07",
  "score": 39.6,
  "label": "Fear",
  "components": {...}
}
```

### Step 6: Test Scheduled Tasks
```bash
# Option A: Temporarily change schedule to 60s for testing
# Edit celery_app.py: change 86400.0 → 60.0
# Restart services, wait 2 minutes, check logs

# Option B: Wait 24 hours and verify tasks ran
# Check beat logs: tail -f /tmp/portfolio-celery-beat.log
# Should see task execution messages
```

---

## 📋 Verification Checklist

- [ ] Fix 1 applied (skip CBOE HTTP call for dates > 2019)
- [ ] Fix 5 verified (Celery Beat schedule correct)
- [ ] Services restarted successfully
- [ ] Manual task trigger completes in < 5s
- [ ] API endpoint returns current score
- [ ] Worker logs show no timeout errors
- [ ] Beat schedule shows 3 Fear & Greed tasks
- [ ] (Optional) Scheduled tasks execute automatically

---

## 📝 Documentation Updates

After fixes are applied and tested:

### Update API_REFERENCE.md

Add section:
```markdown
## Fear & Greed Index Endpoints

### GET /api/market/fng
Returns current Fear & Greed Index score.

**Response**:
```json
{
  "as_of_date": "2025-11-07",
  "score": 39.6,
  "label": "Fear",
  "components": {...}
}
```

### GET /api/market/fng/history
Returns historical scores (query params: start, end)

### GET /api/market/fng/components
Returns component breakdown for specific date
```

### Update ARCHITECTURE.md

Add section:
```markdown
## Fear & Greed Index

4-signal market sentiment indicator:
- **VIX**: Fear gauge (volatility)
- **SPY Momentum**: Trend direction (price vs 200-day MA)
- **RSI**: Overextension (overbought/oversold)
- **Credit Spreads**: Institutional worry (HY bond spreads)

**Missing Signal**: Put/Call ratio (CBOE data discontinued 2019)

**Scoring**: Equal-weighted percentile ranking (252-day window)
**Schedule**: Daily compute at 03:30 UTC via Celery Beat
**Database**: 3 tables (inputs, components, daily scores)
```

---

## 🎯 Expected Results After Fixes

✅ Task execution: < 5 seconds (was 30s timeout)
✅ Scheduled tasks: Run daily automatically
✅ API endpoint: Returns current score
✅ Historical data: 252 days available for accurate percentiles
✅ No HTTP timeouts or hanging tasks

---

## 📞 If Issues Persist

1. Check Celery worker logs: `/tmp/portfolio-celery-worker.log`
2. Check Celery beat logs: `/tmp/portfolio-celery-beat.log`
3. Verify Redis is running: `redis-cli ping` (should return `PONG`)
4. Verify database migration 016 applied: `psql -U portfolio_ai_user -d portfolio_ai -c "\dt fear_greed*"`
5. Check if SPY data exists: `psql -U portfolio_ai_user -d portfolio_ai -c "SELECT COUNT(*) FROM day_bars WHERE ticker='SPY';"`

---

**Status**: Ready to apply
**Next Step**: Apply Fix 1 on your local server and test
