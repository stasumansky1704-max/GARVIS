// =============================================================================
// GARVIS API Client — with comprehensive mock data for standalone development
// =============================================================================

import type {
  GovernanceSchema,
  OperationalState,
  StateTransition,
  EpisodicMemory,
  MemoryInfluence,
  AuditEvent,
  CognitionTrace,
  AnalyticsOverview,
  RuntimeStatus,
  AuditFilters,
  CognitionEvent,
  ForbiddenPattern,
  SessionInfo,
  PressureMetrics,
  EcosystemData,
  TrendPoint,
  SystemAlert,
  AlertFilters,
  TopologyData,
} from "./types";

const USE_MOCK = true;
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

// =============================================================================
// MOCK DATA
// =============================================================================

const MOCK_SCHEMAS: GovernanceSchema[] = [
  { schema_id: "SCH-001", name: "Epistemic Boundary", version: "2.1.0", category: "epistemic", policies: 8, constraints: 14, active: true, description: "Limits claims to evidence-backed assertions. Prevents hallucinated facts from propagating to outputs.", last_updated: "2025-01-15T09:00:00Z" },
  { schema_id: "SCH-002", name: "Uncertainty Calibration", version: "1.4.0", category: "epistemic", policies: 5, constraints: 9, active: true, description: "Requires confidence calibration on all factual assertions.", last_updated: "2025-01-14T16:30:00Z" },
  { schema_id: "SCH-003", name: "Operator Override Protocol", version: "3.0.0", category: "operational", policies: 12, constraints: 20, active: true, description: "Defines when and how operator commands override autonomous decisions.", last_updated: "2025-01-15T08:00:00Z" },
  { schema_id: "SCH-004", name: "Fail-Closed Default", version: "2.2.0", category: "operational", policies: 6, constraints: 11, active: true, description: "All governance checks default to DENY on error or ambiguity.", last_updated: "2025-01-13T11:00:00Z" },
  { schema_id: "SCH-005", name: "Harm Boundary", version: "4.0.0", category: "boundary", policies: 15, constraints: 28, active: true, description: "Hard constraints preventing assistance with physical, digital, or societal harm.", last_updated: "2025-01-15T07:45:00Z" },
  { schema_id: "SCH-006", name: "Privacy Firewall", version: "2.0.0", category: "boundary", policies: 10, constraints: 18, active: true, description: "Prevents exposure of PII, credentials, and sensitive operational data.", last_updated: "2025-01-12T14:00:00Z" },
  { schema_id: "SCH-007", name: "Self-Reflection Loop", version: "1.3.0", category: "reflective", policies: 4, constraints: 7, active: true, description: "Requires periodic self-assessment of reasoning quality and bias.", last_updated: "2025-01-14T10:00:00Z" },
  { schema_id: "SCH-008", name: "Bias Detection", version: "1.5.0", category: "reflective", policies: 7, constraints: 12, active: true, description: "Monitors reasoning chains for systematic bias patterns.", last_updated: "2025-01-14T09:30:00Z" },
  { schema_id: "SCH-009", name: "Session Integrity", version: "2.0.0", category: "session", policies: 6, constraints: 10, active: true, description: "Maintains session-level consistency and prevents context leakage.", last_updated: "2025-01-13T15:00:00Z" },
  { schema_id: "SCH-010", name: "Temporal Coherence", version: "1.1.0", category: "session", policies: 3, constraints: 5, active: false, description: "Ensures temporal consistency in multi-turn reasoning.", last_updated: "2025-01-10T08:00:00Z" },
];

const MOCK_STATE: OperationalState = {
  state: "governed",
  since: "2025-01-15T09:23:17Z",
  transitions_today: 47,
};

const MOCK_TRANSITIONS: StateTransition[] = [
  { from_state: "standby", to_state: "active", trigger: "operator_command", timestamp: "2025-01-15T09:23:10Z", governance_check_passed: true },
  { from_state: "active", to_state: "processing", trigger: "inference_request", timestamp: "2025-01-15T09:23:12Z", governance_check_passed: true },
  { from_state: "processing", to_state: "governed", trigger: "governance_check", timestamp: "2025-01-15T09:23:17Z", governance_check_passed: true },
  { from_state: "governed", to_state: "output", trigger: "approval", timestamp: "2025-01-15T09:23:18Z", governance_check_passed: true },
  { from_state: "output", to_state: "standby", trigger: "completion", timestamp: "2025-01-15T09:23:25Z", governance_check_passed: true },
  { from_state: "standby", to_state: "active", trigger: "operator_command", timestamp: "2025-01-15T09:24:01Z", governance_check_passed: true },
  { from_state: "active", to_state: "processing", trigger: "inference_request", timestamp: "2025-01-15T09:24:03Z", governance_check_passed: true },
  { from_state: "processing", to_state: "governed", trigger: "governance_check", timestamp: "2025-01-15T09:24:08Z", governance_check_passed: true },
  { from_state: "processing", to_state: "blocked", trigger: "policy_violation", timestamp: "2025-01-15T09:24:15Z", governance_check_passed: false },
  { from_state: "blocked", to_state: "recovery", trigger: "operator_review", timestamp: "2025-01-15T09:24:20Z", governance_check_passed: true },
  { from_state: "recovery", to_state: "standby", trigger: "reset", timestamp: "2025-01-15T09:24:30Z", governance_check_passed: true },
  { from_state: "standby", to_state: "active", trigger: "operator_command", timestamp: "2025-01-15T09:25:00Z", governance_check_passed: true },
];

