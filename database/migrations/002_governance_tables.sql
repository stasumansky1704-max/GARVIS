-- GARVIS Governance Tables Migration (002)
--
-- Creates additional tables for governance metadata:
--   - governance_schema_registry: tracks loaded and active governance schemas
--   - governance_policy_log: records every policy evaluation with full context
--   - runtime_configuration: key-value runtime configuration store
--
-- This migration depends on 001_initial_schema.sql and is idempotent.

-- ------------------------------------------------------------------------------
-- Governance Schema Registry
-- ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS governance_schema_registry (
    schema_id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    category VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    policies JSONB NOT NULL DEFAULT '[]',
    constraints JSONB NOT NULL DEFAULT '[]',
    fail_closed BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at TIMESTAMPTZ,
    deactivated_at TIMESTAMPTZ,
    checksum VARCHAR(64)  -- SHA-256 of the schema file for integrity verification
);

COMMENT ON TABLE governance_schema_registry IS 'Registry of all loaded governance schemas with activation state';
COMMENT ON COLUMN governance_schema_registry.schema_id IS 'Unique schema identifier, e.g. uncertainty_management';
COMMENT ON COLUMN governance_schema_registry.name IS 'Human-readable schema name';
COMMENT ON COLUMN governance_schema_registry.version IS 'Schema version, e.g. 1.0.0';
COMMENT ON COLUMN governance_schema_registry.category IS 'Category: epistemic, operational, boundary, ethical';
COMMENT ON COLUMN governance_schema_registry.description IS 'Detailed description of what the schema governs';
COMMENT ON COLUMN governance_schema_registry.policies IS 'Serialized array of governance policies as JSONB';
COMMENT ON COLUMN governance_schema_registry.constraints IS 'Serialized array of governance constraints as JSONB';
COMMENT ON COLUMN governance_schema_registry.fail_closed IS 'Whether schema violations trigger fail-closed halt';
COMMENT ON COLUMN governance_schema_registry.is_active IS 'Whether the schema is currently active and enforced';
COMMENT ON COLUMN governance_schema_registry.loaded_at IS 'UTC timestamp when the schema was loaded';
COMMENT ON COLUMN governance_schema_registry.activated_at IS 'UTC timestamp when the schema was activated';
COMMENT ON COLUMN governance_schema_registry.deactivated_at IS 'UTC timestamp when the schema was deactivated';
COMMENT ON COLUMN governance_schema_registry.checksum IS 'SHA-256 checksum of the source schema file';

-- ------------------------------------------------------------------------------
-- Governance Policy Log
-- ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS governance_policy_log (
    log_id UUID PRIMARY KEY,
    schema_id VARCHAR(100) NOT NULL,
    policy_id VARCHAR(100) NOT NULL,
    policy_version VARCHAR(50),  -- version of the policy at evaluation time
    rule_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id UUID,
    trace_id UUID NOT NULL,
    passed BOOLEAN NOT NULL,
    input_context JSONB NOT NULL DEFAULT '{}',
    output_context JSONB NOT NULL DEFAULT '{}',
    violation_id UUID REFERENCES governance_violations(violation_id) ON DELETE SET NULL,
    evaluation_duration_ms INT,  -- how long the evaluation took
    remediation_triggered BOOLEAN NOT NULL DEFAULT FALSE,
    remediation_action VARCHAR(100),
    notes TEXT
);

COMMENT ON TABLE governance_policy_log IS 'Immutable log of every policy evaluation';
COMMENT ON COLUMN governance_policy_log.log_id IS 'Unique identifier for this log entry';
COMMENT ON COLUMN governance_policy_log.schema_id IS 'Schema containing the evaluated policy';
COMMENT ON COLUMN governance_policy_log.policy_id IS 'Policy that was evaluated';
COMMENT ON COLUMN governance_policy_log.policy_version IS 'Version of the policy at evaluation time';
COMMENT ON COLUMN governance_policy_log.rule_type IS 'Type: threshold, prohibition, requirement, constraint';
COMMENT ON COLUMN governance_policy_log.severity IS 'Severity: critical, warning, info';
COMMENT ON COLUMN governance_policy_log.evaluated_at IS 'UTC timestamp when the evaluation occurred';
COMMENT ON COLUMN governance_policy_log.session_id IS 'Session during which the evaluation occurred';
COMMENT ON COLUMN governance_policy_log.trace_id IS 'Cognition trace the evaluation belongs to';
COMMENT ON COLUMN governance_policy_log.passed IS 'Whether the policy evaluation passed';
COMMENT ON COLUMN governance_policy_log.input_context IS 'Input context provided to the evaluator as JSONB';
COMMENT ON COLUMN governance_policy_log.output_context IS 'Output/decision from the evaluator as JSONB';
COMMENT ON COLUMN governance_policy_log.violation_id IS 'Foreign key to violation if one was recorded';
COMMENT ON COLUMN governance_policy_log.evaluation_duration_ms IS 'Duration of policy evaluation in milliseconds';
COMMENT ON COLUMN governance_policy_log.remediation_triggered IS 'Whether auto-remediation was triggered';
COMMENT ON COLUMN governance_policy_log.remediation_action IS 'Action taken by auto-remediation if triggered';
COMMENT ON COLUMN governance_policy_log.notes IS 'Additional operator notes';

