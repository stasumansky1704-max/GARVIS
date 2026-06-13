"""
Parameterized SQL query definitions for GARVIS.

All queries use asyncpg-compatible parameter placeholders ($1, $2, ...).
Queries are organized by domain: memory, audit, state transitions, governance,
traces, and sessions.

These constants are imported and used by the respective runtime components
(EpisodicMemoryStore, AuditPipeline, CognitiveStateMachine, etc.).
"""

# =============================================================================
# Episodic Memory Queries
# =============================================================================

MEMORY_INSERT = """
    INSERT INTO episodic_memories (
        memory_id, session_id, episode_type, content, provenance,
        governance_influences, confidence, created_at, retrieval_count, last_accessed
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
"""
"""Insert a new episodic memory. Parameters: memory_id, session_id, episode_type,
content, provenance(JSONB), governance_influences, confidence, created_at,
retrieval_count, last_accessed."""

MEMORY_GET_BY_ID = """
    SELECT
        memory_id, session_id, episode_type, content, provenance,
        governance_influences, confidence, created_at, retrieval_count, last_accessed
    FROM episodic_memories
    WHERE memory_id = $1
"""
"""Retrieve a single memory by its UUID. Parameter: memory_id."""

MEMORY_GET_BY_SESSION = """
    SELECT
        memory_id, session_id, episode_type, content, provenance,
        governance_influences, confidence, created_at, retrieval_count, last_accessed
    FROM episodic_memories
    WHERE session_id = $1
    ORDER BY created_at DESC
"""
"""Retrieve all memories for a session, newest first. Parameter: session_id."""

MEMORY_GET_BY_SESSION_LIMIT = """
    SELECT
        memory_id, session_id, episode_type, content, provenance,
        governance_influences, confidence, created_at, retrieval_count, last_accessed
    FROM episodic_memories
    WHERE session_id = $1
    ORDER BY created_at DESC
    LIMIT $2
"""
"""Retrieve memories for a session with a limit. Parameters: session_id, limit."""

MEMORY_GET_BY_TYPE = """
    SELECT
        memory_id, session_id, episode_type, content, provenance,
        governance_influences, confidence, created_at, retrieval_count, last_accessed
    FROM episodic_memories
    WHERE session_id = $1 AND episode_type = $2
    ORDER BY created_at DESC
    LIMIT $3
"""
"""Retrieve memories by session and episode type. Parameters: session_id, episode_type, limit."""

MEMORY_UPDATE_RETRIEVAL = """
    UPDATE episodic_memories
    SET retrieval_count = retrieval_count + 1,
        last_accessed = $2
    WHERE memory_id = $1
"""
"""Increment retrieval count and update last_accessed. Parameters: memory_id, accessed_at."""

MEMORY_DELETE = """
    DELETE FROM episodic_memories WHERE memory_id = $1
"""
"""Delete a memory by ID. Parameter: memory_id."""

MEMORY_SEARCH_BY_CONTENT = """
    SELECT
        memory_id, session_id, episode_type, content, provenance,
        governance_influences, confidence, created_at, retrieval_count, last_accessed
    FROM episodic_memories
    WHERE session_id = $1 AND content ILIKE $2
    ORDER BY created_at DESC
    LIMIT $3
"""
"""Search memories by content pattern (case-insensitive). Parameters: session_id, pattern, limit."""

# =============================================================================
# Memory Influence Queries
# =============================================================================

INFLUENCE_INSERT = """
    INSERT INTO memory_influences (
        influence_id, memory_id, inference_request_id, influence_type,
        strength, trace_visible, created_at
    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
"""
"""Insert a memory influence record. Parameters: influence_id, memory_id,
inference_request_id, influence_type, strength, trace_visible, created_at."""

INFLUENCE_GET_BY_MEMORY = """
    SELECT
        influence_id, memory_id, inference_request_id, influence_type,
        strength, trace_visible, created_at
    FROM memory_influences
    WHERE memory_id = $1
    ORDER BY created_at DESC
"""
"""Retrieve all influences for a specific memory. Parameter: memory_id."""

