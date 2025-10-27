---
description: Execute tasks from a task list one-by-one with test/commit protocol
argument-hint: [task list filename]
---

# Task List Management

Guidelines for managing task lists in markdown files to track progress on completing a PRD

## Task Implementation
- **One sub-task at a time:** Do **NOT** start the next sub‑task until you ask the user for permission and they say "yes" or "y"
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
- Stop after each sub‑task and wait for the user's go‑ahead.

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
6. After implementing a sub‑task, update the file and then pause for user approval.

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
3. Ask permission to start
4. Implement the sub-task
5. Mark it complete
6. Run tests and commit if parent task is complete
7. Ask permission for the next sub-task

## Example Flow

```
AI: "Next task is 1.1: Create app/source_cache.py with LRU cache. Ready to start? (yes/y)"
User: "y"
AI: [implements task, marks complete]
AI: "Task 1.1 complete. Next is 1.2: Add unit tests. Ready? (yes/y)"
User: "y"
AI: [implements task, marks complete]
AI: "All subtasks for Task 1.0 complete. Running tests..."
AI: [runs pytest, all pass]
AI: [creates commit with conventional format]
AI: "Task 1.0 complete. Next parent task is 2.0. Ready? (yes/y)"
```
