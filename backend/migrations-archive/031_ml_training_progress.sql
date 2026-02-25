-- Migration 031: ML Training Progress Tracking
-- Track real-time progress for manual training runs

CREATE TABLE IF NOT EXISTS ml_training_progress (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(50) UNIQUE NOT NULL,
    status VARCHAR(50) NOT NULL, -- querying, labeling, training, complete, failed
    current_step VARCHAR(200),
    progress_percent INTEGER DEFAULT 0,

    -- Progress details
    articles_found INTEGER DEFAULT 0,
    articles_labeled INTEGER DEFAULT 0,
    articles_total INTEGER DEFAULT 0,

    -- Timestamps
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,

    -- Results (when complete)
    model_version VARCHAR(50),
    accuracy FLOAT,
    error_message TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ml_training_progress_session ON ml_training_progress(session_id);
CREATE INDEX IF NOT EXISTS idx_ml_training_progress_status ON ml_training_progress(status);

COMMENT ON TABLE ml_training_progress IS 'Real-time progress tracking for manual ML training runs';
COMMENT ON COLUMN ml_training_progress.session_id IS 'Unique session ID for this training run';
COMMENT ON COLUMN ml_training_progress.status IS 'Current status: querying, labeling, training, complete, failed';
