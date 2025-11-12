# Task List: Market Conditions Dashboard Redesign

**Source**: User request - Remove redundancy, add narrative, simplify jargon
**Complexity**: Medium-High
**Effort**: MEDIUM (8-12 hours)
**Environment**: Local (requires service restarts)
**Created**: 2025-11-11
**Status**: Active
**Strategy**: Systematic implementation - backend API first, then frontend UI

---

## Summary

**Goal**: Consolidate and improve market conditions section with plain-language narrative, dual health scoring, and zero-jargon sector display.

**User Requirements (Confirmed)**:
1. ✅ Keep BOTH Market Health (4 indicators) AND Fear & Greed Index (5 signals)
2. ✅ Actionable narrative with recommendations at the top
3. ✅ Sectors grouped as Leading/Neutral/Lagging with counts (not full list)
4. ✅ Plain-language labels for all technical jargon (tooltips for education)
5. ✅ Split-view layout: indicators left, sectors right

**Current Problems**:
- Redundant data shown twice (main + expandable section)
- Fear & Greed Index exists but NOT displayed on dashboard
- Technical jargon everywhere (VIX, DXY, TNX, XLK, XLF, etc.)
- Sectors hidden behind expansion (11 ETFs with symbols)
- No narrative explaining what it all means
- Component breakdown requires click to expand