INFLUENCE_GET_BY_INFERENCE = """
    SELECT
        influence_id, memory_id, inference_request_id, influence_type,
        strength, trace_visible, created_at
    FROM memory_influences
    WHERE inference_request_id = $1
    ORDER BY created_at DESC
"""
"""Retrieve all influences for a specific inference request. Parameter: inference_request_id."""

# =============================================================================
# Audit Event Queries
# =============================================================================

AUDIT_INSERT = """
    INSERT INTO audit_events (
        event_id, event_type, severity, component, session_id,
        trace_id, created_at, details, governance_context
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
"""
"""Insert an audit event. Parameters: event_id, event_type, severity, component,
session_id, trace_id, created_at, details(JSONB), governance_context."""

AUDIT_GET_BY_SESSION = """
    SELECT
        event_id, event_type, severity, component, session_id,
        trace_id, created_at, details, governance_context
    FROM audit_events
    WHERE session_id = $1
    ORDER BY created_at DESC
    LIMIT $2
"""
"""Retrieve audit events for a session. Parameters: session_id, limit."""

AUDIT_GET_BY_TRACE = """
    SELECT
        event_id, event_type, severity, component, session_id,
        trace_id, created_at, details, governance_context
    FROM audit_events
    WHERE trace_id = $1
    ORDER BY created_at ASC
"""
"""Retrieve audit events for a trace in chronological order. Parameter: trace_id."""

AUDIT_GET_BY_TYPE = """
    SELECT
        event_id, event_type, severity, component, session_id,
        trace_id, created_at, details, governance_context
    FROM audit_events
    WHERE event_type = $1
    ORDER BY created_at DESC
    LIMIT $2
"""
"""Retrieve audit events by type. Parameters: event_type, limit."""

AUDIT_GET_BY_SEVERITY = """
    SELECT
        event_id, event_type, severity, component, session_id,
        trace_id, created_at, details, governance_context
    FROM audit_events
    WHERE severity = $1
    ORDER BY created_at DESC
    LIMIT $2
"""
"""Retrieve audit events by severity. Parameters: severity, limit."""

AUDIT_GET_SINCE = """
    SELECT
        event_id, event_type, severity, component, session_id,
        trace_id, created_at, details, governance_context
    FROM audit_events
    WHERE created_at > $1
    ORDER BY created_at DESC
    LIMIT $2
"""
"""Retrieve audit events since a given timestamp. Parameters: since(TIMESTAMPTZ), limit."""

AUDIT_GET_BY_COMPONENT = """
    SELECT
        event_id, event_type, severity, component, session_id,
        trace_id, created_at, details, governance_context
    FROM audit_events
    WHERE component = $1
    ORDER BY created_at DESC
    LIMIT $2
"""
"""Retrieve audit events by component. Parameters: component, limit."""

# =============================================================================
# State Transition Queries
# =============================================================================

TRANSITION_INSERT = """
    INSERT INTO state_transitions (
        transition_id, from_state, to_state, trigger_description,
        governance_check_passed, trace_id, created_at
    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
"""
"""Insert a state transition record. Parameters: transition_id, from_state, to_state,
trigger_description, governance_check_passed, trace_id, created_at."""

TRANSITION_GET_BY_TRACE = """
    SELECT
        transition_id, from_state, to_state, trigger_description,
        governance_check_passed, trace_id, created_at
    FROM state_transitions
    WHERE trace_id = $1
    ORDER BY created_at ASC
"""
"""Retrieve all state transitions for a trace in chronological order. Parameter: trace_id."""

TRANSITION_GET_LATEST = """
    SELECT
        transition_id, from_state, to_state, trigger_description,
        governance_check_passed, trace_id, created_at
    FROM state_transitions
    WHERE trace_id = $1
    ORDER BY created_at DESC
    LIMIT 1
"""
"""Retrieve the most recent state transition for a trace. Parameter: trace_id."""

# =============================================================================
# Governance Check Queries
# =============================================================================

