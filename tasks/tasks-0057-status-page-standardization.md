# Task List: Status Page Standardization & Collapse Framework

**Source**: Frontend status UI refactor request (2025-11-13)
**Complexity**: High
**Effort**: HIGH (6-8 hours, 15+ files)
**Environment**: Local Dev
**Created**: 2025-11-13

---

## Summary

**Goal**: Bring the Status experience in line with the shared Portfolio AI layout system, introduce a reusable collapse/summary pattern, and reorganize sections so top-level information is surfaced first.

**Approach**: Create a single `ExpandableCard` helper, refactor every verbose status card to use it, collapse targeted sections by default with consistent summaries, and reorder the page into clear groupings (Overview → Data Pipelines → Scheduled Tasks → News Sources → Maintenance → Unified Logging).

**Scope Discovery**: Required – changes span many cards, shared components, and layout glue.

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [x] 0.1 Run Explore subagent in "very thorough" mode
  - Pattern: Status page sections, cards using collapsible logic, summary/chevron buttons, layout ordering, TableFreshness legends
  - Goal: Identify every component affected (status page + cards referenced inside)
- [x] 0.2 Update this task list with the precise file list + estimates
  - Files confirmed so far: `frontend/app/status/page.tsx`, `frontend/components/status/{ExpandableCard.tsx,DataSourcesCard.tsx,TableFreshnessCard.tsx,MaintenanceCard.tsx,LogsCard.tsx,SourceQualityCard.tsx,MLModelCard.tsx,APIKeysCard.tsx,QueueDepthCard.tsx,BeatScheduleCard.tsx,ServiceCard.tsx,ResourceCard.tsx}`
- [x] 0.3 Checkpoint: lock scope before coding (files count, complexity, concerns)

### 1.0 Shared Expandable Card Primitive

- [x] 1.1 Design `ExpandableCard` component (title, description, summary, actions, default collapsed)
- [x] 1.2 Replace ad-hoc collapsible logic in Maintenance, Logs, Data Sources, TableFreshness, SourceQuality, MLModel, APIKeys, News cards with `ExpandableCard`
- [x] 1.3 Ensure a single chevron/toggle style is used globally

### 2.0 Status Page Layout Reorganization

- [x] 2.1 Replace bespoke header with `PageHeader` + action slot and remove duplicate badges
- [x] 2.2 Reorder sections: Overview (includes Services grid + System resources), Data Pipelines (Data Sources, Data Freshness, API Keys), Scheduled Tasks (Celery + Beat), News Sources (News Health + News Quality + Article Quality ML), Maintenance, Unified Logging
- [x] 2.3 Remove redundant `SystemStatusCard` duplication and integrate into Overview section cards

### 3.0 Card Content Adjustments

- [x] 3.1 TableFreshness: apply shared collapse, move legend rules into header summary, keep list concise
- [x] 3.2 Data Sources / News Quality / ML Model / API Keys: collapse by default with quantitative summary lines
- [x] 3.3 Scheduled Tasks + Maintenance: ensure summary strings (worker status, last run) appear when collapsed

### 4.0 Verification & Tests

- [x] 4.1 Update screenshots (`status-page.png`) to capture new structure
- [x] 4.2 Extend tests (unit or Playwright) to assert the PageHeader + default-collapsed sections render as expected
- [x] 4.3 Run `npm test` (Vitest) and lint as needed

---

## Verification

- [ ] Visual parity across light/dark themes, no duplicate chevron styles
- [ ] Status page sections ordered Overview → Data Pipelines → Scheduled Tasks → News Sources → Maintenance → Unified Logging
- [ ] Each collapsed card surfaces summary text + consistent toggle controls
- [ ] Table Freshness legend simplified and moved inline
- [ ] Tests + screenshots updated, `npm test` passing