const MOCK_MEMORIES: EpisodicMemory[] = [
  { memory_id: "MEM-001", session_id: "SES-20250115-001", episode_type: "inference", content: "Operator requested analysis of governance schema coverage. Identified gap in temporal coherence constraints across multi-session contexts.", confidence: 0.94, timestamp: "2025-01-15T09:20:00Z", retrieval_count: 3 },
  { memory_id: "MEM-002", session_id: "SES-20250115-001", episode_type: "correction", content: "Operator corrected inference: epistemic boundary applies to generated content, not to retrieved context. Updated policy interpretation.", confidence: 0.98, timestamp: "2025-01-15T09:18:00Z", retrieval_count: 7 },
  { memory_id: "MEM-003", session_id: "SES-20250115-002", episode_type: "observation", content: "Session integrity check detected potential context leakage between SES-20250115-001 and SES-20250115-002. Firewall rule SCH-009.3 triggered.", confidence: 0.87, timestamp: "2025-01-15T09:15:00Z", retrieval_count: 2 },
  { memory_id: "MEM-004", session_id: "SES-20250115-002", episode_type: "inference", content: "Analyzed operator preference patterns: prefers verbose governance trace visibility. Adjusted output format accordingly.", confidence: 0.82, timestamp: "2025-01-15T09:10:00Z", retrieval_count: 5 },
  { memory_id: "MEM-005", session_id: "SES-20250114-010", episode_type: "governance_event", content: "Hard stop triggered by Harm Boundary policy SCH-005.7: attempted reasoning path led to dual-use suggestion. Fail-closed invoked.", confidence: 0.99, timestamp: "2025-01-14T16:45:00Z", retrieval_count: 12 },
  { memory_id: "MEM-006", session_id: "SES-20250114-009", episode_type: "reflection", content: "Self-assessment: reasoning chain showed anchoring bias toward recent successful governance patterns. Applied debiasing correction.", confidence: 0.76, timestamp: "2025-01-14T14:30:00Z", retrieval_count: 1 },
  { memory_id: "MEM-007", session_id: "SES-20250114-008", episode_type: "operator_interaction", content: "Operator requested override of uncertainty calibration for time-critical analysis. Override logged and approved per SCH-003.4.", confidence: 0.91, timestamp: "2025-01-14T11:20:00Z", retrieval_count: 4 },
  { memory_id: "MEM-008", session_id: "SES-20250113-005", episode_type: "system_event", content: "Governance schema SCH-010 (Temporal Coherence) deactivated due to conflict with session recovery protocol. Awaiting operator review.", confidence: 0.95, timestamp: "2025-01-13T09:00:00Z", retrieval_count: 8 },
];

const MOCK_INFLUENCES: MemoryInfluence[] = [
  { influence_id: "INF-001", memory_id: "MEM-002", target_inference_id: "INF-2025-001", influence_type: "policy_correction", strength: 0.92, trace_visible: true },
  { influence_id: "INF-002", memory_id: "MEM-005", target_inference_id: "INF-2025-003", influence_type: "hard_stop_precedent", strength: 0.88, trace_visible: true },
  { influence_id: "INF-003", memory_id: "MEM-001", target_inference_id: "INF-2025-002", influence_type: "coverage_analysis", strength: 0.74, trace_visible: true },
  { influence_id: "INF-004", memory_id: "MEM-004", target_inference_id: "INF-2025-004", influence_type: "preference_adaptation", strength: 0.65, trace_visible: false },
  { influence_id: "INF-005", memory_id: "MEM-003", target_inference_id: "INF-2025-005", influence_type: "firewall_trigger", strength: 0.79, trace_visible: true },
  { influence_id: "INF-006", memory_id: "MEM-006", target_inference_id: "INF-2025-006", influence_type: "bias_mitigation", strength: 0.58, trace_visible: false },
  { influence_id: "INF-007", memory_id: "MEM-007", target_inference_id: "INF-2025-007", influence_type: "override_authorized", strength: 0.85, trace_visible: true },
  { influence_id: "INF-008", memory_id: "MEM-008", target_inference_id: "INF-2025-008", influence_type: "schema_conflict", strength: 0.71, trace_visible: true },
];

const MOCK_TRACES: CognitionTrace[] = [
  {
    trace_id: "TRC-2025-001",
    session_id: "SES-20250115-001",
    status: "completed",
    duration_ms: 3420,
    start_time: "2025-01-15T09:23:10Z",
    end_time: "2025-01-15T09:23:14Z",
    state_transitions: MOCK_TRANSITIONS.slice(0, 4),
    governance_checks: [
      { check_id: "GC-001", schema_id: "SCH-001", policy_id: "POL-001", passed: true, severity: "info", details: "Evidence threshold met for 8/8 claims", timestamp: "2025-01-15T09:23:12Z" },
      { check_id: "GC-002", schema_id: "SCH-005", policy_id: "POL-012", passed: true, severity: "info", details: "No harm vectors detected", timestamp: "2025-01-15T09:23:13Z" },
      { check_id: "GC-003", schema_id: "SCH-003", policy_id: "POL-007", passed: true, severity: "info", details: "Operator authorization verified", timestamp: "2025-01-15T09:23:13Z" },
    ],
    memory_influences: MOCK_INFLUENCES.slice(0, 2),
    audit_events: [
      { event_id: "AUD-001", event_type: "governance_check", severity: "info", component: "governance", timestamp: "2025-01-15T09:23:12Z", details: { check_id: "GC-001", result: "pass" } },
      { event_id: "AUD-002", event_type: "state_change", severity: "info", component: "cognition", timestamp: "2025-01-15T09:23:17Z", details: { from: "processing", to: "governed" } },
    ],
  },
  {
    trace_id: "TRC-2025-002",
    session_id: "SES-20250115-001",
    status: "violated",
    duration_ms: 5120,
    start_time: "2025-01-15T09:24:01Z",
    end_time: "2025-01-15T09:24:30Z",
    state_transitions: MOCK_TRANSITIONS.slice(5, 11),
    governance_checks: [
      { check_id: "GC-004", schema_id: "SCH-001", policy_id: "POL-002", passed: true, severity: "info", details: "Evidence threshold met", timestamp: "2025-01-15T09:24:03Z" },
      { check_id: "GC-005", schema_id: "SCH-005", policy_id: "POL-015", passed: false, severity: "critical", details: "Potential dual-use vector detected in reasoning chain", timestamp: "2025-01-15T09:24:15Z" },
      { check_id: "GC-006", schema_id: "SCH-004", policy_id: "POL-009", passed: true, severity: "warning", details: "Fail-closed invoked. Output blocked.", timestamp: "2025-01-15T09:24:15Z" },
    ],
    memory_influences: MOCK_INFLUENCES.slice(2, 4),
    audit_events: [
      { event_id: "AUD-003", event_type: "governance_check", severity: "critical", component: "governance", timestamp: "2025-01-15T09:24:15Z", details: { check_id: "GC-005", result: "fail", policy: "POL-015" } },
      { event_id: "AUD-004", event_type: "violation_blocked", severity: "warning", component: "governance", timestamp: "2025-01-15T09:24:15Z", details: { trace_id: "TRC-2025-002", blocked_by: "SCH-005" } },
      { event_id: "AUD-005", event_type: "state_change", severity: "info", component: "cognition", timestamp: "2025-01-15T09:24:20Z", details: { from: "blocked", to: "recovery" } },
    ],
  },
  {
    trace_id: "TRC-2025-003",
    session_id: "SES-20250115-002",
    status: "active",
    duration_ms: 12340,
    start_time: "2025-01-15T09:25:00Z",
    state_transitions: MOCK_TRANSITIONS.slice(11),
    governance_checks: [
      { check_id: "GC-007", schema_id: "SCH-001", policy_id: "POL-001", passed: true, severity: "info", details: "Evidence check in progress", timestamp: "2025-01-15T09:25:02Z" },
      { check_id: "GC-008", schema_id: "SCH-009", policy_id: "POL-018", passed: true, severity: "info", details: "Session integrity verified", timestamp: "2025-01-15T09:25:03Z" },
    ],
    memory_influences: MOCK_INFLUENCES.slice(4, 6),
    audit_events: [
      { event_id: "AUD-006", event_type: "session_start", severity: "info", component: "session", timestamp: "2025-01-15T09:25:00Z", details: { session_id: "SES-20250115-002" } },
    ],
  },
];

