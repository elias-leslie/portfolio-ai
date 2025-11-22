# Task List: Autonomous AI Agent Scheduling at 03:30 UTC

**Source**: User request via /task_it - VISION.md Gap Analysis Priority #1
**Complexity**: Simple
**Effort**: LOW (30 minutes)
**Environment**: Local Dev
**Created**: 2025-11-22 14:15

---

## Summary

**Goal**: Enable autonomous daily execution of Discovery Agent and Portfolio Analyzer Agent at 03:30 UTC to fulfill VISION.md requirement: "Agents generate ideas autonomously on schedule (daily at 03:30 UTC)"

**Approach**: Add both agents to Celery beat schedule in `backend/app/celery_schedules.py`. Agents are fully implemented (`discovery.py` 128L, `portfolio_analyzer.py` 142L) but not currently scheduled. This is a 5-line configuration change plus testing.

**Scope Discovery**: Not needed (single file, known location)

---

## Tasks

### 1.0 Add Discovery Agent to Celery Beat Schedule

- [ ] 1.1 Open `backend/app/celery_schedules.py`
- [ ] 1.2 Add Discovery Agent schedule entry after line 383:
  ```python
  "run-discovery-agent-daily": {
      "task": "run_discovery_agent",
      "schedule": crontab(hour=3, minute=30),  # Daily at 03:30 UTC
      "options": {"expires": 1800},  # 30-minute expiry
  },
  ```
- [ ] 1.3 Verify task name matches `backend/app/tasks/agent_tasks.py` definition

### 2.0 Add Portfolio Analyzer to Celery Beat Schedule

- [ ] 2.1 Add Portfolio Analyzer schedule entry after Discovery Agent:
  ```python
  "run-portfolio-analyzer-daily": {
      "task": "run_portfolio_analyzer",
      "schedule": crontab(hour=3, minute=30),  # Daily at 03:30 UTC
      "options": {"expires": 1800},  # 30-minute expiry
  },
  ```
- [ ] 2.2 Verify task name matches `backend/app/tasks/agent_tasks.py` definition

### 3.0 Restart Services and Verify Schedule

- [ ] 3.1 Restart Celery beat service:
  ```bash
  bash ~/portfolio-ai/scripts/restart.sh
  ```
- [ ] 3.2 Verify beat schedule includes new tasks:
  ```bash
  cd ~/portfolio-ai/backend && source .venv/bin/activate && celery -A app.celery_app inspect scheduled
  ```
- [ ] 3.3 Check Celery logs for schedule registration:
  ```bash
  tail -50 /var/log/portfolio-ai/celery-beat.log
  ```

### 4.0 Manual Test Execution (Validate Before Waiting for 03:30)

- [ ] 4.1 Manually trigger Discovery Agent:
  ```bash
  cd ~/portfolio-ai/backend && source .venv/bin/activate && celery -A app.celery_app call app.tasks.agent_tasks.run_discovery_agent
  ```
- [ ] 4.2 Verify agent execution in database:
  ```bash
  cd ~/portfolio-ai/backend && source .venv/bin/activate && python -c "from app.storage import get_storage; storage = get_storage(); df = storage.query('SELECT * FROM agent_runs ORDER BY created_at DESC LIMIT 5'); print(df)"
  ```
- [ ] 4.3 Manually trigger Portfolio Analyzer:
  ```bash
  cd ~/portfolio-ai/backend && source .venv/bin/activate && celery -A app.celery_app call app.tasks.agent_tasks.run_portfolio_analyzer
  ```
- [ ] 4.4 Verify both agents created ideas in `agent_ideas` table
- [ ] 4.5 Check agent run status (should be "complete" not "failed")

### 5.0 Documentation and Verification

- [ ] 5.1 Update `docs/core/OPERATIONS.md` with new scheduled tasks
  - Add to "Scheduled Tasks" section
  - Document: "Discovery Agent and Portfolio Analyzer run daily at 03:30 UTC"
- [ ] 5.2 Verify VISION.md compliance:
  - ✅ "Agents generate ideas autonomously on schedule (daily at 03:30 UTC)" - NOW TRUE
- [ ] 5.3 Wait for next 03:30 UTC execution (or manually trigger for immediate validation)
- [ ] 5.4 Confirm ideas appear in `/api/ideas` endpoint

---

## Verification

- [ ] Functional: Both agents scheduled in Celery beat
- [ ] Execution: Manual test runs complete successfully
- [ ] Database: agent_runs and agent_ideas tables populated
- [ ] Schedule: Celery inspect shows 03:30 UTC cron entries
- [ ] Services: Celery beat restarted and running
- [ ] Docs: OPERATIONS.md updated with new schedules
- [ ] VISION: "Autonomous on schedule" requirement fulfilled

---

## Technical Notes

**Existing Infrastructure:**
- Discovery Agent: `backend/app/agents/discovery.py` (128 lines)
- Portfolio Analyzer: `backend/app/agents/portfolio_analyzer.py` (142 lines)
- Task definitions: `backend/app/tasks/agent_tasks.py` (run_discovery_agent, run_portfolio_analyzer)
- Database tables: agent_runs, agent_ideas (fully implemented)
- API endpoint: `/api/ideas` (working)

**Current Gap:**
- Celery beat schedule at line 371-383 runs `daily-gap-analysis-workflow` at 03:30 UTC
- This analyzes data gaps, NOT generates investment ideas
- Discovery + Portfolio Analyzer need separate schedule entries

**Expected Behavior After Fix:**
- 03:30 UTC daily: Discovery Agent scans news/economic data → generates 5 general ideas
- 03:30 UTC daily: Portfolio Analyzer reviews user portfolio → generates 5 personalized ideas
- Ideas stored in database, visible via `/api/ideas` endpoint
- Autonomous execution without manual intervention

**Verification Commands:**
```bash
# Check beat schedule
cd ~/portfolio-ai/backend && source .venv/bin/activate && celery -A app.celery_app inspect scheduled

# Check recent agent runs
cd ~/portfolio-ai/backend && source .venv/bin/activate && python -c "from app.storage import get_storage; storage = get_storage(); print(storage.query('SELECT * FROM agent_runs ORDER BY created_at DESC LIMIT 10'))"

# Check generated ideas
cd ~/portfolio-ai/backend && source .venv/bin/activate && python -c "from app.storage import get_storage; storage = get_storage(); print(storage.query('SELECT * FROM agent_ideas ORDER BY created_at DESC LIMIT 10'))"
```
