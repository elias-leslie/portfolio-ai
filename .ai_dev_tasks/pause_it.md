---
description: Pause current work and save state for resuming later
---

# Rule: Pause and Save Work State

## Goal

To guide an AI assistant in pausing current work, updating the task list status, and creating a handoff document for seamless resumption in a future session. Use this when running low on context/tokens or when you need to pause and resume later.

## When to Use

Invoke this workflow by using `/pause_it` in these scenarios:

1. **Context/token limit approaching** - Running low on available tokens
2. **Session ending** - Need to stop work but will continue later
3. **Switching tasks** - Pausing current work to work on something else
4. **End of work day** - Saving progress before logging off
5. **Before major changes** - Creating a checkpoint before risky operations

## Process

### Phase 1: Identify Current Work

1. **Detect active task list**:
   - Look for most recently modified file in `tasks/` matching `tasks-*.md`
   - Check for task list referenced in recent conversation
   - If multiple, ask user which task list to pause

2. **Analyze current state**:
   - Count completed tasks (marked `[x]`)
   - Identify in-progress tasks (partially complete sub-tasks)
   - Note next uncompleted task
   - Check git status for uncommitted changes

### Phase 2: Update Task List Status

1. **Update header status section** in task list:
   ```markdown
   **Status**: Paused (In Progress)
   **Completion**: XX% (Y/Z tasks complete)
   **Last Updated**: YYYY-MM-DD HH:MM
   ```

2. **Update Summary section**:
   ```markdown
   **✅ COMPLETE:**
   - Task X.X: [Brief description]
   - Task Y.Y: [Brief description]

   **🔄 IN PROGRESS:**
   - Task Z.Z: [What's done, what remains]

   **⚠️ NEXT STEPS:**
   1. Resume with Task Z.Z.[next sub-task]
   2. Then proceed to Task W.W
   3. [Any critical notes or blockers]

   **PAUSED:** YYYY-MM-DD HH:MM (session context limit / user request / [reason])
   ```

3. **Add pause marker** at the location where work stopped:
   ```markdown
   <!-- PAUSED: YYYY-MM-DD HH:MM - Resume from here -->
   ```

### Phase 3: Create Handoff Document

Create `tasks/PAUSE-HANDOFF-[timestamp].md` with the following structure:

```markdown
# Work Session Handoff

**Date Paused**: YYYY-MM-DD HH:MM UTC
**Reason**: [Context limit / User request / End of session / etc.]
**Task List**: `tasks-NNNN-prd-[feature].md`
**Overall Progress**: XX% (Y/Z parent tasks complete)

---

## Current Status

**What Was Accomplished This Session:**
- ✅ Completed Task X.X: [Brief description]
- ✅ Completed Task Y.Y: [Brief description]
- ✅ Fixed [N] issues found during implementation

**What's In Progress:**
- 🔄 Task Z.Z: [Specific sub-task]
  - ✅ Done: [What's completed]
  - ⏸️ Next: [Exact next action to take]
  - 📝 Notes: [Any important context or decisions made]

**What's Blocked (if any):**
- ❌ [Description of blocker]
- ❌ [Another blocker]

---

## Code State

**Git Status:**
```
[Output of `git status --short`]
```

**Uncommitted Changes:**
- [List modified files with brief description]
- If none: "✅ All changes committed"

**Last Commit:**
- Hash: [commit hash]
- Message: [commit message]
- Date: [commit date]

**Branch:** [current branch name]

---

## Environment State

**Services Running:**
- Backend: [running/stopped] - PID [N] or N/A
- Frontend: [running/stopped] - PID [N] or N/A
- Celery: [running/stopped] - PID [N] or N/A
- Database: [PostgreSQL] - [status]

**Virtual Environment:**
- Python venv: [activated location or "not activated"]
- Node modules: [installed/not installed]

**Recent Test Results:**
- Last test run: [passing/failing] - [N passed, M failed]
- Coverage: [XX%]

---

## Key Decisions & Context

**Architecture Decisions Made:**
1. [Decision 1 with brief rationale]
2. [Decision 2 with brief rationale]

**Patterns Established:**
- [Pattern 1: Where it's used]
- [Pattern 2: Where it's used]

**Issues Discovered:**
- [Issue 1: How it was handled]
- [Issue 2: How it was handled]

**Band-Aids Avoided:**
- [Workaround that was tempting but avoided, and why]

---

## To Resume

**Immediate Next Steps:**
1. **Resume environment:**
   ```bash
   cd ~/[project-name]
   source backend/.venv/bin/activate  # if needed
   git status  # verify clean state
   ```

2. **Review context:**
   - Read this handoff document
   - Check task list: `tasks/tasks-NNNN-prd-[feature].md`
   - Look for `<!-- PAUSED: ... -->` marker

3. **Continue work:**
   - Start with: Task Z.Z.[next sub-task]
   - Run: `/do_it tasks/tasks-NNNN-prd-[feature].md`
   - Say: "Resume from pause - continue autonomously"

**Critical Reminders:**
- [Any important context that must be remembered]
- [Any gotchas or edge cases encountered]
- [Any dependencies or external factors]

---

## Files Modified This Session

**Created:**
- `path/to/new_file.py` - [Purpose]
- `path/to/another_file.py` - [Purpose]

**Modified:**
- `path/to/existing_file.py` - [What changed]
- `path/to/config.yaml` - [What changed]

**Deleted:**
- None (or list files)

---

## Quick Stats

- **Session Duration**: [X hours Y minutes] (approximate)
- **Parent Tasks Completed**: Y of Z (XX%)
- **Sub-tasks Completed**: N total
- **Files Created**: N
- **Files Modified**: M
- **Tests Passing**: N/M (XX%)
- **Commits Created**: K

---

## Session Notes

[Any additional notes, observations, or context that would be helpful when resuming]

---

**To Resume**: Run `/do_it tasks/tasks-NNNN-prd-[feature].md` and say "Resume from pause - continue autonomously"

**Handoff Version**: 1.0
**Generated by**: /pause_it command
```

