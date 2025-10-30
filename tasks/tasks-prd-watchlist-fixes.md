# Task List: Watchlist Page Fixes - Timezone Display and Sparkline Data

**PRD**: `prd-watchlist-fixes.md`
**Status**: Ready for Implementation
**Completion**: 0% (Not started)
**Effort to Complete**: Medium
**Last Updated**: 2025-10-30

**Note on Effort Levels**:
- **Low**: 1-2 hours of straightforward work
- **Medium**: Half day of work with some complexity
- **High**: Full day or more, significant complexity

---

## Summary

**✅ COMPLETE:**
- (None yet)

**🔄 IN PROGRESS:**
- (Not started)

**⚠️ NEXT STEPS:**
1. Begin with Task 1.0
2. Follow checklist sequentially
3. Update this summary as work progresses

**EFFORT TO COMPLETE:** Medium

---

## Relevant Files

### Files to Create (2 new files)

- `backend/migrations/003_add_display_timezone.sql` (~20 lines) - Migration to add display_timezone column to user_preferences
- `frontend/components/watchlist/SparklineWithHistory.tsx` (~80 lines) - Component to fetch and display real historical score data

### Files to Update (4 files)

- `backend/app/api/preferences.py` - Add display_timezone field to Pydantic models and CRUD operations
- `frontend/components/watchlist/WatchlistTable.tsx` - Replace hardcoded sparkline, add timezone-aware formatDate
- `frontend/app/settings/page.tsx` - Add timezone selector in Display Preferences section
- `frontend/lib/api/preferences.ts` - Add display_timezone to TypeScript types

### Notes

- This project uses DuckDB with SQL migrations in `backend/migrations/` directory
- Migration files follow pattern: `NNN_description.sql` (e.g., `003_add_display_timezone.sql`)
- Existing migrations: 001 (schema_migrations), 002 (watchlist_preferences)
- Backend uses Pydantic for API models with strict type validation
- Frontend uses React Query for data fetching with automatic caching
- Existing `useScoreHistory` hook and `fetchScoreHistory` API confirmed working
- Use `pytest tests/` to run all tests
- Use `mypy app/ --strict` to verify type safety
- Use `scripts/lint.sh` to run linting and formatting checks

---

## Tasks

- [ ] 1.0 Add Timezone Preference to Backend Database and API
- [ ] 2.0 Create SparklineWithHistory Component with Real Data
- [ ] 3.0 Update WatchlistTable to Use Sparkline and Timezone
- [ ] 4.0 Add Timezone Selector to Settings Page
- [ ] 5.0 Verification and Integration Testing

---

## High-Level Tasks Generated

I have generated the 5 high-level tasks based on the PRD. These cover:

1. **Backend timezone infrastructure** - Database migration + API models + validation
2. **Sparkline component** - New React component to fetch/display real historical data
3. **WatchlistTable updates** - Integrate sparkline + timezone-aware formatting
4. **Settings UI** - Add timezone selector dropdown
5. **Testing & verification** - End-to-end integration tests

**Ready to generate the sub-tasks?** Respond with **'Go'** to proceed with detailed breakdown (2-5 minute tasks each).