GOVERNANCE_CHECK_INSERT = """
    INSERT INTO governance_checks (
        check_id, schema_id, policy_id, passed, violation,
        session_id, trace_id, created_at
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
"""
"""Insert a governance check result. Parameters: check_id, schema_id, policy_id,
passed, violation(JSONB), session_id, trace_id, created_at."""

GOVERNANCE_CHECK_GET_BY_TRACE = """
    SELECT
        check_id, schema_id, policy_id, passed, violation,
        session_id, trace_id, created_at
    FROM governance_checks
    WHERE trace_id = $1
    ORDER BY created_at DESC
"""
"""Retrieve governance checks for a trace. Parameter: trace_id."""

GOVERNANCE_CHECK_GET_BY_SESSION = """
    SELECT
        check_id, schema_id, policy_id, passed, violation,
        session_id, trace_id, created_at
    FROM governance_checks
    WHERE session_id = $1
    ORDER BY created_at DESC
"""
"""Retrieve governance checks for a session. Parameter: session_id."""

GOVERNANCE_CHECK_GET_FAILED = """
    SELECT
        check_id, schema_id, policy_id, passed, violation,
        session_id, trace_id, created_at
    FROM governance_checks
    WHERE passed = FALSE
    ORDER BY created_at DESC
    LIMIT $1
"""
"""Retrieve the most recent failed governance checks. Parameter: limit."""

GOVERNANCE_CHECK_GET_BY_SCHEMA = """
    SELECT
        check_id, schema_id, policy_id, passed, violation,
        session_id, trace_id, created_at
    FROM governance_checks
    WHERE schema_id = $1
    ORDER BY created_at DESC
    LIMIT $2
"""
"""Retrieve governance checks for a schema. Parameters: schema_id, limit."""

# =============================================================================
# Governance Violation Queries
# =============================================================================

VIOLATION_INSERT = """
    INSERT INTO governance_violations (
        violation_id, schema_id, policy_id, severity, description,
        context, resolution, created_at
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
"""
"""Insert a governance violation record. Parameters: violation_id, schema_id, policy_id,
severity, description, context(JSONB), resolution, created_at."""

VIOLATION_GET_BY_SCHEMA = """
    SELECT
        violation_id, schema_id, policy_id, severity, description,
        context, resolution, created_at
    FROM governance_violations
    WHERE schema_id = $1
    ORDER BY created_at DESC
    LIMIT $2
"""
"""Retrieve violations for a schema. Parameters: schema_id, limit."""

VIOLATION_GET_BY_SEVERITY = """
    SELECT
        violation_id, schema_id, policy_id, severity, description,
        context, resolution, created_at
    FROM governance_violations
    WHERE severity = $1
    ORDER BY created_at DESC
    LIMIT $2
"""
"""Retrieve violations by severity. Parameters: severity, limit."""

VIOLATION_GET_UNRESOLVED = """
    SELECT
        violation_id, schema_id, policy_id, severity, description,
        context, resolution, created_at
    FROM governance_violations
    WHERE resolution IS NULL
    ORDER BY created_at DESC
"""
"""Retrieve all unresolved violations."""

VIOLATION_UPDATE_RESOLUTION = """
    UPDATE governance_violations
    SET resolution = $2
    WHERE violation_id = $1
"""
"""Update the resolution of a violation. Parameters: violation_id, resolution."""

VIOLATION_GET_SUMMARY = """
    SELECT
        severity,
        COUNT(*) AS count,
        COUNT(*) FILTER (WHERE resolution IS NULL) AS unresolved_count,
        MAX(created_at) AS latest_occurrence
    FROM governance_violations
    WHERE ($1::TIMESTAMPTZ IS NULL OR created_at > $1)
    GROUP BY severity
    ORDER BY severity
"""
"""Get violation summary grouped by severity. Parameter: since(TIMESTAMPTZ, nullable)."""

# =============================================================================
# Cognition Trace Queries
# =============================================================================