const MOCK_EVENTS: AuditEvent[] = [
  { event_id: "AUD-001", event_type: "governance_check", severity: "info", component: "governance", timestamp: "2025-01-15T09:23:12Z", details: { check_id: "GC-001", result: "pass" } },
  { event_id: "AUD-002", event_type: "state_change", severity: "info", component: "cognition", timestamp: "2025-01-15T09:23:17Z", details: { from: "processing", to: "governed" } },
  { event_id: "AUD-003", event_type: "governance_check", severity: "critical", component: "governance", timestamp: "2025-01-15T09:24:15Z", details: { check_id: "GC-005", result: "fail", policy: "POL-015" }, message: "Policy violation: Harm Boundary POL-015 triggered" },
  { event_id: "AUD-004", event_type: "violation_blocked", severity: "warning", component: "governance", timestamp: "2025-01-15T09:24:15Z", details: { trace_id: "TRC-2025-002", blocked_by: "SCH-005" }, message: "Output blocked by Harm Boundary schema" },
  { event_id: "AUD-005", event_type: "state_change", severity: "info", component: "cognition", timestamp: "2025-01-15T09:24:20Z", details: { from: "blocked", to: "recovery" } },
  { event_id: "AUD-006", event_type: "session_start", severity: "info", component: "session", timestamp: "2025-01-15T09:25:00Z", details: { session_id: "SES-20250115-002" } },
  { event_id: "AUD-007", event_type: "memory_retrieval", severity: "info", component: "memory", timestamp: "2025-01-15T09:25:05Z", details: { memory_id: "MEM-002", confidence: 0.98 } },
  { event_id: "AUD-008", event_type: "governance_check", severity: "warning", component: "governance", timestamp: "2025-01-15T09:25:10Z", details: { check_id: "GC-009", result: "degraded", schema: "SCH-007" }, message: "Self-reflection loop lagging: 340ms delay" },
  { event_id: "AUD-009", event_type: "schema_conflict", severity: "warning", component: "governance", timestamp: "2025-01-15T09:25:15Z", details: { schemas: ["SCH-009", "SCH-010"], resolution: "SCH-009 priority" }, message: "Schema conflict detected: Session Integrity vs Temporal Coherence" },
  { event_id: "AUD-010", event_type: "operator_override", severity: "info", component: "governance", timestamp: "2025-01-15T09:25:20Z", details: { schema: "SCH-003", operator_id: "OP-001", authorized: true } },
  { event_id: "AUD-011", event_type: "enforcement_action", severity: "critical", component: "governance", timestamp: "2025-01-15T09:24:15Z", details: { action: "block_output", reason: "harm_boundary" }, message: "ENFORCEMENT: Output blocked - Harm Boundary violation" },
  { event_id: "AUD-012", event_type: "continuity_alert", severity: "warning", component: "continuity", timestamp: "2025-01-15T09:25:25Z", details: { drift: 0.12, threshold: 0.1 }, message: "Alignment drift detected: 0.12 exceeds threshold 0.10" },
];

const generateTrend = (count: number, base: number, variance: number): TrendPoint[] => {
  const points: TrendPoint[] = [];
  const now = new Date("2025-01-15T09:30:00Z");
  for (let i = count; i >= 0; i--) {
    const t = new Date(now.getTime() - i * 5 * 60 * 1000);
    const v = base + (Math.random() - 0.5) * variance * 2;
    points.push({ timestamp: t.toISOString(), value: Math.max(0, Math.min(1, v)) });
  }
  return points;
};

const MOCK_OVERVIEW: AnalyticsOverview = {
  governance: { active_schemas: 9, total_constraints: 134, hard_stop_rate: 0.02, coverage_score: 0.94, pressure: 0.31 },
  cognition: { current_state: "governed", session_count: 15, success_rate: 0.97, avg_response_time_ms: 3420, quality_score: 0.89 },
  memory: { total_memories: 2341, avg_retrievals: 4.2, influences_tracked: 187, trace_visible_rate: 0.82 },
  traceability: { total_traces: 156, avg_governance_checks: 3.4, violation_count: 4, audit_event_count: 1289 },
  continuity: { continuity_score: 0.87, alignment_drift: 0.12, resilience_score: 0.91, equilibrium_stability: 0.84 },
  pressure: { adaptation_pressure: 0.25, enforcement_pressure: 0.38, conflict_pressure: 0.29, overall_pressure: 0.31 },
  trends: {
    governance_trend: generateTrend(24, 0.94, 0.04),
    state_stability_trend: generateTrend(24, 0.88, 0.08),
    quality_trend: generateTrend(24, 0.89, 0.05),
    degradation_trend: generateTrend(24, 0.08, 0.04),
  },
  ecosystem: { governance_nodes: 10, memory_nodes: 234, reasoning_nodes: 156, total_edges: 412, alignment_ecology: { schema_interconnections: 28, memory_influence_density: 0.45, reasoning_branching_factor: 2.3 } },
};

const MOCK_STATUS: RuntimeStatus = {
  state: "operational",
  uptime_seconds: 86400 * 3 + 3600 * 4 + 1800,
  version: "2.0.0-phases3-6",
  components: [
    { name: "governance", status: "healthy", last_check: "2025-01-15T09:25:30Z" },
    { name: "cognition", status: "healthy", last_check: "2025-01-15T09:25:30Z" },
    { name: "memory", status: "healthy", last_check: "2025-01-15T09:25:30Z" },
    { name: "traceability", status: "healthy", last_check: "2025-01-15T09:25:30Z" },
    { name: "audit", status: "healthy", last_check: "2025-01-15T09:25:30Z" },
    { name: "analytics", status: "healthy", last_check: "2025-01-15T09:25:30Z" },
    { name: "continuity", status: "degraded", last_check: "2025-01-15T09:25:30Z", message: "Alignment drift detection delayed 180ms" },
    { name: "websocket", status: "healthy", last_check: "2025-01-15T09:25:30Z" },
  ],
};

