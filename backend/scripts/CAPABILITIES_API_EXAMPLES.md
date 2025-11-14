# Capabilities API - Example Usage

Created: 2025-11-13

This document provides curl examples for testing the System Capabilities API endpoints.

## Base URL

```
http://localhost:8000/api/capabilities
```

## Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/capabilities` | List all capabilities (paginated) |
| GET | `/api/capabilities/{type}/{id}` | Get single capability with details |
| GET | `/api/capabilities/insights` | List all insights (paginated) |
| POST | `/api/capabilities/insights/{id}/review` | Update insight status |
| POST | `/api/capabilities/notes` | Create a new note |
| GET | `/api/capabilities/notes` | List notes (filtered) |
| POST | `/api/capabilities/scan` | Trigger manual capability scan |

---

## 1. GET /api/capabilities

List capabilities from all tables (db, celery, api) or filter by type.

### Examples

**Get all capabilities (first 5):**
```bash
curl -s "http://localhost:8000/api/capabilities?limit=5" | python3 -m json.tool
```

**Get only database capabilities:**
```bash
curl -s "http://localhost:8000/api/capabilities?type=db&limit=10" | python3 -m json.tool
```

**Get only Celery tasks:**
```bash
curl -s "http://localhost:8000/api/capabilities?type=celery" | python3 -m json.tool
```

**Get only API endpoints:**
```bash
curl -s "http://localhost:8000/api/capabilities?type=api" | python3 -m json.tool
```

**Filter by category:**
```bash
curl -s "http://localhost:8000/api/capabilities?category=portfolio&limit=10" | python3 -m json.tool
```

**Filter by freshness status (DB only):**
```bash
curl -s "http://localhost:8000/api/capabilities?type=db&status=stale" | python3 -m json.tool
```

**Pagination:**
```bash
curl -s "http://localhost:8000/api/capabilities?limit=10&offset=20" | python3 -m json.tool
```

### Response Format

```json
{
  "total": 68,
  "capabilities": [
    {
      "capability_type": "db",
      "id": 1,
      "table_name": "maintenance_log",
      "category": "infrastructure",
      "row_count": 0,
      "total_columns": 8,
      "columns": [...],
      "completeness_pct": 0,
      "freshness_status": "unknown",
      "insights_count": 0,
      "notes_count": 0,
      ...
    }
  ]
}
```

---

## 2. GET /api/capabilities/{type}/{id}

Get detailed view of a single capability with insights, notes, and dependencies.

### Examples

**Get specific database table:**
```bash
curl -s "http://localhost:8000/api/capabilities/db/1" | python3 -m json.tool
```

**Get specific Celery task:**
```bash
curl -s "http://localhost:8000/api/capabilities/celery/1" | python3 -m json.tool
```

**Get specific API endpoint:**
```bash
curl -s "http://localhost:8000/api/capabilities/api/1" | python3 -m json.tool
```

### Response Format

```json
{
  "capability": {
    "id": 1,
    "table_name": "maintenance_log",
    "category": "infrastructure",
    ...
  },
  "insights": [
    {
      "id": 1,
      "insight_type": "data_quality",
      "severity": "medium",
      "finding": "Table has no data",
      "status": "pending",
      ...
    }
  ],
  "notes": [
    {
      "id": 1,
      "note_type": "observation",
      "note": "This table is used for maintenance logging",
      "created_by": "human",
      ...
    }
  ],
  "dependencies": {
    "populates_tables": ["table1", "table2"],
    "depends_on_tasks": ["task1"]
  }
}
```

---

## 3. GET /api/capabilities/insights

List AI-generated insights about capabilities.

### Examples

**Get all insights:**
```bash
curl -s "http://localhost:8000/api/capabilities/insights" | python3 -m json.tool
```

**Filter by status:**
```bash
curl -s "http://localhost:8000/api/capabilities/insights?status=pending" | python3 -m json.tool
```

**Filter by severity:**
```bash
curl -s "http://localhost:8000/api/capabilities/insights?severity=high" | python3 -m json.tool
```

**Filter by type:**
```bash
curl -s "http://localhost:8000/api/capabilities/insights?type=data_quality" | python3 -m json.tool
```

**Combined filters:**
```bash
curl -s "http://localhost:8000/api/capabilities/insights?status=pending&severity=high&limit=10" | python3 -m json.tool
```

### Response Format

```json
{
  "total": 5,
  "insights": [
    {
      "id": 1,
      "capability_type": "db",
      "capability_id": 1,
      "table_name": "maintenance_log",
      "insight_type": "data_quality",
      "severity": "medium",
      "finding": "Table has zero rows but is expected to be daily",
      "expected_behavior": "Should have data entries",
      "actual_behavior": "Empty table",
      "impact": "Maintenance tracking not working",
      "suggested_fix": "Verify maintenance tasks are running",
      "status": "pending",
      "ai_model": "claude-sonnet-4",
      "ai_confidence": 0.85,
      "generated_at": "2025-11-13T03:15:00Z"
    }
  ]
}
```

---

## 4. POST /api/capabilities/insights/{id}/review

Update the review status of an insight (confirm, dismiss, mark in progress, or fixed).

### Examples

**Confirm an insight:**
```bash
curl -X POST "http://localhost:8000/api/capabilities/insights/1/review" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "confirmed",
    "status_reason": "Verified this is a real issue",
    "reviewed_by": "john.doe"
  }' | python3 -m json.tool
```

**Dismiss an insight:**
```bash
curl -X POST "http://localhost:8000/api/capabilities/insights/1/review" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "dismissed",
    "status_reason": "This is expected behavior for new tables",
    "reviewed_by": "jane.smith"
  }' | python3 -m json.tool
```