TRACE_INSERT = """
    INSERT INTO cognition_traces (
        trace_id, session_id, started_at, ended_at, final_state, metadata
    ) VALUES ($1, $2, $3, $4, $5, $6)
"""
"""Insert a cognition trace. Parameters: trace_id, session_id, started_at,
ended_at, final_state, metadata(JSONB)."""

TRACE_GET_BY_ID = """
    SELECT
        trace_id, session_id, started_at, ended_at, final_state, metadata
    FROM cognition_traces
    WHERE trace_id = $1
"""
"""Retrieve a trace by ID. Parameter: trace_id."""

TRACE_GET_BY_SESSION = """
    SELECT
        trace_id, session_id, started_at, ended_at, final_state, metadata
    FROM cognition_traces
    WHERE session_id = $1
    ORDER BY started_at DESC
"""
"""Retrieve all traces for a session. Parameter: session_id."""

TRACE_UPDATE_END = """
    UPDATE cognition_traces
    SET ended_at = $2, final_state = $3
    WHERE trace_id = $1
"""
"""Finalize a trace with end time and final state. Parameters: trace_id, ended_at, final_state."""

TRACE_GET_ACTIVE = """
    SELECT
        trace_id, session_id, started_at, ended_at, final_state, metadata
    FROM cognition_traces
    WHERE ended_at IS NULL
    ORDER BY started_at DESC
"""
"""Retrieve all active (not yet ended) traces."""

# =============================================================================
# Runtime Session Queries
# =============================================================================

SESSION_INSERT = """
    INSERT INTO runtime_sessions (
        session_id, started_at, ended_at, initial_state, final_state,
        active_schemas, metadata
    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
"""
"""Insert a runtime session. Parameters: session_id, started_at, ended_at,
initial_state, final_state, active_schemas, metadata(JSONB)."""

SESSION_GET_BY_ID = """
    SELECT
        session_id, started_at, ended_at, initial_state, final_state,
        active_schemas, metadata
    FROM runtime_sessions
    WHERE session_id = $1
"""
"""Retrieve a session by ID. Parameter: session_id."""

SESSION_GET_ACTIVE = """
    SELECT
        session_id, started_at, ended_at, initial_state, final_state,
        active_schemas, metadata
    FROM runtime_sessions
    WHERE ended_at IS NULL
    ORDER BY started_at DESC
"""
"""Retrieve all active (not yet ended) sessions."""

SESSION_UPDATE_END = """
    UPDATE runtime_sessions
    SET ended_at = $2, final_state = $3, active_schemas = $4
    WHERE session_id = $1
"""
"""Finalize a session. Parameters: session_id, ended_at, final_state, active_schemas."""

SESSION_UPDATE_SCHEMAS = """
    UPDATE runtime_sessions
    SET active_schemas = $2
    WHERE session_id = $1
"""
"""Update active schemas for a session. Parameters: session_id, active_schemas."""

SESSION_GET_ALL = """
    SELECT
        session_id, started_at, ended_at, initial_state, final_state,
        active_schemas, metadata
    FROM runtime_sessions
    ORDER BY started_at DESC
    LIMIT $1
"""
"""Retrieve all sessions with a limit. Parameter: limit."""

SESSION_GET_SINCE = """
    SELECT
        session_id, started_at, ended_at, initial_state, final_state,
        active_schemas, metadata
    FROM runtime_sessions
    WHERE started_at > $1
    ORDER BY started_at DESC
    LIMIT $2
"""
"""Retrieve sessions started since a given timestamp. Parameters: since(TIMESTAMPTZ), limit."""

# =============================================================================
# Governance Schema Registry Queries
# =============================================================================

SCHEMA_REGISTRY_INSERT = """
    INSERT INTO governance_schema_registry (
        schema_id, name, version, category, description,
        policies, constraints, fail_closed, is_active, loaded_at, checksum
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
"""
"""Register a governance schema. Parameters: schema_id, name, version, category,
description, policies(JSONB), constraints(JSONB), fail_closed, is_active, loaded_at, checksum."""

