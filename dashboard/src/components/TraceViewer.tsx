// =============================================================================
// TraceViewer — Phase 3: Cognition trace visualization
// =============================================================================

import React, { useState } from "react";
import Panel from "./common/Panel";
import Badge from "./common/Badge";
import DataTable from "./common/DataTable";
import Timeline from "./common/Timeline";
import type { TimelineEntry } from "./common/Timeline";
import { useApi } from "@/hooks/useApi";
import { api } from "@/api";
import type { CognitionTrace } from "@/types";

const statusBadge = (s: string) => s as "pass" | "fail" | "warn" | "info";

const TraceViewer: React.FC = () => {
  const { data: traces } = useApi(api.traceability.getTraces);
  const [selected, setSelected] = useState<CognitionTrace | null>(null);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--gap)", height: "100%" }}>
      {/* Trace List */}
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)" }}>
        <Panel title="Cognition Traces" style={{ flex: 1 }}>
          <DataTable
            columns={[
              { key: "trace_id", header: "ID", width: "90px" },
              { key: "session_id", header: "Session", width: "110px" },
              {
                key: "status",
                header: "Status",
                width: "80px",
                render: (row: CognitionTrace) => <Badge label={row.status.toUpperCase()} variant={statusBadge(row.status === "completed" ? "pass" : row.status === "violated" ? "fail" : row.status === "active" ? "info" : "warn")} size="sm" />,
              },
              {
                key: "duration_ms",
                header: "Duration",
                width: "70px",
                render: (row: CognitionTrace) => <span className="mono">{row.duration_ms}ms</span>,
              },
              {
                key: "start_time",
                header: "Started",
                width: "80px",
                render: (row: CognitionTrace) => <span className="mono">{row.start_time.slice(11, 19)}</span>,
              },
              {
                key: "governance_checks",
                header: "Checks",
                width: "55px",
                render: (row: CognitionTrace) => <span className="mono">{row.governance_checks.length}</span>,
              },
              {
                key: "audit_events",
                header: "Events",
                width: "55px",
                render: (row: CognitionTrace) => <span className="mono">{row.audit_events.length}</span>,
              },
            ]}
            data={traces || []}
            keyExtractor={(row) => row.trace_id}
            onRowClick={(row) => setSelected(row)}
            selectedRow={selected?.trace_id ?? null}
          />
        </Panel>
      </div>

      {/* Trace Detail */}
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)", overflowY: "auto" }}>
        {selected ? (
          <>
            {/* Header */}
            <Panel title={`Trace: ${selected.trace_id}`}>
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontFamily: "var(--font-mono)", fontSize: 10 }}>
                <div><span style={{ color: "#666" }}>SESSION: </span><span style={{ color: "#3388ff" }}>{selected.session_id}</span></div>
                <div><span style={{ color: "#666" }}>STATUS: </span><Badge label={selected.status.toUpperCase()} variant={statusBadge(selected.status === "completed" ? "pass" : selected.status === "violated" ? "fail" : selected.status === "active" ? "info" : "warn")} size="sm" /></div>
                <div><span style={{ color: "#666" }}>DURATION: </span><span style={{ color: "#e0e0e0" }}>{selected.duration_ms}ms</span></div>
                <div><span style={{ color: "#666" }}>CHECKS: </span><span style={{ color: "#e0e0e0" }}>{selected.governance_checks.length}</span></div>
                <div><span style={{ color: "#666" }}>EVENTS: </span><span style={{ color: "#e0e0e0" }}>{selected.audit_events.length}</span></div>
                <div><span style={{ color: "#666" }}>INFLUENCES: </span><span style={{ color: "#e0e0e0" }}>{selected.memory_influences.length}</span></div>
              </div>
            </Panel>

            {/* State Transitions */}
            <Panel title="State Transitions" style={{ maxHeight: 200 }}>
              <Timeline
                entries={selected.state_transitions.map((t, i) => ({
                  id: `st-${i}`,
                  timestamp: t.timestamp.slice(11, 19),
                  label: `${t.from_state} → ${t.to_state}`,
                  detail: `trigger: ${t.trigger}`,
                  status: t.governance_check_passed ? "pass" : "fail",
                }))}
                maxHeight={140}
              />
            </Panel>

            {/* Governance Checks */}
            <Panel title="Governance Checks" style={{ maxHeight: 200 }}>
              <DataTable
                columns={[
                  { key: "check_id", header: "ID", width: "60px" },
                  { key: "schema_id", header: "Schema", width: "70px" },
                  {
                    key: "passed",
                    header: "Result",
                    width: "50px",
                    render: (row) => <Badge label={row.passed ? "PASS" : "FAIL"} variant={row.passed ? "pass" : "fail"} size="sm" />,
                  },
                  {
                    key: "severity",
                    header: "Sev",
                    width: "50px",
                    render: (row) => <Badge label={row.severity.toUpperCase()} variant={row.severity as "critical" | "warn" | "info" | "low"} size="sm" />,
                  },
                  { key: "details", header: "Details", render: (row) => row.details ?? "—" },
                ]}
                data={selected.governance_checks}
                keyExtractor={(row) => row.check_id}
              />
            </Panel>

            {/* Memory Influences */}
            <Panel title="Memory Influences" style={{ maxHeight: 180 }}>
              <DataTable
                columns={[
                  { key: "influence_id", header: "ID", width: "60px" },
                  { key: "memory_id", header: "Memory", width: "70px" },
                  { key: "influence_type", header: "Type", width: "100px" },
                  {
                    key: "strength",
                    header: "Str",
                    width: "40px",
                    render: (row) => <span style={{ color: row.strength > 0.8 ? "#33ff33" : row.strength > 0.5 ? "#ffaa00" : "#ff3333" }}>{(row.strength * 100).toFixed(0)}%</span>,
                  },
                  {
                    key: "trace_visible",
                    header: "Vis",
                    width: "40px",
                    render: (row) => <span style={{ color: row.trace_visible ? "#33ff33" : "#666" }}>{row.trace_visible ? "Y" : "N"}</span>,
                  },
                ]}
                data={selected.memory_influences}
                keyExtractor={(row) => row.influence_id}
              />
            </Panel>

            {/* Audit Events */}
            <Panel title="Audit Events" style={{ maxHeight: 200 }}>
              <DataTable
                columns={[
                  { key: "event_id", header: "ID", width: "60px" },
                  { key: "event_type", header: "Type", width: "100px" },
                  {
                    key: "severity",
                    header: "Sev",
                    width: "50px",
                    render: (row) => <Badge label={row.severity.toUpperCase()} variant={row.severity as "critical" | "warn" | "info" | "low"} size="sm" />,
                  },
                  { key: "component", header: "Comp", width: "60px" },
                  { key: "timestamp", header: "Time", width: "60px", render: (row) => row.timestamp.slice(11, 19) },
                  { key: "message", header: "Message", render: (row) => row.message ?? "—" },
                ]}
                data={selected.audit_events}
                keyExtractor={(row) => row.event_id}
              />
            </Panel>
          </>
        ) : (
          <Panel title="Trace Detail">
            <div style={{ color: "#666", fontFamily: "var(--font-mono)", fontSize: 11, padding: 40, textAlign: "center" }}>
              Select a trace to view full detail
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
};

export default TraceViewer;