-- ------------------------------------------------------------------------------
-- Runtime Configuration
-- ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS runtime_configuration (
    config_key VARCHAR(255) PRIMARY KEY,
    config_value JSONB NOT NULL,
    description TEXT,
    is_sensitive BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by VARCHAR(100)  -- component or operator that last updated the value
);

COMMENT ON TABLE runtime_configuration IS 'Key-value runtime configuration store';
COMMENT ON COLUMN runtime_configuration.config_key IS 'Unique configuration key';
COMMENT ON COLUMN runtime_configuration.config_value IS 'Configuration value as JSONB for type flexibility';
COMMENT ON COLUMN runtime_configuration.description IS 'Human-readable description of the configuration';
COMMENT ON COLUMN runtime_configuration.is_sensitive IS 'Whether the value contains sensitive data';
COMMENT ON COLUMN runtime_configuration.created_at IS 'UTC timestamp when the config was created';
COMMENT ON COLUMN runtime_configuration.updated_at IS 'UTC timestamp when the config was last updated';
COMMENT ON COLUMN runtime_configuration.updated_by IS 'Component or operator that last updated the value';

-- ------------------------------------------------------------------------------
-- Indexes
-- ------------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_schema_registry_active ON governance_schema_registry(is_active);
CREATE INDEX IF NOT EXISTS idx_schema_registry_category ON governance_schema_registry(category);
CREATE INDEX IF NOT EXISTS idx_schema_registry_loaded ON governance_schema_registry(loaded_at);

CREATE INDEX IF NOT EXISTS idx_policy_log_schema ON governance_policy_log(schema_id);
CREATE INDEX IF NOT EXISTS idx_policy_log_policy ON governance_policy_log(policy_id);
CREATE INDEX IF NOT EXISTS idx_policy_log_session ON governance_policy_log(session_id);
CREATE INDEX IF NOT EXISTS idx_policy_log_trace ON governance_policy_log(trace_id);
CREATE INDEX IF NOT EXISTS idx_policy_log_evaluated ON governance_policy_log(evaluated_at);
CREATE INDEX IF NOT EXISTS idx_policy_log_passed ON governance_policy_log(passed);
CREATE INDEX IF NOT EXISTS idx_policy_log_severity ON governance_policy_log(severity);

CREATE INDEX IF NOT EXISTS idx_runtime_config_sensitive ON runtime_configuration(is_sensitive);

-- ------------------------------------------------------------------------------
-- Trigger for automatic updated_at on runtime_configuration
-- ------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION update_runtime_config_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_runtime_config_updated ON runtime_configuration;
CREATE TRIGGER trigger_runtime_config_updated
    BEFORE UPDATE ON runtime_configuration
    FOR EACH ROW
    EXECUTE FUNCTION update_runtime_config_timestamp();

-- ------------------------------------------------------------------------------
-- Default runtime configuration values
-- ------------------------------------------------------------------------------

INSERT INTO runtime_configuration (config_key, config_value, description, is_sensitive)
VALUES
    ('inference.default_temperature', '"0.7"'::JSONB, 'Default temperature for LLM inference', FALSE),
    ('inference.default_max_tokens', '"2048"'::JSONB, 'Default maximum tokens for LLM responses', FALSE),
    ('inference.timeout_seconds', '"120"'::JSONB, 'Timeout for LLM inference calls', FALSE),
    ('inference.max_retries', '"3"'::JSONB, 'Maximum retries for failed inference calls', FALSE),
    ('audit.buffer_size', '"100"'::JSONB, 'Number of audit events to buffer before flush', FALSE),
    ('audit.flush_interval_seconds', '"5"'::JSONB, 'Interval between audit buffer flushes', FALSE),
    ('governance.auto_remediation_enabled', '"false"'::JSONB, 'Whether auto-remediation is globally enabled', FALSE),
    ('memory.max_retrieval_results', '"10"'::JSONB, 'Maximum number of memories to retrieve per query', FALSE),
    ('trace.include_raw_responses', '"false"'::JSONB, 'Whether to include raw LLM responses in traces', FALSE)
ON CONFLICT (config_key) DO NOTHING;
