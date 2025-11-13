# System Capabilities UI - Mockup

## Main View - Full Table

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  System Capabilities                                           Last Scan: 2 minutes ago │
│                                                                                          │
│  [🔄 Refresh Scan]  [📊 View: All ▾]  [🔍 Search...]                          48 total │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ Category ▾    │ Capability Name ▾              │ Source ▾           │ Coverage ▾        │
├───────────────┼────────────────────────────────┼────────────────────┼───────────────────┤
│ 🔵 Market Data│ Historical Market Data (Task)  │ Celery: maintain_  │ Runs daily        │
│               │                                 │ historical_market_ │ (04:00 UTC)       │
│               │                                 │ data               │                   │
│               │ 📝 Notes: Maintains 252 trading days per symbol...  │ [Edit]            │
├───────────────┼────────────────────────────────┼────────────────────┼───────────────────┤
│ 🔵 Market Data│ Daily OHLCV Refresh (Task)     │ Celery: refresh_   │ Runs daily        │
│               │                                 │ daily_ohlcv        │ (after market)    │
│               │ 📝 Notes: (empty)                                    │ [Add Note]        │
├───────────────┼────────────────────────────────┼────────────────────┼───────────────────┤
│ 📰 News       │ News Cache Table               │ DB: news_cache     │ 8,218 rows        │
│               │                                 │                    │ Nov 6-13, 2025    │
│               │ 📝 Notes: Primary cache for filtered news. Deduplicated by hash...      │
│               │ ⚠️  GAP: Missing sentiment breakdown by source      │ [Edit]            │
├───────────────┼────────────────────────────────┼────────────────────┼───────────────────┤
│ 📰 News       │ News Sentiment Refresh (Task)  │ Celery: refresh_   │ Runs every 65s    │
│               │                                 │ news_sentiment     │                   │
│               │ 📝 Notes: (empty)                                    │ [Add Note]        │
├───────────────┼────────────────────────────────┼────────────────────┼───────────────────┤
│ 📈 Portfolio  │ Watchlist Items Table          │ DB: watchlist_     │ 9 rows            │
│               │                                 │ items              │ Nov 9-13, 2025    │
│               │ 📝 Notes: User watchlist symbols. Snapshots tracked separately.         │
│               │ ✅ VERIFIED: 2025-11-13 - Tested manual add/remove │ [Edit]            │
├───────────────┼────────────────────────────────┼────────────────────┼───────────────────┤
│ 📈 Portfolio  │ Watchlist Score Refresh (Task) │ Celery: refresh_   │ Runs every 60s    │
│               │                                 │ watchlist_scores   │                   │
│               │ 📝 Notes: Real-time scoring. Uses price + technical + fundamental...    │
│               │ 🔴 ISSUE: N/A scores for some symbols (investigating) [Edit]            │
├───────────────┼────────────────────────────────┼────────────────────┼───────────────────┤
│ 🔬 Analytics  │ Fear & Greed Daily Table       │ DB: fear_greed_    │ 9 rows            │
│               │                                 │ daily              │ Nov 7-11, 2025    │
│               │ 📝 Notes: (empty)                                    │ [Add Note]        │
├───────────────┼────────────────────────────────┼────────────────────┼───────────────────┤
│ 🔬 Analytics  │ Fear & Greed Components Table  │ DB: fear_greed_    │ 5 rows            │
│               │                                 │ components         │ Nov 7-11, 2025    │
│               │ 📝 Notes: 5 components: VIX, Put/Call, Breadth, Junk Bond, Safe Haven  │
│               │ 🔴 ISSUE: 4 of 5 components broken (3-day old data) │ [Edit]            │
└───────────────┴────────────────────────────────┴────────────────────┴───────────────────┘

[< Previous]  [Page 1 of 3]  [Next >]
```

---

## Filtered View - Market Data Only

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  System Capabilities                                           Last Scan: 2 minutes ago │
│                                                                                          │
│  [🔄 Refresh Scan]  [📊 View: Market Data ▾]  [🔍 Search...]                   2 items │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ Capability Name ▾                       │ Source ▾              │ Coverage ▾            │
├─────────────────────────────────────────┼───────────────────────┼───────────────────────┤
│ Historical Market Data (Task)           │ Celery Task           │ Runs daily (04:00 UTC)│
│ app/tasks/market_data_tasks.py          │ maintain_historical_  │                       │
│                                          │ market_data           │                       │
│ 📝 Notes: Maintains 252 trading days per symbol. Backfills missing data.               │
│          Idempotent - safe to run multiple times.                                       │
│ ✅ VERIFIED: 2025-11-10 - Tested against Yahoo Finance (matches)     [Edit]            │
├─────────────────────────────────────────┼───────────────────────┼───────────────────────┤
│ Daily OHLCV Refresh (Task)              │ Celery Task           │ Runs daily (16:30 ET) │
│ app/tasks/market_data_tasks.py          │ refresh_daily_ohlcv   │                       │
│ 📝 Notes: (empty)                                                       [Add Note]      │
└─────────────────────────────────────────┴───────────────────────┴───────────────────────┘
```

