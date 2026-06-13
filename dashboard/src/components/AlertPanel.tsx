// =============================================================================
// AlertPanel — Dedicated alerts view for the GARVIS Operator Governance Console
// =============================================================================

import React, { useState, useMemo } from "react";
import { MOCK_ALERTS } from "../api";
import type { SystemAlert, AlertSeverity, AlertCategory, AlertStatus } from "../types";

// Severity color configuration
const SEVERITY_COLORS: Record<AlertSeverity, { bg: string; text: string }> = {
  critical: { bg: "#ff3333", text: "#ffffff" },
  warning: { bg: "#ffaa00", text: "#000000" },
  info: { bg: "#3388ff", text: "#ffffff" },
  debug: { bg: "#666666", text: "#ffffff" },
};

const STATUS_LABEL = (alert: SystemAlert): AlertStatus => {
  if (alert.resolved) return "resolved";
  if (alert.acknowledged) return "acknowledged";
  return "active";
};

const STATUS_COLOR: Record<AlertStatus, string> = {
  active: "#ff3333",
  acknowledged: "#ffaa00",
  resolved: "#33ff33",
};

// Filter options
const SEVERITY_OPTIONS: (AlertSeverity | "all")[] = ["all", "critical", "warning", "info", "debug"];
const CATEGORY_OPTIONS: (AlertCategory | "all")[] = ["all", "governance", "cognition", "system", "memory", "traceability", "inference", "monitoring"];
const STATUS_OPTIONS: (AlertStatus | "all")[] = ["all", "active", "acknowledged", "resolved"];

