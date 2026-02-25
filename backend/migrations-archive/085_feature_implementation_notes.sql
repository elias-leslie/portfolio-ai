-- Migration: Add implementation_notes JSONB field to feature_capabilities
-- Purpose: Store detailed implementation context (steps, files, examples, blockers)
-- This field replaces task markdown files with structured in-DB storage

ALTER TABLE feature_capabilities
ADD COLUMN IF NOT EXISTS implementation_notes JSONB DEFAULT '{}';

COMMENT ON COLUMN feature_capabilities.implementation_notes IS
'Structured implementation details for replacing task markdown files.
Schema:
{
  "steps": ["Step 1: ...", "Step 2: ..."],
  "files": ["path/to/file.py", "path/to/other.tsx"],
  "examples": {"code": "...", "description": "..."},
  "blockers": ["Blocker 1", "Blocker 2"],
  "notes": "Free-form notes",
  "context": "Background/motivation"
}';

-- Add index for JSONB queries if needed
CREATE INDEX IF NOT EXISTS idx_feature_capabilities_implementation_notes
ON feature_capabilities USING GIN (implementation_notes);
