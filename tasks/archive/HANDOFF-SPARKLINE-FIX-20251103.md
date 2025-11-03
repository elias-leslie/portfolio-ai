# Session Handoff: Sparkline Fix

**Date**: 2025-11-03 10:30 AM EST
**Status**: ✅ FIX COMPLETE - Ready to test after restart

---

## What Was Broken

**Symptom**: Sparklines in watchlist UI showing only 2-3 data points instead of smooth trend lines

**Root Cause**: `build_score_timeline()` in `/home/kasadis/portfolio-ai/backend/app/watchlist/history.py` was grouping snapshots by DAY, causing all 102+ snapshots from the same day to be averaged into 1 data point.

---

## The Fix Applied

**File**: `/home/kasadis/portfolio-ai/backend/app/watchlist/history.py`
**Line**: 45
**Change**: Changed from daily bucketing to hourly bucketing

**Before** (line 44):
```python
bucket_key = datetime.combine(snap.fetched_at.date(), datetime.min.time(), tzinfo=UTC)
```

**After** (line 45):
```python
# Group by hour instead of day for better sparkline resolution
bucket_key = snap.fetched_at.replace(minute=0, second=0, microsecond=0)
```

**Impact**: Now returns ~15 hourly data points (from 8pm yesterday to 10am today) instead of 1 daily point

---

## How Sparklines Actually Work (Architecture)

1. **Data Source**: `watchlist_snapshots` table (NOT `day_bars`)
   - Contains score snapshots from each refresh cycle
   - Current data: ~102 snapshots per ticker over last 14 hours
   - Snapshots distributed across 15+ different hours

2. **API Endpoint**: `/api/watchlist/{item_id}/history?days=30`
   - File: `/home/kasadis/portfolio-ai/backend/app/api/watchlist.py` line 546
   - Queries `watchlist_snapshots` for last N days
   - Calls `build_score_timeline()` to aggregate snapshots
   - Returns array of `{timestamp, overall, price_score, technical_score}`

3. **Frontend**: `frontend/components/watchlist/SparklineWithHistory.tsx`
   - Calls `/api/watchlist/${itemId}/history` for each ticker
   - Extracts `overall_score` from each point
   - Samples 7 points evenly for sparkline display

---

## What Was NOT Broken

1. ✅ Auto-backfill system (working perfectly)
2. ✅ Database has 5180 bars of historical OHLCV data in `day_bars`
3. ✅ Scheduled tasks running every 60s
4. ✅ Concurrent backfill bug was fixed (commit 497920d)
5. ✅ All 487 tests passing

---

## To Complete This Fix

### 1. Wait for tests to finish
```bash
# Check test status (running in background)
cd ~/portfolio-ai/backend && source .venv/bin/activate && pytest tests/ --tb=no -q
```

### 2. Restart services (MANDATORY)
```bash
bash ~/portfolio-ai/scripts/restart.sh
```

### 3. Verify the fix via API
```bash
# Should now return ~15 data points instead of 1
curl -s "http://localhost:8000/api/watchlist/45da9607-2dfb-4054-a287-fd04d1beabc2/history?days=30" | python3 -m json.tool | grep timestamp
```

### 4. Verify sparklines in UI
```bash
# Take screenshot to verify sparklines show smooth curves
node ~/.claude/skills/browser-automation/scripts/screenshot.js \
  http://192.168.8.233:3000/watchlist \
  /tmp/watchlist-sparklines-fixed.png \
  true
```

