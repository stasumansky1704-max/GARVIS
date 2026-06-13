// =============================================================================
// GovernancePanel — Phase 3: Active governance schemas display
// =============================================================================

import React, { useState } from "react";
import Panel from "./common/Panel";
import Badge from "./common/Badge";
import DataTable from "./common/DataTable";
import { useApi } from "@/hooks/useApi";
import { api } from "@/api";
import type { GovernanceSchema } from "@/types";

const categoryVariant = (cat: string) => cat as "epistemic" | "operational" | "boundary" | "reflective" | "session";

const GovernancePanel: React.FC = () => {
  const { data: schemas, loading } = useApi(api.governance.getSchemas);
  const [selectedSchema, setSelectedSchema] = useState<GovernanceSchema | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [showInactive, setShowInactive] = useState(false);

  const filtered = (schemas || []).filter((s) => {
    if (filterCategory !== "all" && s.category !== filterCategory) return false;
    if (!showInactive && !s.active) return false;
    return true;
  });

  const categories = ["all", "epistemic", "operational", "boundary", "reflective", "session"];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)", height: "100%" }}>
      {/* Stats Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--gap)" }}>
        <div className="metric-card">
          <div className="metric-label">Active Schemas</div>
          <div className="metric-value" style={{ color: "#33ff33" }}>{schemas?.filter((s) => s.active).length ?? "—"}</div>
          <div className="metric-sub">of {schemas?.length ?? 0} total</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Total Policies</div>
          <div className="metric-value" style={{ color: "#3388ff" }}>{schemas?.reduce((s, x) => s + x.policies, 0) ?? "—"}</div>
          <div className="metric-sub">across all schemas</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Total Constraints</div>
          <div className="metric-value" style={{ color: "#ff33ff" }}>{schemas?.reduce((s, x) => s + x.constraints, 0) ?? "—"}</div>
          <div className="metric-sub">hard + soft</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Coverage Score</div>
          <div className="metric-value" style={{ color: "#ffaa00" }}>94%</div>
          <div className="metric-sub">target: 95%</div>
        </div>
      </div>

      {/* Schema Table */}
      <Panel
        title="Governance Schemas"
        actions={
          <>
            <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}>
              {categories.map((c) => (
                <option key={c} value={c}>{c === "all" ? "ALL CATEGORIES" : c.toUpperCase()}</option>
              ))}
            </select>
            <label style={{ display: "flex", alignItems: "center", gap: 4, fontFamily: "var(--font-mono)", fontSize: 9, color: "#8888aa", cursor: "pointer" }}>
              <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} style={{ width: 12, height: 12 }} />
              SHOW INACTIVE
            </label>
          </>
        }
        style={{ flex: 1 }}
      >
        {loading ? (
          <div style={{ color: "#666", fontFamily: "var(--font-mono)", fontSize: 11, padding: 20, textAlign: "center" }}>
            Loading schemas...
          </div>
        ) : (
          <DataTable
            columns={[
              { key: "schema_id", header: "ID", width: "80px" },
              { key: "name", header: "Name" },
              {
                key: "category",
                header: "Category",
                width: "110px",
                render: (row: GovernanceSchema) => <Badge label={row.category.toUpperCase()} variant={categoryVariant(row.category)} size="sm" />,
              },
              {
                key: "active",
                header: "Status",
                width: "70px",
                render: (row: GovernanceSchema) => <Badge label={row.active ? "ACTIVE" : "OFF"} variant={row.active ? "active" : "inactive"} size="sm" />,
              },
              { key: "version", header: "Version", width: "70px" },
              { key: "policies", header: "Policies", width: "70px" },
              { key: "constraints", header: "Constraints", width: "90px" },
            ]}
            data={filtered}
            keyExtractor={(row) => row.schema_id}
            onRowClick={(row) => setSelectedSchema(row)}
            selectedRow={selectedSchema?.schema_id ?? null}
          />
        )}
      </Panel>

      {/* Schema Detail */}
      {selectedSchema && (
        <Panel title={`Schema Detail: ${selectedSchema.schema_id}`} style={{ maxHeight: 160, flexShrink: 0 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, fontFamily: "var(--font-mono)", fontSize: 11 }}>
            <div>
              <div style={{ color: "#666", fontSize: 9, textTransform: "uppercase", marginBottom: 2 }}>Name</div>
              <div style={{ color: "#e0e0e0" }}>{selectedSchema.name}</div>
            </div>
            <div>
              <div style={{ color: "#666", fontSize: 9, textTransform: "uppercase", marginBottom: 2 }}>Version</div>
              <div style={{ color: "#e0e0e0" }}>{selectedSchema.version}</div>
            </div>
            <div>
              <div style={{ color: "#666", fontSize: 9, textTransform: "uppercase", marginBottom: 2 }}>Last Updated</div>
              <div style={{ color: "#e0e0e0" }}>{selectedSchema.last_updated?.replace("T", " ").slice(0, 16) ?? "—"}</div>
            </div>
          </div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "#8888aa", marginTop: 4 }}>
            {selectedSchema.description}
          </div>
        </Panel>
      )}
    </div>
  );
};

export default GovernancePanel;
