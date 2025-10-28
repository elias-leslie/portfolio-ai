# 🚀 AI Dev Tasks - Command Suite

A comprehensive set of slash commands for structured feature development with AI coding assistants. Works with **Claude Code**, **Cursor**, **Windsurf**, and other AI-powered development tools.

---

## 📦 What's Included

This package includes **5 powerful commands** for your development workflow:

| Command | Description | Lines |
|---------|-------------|-------|
| `/plan_it` | Create a Product Requirements Document (PRD) from an idea | 78 |
| `/task_it` | Generate a detailed task list from a PRD | 82 |
| `/do_it` | Execute tasks one-by-one with test/commit protocol | 91 |
| `/doc_it` | Update core documentation to reflect recent changes | 199 |
| `/next_it` | Find the next thing to work on and initiate planning | 225 |

**Total**: 5 commands, 675 lines of structured AI guidance

---

## 🎯 The Workflow

```
💡 Idea → /next_it → Select (#1-15) → /plan_it → PRD
                                              ↓
                                         /task_it → Task List
                                              ↓
                                         /do_it → Implementation
                                              ↓
                                         /doc_it → Documentation Update
                                              ↓
                                         Back to /next_it
```

---

## 📥 Installation

### For Claude Code

**Quick Install** (Recommended):
```bash
# From this repository
cp .ai_dev_tasks/*.md ~/.config/claude/commands/

# OR from a fresh clone
git clone <repository-url>
cp <repository>/.ai_dev_tasks/*.md ~/.config/claude/commands/
```

**Per-Project Install**:
```bash
# In your project root
mkdir -p .claude/commands
cp .ai_dev_tasks/*.md .claude/commands/
```

**Verify Installation**:
```bash
ls ~/.config/claude/commands/  # OR ls .claude/commands/
# You should see: plan_it.md, task_it.md, do_it.md, doc_it.md, next_it.md
```

Restart Claude Code (`/exit`) to load the new commands.

### For Cursor

**Install**:
```bash
# Copy to your project or a global location
mkdir -p ~/ai-dev-tasks
cp .ai_dev_tasks/*.md ~/ai-dev-tasks/
```

**Usage**:
Reference commands with `@` in Cursor's Agent chat:
```
@plan_it.md Create a new authentication system
@task_it.md Use tasks/0001-prd-authentication.md
@do_it.md Start with tasks/tasks-0001-prd-authentication.md
```

### For Other AI Tools

Copy the `.md` files to a location accessible by your AI tool, then reference them according to your tool's documentation.

---

## 📖 Command Reference

### 1. `/next_it` - Find Your Next Work

**Purpose**: Discover what to work on next by analyzing your project

**What It Does**:
- Scans existing plans, tasks, documentation, and code
- Identifies known issues (incomplete work, bugs, tech debt)
- Brainstorms quick win ideas (high value, low effort, free/OSS)
- Generates strategic ideas (complex features, extreme value, free/OSS)
- Presents **15 prioritized opportunities** (5 + 5 + 5)
- Auto-initiates `/plan_it` for your selection

**Usage**:
```bash
/next_it
```

**Interactive Flow**:
```
1. AI analyzes your project
2. Presents top 5 known issues + top 5 quick wins + top 5 strategic ideas
3. You select a number (1-15)
4. AI automatically starts /plan_it with full context
```

**Example Output**:
```
📋 Next Work Opportunities

## Known Issues (Top 5)
1. [P1] Extract storage interface for testing
   Effort: Medium | Impact: High

## Quick Win Ideas (Top 5)
6. [NEW] Add pre-commit hooks for code quality
   Effort: Small | Value: High | Free/OSS: Yes

## Strategic Ideas (Top 5)
11. [STRATEGIC] Implement plugin/extension system
    Effort: Large | Value: Extreme | Free/OSS: Yes

Select a number (1-15) to start planning, or 'cancel' to exit:
```

---

### 2. `/plan_it` - Create a PRD

**Purpose**: Create a Product Requirements Document for a new feature

**What It Does**:
- Asks clarifying questions to understand your idea
- Generates a structured PRD with goals, user stories, requirements
- Saves to `/tasks/NNNN-prd-[feature-name].md`
- Written for junior developers (clear, unambiguous)