---

## Edit Notes Modal (Overlay)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  Edit Notes - News Cache Table                                                     [✕]  │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  Source: Database table: news_cache                                                     │
│  Coverage: 8,218 rows, Nov 6-13, 2025                                                   │
│                                                                                          │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ Purpose:                                                                           │ │
│  │ ┌────────────────────────────────────────────────────────────────────────────────┐ │ │
│  │ │ Primary cache for filtered news articles. Deduplicated by content hash.       │ │ │
│  │ │ Populated by news sentiment refresh task every 65 seconds.                    │ │ │
│  │ └────────────────────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                                    │ │
│  │ Gaps / Missing Data:                                                               │ │
│  │ ┌────────────────────────────────────────────────────────────────────────────────┐ │ │
│  │ │ - Missing sentiment breakdown by source (only overall sentiment)              │ │ │
│  │ │ - No topic/category classification                                            │ │ │
│  │ │ - Would benefit from entity extraction (companies/people mentioned)           │ │ │
│  │ └────────────────────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                                    │ │
│  │ Verification / Testing:                                                            │ │
│  │ ┌────────────────────────────────────────────────────────────────────────────────┐ │ │
│  │ │ 2025-11-13: Verified deduplication works (tested with duplicate articles)     │ │ │
│  │ │ 2025-11-10: Compared sentiment scores to Bloomberg - within 10% margin        │ │ │
│  │ └────────────────────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                                    │ │
│  │ Known Issues:                                                                      │ │
│  │ ┌────────────────────────────────────────────────────────────────────────────────┐ │ │
│  │ │ (none)                                                                         │ │ │
│  │ └────────────────────────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                          │
│                                                   [Cancel]  [Save Notes]                │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Compact View (Dense Table - More Rows Visible)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  System Capabilities                                  [Compact ✓] Last Scan: 2 min ago │
│  [🔄 Refresh]  [📊 All ▾]  [🔍 Search...]                                      48 total │
└─────────────────────────────────────────────────────────────────────────────────────────┘

Cat.    │ Name                           │ Type   │ Coverage              │ Notes
────────┼────────────────────────────────┼────────┼───────────────────────┼────────────────
🔵 Mkt  │ Historical Market Data         │ Task   │ Daily (04:00)         │ 252d/symbol ✅
🔵 Mkt  │ Daily OHLCV Refresh            │ Task   │ Daily (16:30)         │ [+]
📰 News │ News Cache                     │ DB     │ 8.2k rows, Nov 6-13   │ Primary cache ⚠️
📰 News │ News Summary Log               │ DB     │ 185k rows, Nov 5-13   │ [+]
📰 News │ News Sentiment Refresh         │ Task   │ Every 65s             │ [+]
📈 Port │ Watchlist Items                │ DB     │ 9 rows, Nov 9-13      │ User symbols ✅
📈 Port │ Watchlist Snapshots            │ DB     │ 456 rows              │ [+]
📈 Port │ Watchlist Score Refresh        │ Task   │ Every 60s             │ N/A issue 🔴
📈 Port │ Portfolio Positions            │ DB     │ 1 row, Nov 8          │ [+]
🔬 Anal │ Fear & Greed Daily             │ DB     │ 9 rows, Nov 7-11      │ [+]
🔬 Anal │ Fear & Greed Components        │ DB     │ 5 rows, Nov 7-11      │ 4/5 broken 🔴
🔬 Anal │ Fear & Greed Inputs            │ DB     │ 10 rows, Nov 7-13     │ [+]
🔬 Anal │ Options Market Metrics         │ DB     │ 1 row, Nov 13         │ [+]
🔬 Anal │ Technical Indicators           │ DB     │ 60 rows               │ [+]
⚙️  Infra│ Fetch Options Activity         │ Task   │ Daily (21:15)         │ [+]
⚙️  Infra│ Fetch Put/Call Ratio           │ Task   │ Daily                 │ [+]

