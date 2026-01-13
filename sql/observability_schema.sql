-- TimescaleDB Schema for AI Agent Observability
-- Based on Research Paper #08: "Real-Time Observability Dashboard for AI Agent Platforms"
-- Phase 3.5 Observability & Monitoring

-- =============================================================================
-- Hypertable: agent_metrics
-- =============================================================================

CREATE TABLE IF NOT EXISTS agent_metrics (
    time TIMESTAMPTZ NOT NULL,
    agent_id TEXT NOT NULL,
    model_id TEXT,
    metric_name TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    labels JSONB DEFAULT '{}'::JSONB
);

-- Create hypertable (partition by time)
-- Retention: 30 days for granular metrics, compressed older data
SELECT create_hypertable('agent_metrics', 'time', if_not_exists => TRUE);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_agent_metrics_agent_id ON agent_metrics (agent_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_agent_metrics_metric_name ON agent_metrics (metric_name, time DESC);
CREATE INDEX IF NOT EXISTS idx_agent_metrics_model_id ON agent_metrics (model_id, time DESC) WHERE model_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_agent_metrics_labels ON agent_metrics USING GIN (labels);

-- Enable compression (compress data older than 7 days)
ALTER TABLE agent_metrics SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'agent_id,metric_name'
);

SELECT add_compression_policy('agent_metrics', INTERVAL '7 days', if_not_exists => TRUE);

-- =============================================================================
-- Helper Functions
-- =============================================================================

-- Calculate error rate for an agent
CREATE OR REPLACE FUNCTION get_agent_error_rate(p_agent_id TEXT, p_interval TEXT)
RETURNS FLOAT AS $$
DECLARE
    error_count FLOAT;
    total_count FLOAT;
BEGIN
    -- Count errors
    SELECT COALESCE(SUM(value), 0)
    INTO error_count
    FROM agent_metrics
    WHERE agent_id = p_agent_id
      AND metric_name = 'error_count'
      AND time >= NOW() - p_interval::INTERVAL;
    
    -- Count total requests (errors + successes)
    SELECT COALESCE(SUM(value), 0)
    INTO total_count
    FROM agent_metrics
    WHERE agent_id = p_agent_id
      AND metric_name IN ('error_count', 'success_count')
      AND time >= NOW() - p_interval::INTERVAL;
    
    -- Calculate error rate percentage
    IF total_count = 0 THEN
        RETURN 0.0;
    ELSE
        RETURN ROUND((error_count / total_count) * 100, 2);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Calculate P95 latency for an agent
CREATE OR REPLACE FUNCTION get_agent_p95_latency(p_agent_id TEXT, p_interval TEXT)
RETURNS FLOAT AS $$
DECLARE
    p95_latency FLOAT;
BEGIN
    SELECT COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value), 0)
    INTO p95_latency
    FROM agent_metrics
    WHERE agent_id = p_agent_id
      AND metric_name = 'latency_ms'
      AND time >= NOW() - p_interval::INTERVAL;
    
    RETURN ROUND(p95_latency, 2);
END;
$$ LANGUAGE plpgsql;

-- Estimate cost from token usage
CREATE OR REPLACE FUNCTION estimate_cost(p_agent_id TEXT, p_interval TEXT)
RETURNS FLOAT AS $$
DECLARE
    total_tokens BIGINT;
    estimated_cost FLOAT;
BEGIN
    -- Sum all token types (input, output, reasoning)
    SELECT COALESCE(SUM(value), 0)
    INTO total_tokens
    FROM agent_metrics
    WHERE agent_id = p_agent_id
      AND metric_name IN ('tokens_input', 'tokens_output', 'tokens_reasoning')
      AND time >= NOW() - p_interval::INTERVAL;
    
    -- Simplified cost estimation: $9 per MTok average (Claude Sonnet 4.5)
    -- Real pricing: $3/MTok input + $15/MTok output = ~$9/MTok average
    estimated_cost := (total_tokens / 1000000.0) * 9.0;
    
    RETURN ROUND(estimated_cost, 4);
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Continuous Aggregates (Materialized Views)
-- =============================================================================

-- 5-minute aggregate for dashboard (fast queries)
CREATE MATERIALIZED VIEW IF NOT EXISTS agent_metrics_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    agent_id,
    metric_name,
    AVG(value) AS avg_value,
    MIN(value) AS min_value,
    MAX(value) AS max_value,
    COUNT(*) AS count
FROM agent_metrics
GROUP BY bucket, agent_id, metric_name
WITH NO DATA;

-- Refresh policy: update every 5 minutes, lag 1 minute
SELECT add_continuous_aggregate_policy('agent_metrics_5min',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE
);

-- 1-hour aggregate for historical analysis
CREATE MATERIALIZED VIEW IF NOT EXISTS agent_metrics_1hour
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    agent_id,
    metric_name,
    AVG(value) AS avg_value,
    MIN(value) AS min_value,
    MAX(value) AS max_value,
    SUM(value) AS sum_value,
    COUNT(*) AS count
FROM agent_metrics
GROUP BY bucket, agent_id, metric_name
WITH NO DATA;

-- Refresh policy: update every hour
SELECT add_continuous_aggregate_policy('agent_metrics_1hour',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- =============================================================================
-- Retention Policy
-- =============================================================================

-- Drop raw data older than 30 days (continuous aggregates preserve historical data)
SELECT add_retention_policy('agent_metrics', INTERVAL '30 days', if_not_exists => TRUE);

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE agent_metrics IS 'Time-series metrics for AI agent observability (OpenTelemetry GenAI v1.37+)';
COMMENT ON COLUMN agent_metrics.time IS 'Metric timestamp (hypertable partition key)';
COMMENT ON COLUMN agent_metrics.agent_id IS 'Unique agent identifier';
COMMENT ON COLUMN agent_metrics.model_id IS 'LLM model used (e.g., claude-sonnet-4.5, gpt-4-turbo)';
COMMENT ON COLUMN agent_metrics.metric_name IS 'Metric name (latency_ms, tokens_input, tokens_output, tokens_reasoning, error_count, success_count)';
COMMENT ON COLUMN agent_metrics.value IS 'Metric value (numeric)';
COMMENT ON COLUMN agent_metrics.labels IS 'Additional metadata (JSONB, e.g., {"task": "search", "environment": "prod"})';

COMMENT ON FUNCTION get_agent_error_rate IS 'Calculate error rate percentage for an agent over specified interval';
COMMENT ON FUNCTION get_agent_p95_latency IS 'Calculate P95 latency (95th percentile) for an agent over specified interval';
COMMENT ON FUNCTION estimate_cost IS 'Estimate dollar cost from token usage ($9/MTok average for Claude Sonnet 4.5)';
