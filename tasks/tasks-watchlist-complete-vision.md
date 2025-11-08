# Watchlist Complete Vision - Implementation Task List

**Created**: 2025-11-08 16:10
**Type**: Comprehensive (Cloud → Local → Cloud handoff pattern)
**Estimated Total**: 12-15 hours
**Priority**: HIGH - Complete watchlist vision to match design references

---

## 🎯 Goal

Implement the complete Watchlist Intelligence Hub as defined in:
- `docs/watchlist_design_guide.md` (text specifications)
- `docs/design_references/watchlist_design_reference/*.html` (structure examples)
- `docs/design_references/watchlist_design_reference/*.png` (visual targets)

**Success Criteria**: Screenshots of implementation MUST match design reference screenshots.

---

## 📋 What's Been Completed

✅ **Part 1 (Quick Wins)**:
- Sparklines (30-day score history)
- Priority indicators foundation
- News intelligence card

✅ **Part 2 (Foundation - Partial)**:
- 3-pillar scoring backend (price/technical/fundamental)
- 4-pillar fundamental scoring (valuation/growth/health/sentiment)
- Score breakdown UI in expanded row
- Migration 019 (weight configuration columns)
- Timeframe and percentile modules

---

## ❌ What's Missing (From Gap Analysis)

**Critical UX Issues**:
1. Main table cluttered with technical columns
2. Missing Trading Style column
3. Missing Risk Level column
4. No search bar
5. No filter dropdowns
6. Settings sliders not implemented

**Source**: `tasks/WATCHLIST-GAP-ANALYSIS.md`

---

## 🔄 Handoff Protocol

This task list is designed for **cloud ↔ local agent collaboration**:

### Cloud Agent Responsibilities
- ✅ Research and architecture
- ✅ Write frontend components (TypeScript/React)
- ✅ Write backend logic (Python)
- ✅ Static analysis (ruff, mypy)
- ✅ Git commits
- ❌ CANNOT run services, tests, database, or take screenshots

### Local Agent Responsibilities
- ✅ Execute migrations
- ✅ Run tests and verify passing
- ✅ Restart services
- ✅ Take screenshots and compare vs design
- ✅ Manual testing and verification
- ✅ Final commit and handoff back

### Handoff Format
When handing off, agent MUST create `HANDOFF-watchlist-YYYYMMDD-HHMM.md` with:
- What was completed
- What needs verification
- Exact commands to run
- Screenshot comparisons needed
- Next agent's starting point

---

## 📊 Task Breakdown

### PHASE 1: Main Table UX (Cloud Start)
**Estimated**: 3-4 hours
**Agent**: Cloud → Local

#### Task 1.1: Research Current Table Structure (Cloud - 30min)
**Objective**: Understand current WatchlistTable.tsx implementation

- [ ] Read `frontend/components/watchlist/WatchlistTable.tsx` completely
- [ ] Document current columns and their data sources
- [ ] Check `frontend/lib/api/watchlist.ts` for WatchlistItem type
- [ ] Compare with design reference column list
- [ ] Create comparison matrix: Current vs Design

**Deliverable**: Comment in code documenting column mapping

---

#### Task 1.2: Hide Technical Columns (Cloud - 1hr)
**Objective**: Remove SMA, RSI, MACD, Volume from main table

**Files to modify**:
- `frontend/components/watchlist/WatchlistTable.tsx`

**Changes**:
1. Comment out or remove column definitions for:
   - SMA columns
   - RSI column
   - MACD column
   - Volume column
2. Keep only: Symbol, Price, Change, Signal, Score, Sparkline, Updated
3. Ensure table header and body stay in sync
4. Run static checks (no runtime needed)

**Acceptance**: Only 7 columns visible in table header

---

#### Task 1.3: Add Trading Style Column (Cloud - 1hr)
**Objective**: Add Trading Style column showing "Swing (3-7d)" format

