# Task List: Settings & Status Standardization

**Source**: User request via /task_it
**Complexity**: Complex
**Effort**: HIGH
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-13 11:41

---

## Summary

**Goal**: Fully align the Status and Settings pages with the new UI system (PageHeader, SectionCard, ExpandableCard) while eliminating redundant data and ensuring DRY logic for collapsible cards, summaries, and defaults.
**Approach**: Inventory every card/section in both pages, centralize collapse/summary helpers, reorganize layouts per the user's order, and remove outdated data while backfilling visual tests.
**Scope Discovery**: Required – multiple shared components and pages must be audited for duplicated collapse logic and legacy defaults.

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [x] 0.1 Run Explore subagent in "very thorough" mode
  - Pattern: Collapse/expand controls, status/settings section headers, redundant summary metrics
  - Goal: Catalogue every component implementing custom expanders or hard-coded defaults so they can be consolidated
  - Output: Identified files: `frontend/app/status/page.tsx`, `frontend/components/status/{ExpandableCard,DataSourcesCard,APIQuotasCard,TableFreshnessCard,SourceQualityCard,MLModelCard,APIKeysCard,MaintenanceCard,LogsCard}.tsx`, `frontend/app/settings/page.tsx`, `frontend/components/settings/{ProfileSelector.tsx,sections/TradingRiskSettings.tsx,sections/DisplaySettings.tsx,sections/WatchlistSettingsSection.tsx,DEFAULTS.ts}`
- [x] 0.2 Update this task list with ALL discovered files
  - New subtasks cover Status layout/expander refactors plus Settings DRY helpers & section wrappers
  - Additional note: `ExpandableCard` needs summary/badge support shared by every collapsed card
- [x] 0.3 Checkpoint: Confirm scope before proceeding
  - Total files affected: 13-15 (depending on helper extraction)
  - Estimated effort: 6-8 hours (UI refactor + tests + screenshots)
  - Architectural concerns: Ensure one Expandable primitive stays client-safe and server components remain untouched

### 1.0 Status Page – Structural Standardization

- [x] 1.1 Rename "Live Overview" to "Overview" and nest Services + System Resources cards there
- [x] 1.2 Remove redundant "System Overview" block and summary metrics (Services 5/5, Healthy daemons, Coverage, etc.)
- [x] 1.3 Implement standardized sections in required order: Overview, Data Pipelines, Scheduled Tasks, News Sources, Maintenance, Unified Logging
- [x] 1.4 Move Celery/Beat cards under new Scheduled Tasks section; Database Maintenance under Maintenance; Unified Logging section last
- [x] 1.5 Combine News Health, News Source Quality, and Article Quality into News Sources section, enforcing collapse-by-default behavior

### 2.0 Status Page – DRY Expandable Cards

- [x] 2.1 Build/extend a single `ExpandableCard` helper that supports summary props (title, status counts, badges)
- [x] 2.2 Refactor Data Sources, Data Freshness, API Quotas, News Health, Article Quality ML Model, API Key Configuration, Unified Logging, and Maintenance cards to use the shared helper
- [x] 2.3 Ensure every card is collapsed by default with concise summary text showing health counts so expansions are optional
- [x] 2.4 Update Data Freshness card to inline freshness thresholds (<1x interval, <2x, >2x) without separate legend; reuse same helper
- [x] 2.5 Delete old/duplicate expand button styles and replace with standardized chevron component

### 3.0 Settings Page Modernization

- [x] 3.1 Introduce shared defaults/utilities (e.g., `DEFAULTS.ts`, merge helpers) to eliminate repeated literal weight objects
- [x] 3.2 Wrap each Settings section (Profile, Trading Risk, Display Preferences, Watchlists, API keys if present) in `SectionCard` + standardized headers
- [ ] 3.3 Apply the same collapsible pattern where sections expose large forms (e.g., Watchlist config) so they match Status behavior
- [x] 3.4 Remove obsolete or redundant settings fields/labels identified during review (legacy metrics, unused intervals)
- [x] 3.5 Ensure DRY summary/apply logic (no duplicated "has changes" calculations) using new helpers

### 4.0 Verification & Polish

- [ ] 4.1 Update unit/screenshot tests covering the reordered Status layout and collapsed cards
- [ ] 4.2 Capture final screenshots (Status + Settings) for stakeholder review
- [ ] 4.3 Run full frontend/test suite plus lint to ensure no regressions
- [ ] 4.4 Document the reusable ExpandableCard/Section pattern in `frontend/README.md`

---

## Verification

- [ ] Functional: All Status/Settings requirements satisfied; redundant data removed
- [ ] Tests: `pnpm test` (or equivalent) passes; screenshots updated
- [ ] Quality: `pnpm lint`/`tsc` clean; no duplicated collapse logic remains (`rg -l "Expand"` limited to shared helper)
- [ ] Docs: README + task file updated with actual scope notes
