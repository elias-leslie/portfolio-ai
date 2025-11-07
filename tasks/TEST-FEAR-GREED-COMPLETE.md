# Fear & Greed Index - Complete Testing Guide

**Branch**: `claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf`
**Status**: ✅ 100% Complete - Ready for final testing

---

## Quick Summary

**What's Ready:**
- Database schema (3 tables)
- Backend (data fetching, calculations, service)
- API (3 endpoints)
- Frontend (gauge component)
- Tests (21 passing)
- Timeout fix (skips slow HTTP call)
- **Backfill task (252 days historical data)**
- Documentation (complete)

**Critical Step**: Must run backfill task once to populate historical data (Step 3)

---

## Testing Steps

### 1. Pull & Restart
```bash
cd ~/portfolio-ai
git fetch origin && git checkout claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf && git pull
bash ~/portfolio-ai/scripts/restart.sh
```

### 2. Verify Services Running
```bash
bash ~/portfolio-ai/scripts/status.sh
```
All should show ✓ Running

### 3. Run Backfill (CRITICAL - Takes 2-3 min)
```bash
cd ~/portfolio-ai/backend && source .venv/bin/activate
python -c "
from app.tasks.data_ingestion_tasks import backfill_fred_indicators
result = backfill_fred_indicators.delay()
output = result.get(timeout=300)
print(f'✅ Backfill complete: {output[\"rows_inserted\"]} rows')
"
```

**Expected**: `✅ Backfill complete: 252 rows`

### 4. Test Computation Task
```bash
python -c "
from app.tasks.fear_greed_tasks import compute_fear_greed_daily
import time
start = time.time()
result = compute_fear_greed_daily.delay().get(timeout=60)
print(f'✅ Computed in {time.time()-start:.1f}s: Score={result[\"score\"]}, Label={result[\"label\"]}')
"
```

**Expected**: Success in <5 seconds (was 30s before fix)

### 5. Test API
```bash
curl http://localhost:8000/api/market/fng | jq '.'
```

**Expected**: JSON with score, label, components

### 6. Check Frontend
Visit `http://localhost:3000` - Should see Fear & Greed gauge

### 7. Run Tests
```bash
pytest tests/unit/market/test_fear_greed.py tests/integration/market/test_fear_greed_service.py -v
```

**Expected**: 21 tests passing

---

## If All Tests Pass - Merge

```bash
cd ~/portfolio-ai
git checkout main
git pull origin main
git merge claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf --no-ff
git push origin main

# Clean up feature branch
git branch -d claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf
git push origin --delete claude/review-fear-greed-feature-011CUtqZcJQwtBiPfrGd1Ukf
```

---

## Troubleshooting

**Backfill fails**: Check FRED API accessible, wait 1 min (rate limit), retry

**Task still times out**: Check services restarted, fix applied (grep for "target_date.year > 2019")

**API returns error**: Check backend logs, database tables exist, SPY data exists

---

## What's Automated

After merge, system automatically:
- Refreshes SPY data daily (02:00 UTC)
- Updates indicators daily (02:30 UTC)
- Computes Fear & Greed daily (03:30 UTC)

**No manual intervention needed!**

Backfill task only runs ONCE - system maintains data from then on.

---

**Total Time**: ~10-15 minutes (including 2-3 min backfill wait)
