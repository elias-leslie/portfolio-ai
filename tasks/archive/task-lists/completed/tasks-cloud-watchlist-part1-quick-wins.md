# Watchlist Improvements - Part 1: Quick Wins

**Created**: 2025-11-08
**Tier**: Quick Wins (Sprint 1)
**Estimated Effort**: 6 hours
**Environment**: Cloud Claude Code (sandbox, limited runtime)
**Priority**: HIGH

---

## ⚠️ IMPORTANT: Cloud Environment Constraints

**This task is for a cloud Claude Code instance with limited environment access:**

✅ **You CAN:**
- **Read ALL source code** (full access to backend/, frontend/, docs/, all files)
- Search, grep, and analyze complete codebase structure
- Plan and design solutions
- Write/edit code files (frontend TypeScript/React, backend Python/FastAPI)
- Create git commits and branches
- Provide detailed implementation plans
- Use code analysis tools (ruff, mypy, eslint - static only)

❌ **You CANNOT (or should avoid):**
- Run Python venv commands (they hang in sandbox)
- Start backend/frontend services
- Run runtime tests (pytest, npm test, vitest - need running services)
- Execute database migrations (provide SQL scripts instead)
- Test API endpoints (no services running)
- Use browser automation (no services running)
- **ANY commands from project scripts** (restart.sh, start.sh, status.sh, etc.)
- **ANY curl/http requests** to localhost or specific IPs
- **ANY database commands** (psql, migrations, queries)
- **ANY package installation** (npm install, pip install during runtime)

✅ **You SHOULD run (static analysis - no services needed):**
- `ruff check backend/` - Python linting
- `ruff format backend/` - Python formatting
- `mypy backend/app/` - Python type checking
- `npx eslint frontend/` - TypeScript/React linting (if project configured)

**❌ DO NOT RUN THESE COMMANDS:**
```bash
source backend/.venv/bin/activate          # ❌ Hangs
bash ~/portfolio-ai/scripts/restart.sh     # ❌ No dev environment
pytest tests/                               # ❌ No runtime
curl http://localhost:8000                 # ❌ No services
psql -U portfolio_ai_user -d portfolio_ai  # ❌ No database access
npm test                                    # ❌ No runtime
```

**✅ USE THESE COMMANDS:**
```bash
# Code reading and analysis:
cat/grep/find/rg                           # ✅ Read and search files
ls/pwd                                      # ✅ Basic navigation

# Static analysis (IMPORTANT - run after changes):
ruff check backend/                         # ✅ Python linting
ruff format backend/                        # ✅ Python formatting
mypy backend/app/                           # ✅ Python type checking

# Git operations:
git status/add/commit/checkout/branch      # ✅ Git operations
```

**Your Workflow:**
1. **Research thoroughly** - Read code, understand architecture, document findings in Task 1
2. **Expand task list** - Add detailed subtasks based on your research
3. **Implement code changes** - Write/edit Python and TypeScript files
4. **Run static analysis** - Use ruff, mypy to catch issues early
5. **Fix any linting errors** - Clean code before committing
6. **Commit to git** - Create feature branch, commit all changes
7. **Provide handoff** - Give user git commands and testing steps for dev environment

**When Done:**
- Work on whatever branch cloud session created (check `git branch`)
- Commit all changes to that branch
- Provide: (1) branch name, (2) testing steps, (3) what's left to do
- User will pull your branch and continue in dev environment with full testing

---

## Overview

**Part 1 Focus**: Quick Wins - Immediate visual improvements and foundational features

**User Requirements** (ALL 5 confirmed):
1. ✅ Show price/technical/fundamental score breakdowns with ALL sub-metrics
2. ✅ Add weight sliders in settings for ALL sub-metrics (RSI, MACD, trend, valuation, growth, health, sentiment)
3. ✅ Priority indicators - NO arbitrary cap (show all 8 relevant ones)
4. ✅ Automated scheduled task for sparkline backfill (not manual)
5. ✅ All tiers: Quick Wins + Foundation + Polish

