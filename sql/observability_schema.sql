/*
 * Observability Schema for Project38-OR
 *
 * Based on Research Paper #08, Section 5.2 (Phase 2: Storage & Ingestion)
 *
 * This schema implements:
 * 1. TimescaleDB hypertable for high-frequency metrics
 * 2. Standard PostgreSQL table for traces (Phase 2)
 * 3. Optimized indexes for dashboard queries
 *
 * Prerequisites:
 *   - PostgreSQL 14+
 *   - TimescaleDB extension
 *
 * Usage:
 *   psql -d project38_db -f sql/observability_schema.sql
 */

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- =============================================================================
-- METRICS TABLE (Hypertable for time-series data)
-- =============================================================================

CREATE TABLE IF NOT EXISTS agent_metrics (
    time TIMESTAMPTZ NOT NULL,
    agent_id TEXT NOT NULL,
    model_id TEXT,
    metric_name TEXT NOT NULL,  -- e.g., 'token_usage', 'latency_ms', 'error_count'
    value DOUBLE PRECISION NOT NULL,
    labels JSONB  -- e.g., {'environment': 'prod', 'customer_level': 'enterprise'}
);

-- Convert to hypertable partitioned by time (1-day chunks)
-- This enables fast ingestion and automatic partitioning
SELECT create_hypertable(
    'agent_metrics',
    'time',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day'
);

-- Index for filtering by agent_id
CREATE INDEX IF NOT EXISTS idx_agent_metrics_agent_id
    ON agent_metrics (agent_id, time DESC);

-- Index for filtering by metric_name
CREATE INDEX IF NOT EXISTS idx_agent_metrics_metric_name
    ON agent_metrics (metric_name, time DESC);

-- GIN index for JSONB labels (enables queries like WHERE labels @> '{"environment": "prod"}')
CREATE INDEX IF NOT EXISTS idx_agent_metrics_labels
    ON agent_metrics USING GIN (labels);

