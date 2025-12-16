## YOUR ROLE - VERIFICATION INITIALIZER AGENT (Session 1)

You are the FIRST agent in a multi-session verification process for the DeVision extraction project.
Your job is to create the comprehensive verification checklist that all subsequent agents will work through.

### YOUR INPUT: The Planning Document

Below is the planning document (NEXT-SESSION-PROMPT.md) that describes all components to be verified:

```markdown
{{PLANNING_DOC}}
```

---

## CRITICAL FIRST TASK: Create verification_list.json

Based on the planning document above, create a file called `verification_list.json` with ALL items that need verification.

**Format:**
```json
{
  "meta": {
    "created": "ISO timestamp",
    "source": "NEXT-SESSION-PROMPT.md",
    "total_items": 0,
    "verified_count": 0,
    "last_updated": "ISO timestamp"
  },
  "items": [
    {
      "id": "v001",
      "category": "backend_services",
      "component": "artifact_manager.py",
      "location": "backend/app/services/artifact_manager.py",
      "expected_action": "MOVE",
      "reason": "Evidence/artifact storage - dev tooling",
      "status": "pending",
      "evidence": null,
      "notes": null,
      "correction": null
    }
  ]
}
```

### MANDATORY: Include ALL These Categories

From the planning document, you MUST create verification items for:

#### 1. Backend Services (backend/app/services/)
For EACH service file mentioned:
- Verify file exists at stated location
- Verify LOC count is accurate
- Verify categorization (MOVE vs STAY) is correct based on actual code analysis
- Check for dependencies that might complicate extraction

#### 2. Backend API Routers (backend/app/api/)
For EACH router mentioned:
- Verify file exists at stated location
- Verify LOC count is accurate
- Verify categorization is correct
- Check what services/models it depends on

#### 3. Frontend Components (frontend/components/)
For EACH component mentioned:
- Verify file exists at stated location
- Verify file size is accurate
- Verify categorization is correct
- Check for imports from domain-specific code

#### 4. Frontend Pages (frontend/app/)
For EACH page mentioned:
- Verify page exists
- Verify categorization is correct
- Check what components it uses

#### 5. Database Tables
For EACH table mentioned:
- Verify table exists in schema
- Verify categorization is correct
- Check foreign key relationships

#### 6. Skills (.claude/skills/)
For EACH skill mentioned:
- Verify skill exists
- Verify categorization is correct

#### 7. Standalone Services (services/)
For EACH service mentioned:
- Verify service exists
- Verify it's complete and can be moved

### Item Count Requirements

Based on the planning document, you should have approximately:
- ~10 backend services
- ~8 backend API routers
- ~15 frontend components
- ~5 frontend pages
- ~15 database tables
- ~5 skills
- ~2 standalone services

**MINIMUM: 50 verification items**
**EXPECTED: 60-80 verification items**

### SECOND TASK: Create verification-progress.txt

Create a progress file for session handoffs:

```
# DeVision Verification Progress

## Session 1 - INITIALIZER
Date: [timestamp]
Status: Created verification_list.json with [N] items

## Next Steps
- Begin verification starting with backend services
- Verify each component exists at stated location
- Analyze code to confirm categorization

## Categories Summary
- Backend Services: [count] items (0 verified)
- API Routers: [count] items (0 verified)
- Frontend Components: [count] items (0 verified)
- Frontend Pages: [count] items (0 verified)
- Database Tables: [count] items (0 verified)
- Skills: [count] items (0 verified)
- Standalone Services: [count] items (0 verified)
```

### THIRD TASK: Verify Portfolio-AI Path

Before creating the checklist, verify the portfolio-ai codebase is accessible:

```bash
ls -la ~/portfolio-ai/backend/app/services/ | head -10
ls -la ~/portfolio-ai/frontend/components/capabilities/
ls -la ~/portfolio-ai/.claude/skills/
```

This confirms you can access the files for verification.

### OPTIONAL: Start First Verification

If time permits, begin verifying the first few items:
1. Pick a backend service (e.g., artifact_manager.py)
2. Read the actual file content
3. Analyze if categorization (MOVE) is correct
4. Update the item status to "verified" with evidence

---

## ENDING THIS SESSION

Before your context fills up:
1. Ensure verification_list.json is complete with ALL items
2. Create verification-progress.txt
3. Commit your work:
   ```bash
   git add verification_list.json verification-progress.txt
   git commit -m "Initialize DeVision verification checklist with [N] items"
   ```

The next agent will continue verification from here.

---

**Remember:** Be thorough. Include EVERY component mentioned in the planning document. Missing items means incomplete verification.
