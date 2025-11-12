# Task List: Finalize Settings Page Branch

**Source**: Cloud agent work - claude/improve-settings-page-011CUzK3ihKhm4re9cjiKCQs
**Complexity**: SIMPLE
**Effort**: LOW-MEDIUM (3-5 hours)
**Environment**: Local Dev
**Created**: 2025-11-11
**Branch**: `claude/improve-settings-page-011CUzK3ihKhm4re9cjiKCQs`
**Status**: Phase 1 & 2 complete (needs local testing + Phase 3)

---

## Summary

**Goal**: Test settings page improvements locally, verify functionality, and merge to main

**What's Already Done**:
- ✅ Phase 1: UI/UX improvements (reusable components, visual hierarchy, theme management)
- ✅ Phase 2: Profile management system (backend + frontend + database migration)
- ✅ All code committed to branch
- ✅ Comprehensive handoff documentation

**What's Left**:
- Run database migration locally
- Test all settings functionality
- Verify profile management works
- Run tests and quality checks
- Merge to main

**Why Second**: Isolated feature, no dependencies, mostly complete

---

## Tasks

### 1.0 Load Branch and Review Work

- [ ] 1.1 Checkout branch
  - `git fetch origin`
  - `git checkout claude/improve-settings-page-011CUzK3ihKhm4re9cjiKCQs`
  - `git pull origin claude/improve-settings-page-011CUzK3ihKhm4re9cjiKCQs`
- [ ] 1.2 Read handoff documentation
  - `cat SETTINGS_IMPROVEMENTS_HANDOFF.md`
  - Understand Phase 1 & 2 completions
  - Note Phase 3 items (AI agent config, notifications - deferred)
- [ ] 1.3 Review changed files
  - Frontend: 19 files (new components, refactored page)
  - Backend: 3 files (API, models, routes)
  - Migration: `backend/migrations/023_settings_profiles.sql`
  - Verify all files present

### 2.0 Database Migration

- [ ] 2.1 Review migration SQL
  - `cat backend/migrations/023_settings_profiles.sql`
  - Understand: Creates `settings_profiles` table
  - Check: No dangerous operations (DROP, CASCADE)
- [ ] 2.2 Run migration
  - `cd ~/portfolio-ai/backend && source .venv/bin/activate`
  - `python scripts/migrate.py` (or your migration command)
  - Verify: Table created successfully
- [ ] 2.3 Verify database schema
  - `psql -U portfolio_ai_user -d portfolio_ai`
  - `\d settings_profiles`
  - Check: Columns match expected schema (name, settings_json, is_active, etc.)

### 3.0 Frontend Testing

- [ ] 3.1 Install new dependencies
  - `cd ~/portfolio-ai/frontend`
  - `npm install` (installs @radix-ui/react-tooltip if not already)
  - Verify: No dependency conflicts
- [ ] 3.2 Start frontend dev server
  - `cd ~/portfolio-ai/frontend && npm run dev`
  - Wait for compilation to complete
  - Check: No TypeScript errors
- [ ] 3.3 Navigate to settings page
  - Open: `http://192.168.8.233:3000/settings`
  - Verify: Page loads without errors
  - Check: New layout with sections visible

### 4.0 UI/UX Testing (Phase 1 Features)

- [ ] 4.1 Test visual hierarchy
  - Verify: Section headers with icons (TrendingUp, Monitor, ListFilter)
  - Verify: Clean spacing and organization
  - Check: Mobile responsive (resize browser)
- [ ] 4.2 Test theme management
  - Find: Theme selector in Display Settings section
  - Test: Switch between Light/Dark/System themes
  - Verify: Theme changes immediately
  - Refresh: Theme persists after reload
- [ ] 4.3 Test tooltips
  - Hover: Over info icons next to settings
  - Verify: Contextual help appears
  - Check: Tooltips are readable and helpful
- [ ] 4.4 Test unified save bar
  - Change: Any setting value
  - Verify: Save bar appears at bottom (sticky)
  - Check: Shows "X unsaved changes"
  - Click: "Discard Changes" → settings revert
  - Change again: Click "Save Changes" → success message
- [ ] 4.5 Test toggle cards
  - Find: Trading preferences (use toggle cards instead of checkboxes)
  - Click: Toggle cards on/off
  - Verify: Visual state changes
  - Save: Changes persist

### 5.0 Profile Management Testing (Phase 2 Features)

- [ ] 5.1 Test profile selector
  - Find: Profile selector at top of page
  - Verify: Shows "Default" profile initially
  - Check: Dropdown shows available profiles
- [ ] 5.2 Test creating new profile
  - Click: "New Profile" or create profile button
  - Enter: Profile name (e.g., "Aggressive Strategy")
  - Save: New profile created
  - Verify: Profile appears in selector
- [ ] 5.3 Test switching profiles
  - Change: Some settings
  - Save: Settings to current profile
  - Switch: To different profile
  - Verify: Settings change to reflect new profile
  - Switch back: Verify original settings restored
- [ ] 5.4 Test profile isolation
  - Profile A: Set weight_price = 0.5
  - Profile B: Set weight_price = 0.8
  - Switch between: Verify weight_price changes correctly
  - Backend check: `curl http://192.168.8.233:8000/api/settings/profiles`
  - Verify: Both profiles stored with different settings
- [ ] 5.5 Test deleting profile
  - Create: Temporary test profile
  - Delete: The test profile
  - Verify: Profile removed from selector
  - Check: Cannot delete active profile or default profile

### 6.0 Backend API Testing