SCHEMA_REGISTRY_GET_ALL = """
    SELECT
        schema_id, name, version, category, description,
        policies, constraints, fail_closed, is_active,
        loaded_at, activated_at, deactivated_at, checksum
    FROM governance_schema_registry
    ORDER BY loaded_at DESC
"""
"""Retrieve all registered schemas."""

SCHEMA_REGISTRY_GET_ACTIVE = """
    SELECT
        schema_id, name, version, category, description,
        policies, constraints, fail_closed, is_active,
        loaded_at, activated_at, deactivated_at, checksum
    FROM governance_schema_registry
    WHERE is_active = TRUE
    ORDER BY category, schema_id
"""
"""Retrieve all currently active schemas."""

SCHEMA_REGISTRY_GET_BY_ID = """
    SELECT
        schema_id, name, version, category, description,
        policies, constraints, fail_closed, is_active,
        loaded_at, activated_at, deactivated_at, checksum
    FROM governance_schema_registry
    WHERE schema_id = $1
"""
"""Retrieve a schema by ID. Parameter: schema_id."""

SCHEMA_REGISTRY_ACTIVATE = """
    UPDATE governance_schema_registry
    SET is_active = TRUE, activated_at = $2, deactivated_at = NULL
    WHERE schema_id = $1
"""
"""Activate a schema. Parameters: schema_id, activated_at."""

SCHEMA_REGISTRY_DEACTIVATE = """
    UPDATE governance_schema_registry
    SET is_active = FALSE, deactivated_at = $2
    WHERE schema_id = $1
"""
"""Deactivate a schema. Parameters: schema_id, deactivated_at."""

# =============================================================================
# Governance Policy Log Queries
# =============================================================================

POLICY_LOG_INSERT = """
    INSERT INTO governance_policy_log (
        log_id, schema_id, policy_id, policy_version, rule_type, severity,
        evaluated_at, session_id, trace_id, passed, input_context,
        output_context, violation_id, evaluation_duration_ms,
        remediation_triggered, remediation_action, notes
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
"""
"""Log a policy evaluation. Parameters: log_id, schema_id, policy_id, policy_version,
rule_type, severity, evaluated_at, session_id, trace_id, passed, input_context(JSONB),
output_context(JSONB), violation_id, evaluation_duration_ms, remediation_triggered,
remediation_action, notes."""

POLICY_LOG_GET_BY_SCHEMA = """
    SELECT
        log_id, schema_id, policy_id, policy_version, rule_type, severity,
        evaluated_at, session_id, trace_id, passed, input_context,
        output_context, violation_id, evaluation_duration_ms,
        remediation_triggered, remediation_action, notes
    FROM governance_policy_log
    WHERE schema_id = $1
    ORDER BY evaluated_at DESC
    LIMIT $2
"""
"""Retrieve policy log entries for a schema. Parameters: schema_id, limit."""

POLICY_LOG_GET_BY_SESSION = """
    SELECT
        log_id, schema_id, policy_id, policy_version, rule_type, severity,
        evaluated_at, session_id, trace_id, passed, input_context,
        output_context, violation_id, evaluation_duration_ms,
        remediation_triggered, remediation_action, notes
    FROM governance_policy_log
    WHERE session_id = $1
    ORDER BY evaluated_at DESC
"""
"""Retrieve policy log entries for a session. Parameter: session_id."""

# =============================================================================
# Runtime Configuration Queries
# =============================================================================

CONFIG_GET = """
    SELECT config_key, config_value, description, is_sensitive, created_at, updated_at, updated_by
    FROM runtime_configuration
    WHERE config_key = $1
"""
"""Retrieve a configuration value by key. Parameter: config_key."""

CONFIG_GET_ALL = """
    SELECT config_key, config_value, description, is_sensitive, created_at, updated_at, updated_by
    FROM runtime_configuration
    WHERE is_sensitive = FALSE OR $1 = TRUE
    ORDER BY config_key
"""
"""Retrieve all configuration values. Parameter: include_sensitive(bool)."""