**Files to modify**:
- `frontend/components/watchlist/WatchlistTable.tsx`
- `frontend/lib/api/watchlist.ts` (if type updates needed)

**Implementation**:
```typescript
// Add column after Score column
{
  header: "Trading Style",
  cell: (item) => {
    if (!item.recommended_style || !item.optimal_holding_period) {
      return <span className="text-text-muted">-</span>;
    }

    // Map style to display label
    const styleLabels: Record<string, string> = {
      "Swing": "Swing",
      "Long": "Long",
      "Momentum": "Momentum",
      "Day": "Day",
      "Event": "Event"
    };

    const label = styleLabels[item.recommended_style] || item.recommended_style;

    return (
      <div className="text-xs">
        <div className="font-medium text-text">{label}</div>
        <div className="text-text-muted">({item.optimal_holding_period})</div>
      </div>
    );
  }
}
```

**Acceptance**: Trading Style column visible between Score and Risk

---

#### Task 1.4: Add Risk Level Column (Cloud - 1hr)
**Objective**: Add Risk Level column with Low/Mid/High + icons

**Files to modify**:
- `frontend/components/watchlist/WatchlistTable.tsx`

**Implementation**:
```typescript
// Add column after Trading Style
{
  header: "Risk",
  cell: (item) => {
    if (!item.risk_level) {
      return <span className="text-text-muted">-</span>;
    }

    const riskConfig: Record<string, { label: string; icon: string; color: string }> = {
      "Low": { label: "Low", icon: "✓", color: "text-gain" },
      "Medium": { label: "Mid", icon: "⚠️", color: "text-neutral" },
      "High": { label: "High", icon: "⚠️⚠️", color: "text-loss" }
    };

    const config = riskConfig[item.risk_level] || { label: item.risk_level, icon: "", color: "text-text-muted" };

    return (
      <div className={`text-xs ${config.color}`}>
        <div className="font-medium">{config.icon} {config.label}</div>
      </div>
    );
  }
}
```

**Acceptance**: Risk column visible after Trading Style

---

#### Task 1.5: Add Search Bar (Cloud - 1hr)
**Objective**: Add search input in header

**Files to modify**:
- `frontend/app/watchlist/page.tsx` (add search state and filter logic)
- `frontend/components/watchlist/WatchlistTable.tsx` (might not need changes)

**Implementation**:
```typescript
// In watchlist page
const [searchQuery, setSearchQuery] = useState("");

// Filter items
const filteredItems = useMemo(() => {
  if (!searchQuery) return items;

  const query = searchQuery.toLowerCase();
  return items.filter(item =>
    item.symbol.toLowerCase().includes(query) ||
    item.note?.toLowerCase().includes(query)
  );
}, [items, searchQuery]);

// Add search input before table
<div className="flex items-center gap-2 mb-4">
  <div className="flex-1">
    <input
      type="text"
      placeholder="Search by Symbol or Company..."
      value={searchQuery}
      onChange={(e) => setSearchQuery(e.target.value)}
      className="w-full px-4 py-2 rounded-lg bg-surface border border-border text-text"
    />
  </div>
  {/* Settings and Refresh buttons */}
</div>
```

**Acceptance**: Search input visible above table

---

#### Task 1.6: Static Analysis & Commit (Cloud - 15min)
**Objective**: Ensure all changes pass checks

```bash
# Run from backend directory
cd ~/portfolio-ai/frontend
npm run build  # Check for TypeScript errors

# Commit
git add frontend/
git commit -m "feat(watchlist): main table UX improvements

- Hide technical columns (SMA, RSI, MACD, Volume) from main table
- Add Trading Style column with holding period
- Add Risk Level column with visual indicators
- Add search bar for symbol/note filtering

Main table now matches design reference structure.

Phase 1 of Watchlist Complete Vision.
Cloud agent handoff to local for verification.

🤖 Generated with Claude Code"
```

**Deliverable**: Clean commit, ready for local verification

---