- [ ] 6.1 Test GET /api/settings/profiles
  - `curl http://192.168.8.233:8000/api/settings/profiles`
  - Verify: Returns list of profiles
  - Check: Each profile has id, name, is_active, settings_json
- [ ] 6.2 Test POST /api/settings/profiles (create)
  - `curl -X POST http://192.168.8.233:8000/api/settings/profiles -H "Content-Type: application/json" -d '{"name": "Test Profile", "settings_json": {}}'`
  - Verify: Returns created profile with id
- [ ] 6.3 Test PUT /api/settings/profiles/{id} (update)
  - Update existing profile settings
  - Verify: Settings saved correctly
- [ ] 6.4 Test PUT /api/settings/profiles/{id}/activate
  - Switch active profile
  - Verify: New profile becomes active, old profile is_active=false
- [ ] 6.5 Test DELETE /api/settings/profiles/{id}
  - Delete non-active profile
  - Verify: Profile deleted
  - Try: Delete active profile → should fail with error

### 7.0 Code Quality and Tests

- [ ] 7.1 Run backend tests
  - `cd ~/portfolio-ai/backend && source .venv/bin/activate`
  - `pytest tests/ -v --tb=short`
  - Target: All tests passing
  - Note: May need to add tests for new profile API endpoints
- [ ] 7.2 Run ruff linter
  - `ruff check backend/app/api/settings_profiles.py backend/app/routes/settings_profiles.py backend/app/models/settings_profile.py`
  - Fix: Any style issues
- [ ] 7.3 Run mypy type checker
  - `mypy backend/app/api/settings_profiles.py backend/app/routes/settings_profiles.py backend/app/models/settings_profile.py --strict`
  - Fix: Any type errors
- [ ] 7.4 Check frontend TypeScript
  - Frontend should compile without errors (checked in step 3.2)
  - If issues: Fix TypeScript errors in new components

### 8.0 Edge Cases and Error Handling

- [ ] 8.1 Test with no profiles
  - Delete all profiles except default (via DB or API)
  - Reload page: Should show default profile
  - Verify: App doesn't crash
- [ ] 8.2 Test with invalid profile data
  - Try: Create profile with empty name
  - Verify: Validation error shown
  - Try: Invalid settings_json
  - Verify: Error handled gracefully
- [ ] 8.3 Test browser persistence
  - Close: Browser tab
  - Clear: localStorage (if used for profile selection)
  - Reopen: Settings page
  - Verify: Active profile loads correctly from backend

### 9.0 Documentation and Cleanup

- [ ] 9.1 Update SETTINGS_IMPROVEMENTS_HANDOFF.md
  - Mark local testing complete
  - Note any issues found and fixed
  - Document final status
- [ ] 9.2 Take screenshots (optional)
  - Settings page with new layout
  - Profile selector
  - Theme switching
  - Save bar in action
  - Useful for future reference

### 10.0 Merge to Main

- [ ] 10.1 Final verification
  - All tests passing
  - No linter/type errors
  - Functionality verified
- [ ] 10.2 Rebase on main (if needed)
  - `git fetch origin main`
  - `git rebase origin/main`
  - Resolve conflicts (unlikely)
  - Push: `git push origin claude/improve-settings-page-011CUzK3ihKhm4re9cjiKCQs --force-with-lease`
- [ ] 10.3 Merge to main
  - `git checkout main`
  - `git pull origin main`
  - `git merge claude/improve-settings-page-011CUzK3ihKhm4re9cjiKCQs --no-ff -m "feat(settings): comprehensive settings page improvements with profile management

Phase 1 & 2 Complete:
- Reusable components (tooltips, save bar, toggle cards, section headers)
- Visual hierarchy and mobile responsiveness
- Theme management (Light/Dark/System)
- Profile management system (create, switch, delete profiles)
- Backend API for profiles with database persistence

Files: 19 frontend components, 3 backend files, 1 migration"`
- [ ] 10.4 Push to remote
  - `git push origin main`
- [ ] 10.5 Verify services after merge
  - `bash ~/portfolio-ai/scripts/restart.sh`
  - Quick smoke test: Load settings page, switch profiles
- [ ] 10.6 Delete remote branch
  - `git push origin --delete claude/improve-settings-page-011CUzK3ihKhm4re9cjiKCQs`
- [ ] 10.7 Update WORK_TRACKER.md
  - Move to Recently Completed
  - Note: Phase 3 (AI agent config, notifications) deferred to future

---

## Verification Checklist

- [ ] Database migration successful
- [ ] All Phase 1 features working (UI/UX, theme, save bar)
- [ ] All Phase 2 features working (profile management)
- [ ] Backend API endpoints tested and working
- [ ] Frontend compiles without TypeScript errors
- [ ] Backend tests passing
- [ ] Ruff + mypy clean for new files
- [ ] Edge cases handled gracefully
- [ ] Branch merged to main
- [ ] Settings page works after merge

---

## Phase 3 Items (Deferred to Future)

These are documented in SETTINGS_IMPROVEMENTS_HANDOFF.md but NOT required for merge:

- AI agent configuration controls
- Notification preferences
- Advanced features (email, webhooks, etc.)

These can be implemented in a separate task when needed.

---

## Success Criteria

- ✅ Settings page has modern, organized UI
- ✅ Theme management working (Light/Dark/System)
- ✅ Profile management fully functional (create, switch, delete)
- ✅ Unified save bar with change tracking
- ✅ All backend API endpoints working
- ✅ Database migration successful
- ✅ Tests passing, code quality checks pass
- ✅ Branch merged to main
- ✅ No regressions in existing functionality
