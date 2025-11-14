-- Migration 038: Capability Notes Table (Human Strategic Context)
-- Purpose: Store human-added strategic notes and context about capabilities
-- Part of: System Capabilities Registry (Task 0059, Phase 3)
-- Created: 2025-11-13
-- Related: tasks/tasks-0059-system-capabilities-registry.md

CREATE TABLE IF NOT EXISTS capability_notes (
    id SERIAL PRIMARY KEY,
    capability_type TEXT NOT NULL,  -- 'db', 'celery', 'api', 'general'
    capability_id INTEGER,  -- FK to respective table
    insight_id INTEGER,  -- Reference to specific AI insight (optional)
    note_type TEXT NOT NULL,  -- purpose, gap_justification, priority, strategic_context, verification, known_issue
    note TEXT NOT NULL,
    created_by TEXT NOT NULL,  -- 'human' or AI agent identifier
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (insight_id) REFERENCES capability_insights(id) ON DELETE SET NULL
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_notes_capability ON capability_notes(capability_type, capability_id);
CREATE INDEX IF NOT EXISTS idx_notes_insight ON capability_notes(insight_id);
CREATE INDEX IF NOT EXISTS idx_notes_type ON capability_notes(note_type);
CREATE INDEX IF NOT EXISTS idx_notes_created_at ON capability_notes(created_at DESC);

-- Comments for documentation
COMMENT ON TABLE capability_notes IS 'Human-added strategic context and notes about system capabilities';
COMMENT ON COLUMN capability_notes.capability_type IS 'Type of capability: db, celery, api, general (not tied to specific capability)';
COMMENT ON COLUMN capability_notes.capability_id IS 'Foreign key to respective capability table (optional if note_type is general)';
COMMENT ON COLUMN capability_notes.insight_id IS 'Optional reference to related AI insight';
COMMENT ON COLUMN capability_notes.note_type IS 'Type of note: purpose, gap_justification, priority, strategic_context, verification, known_issue';
COMMENT ON COLUMN capability_notes.note IS 'Human-written note content (markdown supported)';
COMMENT ON COLUMN capability_notes.created_by IS 'Who created the note (human username or AI agent identifier)';
