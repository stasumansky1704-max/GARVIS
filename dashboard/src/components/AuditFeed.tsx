// =============================================================================
// AuditFeed — Phase 3: Audit event feed with filtering and search
// =============================================================================

import React, { useState, useMemo } from "react";
import Panel from "./common/Panel";
import Badge from "./common/Badge";
import DataTable from "./common/DataTable";
import { useApi } from "@/hooks/useApi";
import { api } from "@/api";
import type { AuditEvent } from "@/types";

const severityBadge = (s: string) => s as "critical" | "warn" | "info" | "low";

const AuditFeed: React.FC = () => {
  const { data: events } = useApi(api.audit.getEvents);
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [componentFilter, setComponentFilter] = useState<string>("all");

  const filtered = useMemo(() => {
    if (!events) return [];
    return events.filter((e) => {
      if (severityFilter !== "all" && e.severity !== severityFilter) return false;
      if (componentFilter !== "all" && e.component !== componentFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          e.event_id.toLowerCase().includes(q) ||
          e.event_type.toLowerCase().includes(q) ||
          e.component.toLowerCase().includes(q) ||
          (e.message ?? "").toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [events, search, severityFilter, componentFilter]);

  const components = useMemo((): string[] => {
    if (!events) return ["all"];
    return ["all", ...Array.from(new Set(events.map((e: any) => e.component))) as string[]];
  }, [events]);

  const handleExport = () => {
    const csv = [
      "event_id,event_type,severity,component,timestamp,message",
      ...filtered.map(
        (e) =>
          `${e.event_id},${e.event_type},${e.severity},${e.component},${e.timestamp},"${(e.message ?? "").replace(/"/g, '""')}"`
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `garvis-audit-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)", height: "100%" }}>
      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--gap)" }}>
        <div className="metric-card">
          <div className="metric-label">Total Events</div>
          <div className="metric-value" style={{ color: "#3388ff" }}>{events?.length ?? 0}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Critical</div>
          <div className="metric-value" style={{ color: "#ff3333" }}>{events?.filter((e) => e.severity === "critical").length ?? 0}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Warnings</div>
          <div className="metric-value" style={{ color: "#ffaa00" }}>{events?.filter((e) => e.severity === "warning").length ?? 0}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Info</div>
          <div className="metric-value" style={{ color: "#8888aa" }}>{events?.filter((e) => e.severity === "info").length ?? 0}</div>
        </div>
      </div>

      {/* Table */}
      <Panel
        title="Audit Events"
        style={{ flex: 1 }}
        actions={
          <>
            <input
              placeholder="SEARCH..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ width: 120 }}
            />
            <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}>
              <option value="all">ALL SEVERITIES</option>
              <option value="critical">CRITICAL</option>
              <option value="warning">WARNING</option>
              <option value="info">INFO</option>
            </select>
            <select value={componentFilter} onChange={(e) => setComponentFilter(e.target.value)}>
              {components.map((c) => (
                <option key={c} value={c}>{c === "all" ? "ALL COMPONENTS" : c.toUpperCase()}</option>
              ))}
            </select>
            <button className="btn" onClick={handleExport}>EXPORT</button>
          </>
        }
      >
        <DataTable
          columns={[
            { key: "timestamp", header: "Time", width: "80px", render: (row: AuditEvent) => <span className="mono">{row.timestamp.slice(11, 19)}</span> },
            { key: "event_id", header: "ID", width: "80px" },
            {
              key: "severity",
              header: "Severity",
              width: "80px",
              render: (row: AuditEvent) => <Badge label={row.severity.toUpperCase()} variant={severityBadge(row.severity)} size="sm" />,
            },
            { key: "event_type", header: "Type", width: "110px" },
            { key: "component", header: "Component", width: "90px" },
            { key: "message", header: "Message", render: (row: AuditEvent) => row.message ?? "—" },
          ]}
          data={filtered}
          keyExtractor={(row) => row.event_id}
          maxHeight={460}
        />
      </Panel>
    </div>
  );
};

export default AuditFeed;