[Click row to expand notes, [+] to add notes, ✅ verified, ⚠️  has gaps, 🔴 has issues]
```

---

## Changes View (What's New/Changed)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  System Capabilities - Changes                                                          │
│                                                                                          │
│  [View: Changes Since Yesterday ▾]                                                      │
└─────────────────────────────────────────────────────────────────────────────────────────┘

🆕 NEW (1)
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ 🔵 Market Data  │ Analyst Ratings Table                                                 │
│                 │ DB: analyst_ratings | 0 rows                                          │
│                 │ Added: 2025-11-13 17:45                                               │
│                 │ 📝 Notes: (empty - newly discovered)                    [Add Note]    │
└─────────────────────────────────────────────────────────────────────────────────────────┘

📝 CHANGED (5)
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ 📰 News         │ News Cache Table                                                      │
│                 │ WAS: 8,196 rows, Nov 6-13                                             │
│                 │ NOW: 8,218 rows, Nov 6-13  (+22 rows)                                 │
└─────────────────────────────────────────────────────────────────────────────────────────┘
│ 📈 Portfolio    │ Watchlist Items Table                                                 │
│                 │ WAS: 8 rows, Nov 9-12                                                 │
│                 │ NOW: 9 rows, Nov 9-13  (+1 row, date range extended)                  │
└─────────────────────────────────────────────────────────────────────────────────────────┘
│ 🔬 Analytics    │ Fear & Greed Daily Table                                              │
│                 │ WAS: 8 rows, Nov 7-11                                                 │
│                 │ NOW: 9 rows, Nov 7-11  (+1 row)                                       │
└─────────────────────────────────────────────────────────────────────────────────────────┘

🗑️ REMOVED (0)
```

---

## Mobile View (Responsive)

```
┌──────────────────────────────┐
│ System Capabilities          │
│ Last scan: 2 min ago         │
│                              │
│ [🔄] [📊 All ▾] [🔍]   48   │
└──────────────────────────────┘

┌──────────────────────────────┐
│ 🔵 Market Data               │
│ Historical Market Data       │
│ Celery Task · Daily (04:00)  │
│                              │
│ 252 days/symbol. Backfills...│
│ ✅ Verified 2025-11-10       │
│                     [Edit]   │
├──────────────────────────────┤
│ 📰 News                      │
│ News Cache Table             │
│ DB · 8,218 rows, Nov 6-13    │
│                              │
│ Primary cache. Deduplicated..│
│ ⚠️  Missing sentiment by src │
│                     [Edit]   │
├──────────────────────────────┤
│ 📈 Portfolio                 │
│ Watchlist Score Refresh      │
│ Celery Task · Every 60s      │
│                              │
│ Real-time scoring...         │
│ 🔴 N/A scores (investigating)│
│                     [Edit]   │
└──────────────────────────────┘

[< Prev] [1/3] [Next >]
```

---

## Key UI Features Shown

### Visual Design
- **Clean table layout** (similar to your Watchlist/Portfolio pages)
- **Category icons** (🔵 Market Data, 📰 News, 📈 Portfolio, 🔬 Analytics, ⚙️ Infrastructure)
- **Status badges** (✅ verified, ⚠️ has gaps, 🔴 has issues)
- **Compact/Expanded views** (toggle density)

### Functionality
- **Filter by category** (dropdown)
- **Search** (by name, source, notes content)
- **Sort** (by category, name, coverage, last updated)
- **Refresh scan** (manual trigger)
- **Edit notes** (modal overlay with 4 sections: purpose, gaps, verification, issues)
- **Changes view** (what's new/changed since last scan)

### Data Columns
1. **Category** - Visual icon + name
2. **Capability Name** - What it is
3. **Source** - Where it lives (DB table, Celery task, API endpoint)
4. **Coverage** - How much data (rows, date range, schedule)
5. **Notes** - Human-added context (inline preview + full edit modal)

### Mobile Responsive
- Stacked cards instead of wide table
- Condensed info, tap to expand
- Same functionality, optimized layout

---

**Would this work for you?** The key design decisions:

1. **Notes are prominent** - shown inline with expand/collapse
2. **Visual status** - quick scan to see verified/gaps/issues
3. **Multiple views** - compact (more rows), expanded (more detail), changes-only
4. **Simple editing** - just notes field, everything else auto-populated

**What would you change?**