const MOCK_COGNITION_EVENTS: CognitionEvent[] = [
  { event_id: "CEV-001", event_type: "state_change", severity: "info", message: "State transition: standby → active (operator_command)", timestamp: "2025-01-15T09:25:00Z" },
  { event_id: "CEV-002", event_type: "inference_start", severity: "info", message: "Inference request received. Initiating governance pre-check.", timestamp: "2025-01-15T09:25:01Z" },
  { event_id: "CEV-003", event_type: "governance_check", severity: "info", message: "Schema SCH-001: Epistemic Boundary — PASS (8/8 claims verified)", timestamp: "2025-01-15T09:25:02Z" },
  { event_id: "CEV-004", event_type: "memory_retrieval", severity: "info", message: "Retrieved MEM-002 (confidence 0.98): Operator corrected inference on epistemic boundary scope", timestamp: "2025-01-15T09:25:03Z" },
  { event_id: "CEV-005", event_type: "inference", severity: "info", message: "Reasoning chain: 4 steps, 2 branching points, depth 3", timestamp: "2025-01-15T09:25:05Z" },
  { event_id: "CEV-006", event_type: "governance_check", severity: "warning", message: "Schema SCH-007: Self-Reflection Loop — DEGRADED (340ms delay)", timestamp: "2025-01-15T09:25:08Z" },
  { event_id: "CEV-007", event_type: "schema_conflict", severity: "warning", message: "Conflict: SCH-009 (Session Integrity) vs SCH-010 (Temporal Coherence). Resolved: SCH-009 priority.", timestamp: "2025-01-15T09:25:10Z" },
  { event_id: "CEV-008", event_type: "governance_check", severity: "info", message: "Schema SCH-005: Harm Boundary — PASS (no vectors detected)", timestamp: "2025-01-15T09:25:12Z" },
  { event_id: "CEV-009", event_type: "state_change", severity: "info", message: "State transition: processing → governed (all checks passed)", timestamp: "2025-01-15T09:25:13Z" },
  { event_id: "CEV-010", event_type: "output", severity: "info", message: "Output approved. 3 governance checks passed. Trace: TRC-2025-003", timestamp: "2025-01-15T09:25:14Z" },
];

const MOCK_FORBIDDEN_PATTERNS: ForbiddenPattern[] = [
  { pattern_id: "FP-001", description: "Direct harm instruction chain", category: "harm", violation_count: 0, last_triggered: undefined },
  { pattern_id: "FP-002", description: "Credential exposure in output", category: "privacy", violation_count: 0, last_triggered: undefined },
  { pattern_id: "FP-003", description: "Dual-use research suggestion", category: "boundary", violation_count: 2, last_triggered: "2025-01-15T09:24:15Z" },
  { pattern_id: "FP-004", description: "Confidence inflation without calibration", category: "epistemic", violation_count: 1, last_triggered: "2025-01-14T10:00:00Z" },
  { pattern_id: "FP-005", description: "Context leakage across sessions", category: "session", violation_count: 3, last_triggered: "2025-01-15T09:15:00Z" },
];

const MOCK_SESSIONS: SessionInfo[] = [
  { session_id: "SES-20250115-003", state: "active", started_at: "2025-01-15T09:25:00Z", trace_count: 1, event_count: 12 },
  { session_id: "SES-20250115-002", state: "completed", started_at: "2025-01-15T09:10:00Z", ended_at: "2025-01-15T09:22:00Z", trace_count: 5, event_count: 34 },
  { session_id: "SES-20250115-001", state: "completed", started_at: "2025-01-15T08:45:00Z", ended_at: "2025-01-15T09:08:00Z", trace_count: 8, event_count: 56 },
  { session_id: "SES-20250114-012", state: "completed", started_at: "2025-01-14T17:00:00Z", ended_at: "2025-01-14T17:30:00Z", trace_count: 6, event_count: 42 },
  { session_id: "SES-20250114-011", state: "completed", started_at: "2025-01-14T15:30:00Z", ended_at: "2025-01-14T16:15:00Z", trace_count: 12, event_count: 89 },
];

const MOCK_PRESSURE: PressureMetrics = {
  schema_pressures: [
    { schema_id: "SCH-001", schema_name: "Epistemic Boundary", adaptation: 0.15, enforcement: 0.30, conflict: 0.10, total: 0.18 },
    { schema_id: "SCH-003", schema_name: "Operator Override Protocol", adaptation: 0.25, enforcement: 0.20, conflict: 0.05, total: 0.17 },
    { schema_id: "SCH-005", schema_name: "Harm Boundary", adaptation: 0.10, enforcement: 0.65, conflict: 0.20, total: 0.32 },
    { schema_id: "SCH-007", schema_name: "Self-Reflection Loop", adaptation: 0.40, enforcement: 0.10, conflict: 0.15, total: 0.22 },
    { schema_id: "SCH-009", schema_name: "Session Integrity", adaptation: 0.20, enforcement: 0.35, conflict: 0.55, total: 0.37 },
  ],
  overall: { adaptation: 0.25, enforcement: 0.38, conflict: 0.29, total: 0.31 },
  history: generateTrend(24, 0.30, 0.08),
};