CONFIG_SET = """
    INSERT INTO runtime_configuration (
        config_key, config_value, description, is_sensitive, created_at, updated_at, updated_by
    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
    ON CONFLICT (config_key)
    DO UPDATE SET
        config_value = EXCLUDED.config_value,
        updated_at = EXCLUDED.updated_at,
        updated_by = EXCLUDED.updated_by
"""
"""Upsert a configuration value. Parameters: config_key, config_value(JSONB),
description, is_sensitive, created_at, updated_at, updated_by."""

CONFIG_DELETE = """
    DELETE FROM runtime_configuration WHERE config_key = $1
"""
"""Delete a configuration entry. Parameter: config_key."""


# Aliases for backward compatibility
MEMORY_SEARCH_TEXT = MEMORY_SEARCH_BY_CONTENT
MEMORY_UPDATE_ACCESS = MEMORY_UPDATE_RETRIEVAL
MEMORY_SOFT_DELETE = MEMORY_DELETE
AUDIT_INSERT_MANY = AUDIT_INSERT
CHECK_INSERT = GOVERNANCE_CHECK_INSERT
CHECK_GET_BY_TRACE = GOVERNANCE_CHECK_GET_BY_TRACE
INFLUENCE_GET_BY_SESSION = INFLUENCE_GET_BY_INFERENCE
VIOLATION_SUMMARY = VIOLATION_GET_SUMMARY

# Queries referenced in source but not yet defined — stub with basic SQL
MEMORY_SEARCH_BY_SCHEMA = """
    SELECT
        memory_id, session_id, episode_type, content, provenance,
        governance_influences, confidence, created_at, retrieval_count, last_accessed
    FROM episodic_memories
    WHERE session_id = $1
      AND provenance ->> 'source_schema' = $2
    ORDER BY created_at DESC
"""

MEMORY_SEARCH_TEMPORAL = """
    SELECT
        memory_id, session_id, episode_type, content, provenance,
        governance_influences, confidence, created_at, retrieval_count, last_accessed
    FROM episodic_memories
    WHERE session_id = $1
      AND created_at BETWEEN $2 AND $3
    ORDER BY created_at DESC
"""

AUDIT_GET_FILTERED = """
    SELECT
        event_id, event_type, severity, component, session_id,
        trace_id, created_at, details, governance_context
    FROM audit_events
    WHERE ($1::UUID IS NULL OR session_id = $1)
      AND ($2::TEXT IS NULL OR event_type = $2)
      AND ($3::TEXT IS NULL OR severity = $3)
      AND ($4::TIMESTAMPTZ IS NULL OR created_at > $4)
    ORDER BY created_at DESC
    LIMIT $5
"""