-- Compression policy: Compress chunks older than 7 days
SELECT add_compression_policy(
    'agent_metrics',
    INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Retention policy: Drop chunks older than 90 days (optional)
-- Uncomment to enable:
-- SELECT add_retention_policy('agent_metrics', INTERVAL '90 days', if_not_exists => TRUE);

-- =============================================================================
-- TRACES TABLE (For Phase 2: detailed request tracing)
-- =============================================================================

CREATE TABLE IF NOT EXISTS agent_traces (
    trace_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    status TEXT,  -- 'success', 'error', 'timeout'
    total_tokens INT,
    total_cost DECIMAL(10, 6),
    trace_json JSONB  -- Full OTel trace structure
);

-- Index for agent_id lookups
CREATE INDEX IF NOT EXISTS idx_agent_traces_agent_id
    ON agent_traces (agent_id, start_time DESC);

-- Index for status filtering (e.g., find all errors)
CREATE INDEX IF NOT EXISTS idx_agent_traces_status
    ON agent_traces (status, start_time DESC);

-- GIN index for searching inside trace JSON
CREATE INDEX IF NOT EXISTS idx_agent_traces_json
    ON agent_traces USING GIN (trace_json);

-- =============================================================================
-- CONTINUOUS AGGREGATES (Pre-computed summaries for fast dashboard queries)
-- =============================================================================

-- Hourly aggregate: Average latency and total tokens per agent
CREATE MATERIALIZED VIEW IF NOT EXISTS agent_metrics_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    agent_id,
    metric_name,
    AVG(value) AS avg_value,
    MAX(value) AS max_value,
    MIN(value) AS min_value,
    COUNT(*) AS count
FROM agent_metrics
GROUP BY bucket, agent_id, metric_name
WITH NO DATA;

-- Refresh policy: Update hourly aggregates every 10 minutes
SELECT add_continuous_aggregate_policy(
    'agent_metrics_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '10 minutes',
    schedule_interval => INTERVAL '10 minutes',
    if_not_exists => TRUE
);

-- Daily aggregate: High-level trends for long-term analysis
CREATE MATERIALIZED VIEW IF NOT EXISTS agent_metrics_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    agent_id,
    metric_name,
    AVG(value) AS avg_value,
    SUM(value) AS sum_value,
    COUNT(*) AS count
FROM agent_metrics
GROUP BY bucket, agent_id, metric_name
WITH NO DATA;

-- Refresh policy: Update daily aggregates once per hour
SELECT add_continuous_aggregate_policy(
    'agent_metrics_daily',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Function to calculate error rate for an agent
CREATE OR REPLACE FUNCTION get_agent_error_rate(
    p_agent_id TEXT,
    p_interval INTERVAL DEFAULT '1 hour'
)
RETURNS NUMERIC AS $$
DECLARE
    error_count NUMERIC;
    total_count NUMERIC;
BEGIN
    -- Count errors
    SELECT COALESCE(SUM(value), 0) INTO error_count
    FROM agent_metrics
    WHERE agent_id = p_agent_id
      AND metric_name = 'error_count'
      AND time >= NOW() - p_interval;

    -- Count total events (errors + successes)
    SELECT COALESCE(SUM(value), 0) INTO total_count
    FROM agent_metrics
    WHERE agent_id = p_agent_id
      AND metric_name IN ('error_count', 'success_count')
      AND time >= NOW() - p_interval;

    -- Return error rate (0-100%)
    IF total_count = 0 THEN
        RETURN 0;
    ELSE
        RETURN ROUND((error_count / total_count) * 100, 2);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to get P95 latency for an agent
CREATE OR REPLACE FUNCTION get_agent_p95_latency(
    p_agent_id TEXT,
    p_interval INTERVAL DEFAULT '1 hour'
)
RETURNS NUMERIC AS $$
BEGIN
    RETURN (
        SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value)
        FROM agent_metrics
        WHERE agent_id = p_agent_id
          AND metric_name = 'latency_ms'
          AND time >= NOW() - p_interval
    );
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SAMPLE QUERIES (for dashboard development)
-- =============================================================================

-- Example 1: Get last hour's metrics for an agent
/*
SELECT
    time_bucket('5 minutes', time) AS bucket,
    metric_name,
    AVG(value) as avg_value
FROM agent_metrics
WHERE agent_id = 'agent-123'
  AND time >= NOW() - INTERVAL '1 hour'
GROUP BY bucket, metric_name
ORDER BY bucket DESC;
*/

-- Example 2: Get error rate for all agents (last hour)
/*
SELECT
    agent_id,
    get_agent_error_rate(agent_id, '1 hour') AS error_rate_pct
FROM (SELECT DISTINCT agent_id FROM agent_metrics) AS agents
ORDER BY error_rate_pct DESC;
*/

-- Example 3: Get top 10 agents by token usage (last 24 hours)
/*
SELECT
    agent_id,
    SUM(value) AS total_tokens
FROM agent_metrics
WHERE metric_name IN ('tokens_input', 'tokens_output', 'tokens_reasoning')
  AND time >= NOW() - INTERVAL '24 hours'
GROUP BY agent_id
ORDER BY total_tokens DESC
LIMIT 10;
*/

-- =============================================================================
-- GRANTS (adjust based on your security model)
-- =============================================================================

-- Grant read access to dashboard user (if using separate user)
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO dashboard_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO dashboard_user;

-- Grant write access to agent application user
-- GRANT INSERT ON agent_metrics TO agent_app_user;
-- GRANT INSERT ON agent_traces TO agent_app_user;

COMMENT ON TABLE agent_metrics IS 'High-frequency time-series metrics for AI agent observability';
COMMENT ON TABLE agent_traces IS 'Detailed trace data for debugging and analysis';
COMMENT ON FUNCTION get_agent_error_rate IS 'Calculate error rate percentage for an agent over a time interval';
COMMENT ON FUNCTION get_agent_p95_latency IS 'Calculate P95 latency for an agent over a time interval';