const MOCK_ALERTS: SystemAlert[] = [
  {
    alert_id: "alert-001",
    severity: "critical",
    category: "governance",
    title: "Critical Governance Violation: boundary_preservation",
    description: "Policy within_operational_scope violated. Enforcement: hard_stop. Schema boundary_preservation triggered a fail-closed response after confidence threshold exceeded.",
    source_schema: "boundary_preservation",
    source_component: "GovernedInferenceExecutor",
    timestamp: "2026-05-26T10:30:00Z",
    acknowledged: true,
    resolved: true,
    acknowledged_by: "operator-001",
    resolved_by: "operator-001",
    notes: "Reviewed and confirmed: inference chain correctly blocked.",
  },
  {
    alert_id: "alert-002",
    severity: "warning",
    category: "governance",
    title: "High Governance Pressure: inference",
    description: "Pressure score 0.78 exceeds threshold 0.70. Schema uncertainty_management experiencing elevated conflict between adaptation and enforcement vectors.",
    source_schema: "uncertainty_management",
    source_component: "SchemaPressureMonitor",
    timestamp: "2026-05-26T11:00:00Z",
    acknowledged: false,
    resolved: false,
  },
  {
    alert_id: "alert-003",
    severity: "critical",
    category: "cognition",
    title: "Runtime Entered FAIL_CLOSED State",
    description: "Reason: critical governance violation. All cognition halted. State machine transitioned to fail_closed at 09:15:00Z. Operator intervention required.",
    source_component: "CognitionStateMachine",
    timestamp: "2026-05-26T09:15:00Z",
    acknowledged: true,
    resolved: true,
    acknowledged_by: "operator-001",
    resolved_by: "system-auto",
    notes: "Auto-recovery initiated after governance clearance.",
  },
  {
    alert_id: "alert-004",
    severity: "warning",
    category: "system",
    title: "Resilience Score Dropped",
    description: "Resilience score 0.52 below threshold 0.60. Continuity module reporting degraded equilibrium stability.",
    source_component: "ContinuityMonitor",
    timestamp: "2026-05-26T12:00:00Z",
    acknowledged: false,
    resolved: false,
  },
  {
    alert_id: "alert-005",
    severity: "info",
    category: "governance",
    title: "Schema Activated: cognitive_humility",
    description: "Schema cognitive_humility was activated by operator. Confidence calibration now enforced on all epistemic claims.",
    source_schema: "cognitive_humility",
    source_component: "SchemaLoader",
    timestamp: "2026-05-26T08:00:00Z",
    acknowledged: true,
    resolved: true,
    acknowledged_by: "operator-001",
    resolved_by: "system-auto",
  },
  {
    alert_id: "alert-006",
    severity: "warning",
    category: "memory",
    title: "Memory Retrieval Latency Spike",
    description: "EpisodicStore average retrieval latency increased to 245ms (threshold: 150ms). 3 retrieval operations timed out in the last 5 minutes.",
    source_component: "EpisodicStore",
    timestamp: "2026-05-26T11:30:00Z",
    acknowledged: true,
    resolved: false,
    acknowledged_by: "operator-002",
    notes: "Investigating root cause. Possible index fragmentation.",
  },
  {
    alert_id: "alert-007",
    severity: "critical",
    category: "inference",
    title: "Inference Pipeline Blocked",
    description: "GovernedInferenceExecutor blocked 3 consecutive inference requests. All blocked by Harm Boundary schema SCH-005. Fail-closed mode active.",
    source_schema: "harm_boundary",
    source_component: "GovernedInferenceExecutor",
    timestamp: "2026-05-26T10:45:00Z",
    acknowledged: true,
    resolved: true,
    acknowledged_by: "operator-001",
    resolved_by: "operator-001",
    notes: "False positive triggered by edge-case input pattern. Schema calibration adjusted.",
  },
  {
    alert_id: "alert-008",
    severity: "info",
    category: "monitoring",
    title: "Audit Pipeline Processing Lag",
    description: "AuditPipeline is 45 seconds behind real-time. Current queue depth: 128 events. Catching up after scheduled maintenance.",
    source_component: "AuditPipeline",
    timestamp: "2026-05-26T11:15:00Z",
    acknowledged: true,
    resolved: true,
    acknowledged_by: "system-auto",
    resolved_by: "system-auto",
  },
  {
    alert_id: "alert-009",
    severity: "warning",
    category: "traceability",
    title: "Lineage Chain Gap Detected",
    description: "LineageTracker found 2 gaps in provenance chain for session SES-20260526-004. Missing provenance entries between inference steps 4-6.",
    source_component: "LineageTracker",
    timestamp: "2026-05-26T10:00:00Z",
    acknowledged: false,
    resolved: false,
  },
  {
    alert_id: "alert-010",
    severity: "info",
    category: "system",
    title: "Schema Update Available",
    description: "New version 2.1.0 available for schema temporal_coherence. Current: 1.1.0. Review changelog before updating.",
    source_schema: "temporal_coherence",
    source_component: "SchemaRegistry",
    timestamp: "2026-05-26T07:00:00Z",
    acknowledged: true,
    resolved: true,
    acknowledged_by: "operator-001",
    notes: "Scheduled for update during next maintenance window.",
  },
  {
    alert_id: "alert-011",
    severity: "critical",
    category: "governance",
    title: "Schema Conflict: Session Integrity vs Temporal Coherence",
    description: "Critical conflict detected between SCH-009 (Session Integrity) and SCH-010 (Temporal Coherence). Resolution priority: SCH-009. Operator review advised.",
    source_schema: "session_integrity",
    source_component: "SchemaConflictResolver",
    timestamp: "2026-05-26T09:45:00Z",
    acknowledged: true,
    resolved: true,
    acknowledged_by: "operator-001",
    resolved_by: "operator-001",
    notes: "SCH-010 temporarily deactivated pending reconciliation.",
  },
  {
    alert_id: "alert-012",
    severity: "warning",
    category: "cognition",
    title: "Forbidden Pattern Trigger Rate Elevated",
    description: "ForbiddenPatterns module triggered 5 times in the last hour (threshold: 3). Pattern FP-003 (dual-use suggestion) accounts for 4 triggers.",
    source_component: "ForbiddenPatterns",
    timestamp: "2026-05-26T11:45:00Z",
    acknowledged: false,
    resolved: false,
  },
  {
    alert_id: "alert-013",
    severity: "info",
    category: "analytics",
    title: "Governance Coverage Score Updated",
    description: "Coverage score improved from 0.91 to 0.94 after activation of cognitive_humility schema. Trend: positive.",
    source_component: "MetricsEngine",
    timestamp: "2026-05-26T08:30:00Z",
    acknowledged: true,
    resolved: true,
    acknowledged_by: "system-auto",
    resolved_by: "system-auto",
  },
  {
    alert_id: "alert-014",
    severity: "warning",
    category: "inference",
    title: "OllamaClient Response Degradation",
    description: "Average response time increased to 8.2s (baseline: 3.4s). 2 timeout events in last 10 minutes. Model may be under load.",
    source_component: "OllamaClient",
    timestamp: "2026-05-26T12:15:00Z",
    acknowledged: false,
    resolved: false,
  },
];