class Queries:
    """Namespace wrapper for all SQL query constants.

    Provides class-level access to every query constant defined in this module,
    so that other modules can import ``Queries`` and reference
    ``Queries.MEMORY_INSERT`` etc.
    """

    MEMORY_INSERT = MEMORY_INSERT
    MEMORY_GET_BY_ID = MEMORY_GET_BY_ID
    MEMORY_GET_BY_SESSION = MEMORY_GET_BY_SESSION
    MEMORY_GET_BY_SESSION_LIMIT = MEMORY_GET_BY_SESSION_LIMIT
    MEMORY_GET_BY_TYPE = MEMORY_GET_BY_TYPE
    MEMORY_UPDATE_RETRIEVAL = MEMORY_UPDATE_RETRIEVAL
    MEMORY_DELETE = MEMORY_DELETE
    MEMORY_SEARCH_BY_CONTENT = MEMORY_SEARCH_BY_CONTENT

    INFLUENCE_INSERT = INFLUENCE_INSERT
    INFLUENCE_GET_BY_MEMORY = INFLUENCE_GET_BY_MEMORY
    INFLUENCE_GET_BY_INFERENCE = INFLUENCE_GET_BY_INFERENCE

    AUDIT_INSERT = AUDIT_INSERT
    AUDIT_GET_BY_SESSION = AUDIT_GET_BY_SESSION
    AUDIT_GET_BY_TRACE = AUDIT_GET_BY_TRACE
    AUDIT_GET_BY_TYPE = AUDIT_GET_BY_TYPE
    AUDIT_GET_BY_SEVERITY = AUDIT_GET_BY_SEVERITY
    AUDIT_GET_SINCE = AUDIT_GET_SINCE
    AUDIT_GET_BY_COMPONENT = AUDIT_GET_BY_COMPONENT

    TRANSITION_INSERT = TRANSITION_INSERT
    TRANSITION_GET_BY_TRACE = TRANSITION_GET_BY_TRACE
    TRANSITION_GET_LATEST = TRANSITION_GET_LATEST

    GOVERNANCE_CHECK_INSERT = GOVERNANCE_CHECK_INSERT
    GOVERNANCE_CHECK_GET_BY_TRACE = GOVERNANCE_CHECK_GET_BY_TRACE
    GOVERNANCE_CHECK_GET_BY_SESSION = GOVERNANCE_CHECK_GET_BY_SESSION
    GOVERNANCE_CHECK_GET_FAILED = GOVERNANCE_CHECK_GET_FAILED
    GOVERNANCE_CHECK_GET_BY_SCHEMA = GOVERNANCE_CHECK_GET_BY_SCHEMA

    VIOLATION_INSERT = VIOLATION_INSERT
    VIOLATION_GET_BY_SCHEMA = VIOLATION_GET_BY_SCHEMA
    VIOLATION_GET_BY_SEVERITY = VIOLATION_GET_BY_SEVERITY
    VIOLATION_GET_UNRESOLVED = VIOLATION_GET_UNRESOLVED
    VIOLATION_UPDATE_RESOLUTION = VIOLATION_UPDATE_RESOLUTION
    VIOLATION_GET_SUMMARY = VIOLATION_GET_SUMMARY
    VIOLATION_SUMMARY = VIOLATION_SUMMARY

    TRACE_INSERT = TRACE_INSERT
    TRACE_GET_BY_ID = TRACE_GET_BY_ID
    TRACE_GET_BY_SESSION = TRACE_GET_BY_SESSION
    TRACE_UPDATE_END = TRACE_UPDATE_END
    TRACE_GET_ACTIVE = TRACE_GET_ACTIVE

    SESSION_INSERT = SESSION_INSERT
    SESSION_GET_BY_ID = SESSION_GET_BY_ID
    SESSION_GET_ACTIVE = SESSION_GET_ACTIVE
    SESSION_UPDATE_END = SESSION_UPDATE_END
    SESSION_UPDATE_SCHEMAS = SESSION_UPDATE_SCHEMAS
    SESSION_GET_ALL = SESSION_GET_ALL
    SESSION_GET_SINCE = SESSION_GET_SINCE

    SCHEMA_REGISTRY_INSERT = SCHEMA_REGISTRY_INSERT
    SCHEMA_REGISTRY_GET_ALL = SCHEMA_REGISTRY_GET_ALL
    SCHEMA_REGISTRY_GET_ACTIVE = SCHEMA_REGISTRY_GET_ACTIVE
    SCHEMA_REGISTRY_GET_BY_ID = SCHEMA_REGISTRY_GET_BY_ID
    SCHEMA_REGISTRY_ACTIVATE = SCHEMA_REGISTRY_ACTIVATE
    SCHEMA_REGISTRY_DEACTIVATE = SCHEMA_REGISTRY_DEACTIVATE

    POLICY_LOG_INSERT = POLICY_LOG_INSERT
    POLICY_LOG_GET_BY_SCHEMA = POLICY_LOG_GET_BY_SCHEMA
    POLICY_LOG_GET_BY_SESSION = POLICY_LOG_GET_BY_SESSION

    CONFIG_GET = CONFIG_GET
    CONFIG_GET_ALL = CONFIG_GET_ALL
    CONFIG_SET = CONFIG_SET
    CONFIG_DELETE = CONFIG_DELETE

    AUDIT_INSERT_MANY = AUDIT_INSERT
    AUDIT_GET_FILTERED = AUDIT_GET_FILTERED

    MEMORY_UPDATE_ACCESS = MEMORY_UPDATE_RETRIEVAL
    MEMORY_SEARCH_TEXT = MEMORY_SEARCH_BY_CONTENT
    MEMORY_SEARCH_BY_SCHEMA = MEMORY_SEARCH_BY_SCHEMA
    MEMORY_SEARCH_TEMPORAL = MEMORY_SEARCH_TEMPORAL
    MEMORY_SOFT_DELETE = MEMORY_DELETE

    INFLUENCE_GET_BY_SESSION = INFLUENCE_GET_BY_INFERENCE

    CHECK_INSERT = GOVERNANCE_CHECK_INSERT
    CHECK_GET_BY_TRACE = GOVERNANCE_CHECK_GET_BY_TRACE


