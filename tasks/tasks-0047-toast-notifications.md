# Task 0047: Toast Notification System

**Created**: 2025-11-11
**Status**: In Progress
**Environment**: Cloud (code only) → Local (testing)

## Summary

**Goal**: Implement toast notification system using the already-installed sonner library to provide user feedback for key operations.

**Approach**:
- Create a useToast hook wrapping sonner's API
- Sonner's Toaster component is already added to layout.tsx
- Add toast notifications to watchlist, portfolio, and idea operations
- Use toast.promise() for async operations with loading/success/error states

**Scope**: Frontend only (no backend changes required)

---

## Tasks

### Task 1: Create useToast Hook
**Status**: Pending

Create a custom hook that wraps sonner's toast API for consistent usage across the app.

**Subtasks**:
- [ ] Create `frontend/lib/hooks/useToast.ts`
- [ ] Export helper functions for common patterns (success, error, loading, promise)
- [ ] Add TypeScript types for toast options
- [ ] Document usage patterns and examples

**Acceptance**:
- Hook provides clean API wrapping sonner
- Supports all toast types (success, error, info, warning, loading)
- Includes toast.promise() wrapper for async operations

---

### Task 2: Add Toasts to Watchlist Operations
**Status**: Pending

Add success/error feedback for watchlist add and delete operations.

**Subtasks**:
- [ ] Update `useAddTicker` hook to show toasts on success/error
- [ ] Update `useDeleteWatchlistItem` hook to show toasts on success/error
- [ ] Use toast.promise() for async operations
- [ ] Provide clear, actionable messages (e.g., "AAPL added to watchlist")

**Acceptance**:
- Adding ticker shows: loading → success/error toast
- Deleting ticker shows: loading → success/error toast
- Error messages are user-friendly and actionable

---

### Task 3: Add Toasts to Portfolio Operations
**Status**: Pending

Add success/error feedback for portfolio position operations.

**Subtasks**:
- [ ] Update `useAddPosition` hook for save operations
- [ ] Update `useUpdatePosition` hook for update operations
- [ ] Update `useDeletePosition` hook for delete operations
- [ ] Include symbol and account info in toast messages

**Acceptance**:
- Position save shows: loading → success/error toast
- Position update shows: loading → success/error toast
- Position delete shows: loading → success/error toast
- Messages include relevant context (symbol, shares, account)

---

### Task 4: Add Toasts to Idea Status Updates
**Status**: Pending

Add success/error feedback when updating investment idea status.

**Subtasks**:
- [ ] Update `useUpdateIdeaStatus` hook
- [ ] Show status change in toast message (e.g., "Moved to Under Review")
- [ ] Handle errors gracefully

**Acceptance**:
- Status updates show: loading → success/error toast
- Messages clearly indicate the new status
- Error messages are helpful

---

### Task 5: Documentation and Handoff
**Status**: Pending

Create handoff documentation for local testing.

**Subtasks**:
- [ ] Create handoff document with testing steps
- [ ] Document all operations that now have toasts
- [ ] Provide test scenarios for each toast type
- [ ] Update WORK_TRACKER.md

**Acceptance**:
- Handoff doc clearly explains what was implemented
- Testing steps are complete and actionable
- WORK_TRACKER.md updated with task completion

---

## Verification Checklist

### Functional Requirements
- [ ] useToast hook created and exports clean API
- [ ] Watchlist add/delete operations show toasts
- [ ] Portfolio save/delete/update operations show toasts
- [ ] Idea status updates show toasts
- [ ] All async operations use toast.promise()
- [ ] Error messages are user-friendly

### Code Quality
- [ ] TypeScript: All functions properly typed
- [ ] No lint errors (`npm run lint`)
- [ ] Follows existing hook patterns
- [ ] Clean, readable code with comments where needed

### Testing (Local Only)
- [ ] Add ticker to watchlist → see success toast
- [ ] Delete ticker from watchlist → see success toast
- [ ] Add position to portfolio → see success toast
- [ ] Update position → see success toast
- [ ] Delete position → see success toast
- [ ] Update idea status → see success toast
- [ ] Trigger errors → see error toasts with helpful messages
- [ ] Toasts appear in correct position (top-right)
- [ ] Toasts auto-dismiss after appropriate time

### Documentation
- [ ] Handoff document created with testing instructions
- [ ] useToast hook has usage examples
- [ ] WORK_TRACKER.md updated

---

## Implementation Notes

**Sonner Setup (Already Complete)**:
- Library installed: `"sonner": "^2.0.7"` in package.json
- Toaster component already added to `app/layout.tsx:76`
- Position: top-right with richColors enabled

**Toast Patterns**:
```typescript
// Simple success/error
toast.success("Action completed!");
toast.error("Action failed");

// Async operation with promise
toast.promise(
  asyncFunction(),
  {
    loading: "Processing...",
    success: "Completed!",
    error: "Failed"
  }
);
```

**Integration Points**:
- `frontend/lib/hooks/useWatchlist.ts` - Add/delete ticker mutations
- `frontend/lib/hooks/usePortfolio.ts` - Position CRUD mutations
- `frontend/lib/hooks/useIdeas.ts` - Status update mutation

---

## Files Changed

**New Files**:
- `frontend/lib/hooks/useToast.ts` - Toast hook wrapper

**Modified Files**:
- `frontend/lib/hooks/useWatchlist.ts` - Add toasts to mutations
- `frontend/lib/hooks/usePortfolio.ts` - Add toasts to mutations
- `frontend/lib/hooks/useIdeas.ts` - Add toasts to status updates

**Documentation**:
- `tasks/HANDOFF-toast-notifications-local-testing.md` - Testing guide

---

## Context

**Why**: Users need immediate feedback when performing actions (add/delete/update operations). Currently, the UI updates but there's no explicit confirmation message.

**Dependencies**: Sonner library (already installed and configured)

**Risk**: Low - additive changes only, no breaking changes to existing functionality

---

**Estimated Complexity**: LOW
- Simple wrapper around existing library
- Straightforward integration into existing mutation hooks
- No API changes required