**Part 1 Deliverables**:
- **Priority Indicators**: 8 types (🔥 Hot, 📋 Earnings, 📰 News, 📈 Insider, 📉 Negative, 💎 Value, ⚡ Momentum, ⚠️ Caution)
- **Actionable Insights**: Display existing backend field in UI
- **Sparkline Backfill**: Automated Celery task (not manual)
- Backend + Frontend integration
- NO runtime testing (cloud environment)

---

## Task 1: Research & Validation (DO THIS FIRST - Cloud Agent)

**Objective**: Fully understand current implementation, verify all file paths, and flesh out detailed subtasks for Part 1

**CRITICAL**: This task is MANDATORY and must be completed FIRST before any implementation. Do NOT skip or defer this research phase.

### 1.1 Backend Structure Analysis

Read and document the following files:

#### Priority Indicators Research
- [ ] **File**: `backend/app/watchlist/response_builders.py`
  - Check WatchlistItemResponse model structure
  - Find where fields are defined (line ~50-100)
  - Note existing patterns for adding new fields
  - Verify from_service_dict() method location (line ~150-200)

- [ ] **File**: `backend/app/watchlist/watchlist_service.py`
  - Read get_items_with_scores() method fully
  - Find where items are built (last 50 lines of method)
  - Note how other calculated fields are added
  - Check existing imports at top of file

#### Signal & News Intelligence Research
- [ ] **File**: `backend/app/watchlist/signal_classifier.py`
  - Read classify_signal() function signature
  - Check what parameters are currently available
  - Note existing signal types (BUY, HOLD, AVOID)
  - Document current logic structure

#### Task Scheduling Research
- [ ] **File**: `backend/app/celery_app.py`
  - Locate beat_schedule definition (around line 83)
  - Check existing task patterns
  - Note schedule format (crontab vs seconds)
  - Document existing watchlist tasks

- [ ] **File**: `backend/app/tasks/watchlist_tasks.py`
  - Read all existing watchlist task functions
  - Note import patterns
  - Check how tasks return results
  - Find where refresh_watchlist_scores is imported from

### 1.2 Frontend Structure Analysis

#### Component Structure Research
- [ ] **File**: `frontend/components/watchlist/WatchlistTable.tsx`
  - Locate Signal column rendering (search for "signal_type")
  - Check current Badge usage
  - Note if SparklineWithHistory import exists (line ~14)
  - Document table cell structure

- [ ] **File**: `frontend/lib/api/watchlist.ts`
  - Read WatchlistItem interface completely
  - Note all existing optional fields
  - Check naming conventions
  - Document interface patterns

- [ ] **File**: `frontend/components/watchlist/NewsIntelligenceCard.tsx`
  - Find impact_summary display location (around line 200-210)
  - Check if actionable_insight is in TypeScript interface
  - Note styling patterns for text display
  - Check if article data structure includes actionable_insight

### 1.3 Database & Data Flow Analysis

#### Snapshot History Research
- [ ] **File**: Review migration files in `backend/migrations/`
  - Find latest migration number
  - Check if watchlist_snapshots table exists
  - Verify fetched_at column type
  - Note migration file naming pattern

#### Data Service Research
- [ ] **File**: `backend/app/watchlist/refresh_processor.py` or similar
  - Find where snapshots are created
  - Check if refresh_watchlist_scores function exists
  - Note parameters for refresh function
  - Document snapshot creation pattern

### 1.4 Document Findings

Create detailed implementation notes below:

#### File Locations (update after research):
```
Backend Files:
- Priority module: backend/app/watchlist/priority.py (NEW - to create)
- Response builder: backend/app/watchlist/response_builders.py (EXISTS - line X)
- Watchlist service: backend/app/watchlist/watchlist_service.py (EXISTS - line Y)
- Celery app: backend/app/celery_app.py (EXISTS - line Z)
- Watchlist tasks: backend/app/tasks/watchlist_tasks.py (EXISTS)

Frontend Files:
- Watchlist table: frontend/components/watchlist/WatchlistTable.tsx (EXISTS - line A)
- API types: frontend/lib/api/watchlist.ts (EXISTS - line B)
- News card: frontend/components/watchlist/NewsIntelligenceCard.tsx (EXISTS - line C)
```

