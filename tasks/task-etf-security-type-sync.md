# Task: ETF/Security Type Dynamic Sync

## Overview

Create a scheduled task that maintains accurate `security_type` values in the `symbols` table by syncing against authoritative ETF lists from free APIs.

## Problem

Currently, security_type is set manually or defaults to "equity". This causes:
- ETFs incorrectly scored on fundamentals they don't have
- Data quality showing lower % for ETFs when they actually have complete data
- Manual maintenance burden when adding new symbols

## Data Sources (Free Tier)

| Provider | Endpoint | Free Tier Limits |
|----------|----------|------------------|
| [Financial Modeling Prep](https://site.financialmodelingprep.com/developer/docs/etf-list-api) | `/api/v3/etf/list` | 250 calls/day |
| [EODHD](https://eodhd.com/financial-apis/search-api-for-stocks-etfs-mutual-funds) | Search API with type filter | 20 calls/day |
| [Twelve Data](https://twelvedata.com/etf) | ETF endpoint | 800 calls/day |

**Recommendation**: Use FMP as primary (most generous free tier), cache the full ETF list.

## Implementation

### 1. Create ETF List Cache Table

```sql
CREATE TABLE etf_registry (
    symbol VARCHAR(20) PRIMARY KEY,
    name VARCHAR(255),
    exchange VARCHAR(20),
    last_verified_at TIMESTAMP WITH TIME ZONE,
    source VARCHAR(50)
);
```

### 2. Celery Task: `sync_etf_registry`

- Runs daily at 05:00 UTC
- Fetches full ETF list from FMP (or fallback to EODHD)
- Upserts into `etf_registry` table
- Updates `symbols.security_type` for any matching symbols

### 3. On Symbol Add Hook

When a new symbol is added to watchlist:
1. Check `etf_registry` for match
2. If found, set `security_type = 'etf'`
3. If not found, default to 'equity' (or query yfinance quoteType)

### 4. Fallback: yfinance quoteType

yfinance provides `quoteType` field:
- "ETF" for ETFs
- "EQUITY" for stocks
- "INDEX" for indices

Use this as fallback if symbol not in registry.

## Acceptance Criteria

- [ ] ETF registry table exists with 2000+ US ETFs
- [ ] Daily sync task updates registry
- [ ] New watchlist symbols auto-detect ETF vs equity
- [ ] Existing symbols corrected on next sync
- [ ] Security type feeds into DQ calculation correctly

## Files to Create/Modify

- `backend/app/tasks/reference_tasks.py` - Add sync_etf_registry task
- `backend/app/celery_schedules.py` - Schedule daily run
- `migrations/xxx_create_etf_registry.py` - Create table
- `backend/app/watchlist/background_tasks.py` - Check registry on add

## Effort

LOW-MEDIUM - Straightforward API integration + scheduled task