**Target State**:
```
┌─────────────────────────────────────────────────────────────┐
│  MARKET CONDITIONS                                          │
│                                                             │
│  📝 NARRATIVE (Actionable - 3-4 sentences)                  │
│  "Markets are bullish today (Health: 68/100). Low          │
│   volatility and strong S&P levels favor staying invested. │
│   Technology and Financials are leading sectors. Dollar    │
│   strength may pressure international stocks."             │
│                                                             │
│  ┌─────────────────────┬────────────────────────────────┐  │
│  │ KEY INDICATORS      │ SECTOR ROTATION                │  │
│  │                     │                                │  │
│  │ Market Health: 68   │ 🟢 Leading (3)                 │  │
│  │ Fear & Greed: 72    │ - Technology                   │  │
│  │                     │ - Financials                   │  │
│  │ Market Volatility   │ - Energy                       │  │
│  │ (was: VIX)          │                                │  │
│  │ 15.2 🟢             │ 🟡 Neutral (5)                 │  │
│  │                     │ - Healthcare, Consumer, ...    │  │
│  │ S&P 500 Level       │                                │  │
│  │ 4,825 📈            │ 🔴 Lagging (3)                 │  │
│  │                     │ - Utilities                    │  │
│  │ Bond Yields         │ - Real Estate                  │  │
│  │ (was: 10Y Treasury) │ - Materials                    │  │
│  │ 4.2% ⚠️             │                                │  │
│  │                     │                                │  │
│  │ Dollar Strength     │ View All Sectors →             │  │
│  │ (was: DXY)          │                                │  │
│  │ 104.5 ⚠️            │                                │  │
│  └─────────────────────┴────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Current Implementation Analysis

### Frontend Components
- `frontend/components/portfolio/MarketConditions.tsx` (300 lines)
  - Shows 4 indicators: S&P 500, VIX, 10Y Treasury, DXY
  - Expandable section with component breakdown (duplicate data)
  - Sector performance hidden in expandable (11 sectors)
  - No narrative generation
  - Uses technical jargon throughout

- `frontend/components/market/FearGreedGauge.tsx` (193 lines)
  - Complete Fear & Greed UI implementation
  - NOT shown on dashboard (exists but unused)
  - Shows score, emoji, trend, description

### Backend APIs
- `backend/app/api/market.py` (431 lines)
  - `GET /api/market/conditions` - Returns market health score
  - `calculate_market_health()` - 4 indicators (VIX, S&P, TNX, DXY)
  - `_calculate_sector_scores()` - Returns all 11 sectors with signals
  - NO narrative generation endpoint

- `backend/app/api/market_fng.py` (exists but not reviewed)
  - Fear & Greed Index API
  - Separate from market conditions

### Narrative Generation Infrastructure
- `backend/app/watchlist/narrative_generator.py` (413 lines)
  - `NARRATIVE_TEMPLATES` - Plain-language mappings
  - Zero-jargon philosophy already implemented
  - Can adapt for market conditions narrative

---

## Tasks

### 0.0 Scope Discovery & Architecture Review (MANDATORY)

**Goal**: Complete inventory and architecture planning before implementation

- [ ] 0.1 Backend API analysis
  - [ ] 0.1.1 Review `backend/app/api/market_fng.py` structure
  - [ ] 0.1.2 Map current `/api/market/conditions` response model
  - [ ] 0.1.3 Map current `/api/market/fng` response model
  - [ ] 0.1.4 Document integration points for unified response

- [ ] 0.2 Frontend component analysis
  - [ ] 0.2.1 Review `frontend/lib/hooks/useMarket.ts` (market conditions hook)
  - [ ] 0.2.2 Review `frontend/lib/hooks/useFearGreed.ts` (F&G hook)
  - [ ] 0.2.3 Review `frontend/lib/api/market.ts` (API client)
  - [ ] 0.2.4 Document current React Query cache strategy

- [ ] 0.3 Plain-language mapping catalog
  - [ ] 0.3.1 Create comprehensive jargon → plain language mappings
    - Indicators: VIX, DXY, TNX, S&P 500
    - Sectors: All 11 sector ETFs (XLK, XLF, XLE, etc.)
    - Metrics: Change %, Score, Percentile
  - [ ] 0.3.2 Write educational tooltips for each term
  - [ ] 0.3.3 Create tooltip component spec

- [ ] 0.4 Narrative generation design
  - [ ] 0.4.1 Design narrative template structure
    - Overall sentiment (1 sentence)
    - Key drivers (1-2 sentences)
    - Actionable recommendation (1 sentence)
  - [ ] 0.4.2 Define input signals for narrative
    - Market Health score + label
    - Fear & Greed score + label
    - Top 3 leading sectors
    - Bottom 3 lagging sectors
    - Significant indicator changes
  - [ ] 0.4.3 Create narrative logic rules
    - Score combinations → sentiment
    - Sector rotation → recommendations
    - Volatility levels → risk guidance

- [ ] 0.5 Checkpoint: Architecture documented
  - [ ] 0.5.1 API integration plan clear
  - [ ] 0.5.2 Frontend component structure defined
  - [ ] 0.5.3 Narrative generation approach validated
  - **PROCEED AUTOMATICALLY** unless major architectural concerns

**Expected Outcomes**:
- Complete API surface map
- Jargon mapping catalog (20+ terms)
- Narrative template examples (5-10 scenarios)
- Component integration plan

---

### 1.0 Backend: Narrative Generation System

**Goal**: Create market conditions narrative generator using existing patterns

- [ ] 1.1 Create narrative generator module
  - [ ] 1.1.1 Create `backend/app/market/narrative_generator.py`
  - [ ] 1.1.2 Define narrative template structure:
    ```python
    MARKET_NARRATIVE_TEMPLATES = {
        # Overall sentiment
        "very_bullish": "Markets are very bullish today (Health: {health_score}/100, F&G: {fg_score}/100).",
        "bullish": "Markets are healthy today (Health: {health_score}/100, F&G: {fg_score}/100).",
        "neutral": "Markets are balanced today (Health: {health_score}/100, F&G: {fg_score}/100).",
        "bearish": "Markets are cautious today (Health: {health_score}/100, F&G: {fg_score}/100).",
        "very_bearish": "Markets are fearful today (Health: {health_score}/100, F&G: {fg_score}/100).",

        # Volatility context
        "low_volatility": "Low volatility shows investor confidence.",
        "normal_volatility": "Normal volatility levels.",
        "high_volatility": "High volatility signals uncertainty.",

        # Sector rotation
        "tech_leading": "Technology and growth sectors are leading.",
        "defensive_leading": "Defensive sectors like Utilities are leading.",
        "broad_strength": "Strength is broad across sectors.",

        # Recommendations
        "stay_invested": "Good time to stay invested.",
        "selective": "Be selective with new positions.",
        "defensive": "Consider defensive positions.",
        "wait": "Wait for better opportunities.",
    }
    ```
  - [ ] 1.1.3 Implement `generate_market_narrative()` function:
    - Input: health_score, fg_score, vix_price, sector_signals
    - Output: 3-4 sentence actionable narrative
  - [ ] 1.1.4 Add unit tests for narrative generation
    - Test all score combinations
    - Test sector rotation scenarios
    - Test edge cases (missing data)

- [ ] 1.2 Create plain-language mapping module
  - [ ] 1.2.1 Create `backend/app/market/plain_language.py`
  - [ ] 1.2.2 Define indicator mappings:
    ```python
    INDICATOR_LABELS = {
        "vix": {
            "label": "Market Volatility",
            "short": "Volatility",
            "tooltip": "Measures how much stocks are bouncing around. Low = calm, High = choppy.",
        },
        "sp500": {
            "label": "S&P 500 Level",
            "short": "S&P 500",
            "tooltip": "The main US stock market index. Higher = stocks doing well.",
        },
        "tnx": {
            "label": "Bond Yields",
            "short": "10Y Yield",
            "tooltip": "Interest rates on safe government bonds. Higher = more competition for stocks.",
        },
        "dxy": {
            "label": "Dollar Strength",
            "short": "Dollar",
            "tooltip": "How strong the US dollar is. Strong dollar can pressure international stocks.",
        },
    }
    ```
  - [ ] 1.2.3 Define sector mappings:
    ```python
    SECTOR_LABELS = {
        "XLK": {
            "name": "Technology",
            "description": "Apple, Microsoft, NVIDIA, software companies",
        },
        "XLF": {
            "name": "Financials",
            "description": "Banks, investment firms, insurance companies",
        },
        # ... all 11 sectors
    }
    ```
  - [ ] 1.2.4 Add helper functions:
    - `get_indicator_label(symbol: str) -> dict`
    - `get_sector_label(symbol: str) -> dict`

- [ ] 1.3 Integrate narrative into market conditions API
  - [ ] 1.3.1 Update `backend/app/api/market.py`
  - [ ] 1.3.2 Add narrative field to `MarketConditionsResponse`:
    ```python
    class MarketConditionsResponse(BaseModel):
        narrative: str = Field(..., description="Plain-language market summary")
        # ... existing fields
    ```
  - [ ] 1.3.3 Generate narrative in `get_market_conditions()`:
    - Fetch Fear & Greed score from `/api/market/fng`
    - Pass health + F&G + indicators to narrative generator
    - Return narrative in response
  - [ ] 1.3.4 Add plain-language labels to response:
    ```python
    class IndicatorData(BaseModel):
        value: float
        label: str  # "Market Volatility"
        short_label: str  # "Volatility"
        tooltip: str  # Educational description
    ```

- [ ] 1.4 Verification & Testing
  - [ ] 1.4.1 Run unit tests for narrative generator
  - [ ] 1.4.2 Test API endpoint manually:
    - `curl http://localhost:8000/api/market/conditions`
    - Verify narrative field present
    - Verify plain-language labels present
  - [ ] 1.4.3 Test various market scenarios:
    - High VIX + low S&P → bearish narrative
    - Low VIX + high S&P → bullish narrative
    - Mixed signals → balanced narrative
  - [ ] 1.4.4 Run pytest suite: `cd backend && pytest tests/`