const AlertPanel: React.FC = () => {
  const [selectedAlert, setSelectedAlert] = useState<SystemAlert | null>(null);
  const [severityFilter, setSeverityFilter] = useState<AlertSeverity | "all">("all");
  const [categoryFilter, setCategoryFilter] = useState<AlertCategory | "all">("all");
  const [statusFilter, setStatusFilter] = useState<AlertStatus | "all">("all");
  const [schemaFilter, setSchemaFilter] = useState<string>("all");
  const [alerts, setAlerts] = useState<SystemAlert[]>(MOCK_ALERTS);

  // Unique schema list for filter dropdown
  const schemas = useMemo(() => {
    const s = new Set<string>();
    alerts.forEach((a) => { if (a.source_schema) s.add(a.source_schema); });
    return ["all", ...Array.from(s).sort()];
  }, [alerts]);

  // Filtered alerts
  const filteredAlerts = useMemo(() => {
    return alerts.filter((a) => {
      if (severityFilter !== "all" && a.severity !== severityFilter) return false;
      if (categoryFilter !== "all" && a.category !== categoryFilter) return false;
      if (schemaFilter !== "all" && a.source_schema !== schemaFilter) return false;
      if (statusFilter !== "all") {
        const status = STATUS_LABEL(a);
        if (status !== statusFilter) return false;
      }
      return true;
    }).sort((a, b) => {
      // Sort by severity priority, then by timestamp desc
      const sevOrder: Record<AlertSeverity, number> = { critical: 0, warning: 1, info: 2, debug: 3 };
      const diff = sevOrder[a.severity] - sevOrder[b.severity];
      if (diff !== 0) return diff;
      return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
    });
  }, [alerts, severityFilter, categoryFilter, statusFilter, schemaFilter]);

  // Summary counts
  const summary = useMemo(() => {
    const critical = alerts.filter((a) => a.severity === "critical" && !a.resolved).length;
    const warning = alerts.filter((a) => a.severity === "warning" && !a.resolved).length;
    const info = alerts.filter((a) => a.severity === "info" && !a.resolved).length;
    const active = alerts.filter((a) => !a.acknowledged && !a.resolved).length;
    return { critical, warning, info, active };
  }, [alerts]);

  const handleAcknowledge = (alertId: string) => {
    setAlerts((prev) =>
      prev.map((a) =>
        a.alert_id === alertId ? { ...a, acknowledged: true, acknowledged_by: "operator" } : a
      )
    );
    if (selectedAlert?.alert_id === alertId) {
      setSelectedAlert((prev) => prev ? { ...prev, acknowledged: true, acknowledged_by: "operator" } : null);
    }
  };

  const handleResolve = (alertId: string) => {
    setAlerts((prev) =>
      prev.map((a) =>
        a.alert_id === alertId
          ? { ...a, acknowledged: true, resolved: true, acknowledged_by: a.acknowledged_by || "operator", resolved_by: "operator" }
          : a
      )
    );
    if (selectedAlert?.alert_id === alertId) {
      setSelectedAlert((prev) =>
        prev ? { ...prev, acknowledged: true, resolved: true, acknowledged_by: prev.acknowledged_by || "operator", resolved_by: "operator" } : null
      );
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)", height: "100%", overflow: "hidden" }}>
      {/* Alert Summary Bar */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--gap)" }}>
        <div className="metric-card" style={{ borderLeft: "3px solid #ff3333" }}>
          <div className="metric-label">Critical</div>
          <div className="metric-value" style={{ color: "#ff3333" }}>{summary.critical}</div>
          <div className="metric-sub">unresolved</div>
        </div>
        <div className="metric-card" style={{ borderLeft: "3px solid #ffaa00" }}>
          <div className="metric-label">Warning</div>
          <div className="metric-value" style={{ color: "#ffaa00" }}>{summary.warning}</div>
          <div className="metric-sub">unresolved</div>
        </div>
        <div className="metric-card" style={{ borderLeft: "3px solid #3388ff" }}>
          <div className="metric-label">Info</div>
          <div className="metric-value" style={{ color: "#3388ff" }}>{summary.info}</div>
          <div className="metric-sub">unresolved</div>
        </div>
        <div className="metric-card" style={{ borderLeft: "3px solid #ff33ff" }}>
          <div className="metric-label">Active</div>
          <div className="metric-value" style={{ color: "#ff33ff" }}>{summary.active}</div>
          <div className="metric-sub">unacknowledged</div>
        </div>
      </div>

      {/* Filter Controls */}
      <div className="panel" style={{ padding: "8px 12px", flexDirection: "row", gap: 12, alignItems: "center", flexShrink: 0 }}>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", color: "var(--text-dim)", whiteSpace: "nowrap" }}>Filters:</span>
        <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value as AlertSeverity | "all")}>
          {SEVERITY_OPTIONS.map((s) => (
            <option key={s} value={s}>{s === "all" ? "All Severities" : s.charAt(0).toUpperCase() + s.slice(1)}</option>
          ))}
        </select>
        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value as AlertCategory | "all")}>
          {CATEGORY_OPTIONS.map((c) => (
            <option key={c} value={c}>{c === "all" ? "All Categories" : c.charAt(0).toUpperCase() + c.slice(1)}</option>
          ))}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as AlertStatus | "all")}>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s === "all" ? "All Statuses" : s.charAt(0).toUpperCase() + s.slice(1)}</option>
          ))}
        </select>
        <select value={schemaFilter} onChange={(e) => setSchemaFilter(e.target.value)}>
          {schemas.map((s) => (
            <option key={s} value={s}>{s === "all" ? "All Schemas" : s}</option>
          ))}
        </select>
        <div style={{ flex: 1 }} />
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-dim)" }}>
          {filteredAlerts.length} alert{filteredAlerts.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Main Content: Table + Detail */}
      <div style={{ display: "grid", gridTemplateColumns: selectedAlert ? "1.4fr 1fr" : "1fr", gap: "var(--gap)", flex: 1, minHeight: 0 }}>
        {/* Alerts Table */}
        <div className="panel" style={{ overflow: "hidden" }}>
          <div className="panel-header">
            <span className="panel-title">Active Alerts</span>
          </div>
          <div className="panel-body" style={{ overflowY: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Severity</th>
                  <th>Category</th>
                  <th>Title</th>
                  <th>Component</th>
                  <th>Time</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredAlerts.map((alert) => {
                  const sevColors = SEVERITY_COLORS[alert.severity];
                  const status = STATUS_LABEL(alert);
                  const isSelected = selectedAlert?.alert_id === alert.alert_id;
                  return (
                    <tr
                      key={alert.alert_id}
                      className={isSelected ? "selected" : ""}
                      onClick={() => setSelectedAlert(alert)}
                      style={{ cursor: "pointer" }}
                    >
                      <td style={{ fontSize: 10, color: "var(--text-dim)" }}>{alert.alert_id}</td>
                      <td>
                        <span
                          className="badge badge-sm"
                          style={{
                            background: sevColors.bg,
                            color: sevColors.text,
                            border: "none",
                          }}
                        >
                          {alert.severity.toUpperCase()}
                        </span>
                      </td>
                      <td>
                        <span style={{ color: "var(--text-secondary)", fontSize: 10, textTransform: "capitalize" }}>
                          {alert.category}
                        </span>
                      </td>
                      <td style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {alert.title}
                      </td>
                      <td style={{ fontSize: 10, color: "var(--text-dim)" }}>{alert.source_component}</td>
                      <td style={{ fontSize: 10, color: "var(--text-dim)", whiteSpace: "nowrap" }}>
                        {alert.timestamp.slice(11, 16)}
                      </td>
                      <td>
                        <span
                          className="badge badge-sm"
                          style={{
                            borderColor: STATUS_COLOR[status],
                            color: STATUS_COLOR[status],
                            background: `${STATUS_COLOR[status]}15`,
                          }}
                        >
                          {status.toUpperCase()}
                        </span>
                      </td>
                    </tr>
                  );
                })}
                {filteredAlerts.length === 0 && (
                  <tr>
                    <td colSpan={7} style={{ textAlign: "center", color: "var(--text-dim)", padding: 24 }}>
                      No alerts match the current filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Detail Panel */}
        {selectedAlert && (
          <div className="panel" style={{ overflow: "hidden", animation: "fadeIn 0.2s ease-out" }}>
            <div className="panel-header" style={{ justifyContent: "space-between" }}>
              <span className="panel-title">Alert Detail</span>
              <button className="btn" onClick={() => setSelectedAlert(null)}>Close</button>
            </div>
            <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {/* Severity banner */}
              <div
                style={{
                  background: SEVERITY_COLORS[selectedAlert.severity].bg,
                  color: SEVERITY_COLORS[selectedAlert.severity].text,
                  padding: "8px 12px",
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: 1,
                }}
              >
                {selectedAlert.severity} — {selectedAlert.category}
              </div>

              {/* Title */}
              <div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>
                  Title
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", lineHeight: 1.4 }}>
                  {selectedAlert.title}
                </div>
              </div>

              {/* Description */}
              <div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>
                  Description
                </div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>
                  {selectedAlert.description}
                </div>
              </div>

              {/* Metadata grid */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase" }}>Alert ID</div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-primary)" }}>{selectedAlert.alert_id}</div>
                </div>
                <div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase" }}>Status</div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: STATUS_COLOR[STATUS_LABEL(selectedAlert)] }}>
                    {STATUS_LABEL(selectedAlert).toUpperCase()}
                  </div>
                </div>
                <div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase" }}>Component</div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-primary)" }}>{selectedAlert.source_component}</div>
                </div>
                <div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase" }}>Timestamp</div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-primary)" }}>{selectedAlert.timestamp}</div>
                </div>
                {selectedAlert.source_schema && (
                  <>
                    <div>
                      <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase" }}>Source Schema</div>
                      <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--color-info)" }}>{selectedAlert.source_schema}</div>
                    </div>
                    <div />
                  </>
                )}
                {selectedAlert.acknowledged_by && (
                  <div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase" }}>Acknowledged By</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-primary)" }}>{selectedAlert.acknowledged_by}</div>
                  </div>
                )}
                {selectedAlert.resolved_by && (
                  <div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase" }}>Resolved By</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-primary)" }}>{selectedAlert.resolved_by}</div>
                  </div>
                )}
              </div>

              {/* Notes */}
              {selectedAlert.notes && (
                <div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>
                    Notes
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5, background: "var(--bg-primary)", padding: 8 }}>
                    {selectedAlert.notes}
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div style={{ display: "flex", gap: 8, marginTop: "auto", paddingTop: 8, borderTop: "1px solid var(--border-color)" }}>
                {!selectedAlert.acknowledged && (
                  <button className="btn btn-primary" onClick={() => handleAcknowledge(selectedAlert.alert_id)}>
                    Acknowledge
                  </button>
                )}
                {!selectedAlert.resolved && (
                  <button className="btn" style={{ background: "rgba(51,255,51,0.1)", borderColor: "#33ff33", color: "#33ff33" }} onClick={() => handleResolve(selectedAlert.alert_id)}>
                    Resolve
                  </button>
                )}
                {selectedAlert.resolved && (
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "#33ff33", display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: 14 }}>&#10003;</span> Resolved
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AlertPanel;