#### Current vs Desired State:
```
Priority Indicators:
- Current: No priority indicator calculation or display
- Desired: 8 indicator types calculated in backend, displayed in UI
- Changes: New priority.py module, add to response, display in table

Actionable Insights:
- Current: Backend generates actionable_insight field (VERIFY THIS)
- Desired: Display in NewsIntelligenceCard
- Changes: Add rendering logic only

Sparklines:
- Current: SparklineWithHistory component exists but may be commented out
- Desired: Automated backfill task + re-enable UI component
- Changes: New Celery task, schedule it, uncomment imports
```

#### Dependencies & Risks:
```
Priority Indicators:
- Depends on: score.overall, signal_type, news_intelligence data
- Risk: If data missing, indicators won't show (graceful degradation needed)

Sparkline Backfill:
- Depends on: Existing snapshot schema, refresh_watchlist_scores function
- Risk: Backfill may use current data (not historical) - document this limitation

Actionable Insights:
- Depends on: Backend already generating field
- Risk: If field not in API response, UI will show nothing (check API first)
```

### 1.5 Expand Subtasks

After research, update the task sections below with:
- Exact line numbers for changes
- Specific function signatures
- Complete code patterns found
- Any deviations from assumptions

**Output Checklist**:
- [ ] All file paths verified and documented
- [ ] Exact line numbers noted for each change
- [ ] Current implementation patterns understood
- [ ] Dependencies mapped between tasks
- [ ] Risks and limitations documented
- [ ] Ready to start Task 2 implementation

---

## Task 2: Priority Indicators - Backend Implementation

**Goal**: Create priority indicator calculation system (ALL 8 indicators, no cap on display)

**Estimated Time**: 2 hours

### 2.1 Create Priority Indicators Module

**File**: `backend/app/watchlist/priority.py` (NEW)
**Lines**: ~200 lines

