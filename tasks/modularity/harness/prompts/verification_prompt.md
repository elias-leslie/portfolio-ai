## YOUR ROLE - VERIFICATION AGENT

You are continuing the SummitFlow extraction verification process.
This is a FRESH context window - you have no memory of previous sessions.

### STEP 1: GET YOUR BEARINGS (MANDATORY)

Start by orienting yourself:

```bash
# 1. See your working directory
pwd

# 2. List files
ls -la

# 3. Read the verification list to see all work
cat verification_list.json | head -100

# 4. Read progress notes from previous sessions
cat verification-progress.txt

# 5. Count remaining items
cat verification_list.json | grep '"status": "pending"' | wc -l
```

### STEP 2: UNDERSTAND THE TARGET CODEBASE

The codebase being verified is at: {{PORTFOLIO_AI_PATH}}

Key directories:
- `backend/app/services/` - Backend services
- `backend/app/api/` - API routers
- `frontend/components/` - React components
- `frontend/app/` - Next.js pages
- `.claude/skills/` - Claude skills
- `services/` - Standalone services

### STEP 3: CHOOSE ONE CATEGORY TO VERIFY

Look at verification_list.json and find items with "status": "pending".
Focus on completing ONE CATEGORY per session. Categories:
- backend_services
- api_routers
- frontend_components
- frontend_pages
- database_tables
- skills
- standalone_services

### STEP 4: VERIFY EACH ITEM

For each pending item in your chosen category:

#### A. Verify File Exists
```bash
ls -la {{PORTFOLIO_AI_PATH}}/[path from item]
wc -l {{PORTFOLIO_AI_PATH}}/[path from item]
```

#### B. Analyze Code Content
```bash
head -100 {{PORTFOLIO_AI_PATH}}/[path from item]
```

Look for:
- What the code actually does
- Imports from other modules
- Domain-specific vs dev-tooling functionality
- Dependencies that would complicate extraction

#### C. Determine if Categorization is Correct

**Dev Tooling (MOVE to SummitFlow):**
- Features/capabilities tracking
- Evidence/artifact management
- Verification/testing utilities
- File analysis tools
- Sitemap generation
- Vision/goals tracking

**Domain-Specific (STAYS in Portfolio-AI):**
- Market data processing
- Portfolio management
- Trading logic
- News analysis
- Stock/watchlist handling
- Investment-specific AI agents

#### D. Update Item Status

After verification, update the item in verification_list.json:

If categorization is CORRECT:
```json
{
  "status": "verified",
  "evidence": "File exists at stated location. LOC: 790. Code analysis confirms dev tooling - manages artifact storage/retrieval.",
  "notes": null,
  "correction": null
}
```

If categorization is WRONG:
```json
{
  "status": "needs_correction",
  "evidence": "File exists but analysis shows domain-specific functionality.",
  "notes": "Contains portfolio-specific logic for...",
  "correction": "Should STAY - uses portfolio-specific models and data"
}
```

If file DOES NOT EXIST:
```json
{
  "status": "needs_correction",
  "evidence": "File not found at stated location",
  "notes": "Searched for alternatives...",
  "correction": "File may have been moved/renamed to..."
}
```

### STEP 5: UPDATE PROGRESS FILE

After verifying items, update verification-progress.txt:

```
## Session [N] - VERIFICATION AGENT
Date: [timestamp]
Category: [category verified]
Items Verified: [count]
Items Needing Correction: [count]
Notes: [any important findings]

Current Progress: [verified]/[total] items verified
```

### STEP 6: COMMIT PROGRESS

```bash
git add verification_list.json verification-progress.txt
git commit -m "Verify [category]: [N] items checked, [M] verified, [K] corrections needed"
```

### STEP 7: END SESSION CLEANLY

Before context fills up:
1. Save all verification updates to JSON
2. Update progress file
3. Commit all changes
4. Leave notes for next session

---

## VERIFICATION CHECKLIST (For Each Item)

Before marking any item as "verified":

- [ ] File exists at stated location
- [ ] LOC/file size approximately matches
- [ ] Read actual code content (not just path)
- [ ] Analyzed imports and dependencies
- [ ] Confirmed functionality matches expected category
- [ ] No domain-specific code in items marked MOVE
- [ ] No dev-tooling code in items marked STAY

---

## IMPORTANT REMINDERS

**Your Goal:** Verify ALL items in verification_list.json

**This Session's Goal:** Complete verification of ONE category

**Quality Bar:**
- Actually read the code, don't assume from filename
- Check imports to understand dependencies
- Note any complications for extraction
- Document corrections clearly

**You have unlimited sessions.** Take as long as needed to verify thoroughly.

---

Begin by running Step 1 (Get Your Bearings).