**Success Criteria**:
- ✅ Narrative generator module created
- ✅ Plain-language mappings comprehensive (15+ terms)
- ✅ API returns narrative + labels
- ✅ All tests passing

---

### 2.0 Backend: Unified Market Intelligence Endpoint

**Goal**: Create single endpoint returning Market Health + Fear & Greed + Narrative

- [ ] 2.1 Design unified response model
  - [ ] 2.1.1 Create `backend/app/models/market_intelligence.py`:
    ```python
    class MarketIntelligenceResponse(BaseModel):
        # Narrative (top of UI)
        narrative: str

        # Dual scoring
        market_health: MarketHealthScore  # Existing model
        fear_greed: FearGreedReading      # Existing model

        # Key indicators (4)
        indicators: dict[str, EnrichedIndicator]  # VIX, SP500, TNX, DXY with labels

        # Sector rotation (grouped)
        sector_rotation: SectorRotationSummary

        # Metadata
        last_updated: str
    ```
  - [ ] 2.1.2 Define `EnrichedIndicator`:
    ```python
    class EnrichedIndicator(BaseModel):
        value: float
        change_pct: float | None
        label: str           # "Market Volatility"
        short_label: str     # "Volatility"
        tooltip: str         # Educational description
        signal: str          # "Bullish" | "Neutral" | "Bearish"
        emoji: str           # "🟢" | "🟡" | "🔴"
    ```
  - [ ] 2.1.3 Define `SectorRotationSummary`:
    ```python
    class SectorRotationSummary(BaseModel):
        leading: list[SectorInfo]   # Top performers
        neutral: list[SectorInfo]   # Middle pack
        lagging: list[SectorInfo]   # Worst performers
        leading_count: int
        neutral_count: int
        lagging_count: int
    ```

