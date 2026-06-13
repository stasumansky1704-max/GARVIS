-- GARVIS Initial Schema Migration (001)
--
-- Creates the core tables for episodic memory, audit logging, state transitions,
-- governance checks, cognition traces, governance violations, and runtime sessions.
--
-- All primary keys use UUID. Timestamps use TIMESTAMPTZ. Flexible metadata uses JSONB.
-- This migration is idempotent: it uses IF NOT EXISTS for all objects.

-- ------------------------------------------------------------------------------
-- Episodic Memories
-- ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS episodic_memories (
    memory_id UUID PRIMARY KEY,
    session_id UUID NOT NULL,
    episode_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    provenance JSONB NOT NULL,
    governance_influences TEXT[] NOT NULL DEFAULT '{}',
    confidence DECIMAL(4,3) NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retrieval_count INT NOT NULL DEFAULT 0,
    last_accessed TIMESTAMPTZ
);

COMMENT ON TABLE episodic_memories IS 'Stores cognitive episodes with full provenance and governance context';
COMMENT ON COLUMN episodic_memories.memory_id IS 'Unique identifier for the memory';
COMMENT ON COLUMN episodic_memories.session_id IS 'Session this memory belongs to';
COMMENT ON COLUMN episodic_memories.episode_type IS 'Type: inference, reflection, retrieval, audit';
COMMENT ON COLUMN episodic_memories.content IS 'Textual content of the memory episode';
COMMENT ON COLUMN episodic_memories.provenance IS 'Full provenance record as JSONB';
COMMENT ON COLUMN episodic_memories.governance_influences IS 'Array of governance schema IDs that influenced this memory';
COMMENT ON COLUMN episodic_memories.confidence IS 'Confidence score in range [0.000, 1.000]';
COMMENT ON COLUMN episodic_memories.created_at IS 'UTC timestamp when the memory was created';
COMMENT ON COLUMN episodic_memories.retrieval_count IS 'Number of times this memory has been retrieved';
COMMENT ON COLUMN episodic_memories.last_accessed IS 'UTC timestamp of most recent retrieval';