const MOCK_TOPOLOGY: TopologyData = {
  nodes: [
    { id: "governance.loader", layer: "governance", status: "healthy", label: "SchemaLoader", description: "Loads and validates governance schemas from registry", version: "2.0.0" },
    { id: "governance.registry", layer: "governance", status: "healthy", label: "Registry", description: "Central schema registry with versioning and dependencies", version: "2.0.0" },
    { id: "governance.validator", layer: "governance", status: "healthy", label: "Validator", description: "Validates inference outputs against active schemas", version: "2.1.0" },
    { id: "governance.middleware", layer: "governance", status: "healthy", label: "Middleware", description: "Intercepts inference calls for governance checks", version: "2.0.0" },
    { id: "governance.enforcer", layer: "governance", status: "healthy", label: "Enforcer", description: "Enforces hard stops and policy violations", version: "2.0.0" },
    { id: "cognition.state_machine", layer: "cognition", status: "healthy", label: "StateMachine", description: "Manages cognitive state transitions", version: "1.5.0" },
    { id: "cognition.transitions", layer: "cognition", status: "healthy", label: "Transitions", description: "Defines valid state transitions and triggers", version: "1.5.0" },
    { id: "cognition.forbidden", layer: "cognition", status: "healthy", label: "ForbiddenPatterns", description: "Detects and blocks forbidden reasoning patterns", version: "1.3.0" },
    { id: "memory.episodic", layer: "memory", status: "degraded", label: "EpisodicStore", description: "Stores episodic memories with provenance chains", version: "1.2.0" },
    { id: "memory.retrieval", layer: "memory", status: "healthy", label: "RetrievalEngine", description: "Retrieves relevant memories for inference context", version: "1.2.0" },
    { id: "traceability.lineage", layer: "traceability", status: "healthy", label: "LineageTracker", description: "Tracks data lineage across inference pipelines", version: "1.1.0" },
    { id: "traceability.audit", layer: "traceability", status: "healthy", label: "AuditPipeline", description: "Processes and persists audit events", version: "1.1.0" },
    { id: "inference.ollama", layer: "inference", status: "healthy", label: "OllamaClient", description: "Client for Ollama LLM inference", version: "1.0.0" },
    { id: "inference.mediator", layer: "inference", status: "healthy", label: "PromptMediator", description: "Mediates between governance and prompt construction", version: "1.0.0" },
    { id: "inference.executor", layer: "inference", status: "healthy", label: "GovernedExecutor", description: "Executes inference with governance middleware", version: "2.0.0" },
    { id: "runtime.bootstrap", layer: "runtime", status: "healthy", label: "Bootstrap", description: "System bootstrap and initialization sequence", version: "1.0.0" },
    { id: "runtime.health", layer: "runtime", status: "healthy", label: "HealthMonitor", description: "Monitors component health and reports status", version: "1.0.0" },
    { id: "analytics.metrics", layer: "analytics", status: "healthy", label: "Metrics", description: "Collects and aggregates system metrics", version: "1.0.0" },
    { id: "analytics.trends", layer: "analytics", status: "healthy", label: "Trends", description: "Analyzes trends and generates forecasts", version: "1.0.0" },
    { id: "monitoring.alerts", layer: "monitoring", status: "healthy", label: "AlertEngine", description: "Alert generation, routing, and management", version: "1.0.0" },
    { id: "monitoring.topology", layer: "monitoring", status: "healthy", label: "Topology", description: "System topology discovery and visualization", version: "1.0.0" },
  ],
  edges: [
    { from: "governance.loader", to: "governance.registry", type: "dependency" },
    { from: "governance.registry", to: "governance.validator", type: "dependency" },
    { from: "governance.validator", to: "governance.middleware", type: "dependency" },
    { from: "governance.middleware", to: "governance.enforcer", type: "dependency" },
    { from: "governance.enforcer", to: "cognition.state_machine", type: "influence" },
    { from: "cognition.state_machine", to: "cognition.transitions", type: "dependency" },
    { from: "cognition.state_machine", to: "cognition.forbidden", type: "dependency" },
    { from: "governance.middleware", to: "inference.executor", type: "mediation" },
    { from: "inference.executor", to: "memory.episodic", type: "dependency" },
    { from: "inference.executor", to: "traceability.lineage", type: "dependency" },
    { from: "inference.executor", to: "traceability.audit", type: "dependency" },
    { from: "memory.episodic", to: "memory.retrieval", type: "dependency" },
    { from: "runtime.bootstrap", to: "governance.loader", type: "initialization" },
    { from: "runtime.health", to: "cognition.state_machine", type: "monitoring" },
    { from: "analytics.metrics", to: "traceability.audit", type: "analysis" },
    { from: "monitoring.alerts", to: "governance.validator", type: "monitoring" },
    { from: "inference.ollama", to: "inference.mediator", type: "dependency" },
    { from: "inference.mediator", to: "inference.executor", type: "dependency" },
    { from: "memory.retrieval", to: "inference.mediator", type: "dependency" },
    { from: "analytics.trends", to: "analytics.metrics", type: "dependency" },
    { from: "monitoring.topology", to: "runtime.health", type: "monitoring" },
    { from: "monitoring.alerts", to: "monitoring.topology", type: "dependency" },
  ],
};