#### Task 1.7: HANDOFF TO LOCAL (Cloud → Local)
**Objective**: Create handoff document

**Create**: `tasks/HANDOFF-watchlist-phase1-YYYYMMDD-HHMM.md`

**Contents**:
```markdown
# Watchlist Phase 1 Handoff - Main Table UX

**Cloud Agent Completed**:
- ✅ Hid technical columns from main table
- ✅ Added Trading Style column
- ✅ Added Risk Level column
- ✅ Added search bar
- ✅ Static analysis passed
- ✅ Committed changes

**Local Agent Tasks**:
1. Pull latest from branch
2. Restart frontend: `bash ~/portfolio-ai/scripts/restart.sh`
3. Take screenshot:
   ```bash
   node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js \
     http://192.168.8.233:3000/watchlist \
     /tmp/watchlist-phase1-after.png
   ```
4. Compare screenshots:
   - Reference: `docs/design_references/watchlist_design_reference/watchlist_main_table_view/screen.png`
   - Current: `/tmp/watchlist-phase1-after.png`
5. Verify table has exactly 9 columns:
   - Symbol, Price, Change, Signal, Score, Trading Style, Risk, Score Trend, Last Update
6. Verify search bar filters by symbol
7. If issues found: Document and hand back to cloud
8. If all good: Continue to Phase 2

**Branch**: claude/implement-watchlist-improvements-XXXXX
**Commit**: [hash]
```

**STOP HERE** - Local agent takes over for verification

---

### PHASE 2: Filter Dropdowns (Local Start)
**Estimated**: 2 hours
**Agent**: Local → Cloud → Local

#### Task 2.1: Verify Phase 1 & Screenshot Comparison (Local - 30min)
**Objective**: Ensure Phase 1 changes match design

- [ ] Pull latest code
- [ ] Restart frontend
- [ ] Take screenshot of main table
- [ ] Compare with design reference side-by-side
- [ ] Verify all 9 columns present
- [ ] Test search functionality
- [ ] Document any issues

**If issues**: Hand back to cloud with specific fixes needed
**If good**: Continue to Task 2.2

---

#### Task 2.2: Filter Dropdowns Research (Cloud - 30min)
**Objective**: Design filter dropdown component

**Research**:
- Check existing UI component library (shadcn/ui)
- Look for existing dropdown patterns in codebase
- Design filter state management approach

**Deliverable**: Code for 3 filter dropdowns (Signal, Style, Risk)

---

#### Task 2.3: Implement Filter Dropdowns (Cloud - 1hr)
**Objective**: Add Signal, Trading Style, Risk filter dropdowns

**Files to modify**:
- `frontend/app/watchlist/page.tsx`

**Implementation**:
```typescript
// Add filter state
const [signalFilter, setSignalFilter] = useState<string>("All");
const [styleFilter, setStyleFilter] = useState<string>("All");
const [riskFilter, setRiskFilter] = useState<string>("All");

// Combine filters
const filteredItems = useMemo(() => {
  let result = items;

  // Search filter
  if (searchQuery) {
    const query = searchQuery.toLowerCase();
    result = result.filter(item =>
      item.symbol.toLowerCase().includes(query) ||
      item.note?.toLowerCase().includes(query)
    );
  }

  // Signal filter
  if (signalFilter !== "All") {
    result = result.filter(item => item.signal_type === signalFilter);
  }

  // Style filter
  if (styleFilter !== "All") {
    result = result.filter(item => item.recommended_style === styleFilter);
  }

  // Risk filter
  if (riskFilter !== "All") {
    result = result.filter(item => item.risk_level === riskFilter);
  }

  return result;
}, [items, searchQuery, signalFilter, styleFilter, riskFilter]);

// Add filter row above table
<div className="flex gap-3 mb-4">
  <Select value={signalFilter} onValueChange={setSignalFilter}>
    <SelectTrigger className="w-40">
      <SelectValue placeholder="Signal: All" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="All">All</SelectItem>
      <SelectItem value="BUY">BUY</SelectItem>
      <SelectItem value="HOLD">HOLD</SelectItem>
      <SelectItem value="AVOID">AVOID</SelectItem>
    </SelectContent>
  </Select>

  {/* Similar for Style and Risk */}
</div>
```

