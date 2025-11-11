# Task List: Unified News Intelligence Component

**Source**: User request - eliminate duplication between MarketNewsCard and NewsIntelligenceCard
**Complexity**: MEDIUM
**Effort**: 2-3 hours
**Environment**: Local Dev
**Created**: 2025-11-11 14:15
**Status**: Paused at Task 0.3 Checkpoint
**PAUSED**: 2025-11-11 15:30 (Context 79%, natural checkpoint - scope confirmed)
**Next**: Proceed to Task 1.1 - Create UnifiedNewsIntelligenceCard component

<!-- PAUSED: 2025-11-11 15:30 | Context: 79% | Next: Task 1.1 - Create new component file -->

---

## Summary

**Goal**: Create a single unified NewsIntelligenceCard component that works for both Market News (dashboard) and ticker-specific News & Sentiment (watchlist), eliminating code duplication and ensuring UI parity.

**Approach**:
- Extract common functionality from both existing components
- Create conditional sections based on `ticker` prop
- Always show: Key Events, Sentiment Breakdown, Articles with Show All
- Conditionally show: Header with price, Price/Technical scores (ticker-specific only)

**Scope Discovery**: Required - need to find all component usages and understand data structures

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Run analysis to understand current components
  - Find: MarketNewsCard location and all usages
  - Find: NewsIntelligenceCard location and all usages
  - Find: Shared utilities already in use (news-formatting.ts)
  - Find: Data structures and API contracts
  - Output: Complete inventory of affected files

- [ ] 0.2 Document component interfaces and requirements
  - List all props used by MarketNewsCard
  - List all props used by NewsIntelligenceCard
  - Identify overlapping functionality
  - Identify unique features per component
  - Design unified prop interface

- [x] 0.3 Checkpoint: Confirm unified design ✅ COMPLETE
  - Total files to modify: 5 files
    - Create: frontend/components/shared/UnifiedNewsIntelligenceCard.tsx
    - Modify: frontend/app/page.tsx (dashboard)
    - Modify: frontend/components/watchlist/ExpandedRow.tsx
    - Delete: frontend/components/dashboard/MarketNewsCard.tsx (190 lines)
    - Delete: frontend/components/watchlist/NewsIntelligenceCard.tsx (245 lines)
  - Shared sections: Articles, Show All, Sorting, AI insights, Key Events
  - Conditional sections: Headline summary (if ticker), Sentiment Breakdown (if ticker), Price/Technical Scores (if ticker)
  - Estimated effort: 2-3 hours (context at 79%, will need multiple sessions)
  - **SCOPE CONFIRMED** - Ready for implementation

---

### 1.0 Create Unified Component Structure

- [ ] 1.1 Create new UnifiedNewsIntelligenceCard component in frontend/components/shared/
- [ ] 1.2 Define comprehensive TypeScript interface for props
  - ticker?: string (optional - determines conditional sections)
  - newsData: NewsBundle or similar
  - showHeader?: boolean
  - showScores?: boolean
  - Other shared props from both components
- [ ] 1.3 Set up component skeleton with conditional rendering logic

### 2.0 Implement Always-Visible Sections

- [ ] 2.1 Add Key Events section
  - Extract from existing watchlist NewsIntelligenceCard
  - Make work with market-level and ticker-specific data
- [ ] 2.2 Add Sentiment Breakdown charts
  - Positive/Negative/Neutral bar charts
  - Works for both market aggregate and ticker-specific
- [ ] 2.3 Add Articles list with Show All functionality
  - Use existing formatting utilities from news-formatting.ts
  - Include AI insights display (💡 impact, actionable)
  - Include ⏳ indicator for pending AI processing
  - Add sorting controls (Recent, Most Positive, Most Negative)
  - Implement Show All button (10 → all articles)

### 3.0 Implement Conditional Sections

- [ ] 3.1 Add Header section (only when ticker provided)
  - Ticker symbol
  - Current price
  - Price change ($ and %)
  - Conditional: {ticker && showHeader && <Header />}
- [ ] 3.2 Add Price Score section (only when ticker provided)
  - Extract from existing watchlist component
  - Conditional: {ticker && showScores && <PriceScore />}
- [ ] 3.3 Add Technical Score section (only when ticker provided)
  - Extract from existing watchlist component
  - Conditional: {ticker && showScores && <TechnicalScore />}

### 4.0 Replace Existing Components

- [ ] 4.1 Update Dashboard to use UnifiedNewsIntelligenceCard
  - Replace MarketNewsCard import
  - Props: ticker={null}, showHeader={false}, showScores={false}
  - Verify Market News section works correctly
- [ ] 4.2 Update Watchlist to use UnifiedNewsIntelligenceCard
  - Replace NewsIntelligenceCard import
  - Props: ticker="NVDA", showHeader={true}, showScores={true}
  - Verify News & Sentiment section works correctly
- [ ] 4.3 Delete old components
  - Remove frontend/components/dashboard/MarketNewsCard.tsx
  - Remove frontend/components/watchlist/NewsIntelligenceCard.tsx
  - Update any imports

### 5.0 Testing and Refinement

- [ ] 5.1 Visual testing with browser automation
  - Screenshot Market News on dashboard (ticker=null)
  - Screenshot News & Sentiment on watchlist (ticker="VTI")
  - Compare side-by-side - verify parity
- [ ] 5.2 Test sorting and Show All functionality
  - Test Recent/Most Positive/Most Negative sorting
  - Test Show All button expands/collapses
  - Verify works in both contexts
- [ ] 5.3 Test conditional sections
  - Verify header only shows for ticker-specific
  - Verify scores only show for ticker-specific
  - Verify market news doesn't show these sections
- [ ] 5.4 Test edge cases
  - Empty news data
  - Missing AI insights
  - Network errors
  - Long article lists

### 6.0 Code Quality and Cleanup

- [ ] 6.1 Run linting
  - TypeScript type checking passes
  - No any types used
  - Proper prop validation
- [ ] 6.2 Verify shared utilities
  - Confirm news-formatting.ts is used consistently
  - No duplicate formatting code
  - Single source of truth
- [ ] 6.3 Update component documentation
  - Add JSDoc comments explaining props
  - Document conditional rendering logic
  - Add usage examples

---

## Verification

- [ ] Functional: Both Market News and News & Sentiment display correctly
- [ ] Parity: Both sections have same features (Show All, sorting, AI insights)
- [ ] Conditional: Ticker-specific sections only show when ticker provided
- [ ] Quality: TypeScript checks pass, no linting errors
- [ ] Clean: Old components deleted, single source of truth
- [ ] Tested: Visual verification with screenshots, edge cases handled

---

## Relevant Files

**To be discovered in Task 0.1:**
- frontend/components/dashboard/MarketNewsCard.tsx (current)
- frontend/components/watchlist/NewsIntelligenceCard.tsx (current)
- frontend/lib/utils/news-formatting.ts (shared utilities)
- frontend/app/page.tsx (dashboard usage)
- frontend/app/watchlist/page.tsx (watchlist usage)
- [Additional files TBD after discovery]

**To be created:**
- frontend/components/shared/UnifiedNewsIntelligenceCard.tsx (new unified component)