**Mark as in progress:**
```bash
curl -X POST "http://localhost:8000/api/capabilities/insights/1/review" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "in_progress",
    "status_reason": "Working on fix in PR #123",
    "reviewed_by": "bob.jones"
  }' | python3 -m json.tool
```

**Mark as fixed:**
```bash
curl -X POST "http://localhost:8000/api/capabilities/insights/1/review" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "fixed",
    "status_reason": "Fixed in commit abc123",
    "reviewed_by": "alice.wong"
  }' | python3 -m json.tool
```

### Response Format

```json
{
  "id": 1,
  "status": "confirmed",
  "reviewed_by": "john.doe",
  "message": "Insight 1 updated to confirmed"
}
```

---

## 5. POST /api/capabilities/notes

Create a human annotation note for a capability or insight.

### Examples

**Add observation to a database table:**
```bash
curl -X POST "http://localhost:8000/api/capabilities/notes" \
  -H "Content-Type: application/json" \
  -d '{
    "capability_type": "db",
    "capability_id": 1,
    "note_type": "observation",
    "note": "This table is used for tracking maintenance task execution"
  }' | python3 -m json.tool
```

**Add recommendation:**
```bash
curl -X POST "http://localhost:8000/api/capabilities/notes" \
  -H "Content-Type: application/json" \
  -d '{
    "capability_type": "celery",
    "capability_id": 5,
    "note_type": "recommendation",
    "note": "Consider increasing task frequency to every 30 minutes"
  }' | python3 -m json.tool
```

**Add note to an insight:**
```bash
curl -X POST "http://localhost:8000/api/capabilities/notes" \
  -H "Content-Type: application/json" \
  -d '{
    "capability_type": "db",
    "capability_id": 1,
    "insight_id": 1,
    "note_type": "decision",
    "note": "Decided to keep empty for now - will backfill in Phase 2"
  }' | python3 -m json.tool
```

**Add question:**
```bash
curl -X POST "http://localhost:8000/api/capabilities/notes" \
  -H "Content-Type: application/json" \
  -d '{
    "capability_type": "api",
    "capability_id": 3,
    "note_type": "question",
    "note": "Is this endpoint still being used by the frontend?"
  }' | python3 -m json.tool
```

**Add reference:**
```bash
curl -X POST "http://localhost:8000/api/capabilities/notes" \
  -H "Content-Type: application/json" \
  -d '{
    "capability_type": "db",
    "capability_id": 2,
    "note_type": "reference",
    "note": "See PRD #42 for context on this table design"
  }' | python3 -m json.tool
```

### Response Format

```json
{
  "id": 1,
  "message": "Note 1 created successfully"
}
```

---

## 6. GET /api/capabilities/notes

List notes with optional filtering.

### Examples

**Get all notes for a capability:**
```bash
curl -s "http://localhost:8000/api/capabilities/notes?capability_type=db&capability_id=1" | python3 -m json.tool
```

**Get all notes for an insight:**
```bash
curl -s "http://localhost:8000/api/capabilities/notes?insight_id=1" | python3 -m json.tool
```

**Get all notes for a capability type:**
```bash
curl -s "http://localhost:8000/api/capabilities/notes?capability_type=celery" | python3 -m json.tool
```

### Response Format

```json
{
  "notes": [
    {
      "id": 1,
      "capability_type": "db",
      "capability_id": 1,
      "insight_id": null,
      "note_type": "observation",
      "note": "This table is used for tracking maintenance task execution",
      "created_by": "human",
      "created_at": "2025-11-13T18:24:24.783455-05:00",
      "updated_at": null
    }
  ]
}
```

---

## 7. POST /api/capabilities/scan

Trigger a manual system capabilities scan. The scan runs asynchronously via Celery.

### Example

```bash
curl -X POST "http://localhost:8000/api/capabilities/scan" | python3 -m json.tool
```

### Response Format

```json
{
  "task_id": "40458ed3-a6ea-4d93-aae4-68af1b824eb0",
  "status": "queued",
  "message": "Capabilities scan queued with task ID: 40458ed3-a6ea-4d93-aae4-68af1b824eb0"
}
```

**Monitor task status:**
```bash
# Check Celery logs
sudo journalctl -u portfolio-celery -f | grep 40458ed3

# Or check database
psql portfolio_ai -c "SELECT * FROM celery_task_results WHERE task_id = '40458ed3-a6ea-4d93-aae4-68af1b824eb0';"
```

---

## Testing Script

Complete test script for all endpoints:

```bash
#!/bin/bash
# Save as: test_capabilities_api.sh

BASE_URL="http://localhost:8000/api/capabilities"

echo "1. List all capabilities"
curl -s "${BASE_URL}?limit=5"

echo -e "\n\n2. Get specific capability"
curl -s "${BASE_URL}/db/1"

echo -e "\n\n3. List insights"
curl -s "${BASE_URL}/insights"

echo -e "\n\n4. Create note"
curl -X POST "${BASE_URL}/notes" \
  -H "Content-Type: application/json" \
  -d '{"capability_type":"db","capability_id":1,"note_type":"observation","note":"Test note"}'

echo -e "\n\n5. List notes"
curl -s "${BASE_URL}/notes?capability_type=db&capability_id=1"

echo -e "\n\n6. Trigger scan"
curl -X POST "${BASE_URL}/scan"

echo -e "\n\nDone!"
```

---

## Interactive API Documentation

FastAPI provides interactive API documentation at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

Use these for interactive testing and to view request/response schemas.
