# Cloud Agent Handoff - Watchlist Complete Vision

**Date**: 2025-11-08 16:25
**Status**: READY TO START
**Context Used**: 65% (130K/200K tokens) - 70K tokens available for cloud agent

---

## 🎯 Your Mission

Implement the complete Watchlist Intelligence Hub to match design references exactly.

**Success Criteria**: Screenshots of final implementation MUST match design reference screenshots pixel-perfect.

---

## 📚 Required Reading (IN THIS ORDER)

1. **Design Vision** (15 min):
   - Read: `docs/watchlist_design_guide.md` (complete ASCII mockups)
   - View: `docs/design_references/watchlist_design_reference/*.png` (4 reference screenshots)
   - Compare with current screenshots at `/tmp/watchlist-*.png`

2. **Gap Analysis** (10 min):
   - Read: `tasks/WATCHLIST-GAP-ANALYSIS.md` (what's broken now)
   - Read: `tasks/TASK-LIST-REVIEW.md` (critical missing features)

3. **Your Task List** (5 min):
   - Read: `tasks/tasks-watchlist-complete-vision.md` (your working document)

**Total Reading Time**: ~30 minutes (DO NOT SKIP - prevents wasted work)

---

## ⚠️ CRITICAL: Missing Features Found

The initial task list was missing **6 critical features** that are in the design:

### 1. Priority Indicators (🔥📰⚡📋💎📉📈)
**What**: Visual badges in Signal column showing why a stock is interesting
**Where**: Main table, Signal column
**Backend**: Need `priority_indicators: list[str]` in snapshot
**Frontend**: Icon display next to BUY/HOLD/AVOID badge

### 2. Rich Fundamental Metrics
**What**: Show actual numbers like "Revenue +24%, EPS +18%" not just scores
**Where**: Expanded row, Score Breakdown section
**Backend**: Need all fundamental fields (margins, growth rates, P/E, etc.)
**Frontend**: Detailed metric display with context

### 3. News Intelligence Enhancements
**What**: Article counts, coverage level, key events timeline
**Where**: Expanded row, News Intelligence section
**Backend**: Article counts, coverage calculation, events structure
**Frontend**: Display counts and events list

### 4. Complete Technical Indicators
**What**: SMA(50/200), Bollinger bands, ATR - not just RSI/MACD
**Where**: Expanded row, Technical Indicators section
**Backend**: Calculate missing indicators
**Frontend**: Display all indicators

### 5. Market Cap Display
**What**: Show market capitalization in billions
**Where**: Expanded row, Price Data section
**Backend**: Fetch from price service
**Frontend**: Display formatted (e.g., "$768B")

### 6. Watchlist Ranking
**What**: Show "Top 3 in watchlist" badge for high scorers
**Where**: Expanded row, Overall score line
**Frontend**: Client-side ranking, conditional display

---

## 📋 Updated Task Breakdown

**Phase 1: Main Table UX** (9 tasks, ~6h)
- Tasks 1.1-1.7: Original (hide columns, add style/risk, search)
- **Task 1.8 (NEW)**: Priority indicators backend logic
- **Task 1.9 (NEW)**: Priority indicators frontend display

**Phase 2: Filters** (4 tasks, ~2h)
- Tasks 2.1-2.4: Signal/Style/Risk filter dropdowns

**Phase 3: Settings** (3 tasks, ~3h)
- Tasks 3.1-3.3: Weight sliders for all pillars

**Phase 4: Enhanced Details** (5 tasks, ~4h)
- **Task 4.1 (ENHANCED)**: Rich fundamental display (specific metrics)
- **Task 4.2 (NEW)**: News intelligence enhancements
- **Task 4.3 (NEW)**: Complete technical indicators
- **Task 4.4 (NEW)**: Watchlist ranking display
- Task 4.5: Market cap display

**Phase 5: Documentation** (2 tasks, ~1h)
- Tasks 5.1-5.2: Screenshot comparison, docs

**New Total**: 23 main tasks (~16 hours)

---

## 🚀 How to Start (Step-by-Step)

### Step 1: Environment Setup (5 min)
```bash
cd ~/portfolio-ai
git status  # Verify on correct branch
git pull    # Get latest changes

# Verify you're on: claude/implement-watchlist-improvements-011CUvqDioH4JoBobHQRa8nD
```

### Step 2: Read Design References (15 min)
```bash
# View text specifications
cat docs/watchlist_design_guide.md

# Open visual references (if you have image viewing capability)
# Or describe them in detail from PNG files in:
ls docs/design_references/watchlist_design_reference/

# Read the 4 reference screenshots:
# 1. watchlist_main_table_view/screen.png - Main table layout
# 2. expanded_row_-_full_intelligence_view/screen.png - Expanded details
# 3. watchlist_settings_panel/screen.png - Settings sliders
# 4. search_and_filter_bar/screen.png - Search/filter UI
```

### Step 3: Review Current State (10 min)
```bash
# Read gap analysis
cat tasks/WATCHLIST-GAP-ANALYSIS.md

# Read missing features
cat tasks/TASK-LIST-REVIEW.md

# Understand current table structure
cat frontend/components/watchlist/WatchlistTable.tsx | head -200
```

### Step 4: Begin Phase 1, Task 1.1 (30 min)
**Objective**: Research and document current table structure

- [ ] Read `frontend/components/watchlist/WatchlistTable.tsx` completely
- [ ] Document all current columns in a code comment
- [ ] Check `frontend/lib/api/watchlist.ts` for WatchlistItem type
- [ ] Compare with design reference (9 columns expected)
- [ ] Create comparison matrix in comment:

```typescript
/**
 * WATCHLIST TABLE STRUCTURE COMPARISON
 *
 * Design Reference (9 columns):
 * 1. Symbol
 * 2. Price
 * 3. Change %
 * 4. Signal (with priority indicators)
 * 5. Score (0-100 with bar)
 * 6. Trading Style (e.g., "Swing (3-7d)")
 * 7. Risk (Low/Mid/High with icons)
 * 8. Score Trend (sparkline)
 * 9. Last Update
 *
 * Current Implementation (X columns):
 * 1. Symbol ✓
 * 2. Price ✓
 * 3. Change % ✓
 * 4. Signal ✓ (missing priority indicators ❌)
 * 5. Score ✓
 * 6. SMA ❌ (should be hidden)
 * 7. RSI ❌ (should be hidden)
 * ... document all current columns ...
 *
 * Actions Needed:
 * - Remove: SMA, RSI, MACD, Volume columns
 * - Add: Trading Style column
 * - Add: Risk column
 * - Enhance: Signal column with priority indicators
 */
```

---

## 📝 Work Protocol

### Code Standards
- ✅ TypeScript strict mode (no `any` types)
- ✅ Prop types for all components
- ✅ Comments for complex logic
- ✅ Consistent naming (camelCase for variables, PascalCase for components)

### Before Each Commit
```bash
# Frontend checks
cd ~/portfolio-ai/frontend
npm run build  # Must pass with 0 errors

# Backend checks (if you modify Python)
cd ~/portfolio-ai/backend
source .venv/bin/activate
ruff check app/
mypy app/ --strict
```

### Commit Message Format
```
<type>(scope): <description>

<body with details>

<footer>
```

**Types**: `feat`, `fix`, `refactor`, `docs`, `style`, `test`
**Scope**: `watchlist`, `settings`, `api`, `types`

**Example**:
```
feat(watchlist): add Trading Style and Risk columns

- Added Trading Style column showing style + holding period
- Added Risk column with Low/Mid/High + visual indicators
- Updated WatchlistItem type with new fields

Implements Phase 1, Tasks 1.3-1.4 of Watchlist Complete Vision.

🤖 Generated with Claude Code
```

---

## 🔄 Handoff Protocol

### After Each Phase, Create Handoff Document

**File**: `tasks/HANDOFF-watchlist-phaseN-YYYYMMDD-HHMM.md`

**Template**:
```markdown
# Watchlist Phase N Handoff

**Cloud Agent Completed**:
- ✅ Task X.Y: Description
- ✅ Task X.Z: Description

**Code Changes**:
- Modified: file1, file2
- Created: file3
- Deleted: file4

**Static Analysis**:
- ✅ npm run build: PASSED
- ✅ ruff check: PASSED
- ✅ mypy: PASSED

**Commits**:
- abc1234: Commit message
- def5678: Commit message

**Local Agent Tasks**:
1. Pull latest: `git pull`
2. Restart services: `bash ~/portfolio-ai/scripts/restart.sh`
3. Take screenshot: [exact command]
4. Compare with design reference: [which file]
5. Verify: [specific features to test]
6. If issues: [hand back with details]
7. If good: [continue to Phase N+1]

**Next Phase**: Phase N+1 starts with Task X.Y

**Branch**: [branch name]
**Last Commit**: [hash]
```

### Handoff Points
- ✅ After Phase 1 (main table UX)
- ✅ After Phase 2 (filters)
- ✅ After Phase 3 (settings)
- ✅ After Phase 4 (enhanced details)
- ✅ After Phase 5 (documentation)

---

## 🎯 Phase 1 Detailed Tasks

### Task 1.1: Research (30 min) ← START HERE
[Already detailed above]

### Task 1.2: Hide Technical Columns (1 hr)
**Objective**: Clean up main table by removing SMA, RSI, MACD, Volume

**Files**: `frontend/components/watchlist/WatchlistTable.tsx`

**Actions**:
1. Find column definitions array
2. Comment out or remove:
   - SMA-related columns
   - RSI column
   - MACD column
   - Volume column
3. Keep only: Symbol, Price, Change, Signal, Score, Sparkline, Updated
4. Ensure header and body stay in sync
5. Run `npm run build` to verify
6. Commit with clear message

**Acceptance**: Table shows 7 columns (will be 9 after adding Style/Risk)

### Task 1.3: Add Trading Style Column (1 hr)
**Objective**: Show "Swing (3-7d)" format between Score and Sparkline

**Files**:
- `frontend/components/watchlist/WatchlistTable.tsx`
- `frontend/lib/api/watchlist.ts` (verify types)

**Implementation**:
```typescript
// After Score column, before Sparkline
{
  header: "Trading Style",
  accessorKey: "recommended_style",  // Or custom accessor
  cell: ({ row }) => {
    const item = row.original;
    if (!item.recommended_style || !item.optimal_holding_period) {
      return <span className="text-text-muted text-xs">-</span>;
    }

    // Map backend style to display label
    const styleLabels: Record<string, string> = {
      "Swing": "Swing",
      "Long": "Long",
      "Momentum": "Momentum",
      "Day": "Day",
      "Event": "Event",
      "Index": "Index",
      "Trend": "Trend",
      "Value": "Value"
    };

    const displayLabel = styleLabels[item.recommended_style] || item.recommended_style;

    return (
      <div className="text-xs">
        <div className="font-medium text-text">{displayLabel}</div>
        <div className="text-text-muted text-[10px]">({item.optimal_holding_period})</div>
      </div>
    );
  }
}
```

**Acceptance**: New column shows style + period for all items

### Task 1.4: Add Risk Level Column (1 hr)
**Objective**: Show Low/Mid/High with ⚠️ icons

**Implementation**:
```typescript
// After Trading Style column
{
  header: "Risk",
  accessorKey: "risk_level",
  cell: ({ row }) => {
    const item = row.original;
    if (!item.risk_level) {
      return <span className="text-text-muted text-xs">-</span>;
    }

    const riskConfig: Record<string, { label: string; icon: string; color: string }> = {
      "Low": {
        label: "Low",
        icon: "✓",
        color: "text-gain"
      },
      "Medium": {
        label: "Mid",
        icon: "⚠️",
        color: "text-neutral"
      },
      "High": {
        label: "High",
        icon: "⚠️⚠️",
        color: "text-loss"
      }
    };

    const config = riskConfig[item.risk_level] || {
      label: item.risk_level,
      icon: "",
      color: "text-text-muted"
    };

    return (
      <div className={`text-xs font-medium ${config.color}`}>
        {config.icon} {config.label}
      </div>
    );
  }
}
```

**Acceptance**: Risk column shows icons and colors correctly

### Task 1.5: Add Search Bar (1 hr)
**Objective**: Filter by symbol or note text

**Files**: `frontend/app/watchlist/page.tsx`

**Implementation**:
```typescript
// Add state
const [searchQuery, setSearchQuery] = useState("");

// Filter items
const filteredItems = useMemo(() => {
  if (!searchQuery.trim()) return items;

  const query = searchQuery.toLowerCase();
  return items.filter(item =>
    item.symbol.toLowerCase().includes(query) ||
    item.note?.toLowerCase().includes(query)
  );
}, [items, searchQuery]);

// Add search input ABOVE table, BELOW title
<div className="flex items-center gap-4 mb-4 px-4">
  <div className="flex-1 max-w-md">
    <div className="relative">
      <input
        type="text"
        placeholder="Search by Symbol or Company..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        className="w-full px-4 py-2 pl-10 rounded-lg bg-surface border border-border text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary"
      />
      <svg
        className="absolute left-3 top-2.5 h-5 w-5 text-text-muted"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>
    </div>
  </div>
  {/* Settings and Refresh buttons move here */}
</div>

// Pass filteredItems to table instead of items
<WatchlistTable items={filteredItems} ... />
```

**Acceptance**: Search filters table in real-time

### Task 1.6: Static Analysis & Commit (15 min)
```bash
cd ~/portfolio-ai/frontend
npm run build  # Must pass

git add frontend/
git commit -m "feat(watchlist): main table UX - hide tech columns, add style/risk/search

- Removed SMA, RSI, MACD, Volume columns from main table
- Added Trading Style column (style + holding period format)
- Added Risk Level column (Low/Mid/High with icons and colors)
- Added search bar for real-time symbol/note filtering
- Main table now has 9 columns matching design reference

Technical columns moved to expanded row only.

Implements Phase 1, Tasks 1.2-1.5 of Watchlist Complete Vision.

🤖 Generated with Claude Code"
```

### Task 1.7: Create Handoff Document (10 min)
**File**: `tasks/HANDOFF-watchlist-phase1-20251108-XXXX.md`

Use template above, fill in all details.

---

## 🚫 What NOT to Do

1. ❌ **Don't** skip reading design references
2. ❌ **Don't** assume current implementation is correct
3. ❌ **Don't** add features not in design
4. ❌ **Don't** use `any` types in TypeScript
5. ❌ **Don't** commit without running build/checks
6. ❌ **Don't** create handoff without testing build
7. ❌ **Don't** move to next phase without handoff approval

---

## 📞 When to Hand Back to Local Agent

**Handoff Triggers**:
1. Completed a full phase (1-5)
2. Need runtime verification (screenshots, tests, database)
3. Encountered blocking issue (missing data, unclear requirement)
4. Hit 90% context limit (pause, create handoff)

**Handoff Format**: Create HANDOFF-*.md with template above

---

## ✅ Success Criteria Reminder

At the end of ALL phases, these MUST be true:

**Main Table**:
- [ ] Exactly 9 columns (Symbol, Price, Change, Signal, Score, Style, Risk, Sparkline, Updated)
- [ ] Priority indicators showing in Signal column
- [ ] Search bar filters in real-time
- [ ] Filter dropdowns for Signal/Style/Risk
- [ ] Screenshot matches `watchlist_main_table_view/screen.png`

**Expanded Row**:
- [ ] Rich fundamental display (Revenue %, margins, P/E with context)
- [ ] Complete technical indicators (SMA, Bollinger, ATR, RSI, MACD)
- [ ] News intelligence (article counts, coverage, events)
- [ ] Watchlist ranking ("Top N" badge)
- [ ] Market cap displayed
- [ ] Screenshot matches `expanded_row_-_full_intelligence_view/screen.png`

**Settings**:
- [ ] All weight sliders functional
- [ ] Settings persist across reloads
- [ ] Screenshot matches `watchlist_settings_panel/screen.png`

---

## 🚀 Ready to Begin!

**Your starting point**: Phase 1, Task 1.1 (Research)

**Your working file**: `tasks/tasks-watchlist-complete-vision.md`

**Update progress in that file** as you complete each task.

**Good luck! Take your time, read the design references thoroughly, and ensure every change aligns with the vision.**

---

**Last Updated**: 2025-11-08 16:25
**Status**: READY FOR CLOUD AGENT
**Context Available**: ~70K tokens (35% of 200K limit)
