-- Migration 002: Add celery_task_id column to agent_runs table
-- This allows tracking Celery background tasks for agent executions

ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS celery_task_id TEXT;
