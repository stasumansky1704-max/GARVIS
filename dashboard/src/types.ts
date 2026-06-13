// =============================================================================
// GARVIS — Governance-Aware Reflective Virtual Intelligence System
// TypeScript type definitions for Operator Governance Console
// =============================================================================

export interface GovernanceSchema {
  schema_id: string;
  name: string;
  version: string;
  category: SchemaCategory;
  policies: number;
  constraints: number;
  active: boolean;
  description?: string;
  last_updated?: string;
}

export type SchemaCategory =
  | "epistemic"
  | "operational"
  | "boundary"
  | "reflective"
  | "session";

export interface OperationalState {
  state: string;
  since: string;
  transitions_today: number;
}

export interface StateTransition {
  from_state: string;
  to_state: string;
  trigger: string;
  timestamp: string;
  governance_check_passed: boolean;
}

export interface GovernanceCheck {
  check_id: string;
  schema_id: string;
  policy_id: string;
  passed: boolean;
  severity: SeverityLevel;
  details?: string;
  timestamp?: string;
}

export type SeverityLevel = "critical" | "warning" | "info" | "low";

export interface EpisodicMemory {
  memory_id: string;
  session_id: string;
  episode_type: string;
  content: string;
  confidence: number;
  timestamp: string;
  retrieval_count: number;
  provenance_chain?: ProvenanceEntry[];
}

export interface ProvenanceEntry {
  step: number;
  source: string;
  operation: string;
  timestamp: string;
}

export interface MemoryInfluence {
  influence_id: string;
  memory_id: string;
  target_inference_id: string;
  influence_type: string;
  strength: number;
  trace_visible: boolean;
}

export interface AuditEvent {
  event_id: string;
  event_type: string;
  severity: SeverityLevel;
  component: string;
  timestamp: string;
  details: Record<string, unknown>;
  message?: string;
}

export interface CognitionTrace {
  trace_id: string;
  session_id: string;
  status: TraceStatus;
  duration_ms: number;
  start_time: string;
  end_time?: string;
  state_transitions: StateTransition[];
  governance_checks: GovernanceCheck[];
  memory_influences: MemoryInfluence[];
  audit_events: AuditEvent[];
}

export type TraceStatus = "active" | "completed" | "failed" | "violated";

export interface TrendPoint {
  timestamp: string;
  value: number;
}

export interface AnalyticsOverview {
  governance: {
    active_schemas: number;
    total_constraints: number;
    hard_stop_rate: number;
    coverage_score: number;
    pressure: number;
  };
  cognition: {
    current_state: string;
    session_count: number;
    success_rate: number;
    avg_response_time_ms: number;
    quality_score: number;
  };
  memory: {
    total_memories: number;
    avg_retrievals: number;
    influences_tracked: number;
    trace_visible_rate: number;
  };
  traceability: {
    total_traces: number;
    avg_governance_checks: number;
    violation_count: number;
    audit_event_count: number;
  };
  continuity: {
    continuity_score: number;
    alignment_drift: number;
    resilience_score: number;
    equilibrium_stability: number;
  };
  pressure: {
    adaptation_pressure: number;
    enforcement_pressure: number;
    conflict_pressure: number;
    overall_pressure: number;
  };
  trends: {
    governance_trend: TrendPoint[];
    state_stability_trend: TrendPoint[];
    quality_trend: TrendPoint[];
    degradation_trend: TrendPoint[];
  };
  ecosystem: {
    governance_nodes: number;
    memory_nodes: number;
    reasoning_nodes: number;
    total_edges: number;
    alignment_ecology: Record<string, unknown>;
  };
}

export interface RuntimeStatus {
  state: string;
  uptime_seconds: number;
  version: string;
  components: ComponentStatus[];
}

export interface ComponentStatus {
  name: string;
  status: "healthy" | "degraded" | "critical" | "unknown";
  last_check: string;
  message?: string;
}

export interface AuditFilters {
  severity?: SeverityLevel;
  event_type?: string;
  component?: string;
  since?: string;
  until?: string;
}

export interface CognitionEvent {
  event_id: string;
  event_type: string;
  severity: SeverityLevel;
  message: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

export interface ForbiddenPattern {
  pattern_id: string;
  description: string;
  category: string;
  violation_count: number;
  last_triggered?: string;
}

export interface SessionInfo {
  session_id: string;
  state: string;
  started_at: string;
  ended_at?: string;
  trace_count: number;
  event_count: number;
}

export interface PressureMetrics {
  schema_pressures: SchemaPressure[];
  overall: {
    adaptation: number;
    enforcement: number;
    conflict: number;
    total: number;
  };
  history: TrendPoint[];
}

export interface SchemaPressure {
  schema_id: string;
  schema_name: string;
  adaptation: number;
  enforcement: number;
  conflict: number;
  total: number;
}

export interface EcosystemNode {
  id: string;
  label: string;
  type: "governance" | "memory" | "reasoning" | "session";
  x?: number;
  y?: number;
  radius?: number;
  metadata?: Record<string, unknown>;
}

export interface EcosystemEdge {
  source: string;
  target: string;
  label?: string;
  strength: number;
  type: string;
}

export interface EcosystemData {
  nodes: EcosystemNode[];
  edges: EcosystemEdge[];
}

export type ConsoleView =
  | "overview"
  | "governance"
  | "cognition"
  | "memory"
  | "traceability"
  | "audit"
  | "analytics"
  | "ecosystem"
  | "alerts"
  | "topology";

// =============================================================================
// Alert Types
// =============================================================================

export type AlertSeverity = "critical" | "warning" | "info" | "debug";
export type AlertStatus = "active" | "acknowledged" | "resolved";
export type AlertCategory = "governance" | "cognition" | "system" | "memory" | "traceability" | "inference" | "monitoring" | "analytics";

export interface SystemAlert {
  alert_id: string;
  severity: AlertSeverity;
  category: AlertCategory;
  title: string;
  description: string;
  source_schema?: string;
  source_component: string;
  timestamp: string;
  acknowledged: boolean;
  resolved: boolean;
  acknowledged_by?: string;
  resolved_by?: string;
  notes?: string;
}

export interface AlertFilters {
  severity?: AlertSeverity;
  category?: AlertCategory;
  source_schema?: string;
  status?: AlertStatus;
}

// =============================================================================
// Topology Types
// =============================================================================

export type TopologyNodeStatus = "healthy" | "degraded" | "critical" | "unknown";
export type TopologyLayer = "governance" | "cognition" | "memory" | "traceability" | "inference" | "runtime" | "analytics" | "monitoring";
export type EdgeType = "dependency" | "influence" | "mediation" | "initialization" | "monitoring" | "analysis";

export interface TopologyNode {
  id: string;
  layer: TopologyLayer;
  status: TopologyNodeStatus;
  label: string;
  description?: string;
  version?: string;
  last_check?: string;
}

export interface TopologyEdge {
  from: string;
  to: string;
  type: EdgeType;
  label?: string;
}

export interface TopologyData {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

export interface WebSocketMessage {
  type: string;
  data: unknown;
  timestamp: string;
}
