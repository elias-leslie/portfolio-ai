---
description: Execute tasks autonomously until ALL complete or genuinely blocked (sudo/credentials/decision needed)
argument-hint: [task list filename]
---

# Task List Management

Guidelines for managing task lists in markdown files to track progress on completing a PRD

## Task Implementation
- **Work autonomously:** Execute tasks continuously unless explicitly instructed otherwise or blocked by technical issues
- **User can request autonomous mode:** If user says "continue autonomously" or "y, continue", work through all remaining tasks without pausing
- **NEVER defer tasks:** Do NOT skip, defer, or postpone tasks without explicit user approval. Complete ALL tasks in the task list.
- **Ask when blocked:** If a task is too complex or you need clarification, ask the user for guidance - do NOT defer or skip
- **ALWAYS fix errors immediately:** Do NOT skip, bypass, or ignore errors even if they're pre-existing:
  - **Pre-commit hook failures:** Fix ALL errors reported by linters/type checkers before committing
  - **Test failures:** Fix ALL failing tests (unless they're pre-existing and unrelated to your changes - document these)
  - **Type errors:** Fix ALL mypy/type errors in code you touch, even if inherited from other files
  - **If error is too complex:** Document it in `docs/known-issues.md` and ask user for guidance
  - **Never use --no-verify:** Always let pre-commit hooks run and fix what they report
- **NO BAND-AIDS:** When implementing tasks, avoid workarounds and shortcuts:
  - **Explicit over implicit:** Don't create "magic" behavior that intercepts/parses strings or inspects scope
  - **Proper types:** Never use `Any` as a shortcut - use proper type hints (e.g., `Iterator[ClassName]` not `Iterator[Any]`)
  - **Clear intent:** Don't hide behavior behind interceptors or dynamic parsing
  - **Single source of truth:** Don't duplicate logic/data across files - one canonical source
  - **Standard patterns:** Use well-known patterns (e.g., `df.to_sql()`) not custom workarounds
  - **If blocked:** Ask user for guidance rather than implementing a hack that "works for now"
- **Completion protocol:**
  1. When you finish a **sub‑task**, immediately mark it as completed by changing `[ ]` to `[x]`.
  2. If **all** subtasks underneath a parent task are now `[x]`, follow this sequence:
    - **First**: Run the full test suite (`pytest`, `npm test`, `bin/rails test`, etc.)
    - **Only if all tests pass**: Stage changes (`git add .`)
    - **Clean up**: Remove any temporary files and temporary code before committing
    - **Commit**: Use a descriptive commit message that:
      - Uses conventional commit format (`feat:`, `fix:`, `refactor:`, etc.)
      - Summarizes what was accomplished in the parent task
      - Lists key changes and additions
      - References the task number and PRD context
      - **Formats the message as a single-line command using `-m` flags**, e.g.:

        ```
        git commit -m "feat: add payment validation logic" -m "- Validates card type and expiry" -m "- Adds unit tests for edge cases" -m "Related to T123 in PRD"
        ```
  3. Once all the subtasks are marked completed and changes have been committed, mark the **parent task** as completed.
- **Default behavior:** Ask for permission before each sub-task UNLESS user has requested autonomous execution

## What "Blocked" Actually Means

You are ONLY blocked if:
1. **Need sudo/root access** - System-level operations you cannot perform (installing packages, modifying system configs)
2. **Need external credentials** - API keys, passwords, access tokens not available in environment
3. **Need user decision** - Architectural choice between 2+ valid approaches where both are reasonable
4. **Exhausted solutions** - Tried 3+ different technical approaches with no progress

You are NOT blocked if:
1. **Tests are failing** - Debug them, fix the code
2. **Errors are occurring** - Fix them, try different approaches
3. **Documentation is needed** - Do it at the end after all tasks complete
4. **You think you're "running out of time"** - This is never true, keep working
5. **Task seems complex** - Break it down into smaller steps and continue
6. **Need to research** - Look up documentation, check similar issues, try solutions
7. **Code needs refactoring** - Do it, that's part of the task
8. **Performance issues** - Profile, optimize, fix them

## Error Resolution Protocol

When you encounter errors during task execution:

1. **Try solution #1** - Most obvious fix based on error message
2. **Try solution #2** - Alternative approach (different method, library, pattern)
3. **Try solution #3** - Research-based solution (check docs, search codebase for similar patterns)
4. **Ask for help** - Only after 3 genuine attempts, explain what you tried and why each failed

**Do NOT:**
- Stop to create status reports mid-task
- Defer errors for "later" or "follow-up work"
- Document issues without attempting multiple fixes first
- Assume complexity or unfamiliarity means you're "blocked"
- Give up after first failed attempt

**Examples of proper error resolution:**
- Test fails → Try fix #1 (obvious bug) → Still fails → Try fix #2 (check test setup) → Still fails → Try fix #3 (research similar tests) → Still fails → Ask user
- Import error → Try fix #1 (check imports) → Try fix #2 (check dependencies) → Try fix #3 (reinstall package) → Ask if still failing
- Type error → Try fix #1 (add type hints) → Try fix #2 (fix type mismatch) → Try fix #3 (refactor types) → Ask if complex

## Status Reporting Rules

Create status reports or summary documents ONLY when:
- ✅ **ALL tasks in the task list are complete** - Everything done, ready for review
- ✅ **You are genuinely blocked** - Meet criteria above (sudo/credentials/user decision)
- ✅ **User explicitly requests status** - "Give me a status update"

**Do NOT create status reports when:**
- ❌ Tests are failing (fix them instead)
- ❌ You encounter errors (resolve them instead)
- ❌ Tasks seem complex (work through them instead)
- ❌ You think you're "running low on time" (never true)
- ❌ You want to "document progress" mid-work (finish first, document after)
- ❌ Some tests pass but others fail (fix the failing ones)
- ❌ You've made "good progress" but aren't done (keep going)

**Exception:** Brief progress updates are fine (e.g., "Fixed 10/15 tests, working on remaining 5"), but don't stop working to write detailed reports.

## Task List Maintenance

1. **Update the task list as you work:**
   - Mark tasks and subtasks as completed (`[x]`) per the protocol above.
   - Add new tasks as they emerge.

2. **Maintain the "Relevant Files" section:**
   - List every file created or modified.
   - Give each file a one‑line description of its purpose.

## AI Instructions

When working with task lists, the AI must:

1. Regularly update the task list file after finishing any significant work.
2. Follow the completion protocol:
   - Mark each finished **sub‑task** `[x]`.
   - Mark the **parent task** `[x]` once **all** its subtasks are `[x]`.
3. Add newly discovered tasks.
4. Keep "Relevant Files" accurate and up to date.
5. Before starting work, check which sub‑task is next.
6. **Execution mode:**
   - If user says "continue autonomously", "y, continue", or similar: work through all tasks without pausing
   - Otherwise: ask permission before each sub-task
7. **Progress reporting:**
   - Use complexity levels: LOW/MEDIUM/HIGH
   - Use percentages for progress (e.g., "13% complete")
   - Avoid time estimates (hours/days/minutes)
8. **NEVER defer tasks:**
   - Do NOT skip, defer, or mark tasks as "deferred" without explicit user approval
   - If stuck or blocked, ASK the user for guidance
   - Complete ALL tasks in the list unless user explicitly tells you to stop
9. **When to pause:**
   - ONLY pause if genuinely blocked: need sudo/root access, external credentials, or user architectural decision
   - Do NOT pause for: test failures, errors, complexity, research needs, or thinking you're "out of time"
   - Follow the "Error Resolution Protocol" above - try 3 solutions before asking for help
   - Do NOT create status reports mid-work - finish all tasks first, then summarize

---

## Usage

**With task list filename:**
```
/do_it tasks/tasks-0004-prd-multi-source-failover-enforcement.md
```

**Interactive (will ask for task list):**
```
/do_it
```

The AI will:
1. Read the task list
2. Identify the next uncompleted sub-task
3. Determine execution mode (autonomous or ask permission)
4. Implement the sub-task(s)
5. Mark completed tasks as `[x]`
6. Run tests and commit when parent task is complete
7. Continue or ask for next direction

## Example Flow (Autonomous Mode)

```
User: "y, please continue autonomously until done"
AI: [reads task list]
AI: "Working on 7.1-7.4 (MEDIUM complexity, ~13% of feature)"
AI: [implements 7.1.1-7.1.5, marks complete]
AI: [implements 7.2.1-7.2.5, marks complete]
AI: [implements 7.3.1-7.3.5, marks complete]
AI: [implements 7.4.1-7.4.4, marks complete]
AI: "Tasks 7.1-7.4 complete. Running tests..."
AI: [runs pytest, all pass]
AI: [creates commit]
AI: "Foundation complete (13%). Remaining: 7.5-7.9 (HIGH complexity, 87%)."
```

## Example Flow (Interactive Mode)

```
AI: "Next task is 1.1: Create app/source_cache.py with LRU cache. Ready to start? (yes/y)"
User: "y"
AI: [implements task, marks complete]
AI: "Task 1.1 complete. Next is 1.2: Add unit tests. Ready? (yes/y)"
User: "y, continue autonomously"
AI: [implements all remaining tasks without pausing]
AI: [commits after each parent task completion]
AI: "All tasks complete."
```