- [ ] 2.2 Create unified endpoint
  - [ ] 2.2.1 Add route to `backend/app/api/market.py`:
    ```python
    @router.get("/intelligence", response_model=MarketIntelligenceResponse)
    async def get_market_intelligence() -> MarketIntelligenceResponse:
        """Get unified market intelligence with narrative."""
    ```
  - [ ] 2.2.2 Implement endpoint logic:
    - Fetch market health (existing logic)
    - Fetch Fear & Greed score (call F&G service)
    - Fetch sector data (existing logic)
    - Group sectors into Leading/Neutral/Lagging (top 33%, middle 34%, bottom 33%)
    - Generate narrative (call narrative generator)
    - Enrich indicators with plain-language labels
    - Return unified response
  - [ ] 2.2.3 Add error handling:
    - Graceful degradation if F&G unavailable
    - Default narrative if generation fails
    - Fallback labels if mappings missing

- [ ] 2.3 Testing & Verification
  - [ ] 2.3.1 Create integration test:
    - `backend/tests/integration/api/test_api_market_intelligence.py`
  - [ ] 2.3.2 Test endpoint with various scenarios:
    - All data available → full response
    - F&G unavailable → graceful degradation
    - Sector data missing → empty rotation summary
  - [ ] 2.3.3 Verify response structure matches TypeScript types
  - [ ] 2.3.4 Run full test suite: `cd backend && pytest tests/ -v`

- [ ] 2.4 Documentation
  - [ ] 2.4.1 Update `docs/core/API_REFERENCE.md`:
    - Add `/api/market/intelligence` endpoint
    - Document response model
    - Add example responses
  - [ ] 2.4.2 Add JSDoc comments to TypeScript types

**Success Criteria**:
- ✅ New `/api/market/intelligence` endpoint working
- ✅ Returns Market Health + Fear & Greed + Narrative
- ✅ Sectors grouped into 3 categories
- ✅ All indicators have plain-language labels
- ✅ Integration tests passing

---

### 3.0 Frontend: Tooltip Component System

**Goal**: Create reusable tooltip component for educational explanations

- [ ] 3.1 Create base tooltip component
  - [ ] 3.1.1 Create `frontend/components/ui/info-tooltip.tsx`:
    ```typescript
    interface InfoTooltipProps {
      content: string;
      side?: "top" | "right" | "bottom" | "left";
      className?: string;
    }

    export function InfoTooltip({ content, side = "top", className }: InfoTooltipProps) {
      // Uses shadcn/ui Tooltip component
      // Shows info icon (ℹ️) that reveals explanation on hover
    }
    ```
  - [ ] 3.1.2 Style tooltip:
    - Max width: 250px
    - Dark background with light text
    - Smooth fade-in animation
    - Mobile-friendly (click to reveal)
  - [ ] 3.1.3 Add accessibility:
    - ARIA labels
    - Keyboard navigation (Tab to focus, Enter to toggle)

- [ ] 3.2 Create labeled indicator component
  - [ ] 3.2.1 Create `frontend/components/market/LabeledIndicator.tsx`:
    ```typescript
    interface LabeledIndicatorProps {
      label: string;        // "Market Volatility"
      value: string;        // "15.2"
      tooltip?: string;     // Educational description
      signal: "bullish" | "neutral" | "bearish";
      emoji?: string;       // "🟢"
    }
    ```
  - [ ] 3.2.2 Implement component:
    - Label with optional tooltip icon
    - Large value display
    - Signal indicator (emoji or color)
    - Responsive sizing

- [ ] 3.3 Testing
  - [ ] 3.3.1 Create Storybook stories (if available) or manual test page
  - [ ] 3.3.2 Test tooltip positioning (all 4 sides)
  - [ ] 3.3.3 Test mobile behavior (click vs hover)
  - [ ] 3.3.4 Test accessibility (keyboard navigation)

**Success Criteria**:
- ✅ InfoTooltip component working
- ✅ LabeledIndicator component working
- ✅ Tooltips accessible on desktop + mobile
- ✅ Consistent styling with design system

---

### 4.0 Frontend: Market Intelligence Component

**Goal**: Create consolidated market intelligence view matching user specs

- [ ] 4.1 Create API client and hook
  - [ ] 4.1.1 Update `frontend/lib/api/market.ts`:
    ```typescript
    export async function fetchMarketIntelligence(): Promise<MarketIntelligenceResponse> {
      const response = await fetch(`${API_BASE}/api/market/intelligence`);
      if (!response.ok) throw new Error("Failed to fetch market intelligence");
      return response.json();
    }
    ```
  - [ ] 4.1.2 Create `frontend/lib/hooks/useMarketIntelligence.ts`:
    ```typescript
    export function useMarketIntelligence() {
      return useQuery({
        queryKey: ["market", "intelligence"],
        queryFn: fetchMarketIntelligence,
        staleTime: 1000 * 60 * 15, // 15 minutes
        refetchInterval: 1000 * 60 * 15,
      });
    }
    ```
  - [ ] 4.1.3 Define TypeScript types:
    ```typescript
    interface MarketIntelligenceResponse {
      narrative: string;
      market_health: MarketHealthScore;
      fear_greed: FearGreedReading;
      indicators: Record<string, EnrichedIndicator>;
      sector_rotation: SectorRotationSummary;
      last_updated: string;
    }
    ```