**Acceptance**: 3 filter dropdowns visible and functional

---

#### Task 2.4: HANDOFF TO LOCAL (Cloud → Local)
**Objective**: Verify filters work

**Local Tasks**:
- Pull code
- Restart frontend
- Test each filter dropdown
- Verify combinations work
- Take screenshot with filters applied
- Compare with design reference

---

### PHASE 3: Settings Sliders (Cloud Start)
**Estimated**: 3 hours
**Agent**: Cloud → Local

#### Task 3.1: Settings Panel UI (Cloud - 2hrs)
**Objective**: Implement weight sliders in settings

**Files to modify**:
- `frontend/components/settings/WatchlistPreferences.tsx`

**Implementation** (as per Part 2 deferred task):
- Add fundamental weight slider (33%)
- Add technical sub-weight sliders (RSI, Trend, MACD)
- Add fundamental sub-weight sliders (Valuation, Growth, Health, Sentiment)
- Add validation (totals must sum to 100%)

**Acceptance**: Settings panel shows 12 total sliders

---

#### Task 3.2: Settings API Integration (Cloud - 1hr)
**Objective**: Wire up save/load for new weight fields

**Files to modify**:
- `frontend/lib/api/preferences.ts`
- `backend/app/api/preferences.py` (if needed)

**Implementation**:
- Add API calls to save weight preferences
- Load weights on page mount
- Handle validation errors

**Acceptance**: Weights persist across page reloads

---

#### Task 3.3: HANDOFF TO LOCAL (Cloud → Local)
**Objective**: Verify settings persistence

**Local Tasks**:
- Test weight slider changes
- Verify saves to database (check migration 019 columns)
- Verify loads on refresh
- Test validation (non-100% totals)

---

### PHASE 4: Enhanced Score Details (Cloud Start)
**Estimated**: 2 hours
**Agent**: Cloud → Local

#### Task 4.1: Rich Fundamental Display (Cloud - 2hrs)
**Objective**: Show detailed fundamental metrics in score breakdown

**Current**: Shows "Growth: 92"
**Design**: Shows "Revenue +24%, EPS +18%"

**Files to modify**:
- `frontend/components/watchlist/ExpandedRow.tsx`

**Implementation**:
Pull from `item.current_score.fundamental.metadata`:
```typescript
{item.current_score?.fundamental?.metadata && (
  <div className="ml-4 mt-2 text-xs text-text-muted space-y-1">
    <div>Revenue Growth: {(item.current_score.fundamental.metadata.revenue_growth * 100).toFixed(1)}% YoY</div>
    <div>Profit Margin: {(item.current_score.fundamental.metadata.profit_margin * 100).toFixed(1)}%</div>
    <div>Debt/Equity: {item.current_score.fundamental.metadata.debt_to_equity?.toFixed(2)}</div>
  </div>
)}
```

**Acceptance**: Fundamental section shows rich context

---

### PHASE 5: Documentation & Final Verification (Local)
**Estimated**: 1 hour
**Agent**: Local only

#### Task 5.1: Screenshot Comparison Matrix (Local - 30min)
**Objective**: Systematic comparison vs design references

Create document: `tasks/WATCHLIST-VERIFICATION-RESULTS.md`

**For each view**:
1. Take screenshot of current implementation
2. Compare with design reference
3. Document matches and gaps
4. Create side-by-side comparison

**Views to verify**:
- Main table (collapsed)
- Expanded row (NVDA, AAPL, TSLA - 3 different examples)
- Search bar (active state)
- Filters (applied state)
- Settings panel (open state)

---

#### Task 5.2: Update Documentation (Cloud - 30min)
**Objective**: Update API reference and user guides