__all__ = [
    "Queries",
    # Memory
    "MEMORY_INSERT",
    "MEMORY_GET_BY_ID",
    "MEMORY_GET_BY_SESSION",
    "MEMORY_GET_BY_SESSION_LIMIT",
    "MEMORY_GET_BY_TYPE",
    "MEMORY_UPDATE_RETRIEVAL",
    "MEMORY_DELETE",
    "MEMORY_SEARCH_BY_CONTENT",
    # Memory Influence
    "INFLUENCE_INSERT",
    "INFLUENCE_GET_BY_MEMORY",
    "INFLUENCE_GET_BY_INFERENCE",
    # Audit
    "AUDIT_INSERT",
    "AUDIT_GET_BY_SESSION",
    "AUDIT_GET_BY_TRACE",
    "AUDIT_GET_BY_TYPE",
    "AUDIT_GET_BY_SEVERITY",
    "AUDIT_GET_SINCE",
    "AUDIT_GET_BY_COMPONENT",
    # State Transitions
    "TRANSITION_INSERT",
    "TRANSITION_GET_BY_TRACE",
    "TRANSITION_GET_LATEST",
    # Governance Checks
    "GOVERNANCE_CHECK_INSERT",
    "GOVERNANCE_CHECK_GET_BY_TRACE",
    "GOVERNANCE_CHECK_GET_BY_SESSION",
    "GOVERNANCE_CHECK_GET_FAILED",
    "GOVERNANCE_CHECK_GET_BY_SCHEMA",
    # Violations
    "VIOLATION_INSERT",
    "VIOLATION_GET_BY_SCHEMA",
    "VIOLATION_GET_BY_SEVERITY",
    "VIOLATION_GET_UNRESOLVED",
    "VIOLATION_UPDATE_RESOLUTION",
    "VIOLATION_GET_SUMMARY",
    # Traces
    "TRACE_INSERT",
    "TRACE_GET_BY_ID",
    "TRACE_GET_BY_SESSION",
    "TRACE_UPDATE_END",
    "TRACE_GET_ACTIVE",
    # Sessions
    "SESSION_INSERT",
    "SESSION_GET_BY_ID",
    "SESSION_GET_ACTIVE",
    "SESSION_UPDATE_END",
    "SESSION_UPDATE_SCHEMAS",
    "SESSION_GET_ALL",
    "SESSION_GET_SINCE",
    # Schema Registry
    "SCHEMA_REGISTRY_INSERT",
    "SCHEMA_REGISTRY_GET_ALL",
    "SCHEMA_REGISTRY_GET_ACTIVE",
    "SCHEMA_REGISTRY_GET_BY_ID",
    "SCHEMA_REGISTRY_ACTIVATE",
    "SCHEMA_REGISTRY_DEACTIVATE",
    # Policy Log
    "POLICY_LOG_INSERT",
    "POLICY_LOG_GET_BY_SCHEMA",
    "POLICY_LOG_GET_BY_SESSION",
    # Runtime Config
    "CONFIG_GET",
    "CONFIG_GET_ALL",
    "CONFIG_SET",
    "CONFIG_DELETE",
]