const MOCK_ECOSYSTEM: EcosystemData = {
  nodes: [
    // Governance schemas
    { id: "SCH-001", label: "Epistemic\nBoundary", type: "governance", radius: 28, metadata: { policies: 8 } },
    { id: "SCH-002", label: "Uncertainty\nCalibration", type: "governance", radius: 22, metadata: { policies: 5 } },
    { id: "SCH-003", label: "Operator\nOverride", type: "governance", radius: 32, metadata: { policies: 12 } },
    { id: "SCH-004", label: "Fail-Closed\nDefault", type: "governance", radius: 20, metadata: { policies: 6 } },
    { id: "SCH-005", label: "Harm\nBoundary", type: "governance", radius: 35, metadata: { policies: 15 } },
    { id: "SCH-006", label: "Privacy\nFirewall", type: "governance", radius: 26, metadata: { policies: 10 } },
    { id: "SCH-007", label: "Self-Reflection\nLoop", type: "governance", radius: 18, metadata: { policies: 4 } },
    { id: "SCH-008", label: "Bias\nDetection", type: "governance", radius: 24, metadata: { policies: 7 } },
    // Memory clusters
    { id: "MEM-CL-001", label: "Epistemic\nMemories", type: "memory", radius: 20, metadata: { count: 456 } },
    { id: "MEM-CL-002", label: "Governance\nEvents", type: "memory", radius: 22, metadata: { count: 789 } },
    { id: "MEM-CL-003", label: "Operator\nInteractions", type: "memory", radius: 18, metadata: { count: 312 } },
    { id: "MEM-CL-004", label: "System\nEvents", type: "memory", radius: 16, metadata: { count: 234 } },
    // Reasoning clusters
    { id: "INF-CL-001", label: "Inference\nChain A", type: "reasoning", radius: 24, metadata: { traces: 45 } },
    { id: "INF-CL-002", label: "Inference\nChain B", type: "reasoning", radius: 20, metadata: { traces: 38 } },
    { id: "INF-CL-003", label: "Blocked\nPaths", type: "reasoning", radius: 16, metadata: { traces: 12 } },
    // Session nodes
    { id: "SES-001", label: "Active\nSession", type: "session", radius: 18, metadata: { status: "active" } },
  ],
  edges: [
    { source: "SCH-001", target: "SCH-002", strength: 0.8, type: "reinforcement", label: "reinforces" },
    { source: "SCH-005", target: "SCH-004", strength: 0.9, type: "dependency", label: "depends" },
    { source: "SCH-003", target: "SCH-004", strength: 0.7, type: "override", label: "overrides" },
    { source: "SCH-007", target: "SCH-008", strength: 0.6, type: "reinforcement", label: "reinforces" },
    { source: "SCH-005", target: "MEM-CL-002", strength: 0.5, type: "influence", label: "influences" },
    { source: "MEM-CL-001", target: "INF-CL-001", strength: 0.7, type: "feeds", label: "feeds" },
    { source: "MEM-CL-002", target: "INF-CL-002", strength: 0.6, type: "feeds", label: "feeds" },
    { source: "MEM-CL-003", target: "SCH-003", strength: 0.8, type: "informs", label: "informs" },
    { source: "INF-CL-001", target: "SCH-001", strength: 0.9, type: "checks", label: "checked by" },
    { source: "INF-CL-002", target: "SCH-005", strength: 0.9, type: "checks", label: "checked by" },
    { source: "INF-CL-003", target: "SCH-005", strength: 1.0, type: "blocked", label: "blocked by" },
    { source: "SES-001", target: "INF-CL-001", strength: 0.8, type: "contains", label: "contains" },
    { source: "SES-001", target: "MEM-CL-003", strength: 0.6, type: "uses", label: "uses" },
    { source: "SCH-009", target: "SES-001", strength: 0.7, type: "protects", label: "protects" },
  ],
};

// =============================================================================
// API Client
// =============================================================================

async function mockResponse<T>(data: T, delay = 200): Promise<T> {
  await new Promise((r) => setTimeout(r, delay));
  return data;
}

function mockFetch<T>(data: T, delay = 200): () => Promise<T> {
  return () => mockResponse(data, delay);
}

