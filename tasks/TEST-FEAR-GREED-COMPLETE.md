# Fear & Greed Index - Complete Testing Guide

**Branch**: `claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf`
**Status**: ✅ 100% Complete with Self-Healing Automation

---

## Key Feature: Self-Healing System

**No manual backfill needed!** The daily compute task automatically:
1. Checks if it has enough historical data (100+ days)
2. If not, triggers backfill task automatically
3. Then computes the Fear & Greed score

**This tests the REAL automation**, not manual workarounds.

---

## Testing Steps

### 1. Pull & Restart
```bash
cd ~/portfolio-ai
git fetch origin && git checkout claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf && git pull
bash ~/portfolio-ai/scripts/restart.sh
bash ~/portfolio-ai/scripts/status.sh  # Verify all services running
```

### 2. Test Automated Execution (Tests Real Automation)

**Option A: Trigger Daily Task (Tests Self-Healing)**
```bash
cd ~/portfolio-ai/backend && source .venv/bin/activate
python -c "
from app.tasks.fear_greed_tasks import compute_fear_greed_daily
import time

print('🧪 Testing Fear & Greed daily task (with auto-backfill)...')
print('This will automatically trigger backfill if needed\\n')

start = time.time()
result = compute_fear_greed_daily.delay().get(timeout=360)  # 6 min (includes backfill)
elapsed = time.time() - start

print(f'\\n✅ Task completed in {elapsed:.1f}s')
print(f'Score: {result[\"score\"]}, Label: {result[\"label\"]}')

if elapsed > 120:
    print('📊 Backfill likely ran (took > 2 min)')
else:
    print('⚡ Quick execution (backfill skipped, data already exists)')
"
```

**Expected First Run**: Takes 2-3 minutes (auto-triggers backfill)
**Expected Subsequent Runs**: Takes <5 seconds (data exists, skips backfill)

**Option B: Wait for Celery Beat (Tests Scheduled Automation)**
```bash
# Check Beat schedule
tail -f /tmp/portfolio-celery-beat.log | grep "compute-fear-greed-daily"

# Wait for next scheduled run (happens daily at 03:30 UTC)
# Or temporarily change schedule in celery_app.py to 300s (5 min) for testing
```

### 3. Verify Results

**Check API**:
```bash
curl http://localhost:8000/api/market/fng | jq '.'
```

**Check Database**:
```bash
psql -U portfolio_ai_user -d portfolio_ai -c "
SELECT COUNT(*) as historical_data FROM fear_greed_inputs WHERE vix_close IS NOT NULL;
SELECT * FROM fear_greed_daily ORDER BY as_of_date DESC LIMIT 3;
"
```

**Expected**: 
- 200-260 rows in fear_greed_inputs (historical data)
- Recent scores in fear_greed_daily

**Check Logs**:
```bash
tail -100 /tmp/portfolio-celery-worker.log | grep -E "backfill|fear_greed"
```

**Look for**:
- `"insufficient_historical_data"` - System detected missing data
- `"triggering_backfill_task"` - Auto-triggered backfill
- `"backfill_completed"` - Backfill successful
- `"fear_greed_task_complete"` - Computation successful

### 4. Check Frontend
Visit `http://localhost:3000` - Should see Fear & Greed gauge with score

### 5. Run Tests
```bash
cd ~/portfolio-ai/backend && source .venv/bin/activate
pytest tests/unit/market/test_fear_greed.py tests/integration/market/test_fear_greed_service.py -v
```

**Expected**: 21 tests passing

---

## If All Tests Pass - Merge

```bash
cd ~/portfolio-ai
git checkout main && git pull origin main
git merge claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf --no-ff
git push origin main

# Clean up
git branch -d claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf
git push origin --delete claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf
```

---

## What's Automated

After merge, system automatically:
1. **Daily at 03:30 UTC**: Computes Fear & Greed Index
   - Checks for historical data first
   - Auto-triggers backfill if needed (first run)
   - Computes score from 4 signals
   - Stores in database
2. **Daily at 02:00 UTC**: Refreshes SPY data
3. **Daily at 02:30 UTC**: Updates technical indicators

**Zero manual intervention!** System is self-healing.

---

## Troubleshooting

**Task times out**: Check services running, logs for specific error

**API returns error**: Check backend logs, database tables exist

**No historical data**: First run takes 2-3 min to backfill - this is expected!

---

## Why This Approach is Better

❌ **OLD (Manual Backfill)**:
- User runs backfill manually
- User tests manual trigger
- User merges
- **Problem**: Scheduled tasks never proven to work!

✅ **NEW (Self-Healing)**:
- User tests daily compute task
- Task auto-detects missing data
- Task auto-triggers backfill
- Task computes score
- **Proves actual automation works!**

---

**Total Time**: ~5-10 minutes (first run includes 2-3 min backfill)