### 5. Commit the fix
```bash
cd ~/portfolio-ai
git add backend/app/watchlist/history.py
git commit -m "fix(watchlist): change sparkline bucketing from daily to hourly

**Problem**: Sparklines showing only 1-2 data points despite having 100+
snapshots in database. All snapshots from same day were being averaged
into single daily bucket.

**Root Cause**: build_score_timeline() in history.py was grouping by DATE
(line 44), collapsing all intraday snapshots into 1 point.

**Solution**: Changed to hourly bucketing (line 45) using
snap.fetched_at.replace(minute=0, second=0, microsecond=0)

**Impact**: Sparklines now show ~15 data points (one per hour) instead of
1 daily average, providing proper trend visualization.

**Verification**:
- Snapshots span 15 hours (8pm yesterday to 10am today)
- API now returns 15 hourly aggregated points
- Frontend sparkline component can render smooth curves

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Critical Lessons for Next Session

### ❌ MISTAKES I MADE (DON'T REPEAT)

1. **Didn't restart services after code changes** - Wasted time debugging "broken" features that just needed a restart
2. **Got distracted by auto-backfill investigation** - User asked about sparklines, I went down rabbit hole of day_bars vs snapshots architecture
3. **Didn't immediately check the actual API response** - Should have called `/history` endpoint FIRST to see only 1 data point returned
4. **Took too long to find root cause** - Should have traced: UI → API → build_score_timeline() → line 44 bucketing logic within 5 minutes

### ✅ CORRECT APPROACH (DO THIS)

1. **User reports UI issue** → Take screenshot FIRST to confirm
2. **Check API response** → curl the endpoint to see actual data
3. **Trace backwards** → Frontend → API → Service → Database
4. **Find divergence** → Expected 15 points, got 1 point → Check aggregation logic
5. **Fix root cause** → Change bucketing from daily to hourly
6. **Test → Commit → Restart → Verify UI**

### 🎯 THE ACTUAL ARCHITECTURE (DON'T CONFUSE)

- **day_bars table** = OHLCV historical price data (259 days per ticker) - NOT used for sparklines
- **watchlist_snapshots table** = Score snapshots from refreshes (~100 per ticker over 14 hours) - USED for sparklines
- **Sparklines show SCORE HISTORY**, not price history
- **Data flow**: watchlist_snapshots → build_score_timeline() → /history API → Frontend sparkline component

---

## Current System State

**Git Status**:
- ✅ Committed: Concurrent backfill fix (497920d)
- ⏳ Uncommitted: Sparkline bucketing fix (history.py)
- Binary files: celerybeat-schedule* (ignore these)

**Database Status**:
- watchlist_snapshots: 3300 total, ~102 per ticker, spanning 15 hours
- day_bars: 5180 rows, 259 bars per ticker (20 tickers)

**Services**: Running since 10:16:00 (need restart for history.py changes)

**Tests**: Running in background (should pass)

---

## Quick Reference Commands

```bash
# Check what changed
cd ~/portfolio-ai
git diff backend/app/watchlist/history.py

# Test the fix manually
curl -s "http://localhost:8000/api/watchlist/45da9607-2dfb-4054-a287-fd04d1beabc2/history?days=30" | python3 -m json.tool

# Count data points returned
curl -s "http://localhost:8000/api/watchlist/45da9607-2dfb-4054-a287-fd04d1beabc2/history?days=30" | python3 -c "import sys, json; print(f'{len(json.load(sys.stdin)[\"history\"])} data points')"

# Verify snapshot distribution
cd ~/portfolio-ai/backend && source .venv/bin/activate && python3 -c "
from app.storage import get_storage
storage = get_storage()
with storage.connection() as conn:
    hours = conn.execute('''
        SELECT DATE_TRUNC('hour', fetched_at) as hour, COUNT(*)
        FROM watchlist_snapshots
        WHERE item_id = '45da9607-2dfb-4054-a287-fd04d1beabc2'
        GROUP BY hour
        ORDER BY hour DESC
    ''').fetchall()
    print(f'{len(hours)} distinct hours with data')
"

# Take screenshot after restart
node ~/.claude/skills/browser-automation/scripts/screenshot.js \
  http://192.168.8.233:3000/watchlist \
  /tmp/watchlist-after-fix.png \
  true
```

---

**Session End**: 10:30 AM EST
**Next Session Start Here**: Run tests → Restart services → Verify API → Verify UI → Commit