export const api = {
  governance: {
    getSchemas: USE_MOCK
      ? mockFetch< GovernanceSchema[]>(MOCK_SCHEMAS)
      : () => fetch(`${API_BASE}/governance/schemas`).then((r) => r.json()),
    getSchema: (id: string) =>
      USE_MOCK
        ? mockResponse< GovernanceSchema | undefined>(MOCK_SCHEMAS.find((s) => s.schema_id === id))
        : fetch(`${API_BASE}/governance/schemas/${id}`).then((r) => r.json()),
    getActiveSchemas: USE_MOCK
      ? mockFetch< GovernanceSchema[]>(MOCK_SCHEMAS.filter((s) => s.active))
      : () => fetch(`${API_BASE}/governance/schemas?active=true`).then((r) => r.json()),
    getConstraints: (scope?: string) =>
      USE_MOCK
        ? mockResponse<number>(MOCK_SCHEMAS.reduce((sum, s) => sum + s.constraints, 0))
        : fetch(`${API_BASE}/governance/constraints${scope ? `?scope=${scope}` : ""}`).then((r) => r.json()),
  },

  cognition: {
    getState: USE_MOCK
      ? mockFetch<OperationalState>(MOCK_STATE)
      : () => fetch(`${API_BASE}/cognition/state`).then((r) => r.json()),
    getTransitions: USE_MOCK
      ? mockFetch<StateTransition[]>(MOCK_TRANSITIONS)
      : () => fetch(`${API_BASE}/cognition/transitions`).then((r) => r.json()),
    getForbiddenPatterns: USE_MOCK
      ? mockFetch<ForbiddenPattern[]>(MOCK_FORBIDDEN_PATTERNS)
      : () => fetch(`${API_BASE}/cognition/forbidden-patterns`).then((r) => r.json()),
    getSessions: USE_MOCK
      ? mockFetch<SessionInfo[]>(MOCK_SESSIONS)
      : () => fetch(`${API_BASE}/cognition/sessions`).then((r) => r.json()),
    getEvents: USE_MOCK
      ? mockFetch<CognitionEvent[]>(MOCK_COGNITION_EVENTS)
      : () => fetch(`${API_BASE}/cognition/events`).then((r) => r.json()),
  },

  memory: {
    getMemories: (page = 1) =>
      USE_MOCK
        ? mockResponse<EpisodicMemory[]>(MOCK_MEMORIES.slice((page - 1) * 5, page * 5))
        : fetch(`${API_BASE}/memory/memories?page=${page}`).then((r) => r.json()),
    searchMemories: (q: string) =>
      USE_MOCK
        ? mockResponse<EpisodicMemory[]>(MOCK_MEMORIES.filter((m) => m.content.toLowerCase().includes(q.toLowerCase())))
        : fetch(`${API_BASE}/memory/memories/search?q=${encodeURIComponent(q)}`).then((r) => r.json()),
    getInfluences: (sessionId?: string) =>
      USE_MOCK
        ? mockResponse<MemoryInfluence[]>(sessionId ? MOCK_INFLUENCES.filter((i) => MOCK_MEMORIES.some((m) => m.memory_id === i.memory_id && m.session_id === sessionId)) : MOCK_INFLUENCES)
        : fetch(`${API_BASE}/memory/influences${sessionId ? `?session_id=${sessionId}` : ""}`).then((r) => r.json()),
  },

  traceability: {
    getTraces: USE_MOCK
      ? mockFetch<CognitionTrace[]>(MOCK_TRACES)
      : () => fetch(`${API_BASE}/traceability/traces`).then((r) => r.json()),
    getTrace: (id: string) =>
      USE_MOCK
        ? mockResponse< CognitionTrace | undefined>(MOCK_TRACES.find((t) => t.trace_id === id))
        : fetch(`${API_BASE}/traceability/traces/${id}`).then((r) => r.json()),
    renderTrace: (id: string, format: string) =>
      USE_MOCK
        ? mockResponse<string>(`Trace ${id} rendered in ${format} format\n\n[MOCK TEXT RENDERING]\nTrace contains 3 state transitions, 3 governance checks, 2 memory influences.`)
        : fetch(`${API_BASE}/traceability/traces/${id}/render?format=${format}`).then((r) => r.json()),
  },

  audit: {
    getEvents: (filters?: AuditFilters) =>
      USE_MOCK
        ? mockResponse<AuditEvent[]>(
            MOCK_EVENTS.filter((e) => {
              if (filters?.severity && e.severity !== filters.severity) return false;
              if (filters?.event_type && e.event_type !== filters.event_type) return false;
              if (filters?.component && e.component !== filters.component) return false;
              return true;
            })
          )
        : fetch(`${API_BASE}/audit/events`, { method: "POST", body: JSON.stringify(filters), headers: { "Content-Type": "application/json" } }).then((r) => r.json()),
    getViolations: USE_MOCK
      ? mockFetch<AuditEvent[]>(MOCK_EVENTS.filter((e) => e.severity === "critical"))
      : () => fetch(`${API_BASE}/audit/violations`).then((r) => r.json()),
    getChecks: USE_MOCK
      ? mockFetch<number>(MOCK_OVERVIEW.traceability.avg_governance_checks)
      : () => fetch(`${API_BASE}/audit/checks`).then((r) => r.json()),
  },

  analytics: {
    getOverview: USE_MOCK
      ? mockFetch<AnalyticsOverview>(MOCK_OVERVIEW)
      : () => fetch(`${API_BASE}/analytics/overview`).then((r) => r.json()),
    getGovernancePressure: USE_MOCK
      ? mockFetch<PressureMetrics>(MOCK_PRESSURE)
      : () => fetch(`${API_BASE}/analytics/pressure`).then((r) => r.json()),
    getAlignmentTrends: USE_MOCK
      ? mockFetch<TrendPoint[]>(MOCK_OVERVIEW.trends.governance_trend)
      : () => fetch(`${API_BASE}/analytics/alignment`).then((r) => r.json()),
    getContinuityStability: USE_MOCK
      ? mockFetch<AnalyticsOverview["continuity"]>(MOCK_OVERVIEW.continuity)
      : () => fetch(`${API_BASE}/analytics/continuity`).then((r) => r.json()),
    getCognitionEcosystem: USE_MOCK
      ? mockFetch<EcosystemData>(MOCK_ECOSYSTEM)
      : () => fetch(`${API_BASE}/analytics/ecosystem`).then((r) => r.json()),
  },

  status: {
    getStatus: USE_MOCK
      ? mockFetch<RuntimeStatus>(MOCK_STATUS)
      : () => fetch(`${API_BASE}/status`).then((r) => r.json()),
    getHealth: USE_MOCK
      ? mockFetch<Record<string, string>>({ status: "healthy", uptime: "3d4h30m" })
      : () => fetch(`${API_BASE}/health`).then((r) => r.json()),
    getMetrics: USE_MOCK
      ? mockFetch<Record<string, number>>({ requests_per_minute: 12, avg_latency_ms: 45, error_rate: 0.001 })
      : () => fetch(`${API_BASE}/metrics`).then((r) => r.json()),
  },

  alerts: {
    getAlerts: (filters?: AlertFilters) =>
      USE_MOCK
        ? mockResponse<SystemAlert[]>(
            MOCK_ALERTS.filter((a) => {
              if (filters?.severity && a.severity !== filters.severity) return false;
              if (filters?.category && a.category !== filters.category) return false;
              if (filters?.source_schema && a.source_schema !== filters.source_schema) return false;
              if (filters?.status) {
                if (filters.status === "active" && (a.acknowledged || a.resolved)) return false;
                if (filters.status === "acknowledged" && !a.acknowledged) return false;
                if (filters.status === "resolved" && !a.resolved) return false;
              }
              return true;
            })
          )
        : fetch(`${API_BASE}/alerts`, { method: "POST", body: JSON.stringify(filters), headers: { "Content-Type": "application/json" } }).then((r) => r.json()),
    getAlert: (id: string) =>
      USE_MOCK
        ? mockResponse<SystemAlert | undefined>(MOCK_ALERTS.find((a) => a.alert_id === id))
        : fetch(`${API_BASE}/alerts/${id}`).then((r) => r.json()),
    acknowledge: (id: string, operator: string = "operator") =>
      USE_MOCK
        ? mockResponse<SystemAlert | undefined>((() => {
            const alert = MOCK_ALERTS.find((a) => a.alert_id === id);
            if (alert) { alert.acknowledged = true; alert.acknowledged_by = operator; }
            return alert;
          })())
        : fetch(`${API_BASE}/alerts/${id}/acknowledge`, { method: "POST", body: JSON.stringify({ operator }), headers: { "Content-Type": "application/json" } }).then((r) => r.json()),
    resolve: (id: string, operator: string = "operator") =>
      USE_MOCK
        ? mockResponse<SystemAlert | undefined>((() => {
            const alert = MOCK_ALERTS.find((a) => a.alert_id === id);
            if (alert) { alert.resolved = true; alert.resolved_by = operator; if (!alert.acknowledged) { alert.acknowledged = true; alert.acknowledged_by = operator; } }
            return alert;
          })())
        : fetch(`${API_BASE}/alerts/${id}/resolve`, { method: "POST", body: JSON.stringify({ operator }), headers: { "Content-Type": "application/json" } }).then((r) => r.json()),
  },

  topology: {
    getTopology: USE_MOCK
      ? mockFetch<TopologyData>(MOCK_TOPOLOGY)
      : () => fetch(`${API_BASE}/topology`).then((r) => r.json()),
    getComponent: (id: string) =>
      USE_MOCK
        ? mockResponse<TopologyData["nodes"][0] | undefined>(MOCK_TOPOLOGY.nodes.find((n) => n.id === id))
        : fetch(`${API_BASE}/topology/components/${id}`).then((r) => r.json()),
  },
};

// Re-export mock data for component use
export { MOCK_SCHEMAS, MOCK_STATE, MOCK_TRANSITIONS, MOCK_MEMORIES, MOCK_INFLUENCES, MOCK_TRACES, MOCK_EVENTS, MOCK_OVERVIEW, MOCK_STATUS, MOCK_COGNITION_EVENTS, MOCK_FORBIDDEN_PATTERNS, MOCK_SESSIONS, MOCK_PRESSURE, MOCK_ECOSYSTEM, MOCK_ALERTS, MOCK_TOPOLOGY };
