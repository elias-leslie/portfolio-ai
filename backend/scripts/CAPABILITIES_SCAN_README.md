# System Capabilities Scanner - Proof of Concept

**Status**: ✅ Validated - Ready for Integration

## What This Does

Auto-discovers data sources, features, and infrastructure from the running system:

1. **Database Tables** - Scans all tables, gets row counts, date ranges, column names
2. **Celery Tasks** - Lists all scheduled tasks and their schedules
3. **API Endpoints** - Discovers REST endpoints from route files (no app import needed)

## Validated Features

### ✅ Auto-Discovery
Scans the system and auto-populates capabilities:
- **48 capabilities discovered** (30 analytics, 7 infrastructure, 2 market_data, 5 news, 4 portfolio)
- No manual entry required - runs automatically
- Categorizes by type (market_data, news, portfolio, analytics, infrastructure)

### ✅ Change Detection
Tracks what's NEW or CHANGED since last scan:
- Detects new tables/tasks/endpoints (🆕 NEW)
- Detects removed capabilities (🗑️ REMOVED)
- Detects coverage changes (📝 CHANGED: row count, date range)
- **Tested**: Added test row → detected 8→9 rows + date range update

### ✅ Coverage Metadata
Auto-extracts useful context:
- Row counts: "10,103 rows"
- Date ranges: "2025-11-07 to 2025-11-13"
- Schedule info: "Runs daily at 04:00 UTC"
- Column names, source files, endpoints

### ✅ Output Formats
- **Text** (default): Human-readable, grouped by category
- **JSON**: Machine-readable for API integration
- **Diff mode** (`--diff`): Shows only changes

## Usage

```bash
# Full scan (text output)
python backend/scripts/scan_capabilities.py

# JSON output (for API integration)
python backend/scripts/scan_capabilities.py --output json

# Show only changes since last scan
python backend/scripts/scan_capabilities.py --diff
```

## Example Output

```
SYSTEM CAPABILITIES SCAN
Scanned at: 2025-11-13T22:28:51.795489
Total capabilities: 48

MARKET_DATA (2 items)
--------------------------------------------------------------------------------
  • Scheduled Task: Maintain Historical Market Data
    Source: Celery task: maintain_historical_market_data
    Coverage: Runs 86400.0

NEWS (5 items)
--------------------------------------------------------------------------------
  • News Cache Table
    Source: Database table: news_cache
    Coverage: 8,196 rows, 2025-11-06 to 2025-11-13
```

## Change Detection Example

```
CHANGES SINCE LAST SCAN
================================================================================

🆕 NEW (1 items)
  • New Feature Table - Database table: new_feature

📝 CHANGED (2 items)
  • News Cache Table
    8,196 rows → 8,218 rows
  • Watchlist Items Table
    8 rows, 2025-11-09 to 2025-11-12 → 9 rows, 2025-11-09 to 2025-11-13
```

## What Can Be Auto-Populated

**100% Automated** (no human input needed):
- ✅ Category (inferred from table/task name)
- ✅ Name (generated from table/task name)
- ✅ Source type (database_table, celery_task, api_endpoint)
- ✅ Source location (table name, task path, endpoint path)
- ✅ Coverage (row count, date range, schedule)
- ✅ Metadata (columns, schedules, files)

**Human Input** (if we add notes field):
- Purpose: "Why do we need this data?"
- Gaps: "What's missing?"
- Verification: "Tested against Yahoo Finance on 2025-11-13"

## Next Steps (If We Build the Full Feature)

1. **Create `system_capabilities` table** in database
2. **Populate on startup** - Run scan on first deployment
3. **Scheduled refresh** - Celery task runs scan daily, updates DB
4. **Add notes API** - `POST /api/capabilities/{id}/note` (only human-editable field)
5. **Build UI page** - Display capabilities, allow note editing
6. **AI agent integration** - Query API before making changes

## Why This Matters

**Problem**: AI agents (Claude) break things when context resets because they forget what data exists and how it's connected.

**Solution**: Queryable, always-up-to-date registry of system capabilities that AI can reference before making changes.

**Example**:
- ❌ Before: Claude changes `market_data` table → breaks Fear & Greed calc (forgot dependency)
- ✅ After: Claude queries capabilities API → sees `market_data` is used by 5 other features → asks first

## Performance

- **Scan time**: ~2-3 seconds (database + Celery + API routes)
- **No app import**: FastAPI app not loaded (avoids 10+ second startup)
- **Lightweight**: Just scans metadata, no heavy queries

## Files

- `scan_capabilities.py` - Main scanner script
- `.capabilities_scan.json` - Cached results for change detection (auto-created)

## Test Results

| Test | Status | Details |
|------|--------|---------|
| Database scan | ✅ Pass | 30 tables discovered, row counts + date ranges extracted |
| Celery task scan | ✅ Pass | 11 scheduled tasks discovered with schedules |
| API endpoint scan | ✅ Pass | Discovered endpoints without loading app (fast) |
| Change detection | ✅ Pass | Added test row → detected 8→9 rows + date update |
| JSON output | ✅ Pass | Valid JSON with full metadata |
| Text output | ✅ Pass | Grouped by category, readable |
| Diff mode | ✅ Pass | Shows only changes since last scan |

---

**Ready for**: Integration into database + API + UI (if approved)
**Blocks**: None - all auto-discovery validated
**Risk**: Low - read-only operations, no breaking changes
