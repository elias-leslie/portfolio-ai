-- Migration 030: ML Model Training Metrics
-- Track model retraining history and performance

CREATE TABLE IF NOT EXISTS ml_model_metrics (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    trained_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Training data stats
    training_samples INTEGER NOT NULL,
    test_samples INTEGER NOT NULL,

    -- Performance metrics
    accuracy FLOAT NOT NULL,
    precision_score FLOAT NOT NULL,
    recall_score FLOAT NOT NULL,
    f1_score FLOAT NOT NULL,

    -- Label distribution
    useful_count INTEGER NOT NULL,
    not_useful_count INTEGER NOT NULL,

    -- Model metadata
    model_path TEXT NOT NULL,
    training_duration_seconds FLOAT,
    notes TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ml_model_metrics_name_version ON ml_model_metrics(model_name, model_version DESC);
CREATE INDEX IF NOT EXISTS idx_ml_model_metrics_trained_at ON ml_model_metrics(trained_at DESC);

COMMENT ON TABLE ml_model_metrics IS 'Tracks ML model retraining history and performance metrics';
COMMENT ON COLUMN ml_model_metrics.model_name IS 'Model identifier (e.g., article_quality)';
COMMENT ON COLUMN ml_model_metrics.model_version IS 'Version string (e.g., v1, v2, v2025-11-11)';