- [ ] 4.2 Create narrative display component
  - [ ] 4.2.1 Create `frontend/components/market/MarketNarrative.tsx`:
    ```typescript
    interface MarketNarrativeProps {
      narrative: string;
      healthScore: number;
      fearGreedScore: number;
    }
    ```
  - [ ] 4.2.2 Implement component:
    - Large, prominent text (text-lg or text-xl)
    - Icon/emoji based on sentiment
    - Highlight scores with color coding
    - Responsive padding and sizing

- [ ] 4.3 Create sector rotation summary component
  - [ ] 4.3.1 Create `frontend/components/market/SectorRotationSummary.tsx`:
    ```typescript
    interface SectorRotationSummaryProps {
      rotation: SectorRotationSummary;
    }
    ```
  - [ ] 4.3.2 Implement grouped display:
    - 🟢 Leading (X): List top 3 sectors
    - 🟡 Neutral (X): Show count, collapse list
    - 🔴 Lagging (X): List bottom 3 sectors
    - "View All Sectors →" link (optional expansion)
  - [ ] 4.3.3 Add tooltips for sector descriptions

- [ ] 4.4 Redesign MarketConditions component
  - [ ] 4.4.1 Update `frontend/components/portfolio/MarketConditions.tsx`
  - [ ] 4.4.2 Implement new layout (split-view):
    ```tsx
    <Card>
      {/* Top: Narrative */}
      <MarketNarrative narrative={...} healthScore={...} fearGreedScore={...} />

      {/* Split View */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Key Indicators */}
        <div>
          <h3>Key Indicators</h3>
          <div className="space-y-4">
            <LabeledIndicator label="Market Health" value={...} />
            <LabeledIndicator label="Fear & Greed Index" value={...} />
            <LabeledIndicator label="Market Volatility" value={...} tooltip={...} />
            <LabeledIndicator label="S&P 500 Level" value={...} tooltip={...} />
            <LabeledIndicator label="Bond Yields" value={...} tooltip={...} />
            <LabeledIndicator label="Dollar Strength" value={...} tooltip={...} />
          </div>
        </div>

        {/* Right: Sector Rotation */}
        <div>
          <h3>Sector Rotation</h3>
          <SectorRotationSummary rotation={...} />
        </div>
      </div>
    </Card>
    ```
  - [ ] 4.4.3 Remove expandable section (no longer needed)
  - [ ] 4.4.4 Replace all technical jargon with plain-language labels
  - [ ] 4.4.5 Add tooltips to all indicators

- [ ] 4.5 Testing & Refinement
  - [ ] 4.5.1 Test responsive layout:
    - Desktop (2 columns)
    - Tablet (stacked)
    - Mobile (single column)
  - [ ] 4.5.2 Test loading states (skeleton loaders)
  - [ ] 4.5.3 Test error states (graceful degradation)
  - [ ] 4.5.4 Verify tooltip behavior on all devices
  - [ ] 4.5.5 Visual polish:
    - Spacing and padding
    - Color consistency
    - Typography hierarchy

**Success Criteria**:
- ✅ New MarketConditions component matches spec
- ✅ Narrative displayed prominently at top
- ✅ Dual health scores shown (Market Health + Fear & Greed)
- ✅ 4 indicators with plain-language labels + tooltips
- ✅ Sectors grouped into 3 categories (Leading/Neutral/Lagging)
- ✅ Zero technical jargon visible
- ✅ Split-view layout on desktop
- ✅ Fully responsive

---

### 5.0 Integration & Polish

**Goal**: Connect all pieces and ensure production-ready quality

- [ ] 5.1 Remove redundant code
  - [ ] 5.1.1 Remove old expandable section from MarketConditions
  - [ ] 5.1.2 Clean up unused imports
  - [ ] 5.1.3 Remove duplicate data fetching logic
  - [ ] 5.1.4 Archive old component version (if needed for reference)