```python
"""Priority indicator calculation for watchlist items.

This module provides 8 priority indicator checks:
1. 🔥 Hot Opportunity - Top 3 BUY signals
2. 📋 Earnings Alert - Earnings within 7 days
3. 📰 Breaking News - 10+ articles in 24h
4. 📈 Insider Buying - Recent insider purchases
5. 📉 Negative Catalyst - News sentiment < -0.3
6. 💎 Value Play - Strong fundamentals, weak price
7. ⚡ Momentum - Strong price AND technical
8. ⚠️ Caution - Score misalignment

NO ARBITRARY CAP - All relevant indicators are returned.
"""

from __future__ import annotations

from pydantic import BaseModel


class PriorityIndicator(BaseModel):
    """Priority indicator model."""

    icon: str  # "🔥", "📋", "📰", "📈", "📉", "💎", "⚡", "⚠️"
    label: str  # "Hot Opportunity", "Earnings Alert", etc.
    tooltip: str  # Full explanation for hover
    priority: int  # 1-8 for sorting (1 = highest)
    category: str  # "time_sensitive", "risk", "opportunity", "caution"


# Priority order constants (lower = higher priority)
PRIORITY_ORDER = {
    "hot_opportunity": 1,
    "earnings_alert": 2,
    "breaking_news": 3,
    "insider_buying": 4,
    "negative_catalyst": 5,
    "value_play": 6,
    "momentum": 7,
    "caution": 8,
}


def check_hot_opportunity(item: dict, rank: int) -> PriorityIndicator | None:
    """Check if item is a top 3 BUY signal by overall score.

    Args:
        item: Watchlist item dict with signal_type and score
        rank: Item's rank by overall score (1 = highest)

    Returns:
        PriorityIndicator if top 3 BUY, else None
    """
    if item.get("signal_type") == "BUY" and rank <= 3:
        return PriorityIndicator(
            icon="🔥",
            label="Hot Opportunity",
            tooltip=f"Top #{rank} highest-scoring BUY signal. Strong technical and fundamental alignment.",
            priority=PRIORITY_ORDER["hot_opportunity"],
            category="opportunity",
        )
    return None


def check_earnings_alert(item: dict) -> PriorityIndicator | None:
    """Check if earnings are within 7 days.

    Args:
        item: Watchlist item dict with earnings_days_away field

    Returns:
        PriorityIndicator if earnings soon, else None
    """
    days_away = item.get("earnings_days_away")
    if days_away is not None and 0 <= days_away <= 7:
        return PriorityIndicator(
            icon="📋",
            label="Earnings Alert",
            tooltip=f"Earnings report in {days_away} days. Volatility expected.",
            priority=PRIORITY_ORDER["earnings_alert"],
            category="time_sensitive",
        )
    return None


def check_breaking_news(item: dict) -> PriorityIndicator | None:
    """Check if 10+ articles published in last 24h.

    Args:
        item: Watchlist item dict with news_intelligence.article_count_24h

    Returns:
        PriorityIndicator if breaking news, else None
    """
    news_intel = item.get("news_intelligence")
    if news_intel and news_intel.get("article_count_24h", 0) >= 10:
        count = news_intel["article_count_24h"]
        return PriorityIndicator(
            icon="📰",
            label="Breaking News",
            tooltip=f"{count} articles in 24h. Major news flow - investigate.",
            priority=PRIORITY_ORDER["breaking_news"],
            category="time_sensitive",
        )
    return None


def check_insider_buying(item: dict) -> PriorityIndicator | None:
    """Check for insider trading activity from news key_events.

    Args:
        item: Watchlist item dict with news_intelligence.key_events

    Returns:
        PriorityIndicator if insider buying detected, else None
    """
    news_intel = item.get("news_intelligence")
    if not news_intel:
        return None

    key_events = news_intel.get("key_events", [])
    for event in key_events:
        if event.get("event_category") == "insider_trade":
            # TODO: Parse transaction value if available
            return PriorityIndicator(
                icon="📈",
                label="Insider Buying",
                tooltip="Recent insider purchases detected. Bullish signal.",
                priority=PRIORITY_ORDER["insider_buying"],
                category="opportunity",
            )
    return None


def check_negative_catalyst(item: dict) -> PriorityIndicator | None:
    """Check if news sentiment is very negative (<-0.3).

    Args:
        item: Watchlist item dict with news_sentiment_score

    Returns:
        PriorityIndicator if bearish news, else None
    """
    sentiment = item.get("news_sentiment_score")
    if sentiment is not None and sentiment < -0.3:
        return PriorityIndicator(
            icon="📉",
            label="Negative Catalyst",
            tooltip=f"Bearish news flow (sentiment: {sentiment:.2f}). Wait for clarity.",
            priority=PRIORITY_ORDER["negative_catalyst"],
            category="risk",
        )
    return None


def check_value_play(item: dict) -> PriorityIndicator | None:
    """Check if strong fundamentals but weak price action.

    Criteria: fundamental_score > 70 AND price_score < 50

    Args:
        item: Watchlist item dict with score breakdown

    Returns:
        PriorityIndicator if value opportunity, else None
    """
    score = item.get("score")
    if not score:
        return None

    fundamental = score.get("fundamental", {}).get("score")
    price = score.get("price", {}).get("score")

    if fundamental and price and fundamental > 70 and price < 50:
        return PriorityIndicator(
            icon="💎",
            label="Value Play",
            tooltip=f"Strong fundamentals ({fundamental:.0f}) but low price momentum ({price:.0f}). Contrarian opportunity.",
            priority=PRIORITY_ORDER["value_play"],
            category="opportunity",
        )
    return None


def check_momentum(item: dict) -> PriorityIndicator | None:
    """Check if strong price AND technical momentum.

    Criteria: price_score > 70 AND technical_score > 70

    Args:
        item: Watchlist item dict with score breakdown

    Returns:
        PriorityIndicator if momentum play, else None
    """
    score = item.get("score")
    if not score:
        return None

    price = score.get("price", {}).get("score")
    technical = score.get("technical", {}).get("score")

    if price and technical and price > 70 and technical > 70:
        return PriorityIndicator(
            icon="⚡",
            label="Momentum",
            tooltip=f"Strong price ({price:.0f}) and technical ({technical:.0f}) momentum. Trend play.",
            priority=PRIORITY_ORDER["momentum"],
            category="opportunity",
        )
    return None


def check_caution(item: dict) -> PriorityIndicator | None:
    """Check for score misalignment between price and fundamentals.

    Criteria:
    - Price > 70 AND fundamental < 40 (overpriced)
    - Price < 30 AND fundamental > 70 (underpriced but falling)

    Args:
        item: Watchlist item dict with score breakdown

    Returns:
        PriorityIndicator if mixed signals, else None
    """
    score = item.get("score")
    if not score:
        return None

    price = score.get("price", {}).get("score")
    fundamental = score.get("fundamental", {}).get("score")

    if not price or not fundamental:
        return None

    if (price > 70 and fundamental < 40) or (price < 30 and fundamental > 70):
        return PriorityIndicator(
            icon="⚠️",
            label="Caution",
            tooltip=f"Score mismatch (price: {price:.0f}, fundamental: {fundamental:.0f}). Mixed signals - wait for confirmation.",
            priority=PRIORITY_ORDER["caution"],
            category="caution",
        )
    return None


def calculate_priority_indicators(
    all_items: list[dict],
    current_item: dict,
) -> list[PriorityIndicator]:
    """Calculate priority indicators for a watchlist item.

    NO ARBITRARY CAP - returns ALL applicable indicators, sorted by priority.

    Args:
        all_items: All watchlist items (for ranking hot opportunities)
        current_item: Item being evaluated

    Returns:
        List of priority indicators, sorted by priority (highest first)
    """
    # Rank items by overall score for hot_opportunity check
    sorted_items = sorted(
        all_items,
        key=lambda x: x.get("score", {}).get("overall", 0),
        reverse=True,
    )
    rank = sorted_items.index(current_item) + 1 if current_item in sorted_items else 999

    # Run all 8 indicator checks
    checks = [
        check_hot_opportunity(current_item, rank),
        check_earnings_alert(current_item),
        check_breaking_news(current_item),
        check_insider_buying(current_item),
        check_negative_catalyst(current_item),
        check_value_play(current_item),
        check_momentum(current_item),
        check_caution(current_item),
    ]

    # Collect non-None results
    indicators = [ind for ind in checks if ind is not None]

    # Sort by priority (1 = highest)
    indicators.sort(key=lambda x: x.priority)

    return indicators
```