### Phase 4: Display Summary

After saving the handoff document and updating the task list, display:

```
⏸️  Work Paused and State Saved

📊 Progress: XX% complete (Y/Z parent tasks done)

✅ Completed This Session:
   - Task X.X: [Brief description]
   - Task Y.Y: [Brief description]

🔄 In Progress:
   - Task Z.Z: [What's done / what's next]

📝 Handoff Saved:
   tasks/PAUSE-HANDOFF-[timestamp].md

📋 Task List Updated:
   tasks/tasks-NNNN-prd-[feature].md

💡 To Resume:
   1. Open new session
   2. Run: /do_it tasks/tasks-NNNN-prd-[feature].md
   3. Say: "Resume from pause - continue autonomously"

🎯 Next Action:
   Task Z.Z.[next sub-task] - [Brief description]
```

## Git Handling

**If uncommitted changes exist:**
1. Ask user: "You have uncommitted changes. Would you like to (1) commit them now, (2) stash them, or (3) leave as-is?"
2. Based on response:
   - **(1) Commit:** Create WIP commit: `git commit -m "wip: pause point - [brief context]"`
   - **(2) Stash:** Stash with message: `git stash push -m "Paused at [timestamp] - [context]"`
   - **(3) Leave:** Note in handoff that changes are uncommitted

**If clean state:**
- Note in handoff: "✅ Clean state, all changes committed"

## Quality Standards

### Handoff Document Should:
- **Be complete**: All context needed to resume is present
- **Be specific**: Exact next action is clear, not vague
- **Be current**: Reflects actual state, not aspirational
- **Be actionable**: Next steps are concrete and immediate
- **Be honest**: Notes blockers and issues, not just successes

### Task List Should:
- **Be up-to-date**: All completed tasks marked `[x]`
- **Show progress**: Percentage and counts are accurate
- **Note pause point**: Clear marker where work stopped
- **List next steps**: Specific actions to resume

## Anti-Patterns to Avoid

- ❌ Vague next steps: "Continue implementation" → "Implement Task Z.Z.4: Add error handling to validate_input() function"
- ❌ Missing context: Not noting decisions or patterns established
- ❌ Outdated status: Task list shows 50% but actually 75% done
- ❌ No environment state: Not noting what's running or installed
- ❌ Assuming memory: Not capturing critical context that exists only in current session

## Target Audience

Assume the reader of the handoff document is:
- **A future AI assistant** (possibly different session, different model)
- **You in the future** (different context, different memory)
- **Another developer** (if needed to hand off work)

Therefore: Be explicit, specific, and assume no prior knowledge of this session.

## Success Criteria

After completion, verify:
- ✅ Task list updated with current status and pause marker
- ✅ Handoff document created with all sections filled
- ✅ Git state is clean or properly noted
- ✅ Next action is crystal clear and actionable
- ✅ All context is captured (no "tribal knowledge" lost)
- ✅ Summary displayed to user with resume instructions

---

## Usage

Simply invoke the command (no arguments needed):
```
/pause_it
```

The AI will:
1. Identify the active task list
2. Update task list status
3. Create comprehensive handoff document
4. Handle git state (commit/stash/note)
5. Display summary with resume instructions

---

## Example Output

```
⏸️  Work Paused and State Saved

📊 Progress: 73% complete (8/11 parent tasks done)

✅ Completed This Session:
   - Task 7.1: Created connection pooling wrapper
   - Task 7.2: Added DataFrame insertion method
   - Task 7.3: Updated type hints throughout

🔄 In Progress:
   - Task 7.4: Fix schema manager
     ✅ Done: Removed duplicate DDL, added validation
     ⏸️  Next: Test validation with missing tables

📝 Handoff Saved:
   tasks/PAUSE-HANDOFF-20251030-143522.md

📋 Task List Updated:
   tasks/tasks-0015-prd-postgresql-migration.md

💾 Git State:
   ✅ All changes committed (clean state)
   📌 Last commit: feat: add DataFrame insertion method (7f3a42b)

💡 To Resume:
   1. Open new session
   2. Run: /do_it tasks/tasks-0015-prd-postgresql-migration.md
   3. Say: "Resume from pause - continue autonomously"

🎯 Next Action:
   Task 7.4.5: Test schema validation with `pytest tests/test_schema.py -v`
```

---

## Integration with Command Suite

**Position in Workflow:**
```
/plan_it → /task_it → /do_it
                        ↓
                   (work in progress)
                        ↓
                    /pause_it
                        ↓
                  (resume later)
                        ↓
                    /do_it (resume)
```

---

## Notes

- **Context preservation**: Handoff document is designed to survive complete context loss
- **Resume-friendly**: Next steps are always actionable without reading entire history
- **Git-aware**: Handles uncommitted changes gracefully
- **Environment-aware**: Notes what's running to restore state quickly