**Usage**:
```bash
# With description
/plan_it Add user authentication with OAuth

# Interactive mode
/plan_it
```

**PRD Structure**:
- Introduction/Overview
- Goals
- User Stories
- Functional Requirements
- Non-Goals (Out of Scope)
- Design Considerations (Optional)
- Technical Considerations (Optional)
- Success Metrics
- Open Questions

---

### 3. `/task_it` - Generate Task List

**Purpose**: Break down a PRD into actionable tasks

**What It Does**:
- Reads an existing PRD
- Assesses current codebase state
- Generates high-level parent tasks (Phase 1)
- Waits for your "Go" confirmation
- Generates detailed sub-tasks (Phase 2)
- Identifies relevant files to create/modify
- Saves to `/tasks/tasks-NNNN-prd-[feature-name].md`

**Usage**:
```bash
# With PRD filename
/task_it tasks/0004-prd-multi-source-failover.md

# Interactive mode
/task_it
```

**Two-Phase Process**:
1. Generate parent tasks → Wait for "Go"
2. Generate detailed sub-tasks → Save task list

---

### 4. `/do_it` - Execute Tasks

**Purpose**: Execute tasks one-by-one with test/commit protocol

**What It Does**:
- Reads task list
- Implements one sub-task at a time
- Waits for your approval after each task
- When parent task complete:
  - Runs full test suite
  - Commits with conventional format (feat:, fix:, etc.)
  - Marks parent task complete

**Usage**:
```bash
# With task list filename
/do_it tasks/tasks-0004-prd-multi-source-failover.md

# Interactive mode
/do_it
```

**Protocol**:
```
1. AI implements sub-task 1.1
2. Marks [x] complete
3. Asks: "Ready for 1.2? (yes/y)"
4. User: "y"
5. Repeat for all sub-tasks
6. All sub-tasks done → Run tests → Commit → Mark parent [x]
```

**Commit Format**:
```bash
git commit -m "feat: add payment validation logic" \
  -m "- Validates card type and expiry" \
  -m "- Adds unit tests for edge cases" \
  -m "Related to T123 in PRD"
```

---

### 5. `/doc_it` - Update Documentation

**Purpose**: Update core documentation to reflect recent changes

**What It Does**:
- Analyzes git history since last documentation update
- Identifies gaps (new features not documented, resolved issues still marked open)
- Updates all core documentation files
- Consolidates stray documentation into core docs
- Reviews for bloat and extracts detailed content if needed
- Creates commit with summary

**Usage**:
```bash
/doc_it
```

**What Gets Updated**:
- Core documentation files (ARCHITECTURE.md, SETUP.md, etc.)
- Status/progress documents (REFACTOR_STATUS.md, etc.)
- Main index (CLAUDE.md, README.md)
- Consolidates stray docs into core files

**Bloat Prevention**:
- Archives bloated docs to `docs/archive/legacy-YYYYMMDD-vN/`
- Extracts detailed content to `docs/reference/`
- Keeps core docs lean and scannable

---

## 🔄 Complete Workflow Example

### Starting Fresh

```bash
# 1. Find what to work on next
/next_it

# Output shows 15 opportunities
# You select: 6 (Quick Win: Add pre-commit hooks)

# 2. AI automatically starts planning
# Creates: tasks/0005-prd-precommit-hooks.md

# 3. Generate task list
/task_it tasks/0005-prd-precommit-hooks.md
# AI: "High-level tasks generated. Ready? Type 'Go'"
# You: "Go"
# Creates: tasks/tasks-0005-prd-precommit-hooks.md

# 4. Execute tasks
/do_it tasks/tasks-0005-prd-precommit-hooks.md
# AI implements each task, waits for your "y" approval
# Commits after each parent task completes

# 5. Update documentation
/doc_it
# AI updates all docs to reflect the new feature

# 6. Repeat!
/next_it
```

---

## 🎨 Customization

### Adapting for Your Project

All commands are **project-agnostic** and discover your project structure dynamically. However, they work best when you have:

1. **Documentation Structure**: Core docs in `docs/core/` or similar
2. **Task Directory**: `/tasks/` for PRDs and task lists
3. **Git Repository**: For history analysis and commits
4. **Coding Standards**: Documented in `CLAUDE.md`, `CONTRIBUTING.md`, or `docs/`

### Standards Checked by Commands

- `/next_it` looks for:
  - Line limits (e.g., 300-line max)
  - Test coverage expectations (e.g., 80% target)
  - DRY principle violations
  - Security patterns (SQL parameterization, etc.)

- `/do_it` enforces:
  - Test before commit
  - Conventional commit format
  - Clean working directory before commit

- `/doc_it` maintains:
  - Single source of truth (no duplication)
  - Cross-references instead of copying
  - Size limits (e.g., <800 lines per core doc)

### Modifying Commands

Commands are plain Markdown files with instructions for the AI. To customize:

1. Copy the command file you want to modify
2. Edit the Markdown to change behavior
3. Save with a new name or overwrite
4. Restart your AI tool to reload

Example customization:
```markdown
<!-- In plan_it.md, change the PRD structure -->
## PRD Structure
1. **Overview** (your custom format)
2. **Requirements** (your format)
...
```

---

## 📊 Benefits

### Structure
- **Systematic approach** from idea → implementation → documentation
- **Clear checkpoints** for review and approval
- **Prevents scope creep** with PRDs and task lists

### Quality
- **Test before commit** enforced by `/do_it`
- **Documentation stays current** with `/doc_it`
- **Standards enforcement** via discovery in `/next_it`

### Efficiency
- **Discover next work** automatically with `/next_it`
- **Parallel innovation** (quick wins + strategic ideas)
- **Reusable workflow** across projects

### Control
- **One task at a time** with approval gates
- **Visible progress** with checkboxes
- **Easy rollback** with atomic commits

---

## 🛠️ Troubleshooting

### Commands Not Working

**Claude Code**:
- Ensure files are in `~/.config/claude/commands/` or `.claude/commands/`
- Restart Claude Code with `/exit`
- Check file permissions: `ls -l ~/.config/claude/commands/`

**Cursor**:
- Reference with `@` symbol: `@plan_it.md`
- Ensure files are accessible in your workspace

### AI Not Following Instructions

- **Be specific**: Provide context and constraints
- **Reference standards**: Point to coding guidelines
- **Correct and iterate**: The AI learns from feedback

### Commands Producing Large Files

- `/doc_it` includes bloat review and archiving
- Adjust size limits in the command files if needed
- Archive detailed content to reference docs

---

## 📚 Additional Resources

### Related Documentation

If your project uses these commands, document them in:
- `CLAUDE.md` - Project overview with quick start
- `CONTRIBUTING.md` - Development workflow for contributors
- `.ai_dev_tasks/` - Custom command adaptations

### Best Practices

1. **Start with `/next_it`** - Don't guess what to work on
2. **Complete the PRD** - Good planning = better implementation
3. **Review each task** - Don't blindly approve
4. **Never defer tasks** - AI must complete ALL tasks or ask for help, never defer without approval
5. **Keep docs current** - Run `/doc_it` after major milestones
6. **Commit frequently** - Atomic commits make debugging easier

### CRITICAL: Task Deferral Policy

**AI agents must NEVER defer tasks without explicit user approval.**

- Complete ALL tasks in the task list
- If blocked or stuck, ASK the user for guidance
- Do NOT skip, defer, or postpone tasks
- Task complexity is NOT a reason to defer
- If uncertain, implement and ask for review - do NOT defer

### Community

These commands are based on the [AI Dev Tasks](https://github.com/snarktank/ai-dev-tasks) methodology, adapted for Claude Code and extended with:
- `/next_it` - Discovery and brainstorming
- `/doc_it` - Automated documentation maintenance

---

## 📄 License

These command files are designed to be copied and customized. Use them freely in your projects.

---

## 🤝 Contributing

Found a bug or have an improvement? Contributions welcome!

1. Test your changes in a real project
2. Document the improvement
3. Submit a pull request with examples

---

**Version**: 2.0.0 (Complete Command Suite)
**Updated**: 2025-10-26
**Commands**: 5 total (plan_it, task_it, do_it, doc_it, next_it)
**Total Lines**: 675 lines of AI guidance