### 2.2 Integrate Priority Indicators into API Response

#### Step 1: Add field to WatchlistItemResponse model

**File**: `backend/app/watchlist/response_builders.py`
**Location**: After line 96 (after news_intelligence field)

Add to `WatchlistItemResponse` model:
```python
priority_indicators: list[dict[str, Any]] = Field(
    default_factory=list,
    description="Priority indicators (🔥 hot, 📋 earnings, 📰 news, etc.)",
)
```

#### Step 2: Add to from_service_dict() method

**File**: `backend/app/watchlist/response_builders.py`
**Location**: In `from_service_dict()` method, after line 168

Add:
```python
priority_indicators=item.get("priority_indicators", []),
```

### 2.3 Calculate Priority Indicators in Watchlist Service

**File**: `backend/app/watchlist/watchlist_service.py`
**Location**: In `get_items_with_scores()` method

#### Step 1: Add import at top of file
```python
from app.watchlist.priority import calculate_priority_indicators
```

#### Step 2: Calculate indicators before returning items

Find the end of the `get_items_with_scores()` method (search for "return items"), and add BEFORE the return:

```python
# Calculate priority indicators for each item (no cap on display)
for item in items:
    indicators = calculate_priority_indicators(items, item)
    item["priority_indicators"] = [ind.model_dump() for ind in indicators]

return items
```

---

## Task 3: Priority Indicators - Frontend Implementation

**Goal**: Display priority indicators in watchlist table (no cap - show all relevant)

**Estimated Time**: 1 hour

### 3.1 Update TypeScript Types

**File**: `frontend/lib/api/watchlist.ts`
**Location**: After WatchlistItem interface

Add interface:
```typescript
export interface PriorityIndicator {
  icon: string;
  label: string;
  tooltip: string;
  priority: number;
  category: "time_sensitive" | "risk" | "opportunity" | "caution";
}
```