**Files to modify**:
- `docs/core/API_REFERENCE.md` (if new endpoints)
- `docs/watchlist_design_guide.md` (mark as implemented)

---

## 🎯 Success Criteria Checklist

### Main Table
- [ ] Exactly 9 columns (no more, no less)
- [ ] Trading Style column shows style + holding period
- [ ] Risk column shows Low/Mid/High with icons
- [ ] Search bar filters by symbol/note
- [ ] Filter dropdowns for Signal, Style, Risk
- [ ] No technical columns in main view
- [ ] Sparklines showing score trend

### Expanded Row
- [ ] Score breakdown shows 3 pillars
- [ ] Fundamental breakdown shows 4 sub-pillars
- [ ] Rich context (revenue %, margins, etc.)
- [ ] News intelligence card
- [ ] Trade recommendation
- [ ] Price data
- [ ] Technical indicators

### Settings
- [ ] Weight sliders for price/technical/fundamental
- [ ] Sub-weight sliders for technical (3 sliders)
- [ ] Sub-weight sliders for fundamental (4 sliders)
- [ ] Validation (sums to 100%)
- [ ] Persistence (saves and loads correctly)

### Screenshots Match Design
- [ ] Main table view matches `watchlist_main_table_view/screen.png`
- [ ] Expanded row matches `expanded_row_-_full_intelligence_view/screen.png`
- [ ] Settings panel matches `watchlist_settings_panel/screen.png`
- [ ] Search/filter bar matches `search_and_filter_bar/screen.png`

---

## 📦 Deliverables

### Code
- [ ] All frontend components updated
- [ ] All TypeScript types updated
- [ ] Static analysis passing (npm build, ruff, mypy)
- [ ] Git commits with descriptive messages

### Documentation
- [ ] Handoff documents for each phase
- [ ] Screenshot comparison matrix
- [ ] Updated API reference
- [ ] WATCHLIST-GAP-ANALYSIS.md marked as resolved

### Verification
- [ ] All tests passing
- [ ] Services restarted
- [ ] Manual testing complete
- [ ] Screenshots match design references

---

## 🚀 Getting Started (Cloud Agent)

**Your first task**: Start with Phase 1, Task 1.1 (Research)

1. Read this entire task list
2. Read design guide: `docs/watchlist_design_guide.md`
3. View design references: `docs/design_references/watchlist_design_reference/*.png`
4. Begin Task 1.1: Research current table structure
5. Work through Tasks 1.2-1.6 autonomously
6. Create handoff document (Task 1.7)
7. Update this file with your progress

**Remember**: Take your time, read the design references thoroughly, and ensure every change aligns with the vision.

---

## 📊 Progress Tracking

**Overall Progress**: 0/24 tasks complete (0%)

### Phase 1: Main Table UX (0/7)
- [ ] 1.1 Research current table
- [ ] 1.2 Hide technical columns
- [ ] 1.3 Add Trading Style column
- [ ] 1.4 Add Risk Level column
- [ ] 1.5 Add search bar
- [ ] 1.6 Static analysis & commit
- [ ] 1.7 Handoff to local

### Phase 2: Filters (0/4)
- [ ] 2.1 Verify Phase 1
- [ ] 2.2 Filter dropdowns research
- [ ] 2.3 Implement filters
- [ ] 2.4 Handoff to local

### Phase 3: Settings (0/3)
- [ ] 3.1 Settings panel UI
- [ ] 3.2 Settings API integration
- [ ] 3.3 Handoff to local

### Phase 4: Enhanced Details (0/1)
- [ ] 4.1 Rich fundamental display

### Phase 5: Documentation (0/2)
- [ ] 5.1 Screenshot comparison
- [ ] 5.2 Update documentation

---

**Ready to begin!** Cloud agent, start with Phase 1, Task 1.1.

**Last Updated**: 2025-11-08 16:10 (created)
**Status**: NOT STARTED - Awaiting cloud agent
