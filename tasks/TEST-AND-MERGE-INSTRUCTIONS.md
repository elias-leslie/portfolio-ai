# Test & Merge Instructions - Fear & Greed Fix

**Branch**: `claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf`
**Fix**: Skip CBOE HTTP call for dates after 2019 (prevents 30s timeout)

---

## Step 1: Pull the Fix to Your Dev Server

```bash
cd ~/portfolio-ai
git fetch origin
git checkout claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf
git pull origin claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf
```

**What changed**:
- `backend/app/market/fear_greed_data.py` - Added date check to skip slow HTTP call
- `tasks/WORK_TRACKER.md` - Updated status
- `tasks/FIX-FEAR-GREED-ISSUES.md` - Comprehensive fix guide

---

## Step 2: Restart Services

```bash
bash ~/portfolio-ai/scripts/restart.sh
```

**Wait for**:
- ✓ Redis running
- ✓ Backend running (http://localhost:8000)
- ✓ Celery Worker running
- ✓ Celery Beat running
- ✓ Frontend running (http://localhost:3000)

---

## Step 3: Test the Fix

### Test A: Manual Task Trigger (CRITICAL)

This should complete in **<5 seconds** (was 30s before):

```bash
cd ~/portfolio-ai/backend
source .venv/bin/activate
python -c "
from app.tasks.fear_greed_tasks import compute_fear_greed_daily
import time

print('🧪 Testing Fear & Greed task...')
start = time.time()
result = compute_fear_greed_daily.delay()
print(f'Task ID: {result.id}')

try:
    output = result.get(timeout=60)
    elapsed = time.time() - start
    print(f'\n✅ SUCCESS in {elapsed:.1f}s')
    print(f'Result: {output}')
    if elapsed < 10:
        print('✅ TIMEOUT FIX WORKING (task completed quickly)')
    else:
        print('⚠️  Task slow but completed')
except Exception as e:
    elapsed = time.time() - start
    print(f'\n❌ FAILED after {elapsed:.1f}s')
    print(f'Error: {e}')
"
```

**Expected output**:
```
🧪 Testing Fear & Greed task...
Task ID: abc123...

✅ SUCCESS in 2.3s
Result: {'status': 'success', 'date': '2025-11-07', 'score': 39.6, 'label': 'Fear'}
✅ TIMEOUT FIX WORKING (task completed quickly)
```

### Test B: Check API Endpoint

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

### Test C: Check Worker Logs

```bash
tail -50 /tmp/portfolio-celery-worker.log | grep -E "fear_greed|put_call"
```

**Look for**:
- `"put_call_skipped_post2019"` - Confirms HTTP call was skipped
- `"fear_greed_compute_complete"` - Confirms task finished
- No timeout errors or exceptions

---

## Step 4: Run Tests (Optional but Recommended)

```bash
cd ~/portfolio-ai/backend
source .venv/bin/activate
pytest tests/unit/market/test_fear_greed.py -v
pytest tests/integration/market/test_fear_greed_service.py -v
```

**Expected**: All 21 tests passing

---

## Step 5A: If Tests PASS - Merge to Main

```bash
cd ~/portfolio-ai
git checkout main
git pull origin main
git merge claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf
git push origin main
```

**Then clean up the feature branch**:
```bash
git branch -d claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf
git push origin --delete claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf
```

---

## Step 5B: If Tests FAIL - Report Issues

**Collect diagnostic info**:
```bash
# 1. Worker logs
tail -100 /tmp/portfolio-celery-worker.log > /tmp/fear-greed-debug.log

# 2. Service status
bash ~/portfolio-ai/scripts/status.sh >> /tmp/fear-greed-debug.log

# 3. Database check
psql -U portfolio_ai_user -d portfolio_ai -c "SELECT * FROM fear_greed_daily ORDER BY as_of_date DESC LIMIT 5;" >> /tmp/fear-greed-debug.log

# 4. View collected info
cat /tmp/fear-greed-debug.log
```

**Report back** with the output from `/tmp/fear-greed-debug.log`

---

## Quick Reference

| Step | Command | Expected Result |
|------|---------|-----------------|
| 1. Pull | `git pull origin claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf` | Updated files |
| 2. Restart | `bash ~/portfolio-ai/scripts/restart.sh` | All services running |
| 3. Test | Python script above | Success in <5s |
| 4. API | `curl http://localhost:8000/api/market/fng` | JSON with score |
| 5. Merge | `git checkout main && git merge ...` | Clean merge |

---

## What Was Fixed

**Problem**: Task timed out after 30 seconds
**Root Cause**: HTTP call to slow/unresponsive CBOE put/call CSV URL (discontinued in 2019)
**Solution**: Skip HTTP call entirely for dates after 2019
**Result**: Task completes in <5 seconds (no HTTP timeout)

**Files Changed**:
- `backend/app/market/fear_greed_data.py:114-122` - Added date check before HTTP call
- Reduced timeout from 15s → 10s for legacy dates (pre-2020)

---

## Troubleshooting

### Issue: "Task still times out"

**Check**:
1. Did services restart properly? `bash ~/portfolio-ai/scripts/status.sh`
2. Is the fix actually applied? `grep "target_date.year > 2019" ~/portfolio-ai/backend/app/market/fear_greed_data.py`
3. Are you on the right branch? `git branch` (should show `claude/review-fear-greed-feature-*`)

### Issue: "API returns error"

**Check**:
1. Backend logs: `tail -50 /tmp/portfolio-backend.log`
2. Database connection: `psql -U portfolio_ai_user -d portfolio_ai -c "SELECT 1;"`
3. SPY data exists: `psql -U portfolio_ai_user -d portfolio_ai -c "SELECT COUNT(*) FROM day_bars WHERE ticker='SPY';"`

### Issue: "Merge conflicts"

**If main branch changed**:
```bash
git checkout claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf
git pull origin main
# Resolve conflicts
git commit
git push origin claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf
```

---

**Ready?** Start with Step 1 above! 🚀