Add to `WatchlistItem` interface:
```typescript
priority_indicators?: PriorityIndicator[];
```

### 3.2 Display in WatchlistTable

**File**: `frontend/components/watchlist/WatchlistTable.tsx`
**Location**: In the Signal column rendering (search for "signal_type")

Replace signal cell with:
```typescript
<TableCell>
  <div className="flex items-center gap-1">
    {/* Signal Badge */}
    <Badge variant={getSignalVariant(item.signal_type || "HOLD")}>
      {item.signal_type || "HOLD"}
    </Badge>

    {/* Priority Indicators (NO CAP - show all) */}
    {item.priority_indicators && item.priority_indicators.length > 0 && (
      <div className="flex gap-0.5 ml-1">
        {item.priority_indicators.map((indicator, idx) => (
          <span
            key={`${item.id}-${indicator.label}-${idx}`}
            className="text-base cursor-help"
            title={indicator.tooltip}
          >
            {indicator.icon}
          </span>
        ))}
      </div>
    )}
  </div>
</TableCell>
```

---

## Task 4: Display Actionable Insights

**Goal**: Show existing actionable_insight field from backend in NewsIntelligenceCard

**Estimated Time**: 30 minutes

**File**: `frontend/components/watchlist/NewsIntelligenceCard.tsx`
**Location**: After impact_summary display (line 204)

Add between lines 204-205:
```typescript
{article.actionable_insight && (
  <p className="text-xs text-primary font-medium mt-1">
    💡 {article.actionable_insight}
  </p>
)}
```

**Note**: Backend already generates this field via LLM - just needs UI display.

---

## Task 5: Sparkline Backfill - Automated Task

**Goal**: Create scheduled Celery task to automatically backfill watchlist snapshot history

**Estimated Time**: 2.5 hours

### 5.1 Create Backfill Task Function

**File**: `backend/app/tasks/watchlist_tasks.py`
**Location**: After existing watchlist tasks

Add function (~80 lines):
```python
@celery_app.task(name="backfill_watchlist_snapshots", bind=True)
def backfill_watchlist_snapshots_task(self) -> dict[str, Any]:
    """Backfill historical watchlist snapshots for sparklines.

    Strategy:
    - For each watchlist item
    - Check how many days of history exist
    - If <30 days, backfill missing days up to 30
    - Uses existing refresh logic to generate snapshots
    - Scheduled daily to gradually fill bucket

    Returns:
        Results dict with counts (backfilled, skipped, failed)
    """
    from app.storage import get_storage
    from app.watchlist.service import refresh_watchlist_scores
    from datetime import datetime, UTC, timedelta

    storage = get_storage()
    results = {
        "backfilled_count": 0,
        "skipped_count": 0,
        "failed": [],
    }

    # Get all watchlist items
    items_df = storage.query("SELECT id, symbol, created_at FROM watchlist_items")

    for row in items_df.iter_rows(named=True):
        item_id = row["id"]
        symbol = row["symbol"]
        created_at = row["created_at"]

        # Check existing snapshot history
        snapshots_df = storage.query(
            """
            SELECT COUNT(*) as count, MIN(fetched_at) as oldest
            FROM watchlist_snapshots
            WHERE item_id = %s
            """,
            [item_id],
        )

        count = snapshots_df.row(0, named=True)["count"]
        oldest = snapshots_df.row(0, named=True)["oldest"]

        # Determine how many days of history we have
        if count > 0 and oldest:
            days_available = (datetime.now(UTC) - oldest).days
        else:
            days_available = 0

        # Skip if already have 30+ days or item <7 days old
        days_since_creation = (datetime.now(UTC) - created_at).days
        if days_available >= 30 or days_since_creation < 7:
            results["skipped_count"] += 1
            continue

        # Backfill up to 30 days (or item creation date, whichever is more recent)
        target_days = min(30, days_since_creation)
        missing_days = target_days - days_available

        if missing_days <= 0:
            results["skipped_count"] += 1
            continue

        # Generate snapshots for missing days (work backwards from today)
        for day_offset in range(1, missing_days + 1):
            backfill_date = datetime.now(UTC) - timedelta(days=day_offset)

            try:
                # Reuse refresh logic but with historical date
                # NOTE: This will use current price/technical data
                # For true historical backfill, would need historical OHLCV data
                refresh_watchlist_scores(symbol, as_of_date=backfill_date)
                results["backfilled_count"] += 1
            except Exception as e:
                results["failed"].append({
                    "symbol": symbol,
                    "date": backfill_date.isoformat(),
                    "error": str(e),
                })

    return results
```