-- ------------------------------------------------------------------------------
-- Memory Influences
-- ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memory_influences (
    influence_id UUID PRIMARY KEY,
    memory_id UUID NOT NULL REFERENCES episodic_memories(memory_id) ON DELETE CASCADE,
    inference_request_id UUID NOT NULL,
    influence_type VARCHAR(50) NOT NULL,
    strength DECIMAL(4,3) NOT NULL CHECK (strength >= 0.0 AND strength <= 1.0),
    trace_visible BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE memory_influences IS 'Tracks how memories influenced reasoning';
COMMENT ON COLUMN memory_influences.influence_id IS 'Unique identifier for this influence record';
COMMENT ON COLUMN memory_influences.memory_id IS 'Foreign key to the influencing memory';
COMMENT ON COLUMN memory_influences.inference_request_id IS 'ID of the inference request that was influenced';
COMMENT ON COLUMN memory_influences.influence_type IS 'Type: retrieval, context, constraint, warning';
COMMENT ON COLUMN memory_influences.strength IS 'Influence strength in range [0.000, 1.000]';
COMMENT ON COLUMN memory_influences.trace_visible IS 'Whether influence is visible in cognition trace';
COMMENT ON COLUMN memory_influences.created_at IS 'UTC timestamp when the influence was recorded';

-- ------------------------------------------------------------------------------
-- Audit Events
-- ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit_events (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    component VARCHAR(100) NOT NULL,
    session_id UUID,
    trace_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    details JSONB NOT NULL DEFAULT '{}',
    governance_context TEXT[] NOT NULL DEFAULT '{}'
);

COMMENT ON TABLE audit_events IS 'Immutable append-only log of auditable runtime events';
COMMENT ON COLUMN audit_events.event_id IS 'Unique identifier for this audit event';
COMMENT ON COLUMN audit_events.event_type IS 'Type: state_transition, inference, governance_check, violation, retrieval, memory_store, lifecycle';
COMMENT ON COLUMN audit_events.severity IS 'Severity: info, warning, critical';
COMMENT ON COLUMN audit_events.component IS 'Runtime component that produced the event';
COMMENT ON COLUMN audit_events.session_id IS 'Session the event belongs to (nullable for global events)';
COMMENT ON COLUMN audit_events.trace_id IS 'Cognition trace the event belongs to';
COMMENT ON COLUMN audit_events.created_at IS 'UTC timestamp when the event occurred';
COMMENT ON COLUMN audit_events.details IS 'Event-specific details as JSONB';
COMMENT ON COLUMN audit_events.governance_context IS 'Active governance schema IDs at event time';

-- ------------------------------------------------------------------------------
-- State Transitions
-- ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS state_transitions (
    transition_id UUID PRIMARY KEY,
    from_state VARCHAR(50) NOT NULL,
    to_state VARCHAR(50) NOT NULL,
    trigger_description TEXT NOT NULL,
    governance_check_passed BOOLEAN NOT NULL,
    trace_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE state_transitions IS 'Record of all operational state transitions';
COMMENT ON COLUMN state_transitions.transition_id IS 'Unique identifier for this transition';
COMMENT ON COLUMN state_transitions.from_state IS 'State before transition';
COMMENT ON COLUMN state_transitions.to_state IS 'State after transition';
COMMENT ON COLUMN state_transitions.trigger_description IS 'What caused the transition';
COMMENT ON COLUMN state_transitions.governance_check_passed IS 'Whether governance approved the transition';
COMMENT ON COLUMN state_transitions.trace_id IS 'Cognition trace this transition belongs to';
COMMENT ON COLUMN state_transitions.created_at IS 'UTC timestamp when the transition occurred';

-- ------------------------------------------------------------------------------
-- Governance Check Results
-- ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS governance_checks (
    check_id UUID PRIMARY KEY,
    schema_id VARCHAR(100) NOT NULL,
    policy_id VARCHAR(100) NOT NULL,
    passed BOOLEAN NOT NULL,
    violation JSONB,
    session_id UUID,
    trace_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE governance_checks IS 'Results of governance validation checks';
COMMENT ON COLUMN governance_checks.check_id IS 'Unique identifier for this check result';
COMMENT ON COLUMN governance_checks.schema_id IS 'Governance schema that was checked';
COMMENT ON COLUMN governance_checks.policy_id IS 'Specific policy that was evaluated';
COMMENT ON COLUMN governance_checks.passed IS 'Whether the check passed';
COMMENT ON COLUMN governance_checks.violation IS 'Violation details as JSONB if check failed';
COMMENT ON COLUMN governance_checks.session_id IS 'Session during which the check was performed';
COMMENT ON COLUMN governance_checks.trace_id IS 'Cognition trace this check belongs to';
COMMENT ON COLUMN governance_checks.created_at IS 'UTC timestamp when the check was performed';

-- ------------------------------------------------------------------------------
-- Cognition Traces
-- ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cognition_traces (
    trace_id UUID PRIMARY KEY,
    session_id UUID NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    final_state VARCHAR(50) NOT NULL DEFAULT 'uninitialized',
    metadata JSONB NOT NULL DEFAULT '{}'
);

COMMENT ON TABLE cognition_traces IS 'Complete traces of cognition sessions';
COMMENT ON COLUMN cognition_traces.trace_id IS 'Unique identifier for this cognition trace';
COMMENT ON COLUMN cognition_traces.session_id IS 'Session this trace captures';
COMMENT ON COLUMN cognition_traces.started_at IS 'UTC timestamp when the session started';
COMMENT ON COLUMN cognition_traces.ended_at IS 'UTC timestamp when the session ended';
COMMENT ON COLUMN cognition_traces.final_state IS 'Final operational state of the session';
COMMENT ON COLUMN cognition_traces.metadata IS 'Additional trace metadata as JSONB';

-- ------------------------------------------------------------------------------
-- Governance Violations
-- ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS governance_violations (
    violation_id UUID PRIMARY KEY,
    schema_id VARCHAR(100) NOT NULL,
    policy_id VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    context JSONB NOT NULL DEFAULT '{}',
    resolution TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE governance_violations IS 'Immutable records of governance policy breaches';
COMMENT ON COLUMN governance_violations.violation_id IS 'Unique identifier for this violation';
COMMENT ON COLUMN governance_violations.schema_id IS 'Governance schema that was violated';
COMMENT ON COLUMN governance_violations.policy_id IS 'Policy or constraint that was breached';
COMMENT ON COLUMN governance_violations.severity IS 'Severity: critical, warning, info';
COMMENT ON COLUMN governance_violations.description IS 'Detailed description of the violation';
COMMENT ON COLUMN governance_violations.context IS 'Snapshot of runtime state at violation time';
COMMENT ON COLUMN governance_violations.resolution IS 'Resolution status or description';
COMMENT ON COLUMN governance_violations.created_at IS 'UTC timestamp when the violation was recorded';

-- ------------------------------------------------------------------------------
-- Runtime Sessions
-- ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS runtime_sessions (
    session_id UUID PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    initial_state VARCHAR(50) NOT NULL,
    final_state VARCHAR(50),
    active_schemas TEXT[] NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}'
);

COMMENT ON TABLE runtime_sessions IS 'Runtime sessions with governance context';
COMMENT ON COLUMN runtime_sessions.session_id IS 'Unique identifier for this session';
COMMENT ON COLUMN runtime_sessions.started_at IS 'UTC timestamp when the session started';
COMMENT ON COLUMN runtime_sessions.ended_at IS 'UTC timestamp when the session ended';
COMMENT ON COLUMN runtime_sessions.initial_state IS 'Initial operational state';
COMMENT ON COLUMN runtime_sessions.final_state IS 'Final operational state';
COMMENT ON COLUMN runtime_sessions.active_schemas IS 'Array of active governance schema IDs';
COMMENT ON COLUMN runtime_sessions.metadata IS 'Additional session metadata as JSONB';

-- ------------------------------------------------------------------------------
-- Indexes
-- ------------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_memories_session ON episodic_memories(session_id);
CREATE INDEX IF NOT EXISTS idx_memories_type ON episodic_memories(episode_type);
CREATE INDEX IF NOT EXISTS idx_memories_created ON episodic_memories(created_at);
CREATE INDEX IF NOT EXISTS idx_memories_last_accessed ON episodic_memories(last_accessed);

CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_events(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at);

CREATE INDEX IF NOT EXISTS idx_transitions_trace ON state_transitions(trace_id);
CREATE INDEX IF NOT EXISTS idx_transitions_created ON state_transitions(created_at);

CREATE INDEX IF NOT EXISTS idx_checks_session ON governance_checks(session_id);
CREATE INDEX IF NOT EXISTS idx_checks_trace ON governance_checks(trace_id);
CREATE INDEX IF NOT EXISTS idx_checks_schema ON governance_checks(schema_id);

CREATE INDEX IF NOT EXISTS idx_violations_schema ON governance_violations(schema_id);
CREATE INDEX IF NOT EXISTS idx_violations_severity ON governance_violations(severity);
CREATE INDEX IF NOT EXISTS idx_violations_created ON governance_violations(created_at);

CREATE INDEX IF NOT EXISTS idx_traces_session ON cognition_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_traces_started ON cognition_traces(started_at);

CREATE INDEX IF NOT EXISTS idx_sessions_started ON runtime_sessions(started_at);

-- ------------------------------------------------------------------------------
-- Row Level Security ( preparatory -- disabled by default, enable if needed )
-- ------------------------------------------------------------------------------

ALTER TABLE episodic_memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE governance_violations ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS episodic_memories_all ON episodic_memories
    FOR ALL TO PUBLIC USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS audit_events_all ON audit_events
    FOR ALL TO PUBLIC USING (true) WITH CHECK (true);

CREATE POLICY IF NOT EXISTS governance_violations_all ON governance_violations
    FOR ALL TO PUBLIC USING (true) WITH CHECK (true);