- [ ] 5.2 Update dashboard integration
  - [ ] 5.2.1 Verify MarketConditions renders on dashboard (`frontend/app/page.tsx`)
  - [ ] 5.2.2 Ensure Fear & Greed data is fetched (new endpoint)
  - [ ] 5.2.3 Test cache invalidation (15-min refetch interval)

- [ ] 5.3 Add sector detail view (optional expansion)
  - [ ] 5.3.1 Create "View All Sectors" link
  - [ ] 5.3.2 Create modal or expandable section with full 11-sector breakdown
  - [ ] 5.3.3 Show sector details:
    - Name (plain language)
    - Description (what companies)
    - Current price
    - Daily change %
    - Signal (Leading/Neutral/Lagging)
  - [ ] 5.3.4 Add search/filter by sector name

- [ ] 5.4 Performance optimization
  - [ ] 5.4.1 Verify API caching (15-min TTL)
  - [ ] 5.4.2 Optimize React Query settings:
    - staleTime: 15 minutes
    - refetchInterval: 15 minutes
    - refetchOnWindowFocus: false (data doesn't change that fast)
  - [ ] 5.4.3 Lazy load sector detail modal (if implemented)

- [ ] 5.5 Accessibility audit
  - [ ] 5.5.1 Add ARIA labels to all interactive elements
  - [ ] 5.5.2 Ensure keyboard navigation works (tooltips, expansion)
  - [ ] 5.5.3 Test screen reader compatibility
  - [ ] 5.5.4 Verify color contrast (WCAG AA)

- [ ] 5.6 Documentation updates
  - [ ] 5.6.1 Update `docs/core/ARCHITECTURE.md`:
    - Document narrative generation system
    - Document plain-language mapping strategy
    - Update Market Conditions section
  - [ ] 5.6.2 Update `docs/core/API_REFERENCE.md`:
    - Document `/api/market/intelligence` endpoint
  - [ ] 5.6.3 Add inline code comments for complex logic
  - [ ] 5.6.4 Update CHANGELOG or version notes

**Success Criteria**:
- ✅ All redundant code removed
- ✅ Dashboard integration working
- ✅ Performance optimized (no unnecessary fetches)
- ✅ Accessibility compliant
- ✅ Documentation updated

---

### 6.0 Testing & Quality Assurance

**Goal**: Comprehensive testing before deployment

- [ ] 6.1 Backend testing
  - [ ] 6.1.1 Run full test suite: `cd backend && pytest tests/ -v`
  - [ ] 6.1.2 Run linting: `~/portfolio-ai/scripts/lint.sh`
  - [ ] 6.1.3 Verify type checking: `cd backend && mypy app/`
  - [ ] 6.1.4 Test API endpoints manually:
    - `GET /api/market/intelligence` (new)
    - `GET /api/market/conditions` (existing, still works)
    - `GET /api/market/fng` (existing, still works)

- [ ] 6.2 Frontend testing
  - [ ] 6.2.1 Visual regression testing:
    - Compare old vs new MarketConditions side-by-side
    - Verify narrative makes sense
    - Check sector grouping is correct
  - [ ] 6.2.2 Test responsive layouts:
    - Desktop (1920x1080)
    - Tablet (768x1024)
    - Mobile (375x667)
  - [ ] 6.2.3 Test loading states (slow network simulation)
  - [ ] 6.2.4 Test error states (backend down, API errors)
  - [ ] 6.2.5 Run frontend tests: `cd frontend && npm test`

- [ ] 6.3 Integration testing
  - [ ] 6.3.1 Test full user flow:
    - Load dashboard
    - Verify narrative appears
    - Verify dual scores shown
    - Verify sector rotation shown
    - Hover tooltips
    - Click "View All Sectors" (if implemented)
  - [ ] 6.3.2 Test data accuracy:
    - Compare narrative to actual market data
    - Verify sector grouping is correct (compare to raw data)
    - Verify indicator values match sources
  - [ ] 6.3.3 Test cache behavior:
    - First load (fresh fetch)
    - Reload within 15 min (cache hit)
    - Reload after 15 min (cache miss, refetch)

- [ ] 6.4 User acceptance testing
  - [ ] 6.4.1 Show to user (you!)
  - [ ] 6.4.2 Verify narrative clarity (no jargon)
  - [ ] 6.4.3 Verify tooltips are helpful
  - [ ] 6.4.4 Verify sector grouping makes sense
  - [ ] 6.4.5 Verify recommendations are actionable

**Success Criteria**:
- ✅ All 508 tests passing
- ✅ Linting passes (ruff + mypy)
- ✅ Visual design approved
- ✅ User acceptance achieved
- ✅ No regressions in other features

---

### 7.0 Service Restart & Deployment

**Goal**: Deploy changes and verify production stability

- [ ] 7.1 Pre-deployment checklist
  - [ ] 7.1.1 Commit all changes with descriptive messages
  - [ ] 7.1.2 Run `~/portfolio-ai/scripts/lint.sh` (final check)
  - [ ] 7.1.3 Run `cd backend && pytest tests/` (final check)
  - [ ] 7.1.4 Build frontend: `cd frontend && npm run build`
  - [ ] 7.1.5 Verify no console errors in build

- [ ] 7.2 Service restart protocol (MANDATORY)
  - [ ] 7.2.1 Restart all services: `bash ~/portfolio-ai/scripts/restart.sh`
  - [ ] 7.2.2 Verify service start times AFTER changes:
    - `systemctl show portfolio-backend -p ActiveEnterTimestamp`
    - `systemctl show portfolio-frontend -p ActiveEnterTimestamp`
  - [ ] 7.2.3 Check service health: `bash ~/portfolio-ai/scripts/status.sh`
  - [ ] 7.2.4 Monitor logs for errors:
    - `tail -f /var/log/portfolio-ai/backend-error.log`
    - `tail -f /var/log/portfolio-ai/frontend-error.log`

- [ ] 7.3 Post-deployment verification
  - [ ] 7.3.1 Test new endpoint in production:
    - `curl http://192.168.8.233:8000/api/market/intelligence`
  - [ ] 7.3.2 Load dashboard in browser
  - [ ] 7.3.3 Verify narrative appears correctly
  - [ ] 7.3.4 Verify dual scores shown
  - [ ] 7.3.5 Verify sectors grouped correctly
  - [ ] 7.3.6 Verify tooltips work
  - [ ] 7.3.7 Test on mobile device (if available)

- [ ] 7.4 Monitoring (first 24 hours)
  - [ ] 7.4.1 Monitor API response times (should be <500ms)
  - [ ] 7.4.2 Monitor error rates (should be 0%)
  - [ ] 7.4.3 Monitor cache hit rate (should be >80% after warmup)
  - [ ] 7.4.4 Monitor narrative quality (read samples for accuracy)

**Success Criteria**:
- ✅ Services restarted successfully
- ✅ Dashboard loads without errors
- ✅ New market intelligence UI visible
- ✅ No performance regressions
- ✅ No error spikes in logs

---

## Verification Checklist (MANDATORY before "COMPLETE ✅")

**Backend**:
- [ ] `/api/market/intelligence` endpoint working
- [ ] Narrative generation producing sensible output
- [ ] Plain-language labels comprehensive (15+ terms)
- [ ] All tests passing (508 total)
- [ ] Linting passes (ruff + mypy)
- [ ] Type safety maintained (mypy --strict)

**Frontend**:
- [ ] MarketConditions component redesigned
- [ ] Narrative displayed at top
- [ ] Dual scores shown (Market Health + Fear & Greed)
- [ ] 4 indicators with plain-language labels + tooltips
- [ ] Sectors grouped into Leading/Neutral/Lagging
- [ ] Zero technical jargon visible
- [ ] Split-view layout working
- [ ] Fully responsive (desktop, tablet, mobile)
- [ ] Tooltips working on all devices

**Quality**:
- [ ] No redundant data displayed
- [ ] No expandable section needed
- [ ] Fear & Greed Index now visible on dashboard
- [ ] Narrative is actionable (has recommendations)
- [ ] All jargon replaced with plain language
- [ ] Educational tooltips helpful

**Documentation**:
- [ ] ARCHITECTURE.md updated
- [ ] API_REFERENCE.md updated
- [ ] Code comments added for complex logic

**Production**:
- [ ] Services restarted successfully
- [ ] Dashboard loads without errors
- [ ] User acceptance achieved

---

## Success Metrics

### Baseline (Current)
```
❌ Redundant data shown twice (main + expandable)
❌ Fear & Greed Index exists but not shown
❌ Technical jargon everywhere (VIX, DXY, TNX, XLK, etc.)
❌ Sectors hidden behind expansion (11 ETFs)
❌ No narrative explaining market conditions
❌ No actionable recommendations
```

### Target (After)
```
✅ Single consolidated view (no redundancy)
✅ Both Market Health AND Fear & Greed visible
✅ All jargon replaced with plain language
✅ Sectors grouped (Leading/Neutral/Lagging) - visible immediately
✅ Actionable narrative at top (3-4 sentences)
✅ Educational tooltips for all terms
✅ Split-view layout (indicators left, sectors right)
✅ Fully responsive design
```

---

## Estimated Effort Breakdown

| Task | Estimated Time | Priority |
|------|----------------|----------|
| 0.0 Scope Discovery | 1-2 hours | CRITICAL |
| 1.0 Backend Narrative System | 2-3 hours | HIGH |
| 2.0 Unified API Endpoint | 2-3 hours | HIGH |
| 3.0 Frontend Tooltip System | 1-2 hours | MEDIUM |
| 4.0 Market Intelligence UI | 3-4 hours | HIGH |
| 5.0 Integration & Polish | 1-2 hours | MEDIUM |
| 6.0 Testing & QA | 1-2 hours | HIGH |
| 7.0 Deployment | 1 hour | CRITICAL |
| **TOTAL** | **12-19 hours** | - |

**Recommended approach**: Work through tasks sequentially (0 → 7). Backend-first ensures API is ready before frontend work begins.

---

## Notes for Implementation

### Plain-Language Mapping Examples

**Indicators**:
- "VIX" → "Market Volatility" (tooltip: "Measures how much stocks bounce around")
- "S&P 500" → "S&P 500 Level" (tooltip: "The main US stock market index")
- "10Y Treasury" → "Bond Yields" (tooltip: "Interest rates on safe government bonds")
- "DXY" → "Dollar Strength" (tooltip: "How strong the US dollar is")

**Sectors**:
- "XLK" → "Technology" (tooltip: "Apple, Microsoft, NVIDIA, software companies")
- "XLF" → "Financials" (tooltip: "Banks, investment firms, insurance companies")
- "XLE" → "Energy" (tooltip: "Oil and gas companies like Exxon, Chevron")
- "XLV" → "Healthcare" (tooltip: "Hospitals, drug makers, medical devices")
- "XLY" → "Consumer Discretionary" (tooltip: "Retailers, restaurants, entertainment")
- "XLP" → "Consumer Staples" (tooltip: "Groceries, household goods, basic needs")
- "XLI" → "Industrials" (tooltip: "Manufacturing, construction, aerospace")
- "XLU" → "Utilities" (tooltip: "Electric, water, gas companies")
- "XLRE" → "Real Estate" (tooltip: "Property companies, REITs")
- "XLB" → "Materials" (tooltip: "Mining, chemicals, raw materials")
- "XLC" → "Communication Services" (tooltip: "Telecom, media, Google, Meta")

### Narrative Examples

**Very Bullish (Health: 75, F&G: 80)**:
"Markets are very bullish today (Health: 75/100, F&G: 80/100). Low volatility and strong S&P levels favor staying invested. Technology and Financials are leading sectors. Dollar strength may pressure international stocks."

**Bullish (Health: 65, F&G: 68)**:
"Markets are healthy today (Health: 65/100, F&G: 68/100). Normal volatility levels and moderate bond yields support stocks. Broad strength across sectors is a positive sign. Good time to stay invested."

**Neutral (Health: 50, F&G: 52)**:
"Markets are balanced today (Health: 50/100, F&G: 52/100). Mixed signals with some volatility present. Be selective with new positions and focus on quality names."

**Bearish (Health: 35, F&G: 30)**:
"Markets are cautious today (Health: 35/100, F&G: 30/100). Elevated volatility signals uncertainty. Defensive sectors like Utilities are leading. Consider defensive positions or wait for better opportunities."

**Very Bearish (Health: 20, F&G: 18)**:
"Markets are fearful today (Health: 20/100, F&G: 18/100). High volatility and weak S&P levels indicate risk. Preserve capital and wait for better entry points. This could be a buying opportunity for patient investors."

### Sector Grouping Logic

**Leading** (Top 33%):
- Daily change % in top third of all sectors
- Signal: "Leading" 🟢
- Show sector names (no symbols)

**Neutral** (Middle 34%):
- Daily change % in middle third
- Signal: "Neutral" 🟡
- Show count only, collapse list

**Lagging** (Bottom 33%):
- Daily change % in bottom third
- Signal: "Lagging" 🔴
- Show sector names (no symbols)

---

## Handoff Instructions

When complete or blocked, document:
- [ ] Tasks completed (with commit SHAs)
- [ ] Tasks remaining (if blocked)
- [ ] Quality metrics (tests passing, linting clean)
- [ ] Any architectural decisions made
- [ ] Screenshots of new UI (before/after)
- [ ] User acceptance status

---

**Version**: 1.0
**Created**: 2025-11-11
**Updated**: 2025-11-11