### 5.2 Add Task to Beat Schedule

**File**: `backend/app/celery_app.py`
**Location**: After "update-technical-indicators-daily" task (around line 164)

Add to beat_schedule dict:
```python
"backfill-watchlist-history-daily": {
    "task": "backfill_watchlist_snapshots",
    "schedule": 86400.0,  # Daily (24 hours in seconds)
    "options": {"expires": 7200},  # 2 hour expiry
    # Notes:
    # - Runs daily at ~03:00 UTC (after other tasks)
    # - Gradually fills snapshot history up to 30 days
    # - Stops backfilling once 30 days achieved per item
    # - Runs automatically (no manual intervention needed)
},
```

### 5.3 Re-enable Sparklines in UI

**File**: `frontend/components/watchlist/WatchlistTable.tsx`

#### Step 1: Uncomment import (line 14)
Change:
```typescript
// OLD (commented):
// import { SparklineWithHistory } from "@/components/watchlist/SparklineWithHistory";

// NEW (uncommented):
import { SparklineWithHistory } from "@/components/watchlist/SparklineWithHistory";
```

#### Step 2: Verify sparkline usage
Search for `<SparklineWithHistory` in the file and ensure it's uncommented (around line 480).

---

## Task 6: Static Analysis & Code Quality

**Goal**: Ensure all code passes linting and type checking before commit

**Estimated Time**: 30 minutes

### 6.1 Run Backend Linting

```bash
# Python linting
ruff check backend/app/watchlist/priority.py
ruff format backend/app/watchlist/priority.py

# Check all modified backend files
ruff check backend/app/watchlist/
ruff format backend/app/watchlist/
```

### 6.2 Run Backend Type Checking

```bash
# Type check priority module
mypy backend/app/watchlist/priority.py --strict

# Check all watchlist modules
mypy backend/app/watchlist/ --strict
```

### 6.3 Fix All Errors

- [ ] Fix ALL ruff linting errors
- [ ] Fix ALL mypy type errors
- [ ] Do NOT use `# type: ignore` without documenting why
- [ ] Ensure all functions have type hints
- [ ] Ensure all imports are at module level

### 6.4 Verify Frontend TypeScript

Read modified TypeScript files to check for obvious syntax errors:
- `frontend/lib/api/watchlist.ts`
- `frontend/components/watchlist/WatchlistTable.tsx`
- `frontend/components/watchlist/NewsIntelligenceCard.tsx`

**Note**: No runtime TypeScript checking available in cloud environment.

---

## Task 7: Git Commit & Handoff to Local Dev

**Goal**: Commit all Part 1 changes and provide clear handoff instructions

**Estimated Time**: 15 minutes

### 7.1 Check Current Branch

```bash
git branch --show-current
```

**Document your branch name here**: `_______________________`

### 7.2 Stage All Changes

```bash
git add -A
git status  # Review what's being committed
```

### 7.3 Commit with Descriptive Message

```bash
git commit -m "feat(watchlist): Part 1 Quick Wins - priority indicators, insights, sparklines

Backend Changes:
- New priority.py module with 8 indicator types
- NO cap on indicator display (show all relevant)
- Priority indicators added to WatchlistItemResponse
- Priority calculation integrated into watchlist service
- Sparkline backfill task created (daily scheduled)
- Backfill task added to beat_schedule

Frontend Changes:
- PriorityIndicator TypeScript interface
- Priority indicators displayed in Signal column with tooltips
- Actionable insights shown in NewsIntelligenceCard
- SparklineWithHistory import re-enabled

Static Analysis:
- All code passes ruff check + format
- All code passes mypy --strict
- No type errors or linting issues

Part 1 of 3 (Quick Wins tier, 6 hours)"
```

