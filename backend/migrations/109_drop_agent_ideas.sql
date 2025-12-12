-- Migration 109: Drop deprecated agent_ideas table
-- Ideas system replaced by Strategy Seed Pipeline (FEAT-218)

-- Drop the deprecated table
DROP TABLE IF EXISTS agent_ideas CASCADE;

-- Remove from table_registry if exists
DELETE FROM table_registry WHERE table_name = 'agent_ideas';
