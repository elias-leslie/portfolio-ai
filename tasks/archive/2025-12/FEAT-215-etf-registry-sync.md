# ETF Registry Sync

**Implements**: FEAT-215
**Status**: planned
**Effort**: LOW-MEDIUM
**Priority**: P2

## Context

Currently `security_type` is set manually or defaults to "equity". This causes:
- ETFs incorrectly scored on fundamentals they don't have
- Data quality showing lower % for ETFs when they actually have complete data
- Manual maintenance burden when adding new symbols

Need automated sync from authoritative ETF list API.

## Data Source

**Financial Modeling Prep (FMP)** - Primary choice:
- Endpoint: `https://financialmodelingprep.com/api/v3/etf/list?apikey=KEY`
- Free tier: 250 calls/day (sufficient for daily sync)
- Returns: symbol, name, price, exchange, exchangeShortName

**Fallback**: yfinance `quoteType` field ("ETF" vs "EQUITY")

## Files to Modify

- `backend/app/tasks/reference_tasks.py` - Add `sync_etf_registry` task
- `backend/app/celery_schedules.py` - Schedule daily at 04:50 UTC
- `backend/app/watchlist/background_tasks.py` - Check ETF status on symbol add

## Steps

- [ ] Add FMP API key to environment/credentials (or use existing)
- [ ] Create `sync_etf_registry` task in reference_tasks.py following existing patterns
- [ ] Schedule task in celery_schedules.py at 04:50 UTC
- [ ] Update `schedule_new_symbol_tasks()` to check if symbol is ETF before setting security_type
- [ ] Test with manual task trigger and verify symbols table updated

## Implementation Notes

```python
@celery_app.task(bind=True, name="sync_etf_registry", max_retries=3)
def sync_etf_registry(self: Task) -> dict[str, int | str]:
    """Daily sync of ETF list from FMP API."""
    # 1. Fetch ETF list from FMP
    # 2. Upsert into symbols table with security_type='etf'
    # 3. Return stats (symbols_synced, duration)
```

## Verification

- [ ] `journalctl --user -u portfolio-celery | grep sync_etf` shows task runs
- [ ] `SELECT COUNT(*) FROM symbols WHERE security_type='etf'` returns 2000+
- [ ] Add new ETF symbol to watchlist, verify auto-detected as ETF

## Rollback

If issues occur: `git reset --hard HEAD~1` and revert celery schedule