### 7.4 Verify Commit

```bash
git log -1 --stat
git diff main --name-only
```

---

## Handoff Instructions for Local Dev Environment

**Cloud Agent Completed**: Part 1 Quick Wins implementation

### What Was Implemented

**✅ Backend**:
- Priority indicators module (`backend/app/watchlist/priority.py`)
- Priority indicator calculation integrated into watchlist service
- Sparkline backfill task created and scheduled
- All code passes static analysis

**✅ Frontend**:
- Priority indicators displayed in watchlist table
- Actionable insights shown in news cards
- Sparklines re-enabled (will populate over time)

**✅ Static Analysis**:
- All code passes ruff + mypy
- No linting or type errors

### What Local Dev Must Do

**Your Branch**: `[branch-name from git branch --show-current]`

#### Step 1: Pull Branch
```bash
git fetch origin [branch-name]
git checkout [branch-name]
```

#### Step 2: Restart Services
```bash
bash ~/portfolio-ai/scripts/restart.sh
bash ~/portfolio-ai/scripts/status.sh  # Verify services started
```

#### Step 3: Test Backend
```bash
# Test priority indicators API
curl http://localhost:8000/api/watchlist | jq '.[0].priority_indicators'
# Expected: Array of indicator objects with icon, label, tooltip, priority, category

# Verify sparkline backfill task is scheduled
curl http://localhost:8000/api/status | jq '.celery_beat_schedule' | grep backfill
# Expected: "backfill-watchlist-history-daily" task present
```

#### Step 4: Test Frontend (Manual)
1. Open http://192.168.8.233:3000/watchlist
2. Check Signal column for emoji indicators (🔥📋📰📈📉💎⚡⚠️)
3. Hover over indicators to see tooltips
4. Verify multiple indicators shown (no cap at 2)
5. Expand a watchlist item with news
6. Verify actionable insights displayed with 💡 icon
7. Check if sparklines appear (may need 7+ days of data)

#### Step 5: Run Tests
```bash
cd ~/portfolio-ai/backend && source .venv/bin/activate
pytest tests/unit/watchlist/ -v
pytest tests/integration/watchlist/ -v
pytest tests/ -v  # All tests
```

#### Step 6: If All Tests Pass
- Merge to main or continue to Part 2
- Monitor sparkline backfill task over next 24h
- Verify priority indicators update correctly

### Known Limitations

- **Sparklines**: Need 7-30 days of snapshot data to be useful (backfill runs daily)
- **Historical Data**: Backfill uses current price/technical data, not true historical OHLCV
- **Fundamental Scores**: Part 2 adds fundamental scoring (not in Part 1)
- **Value Play & Caution Indicators**: Will show "None" for fundamental field until Part 2

### Next Steps

**Part 2** will add:
- 4-pillar fundamental scoring (valuation/growth/health/sentiment)
- 3-pillar overall formula (price 33%, technical 33%, fundamental 34%)
- Volume/timeframe/percentile calculations
- Settings sliders for sub-metric weights
- AVOID signal bug fixes

---

## Files Summary (Part 1)

**New Backend Files** (1):
1. `backend/app/watchlist/priority.py` (~200 lines) ✅

**Modified Backend Files** (3):
1. `backend/app/watchlist/response_builders.py` - priority_indicators field ✅
2. `backend/app/watchlist/watchlist_service.py` - calculate priority indicators ✅
3. `backend/app/celery_app.py` - backfill task schedule ✅
4. `backend/app/tasks/watchlist_tasks.py` - backfill task function ✅

**Modified Frontend Files** (3):
1. `frontend/lib/api/watchlist.ts` - PriorityIndicator interface ✅
2. `frontend/components/watchlist/WatchlistTable.tsx` - indicators display, sparkline enable ✅
3. `frontend/components/watchlist/NewsIntelligenceCard.tsx` - actionable_insight display ✅

**Total**: 1 new file, 6 modified files

---

**END OF PART 1 - Ready for Local Dev Testing**
