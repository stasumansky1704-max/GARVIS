// =============================================================================
// MemoryExplorer — Phase 3 + Phase 5: Episodic memory browser
// =============================================================================

import React, { useState, useMemo } from "react";
import Panel from "./common/Panel";
import Badge from "./common/Badge";
import DataTable from "./common/DataTable";
import { useApi } from "@/hooks/useApi";
import { api, MOCK_INFLUENCES } from "@/api";
import type { EpisodicMemory, MemoryInfluence } from "@/types";

const typeBadge = (t: string) => {
  const map: Record<string, string> = { inference: "info", correction: "warn", observation: "memory", governance_event: "fail", reflection: "governance", operator_interaction: "pass", system_event: "default" };
  return (map[t] || "default") as "info" | "warn" | "memory" | "fail" | "governance" | "pass" | "default";
};

const MemoryExplorer: React.FC = () => {
  const { data: memories, loading } = useApi(api.memory.getMemories);
  const [selected, setSelected] = useState<EpisodicMemory | null>(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");

  const filtered = useMemo(() => {
    if (!memories) return [];
    return memories.filter((m) => {
      if (typeFilter !== "all" && m.episode_type !== typeFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        return m.content.toLowerCase().includes(q) || m.memory_id.toLowerCase().includes(q);
      }
      return true;
    });
  }, [memories, search, typeFilter]);

  const types = useMemo((): string[] => {
    if (!memories) return ["all"];
    return ["all", ...Array.from(new Set(memories.map((m: any) => m.episode_type))) as string[]];
  }, [memories]);

  const influences = useMemo(() => {
    if (!selected) return [];
    return MOCK_INFLUENCES.filter((i) => i.memory_id === selected.memory_id);
  }, [selected]);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gridTemplateRows: "auto 1fr", gap: "var(--gap)", height: "100%" }}>
      {/* Stats */}
      <div className="metric-card">
        <div className="metric-label">Total Memories</div>
        <div className="metric-value" style={{ color: "#00ffff" }}>{memories?.length ?? 0}</div>
      </div>
      <div className="metric-card">
        <div className="metric-label">Influences Tracked</div>
        <div className="metric-value" style={{ color: "#ff33ff" }}>{MOCK_INFLUENCES.length}</div>
      </div>

      {/* Memory List */}
      <Panel
        title="Episodic Memories"
        actions={
          <>
            <input placeholder="SEARCH..." value={search} onChange={(e) => setSearch(e.target.value)} style={{ width: 100 }} />
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              {types.map((t) => <option key={t} value={t}>{t === "all" ? "ALL TYPES" : t.toUpperCase()}</option>)}
            </select>
          </>
        }
        style={{ gridRow: "2", gridColumn: "1" }}
      >
        {loading ? (
          <div style={{ color: "#666", fontFamily: "var(--font-mono)", fontSize: 11, padding: 20, textAlign: "center" }}>Loading memories...</div>
        ) : (
          <DataTable
            columns={[
              { key: "memory_id", header: "ID", width: "70px" },
              { key: "timestamp", header: "Time", width: "70px", render: (row: EpisodicMemory) => <span className="mono">{row.timestamp.slice(11, 16)}</span> },
              {
                key: "episode_type",
                header: "Type",
                width: "90px",
                render: (row: EpisodicMemory) => <Badge label={row.episode_type.toUpperCase()} variant={typeBadge(row.episode_type)} size="sm" />,
              },
              { key: "content", header: "Content", render: (row: EpisodicMemory) => row.content.length > 80 ? row.content.slice(0, 80) + "..." : row.content },
              { key: "confidence", header: "Conf", width: "50px", render: (row: EpisodicMemory) => <span style={{ color: row.confidence > 0.9 ? "#33ff33" : row.confidence > 0.7 ? "#ffaa00" : "#ff3333" }}>{(row.confidence * 100).toFixed(0)}%</span> },
              { key: "retrieval_count", header: "Uses", width: "40px" },
            ]}
            data={filtered}
            keyExtractor={(row) => row.memory_id}
            onRowClick={(row) => setSelected(row)}
            selectedRow={selected?.memory_id ?? null}
          />
        )}
      </Panel>

      {/* Memory Detail */}
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)", gridRow: "2", gridColumn: "2" }}>
        {selected ? (
          <>
            <Panel title={`Memory: ${selected.memory_id}`} style={{ flex: "0 0 auto" }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                  <div><span style={{ color: "#666" }}>Type: </span><Badge label={selected.episode_type.toUpperCase()} variant={typeBadge(selected.episode_type)} size="sm" /></div>
                  <div><span style={{ color: "#666" }}>Session: </span><span style={{ color: "#3388ff" }}>{selected.session_id}</span></div>
                  <div><span style={{ color: "#666" }}>Confidence: </span><span style={{ color: selected.confidence > 0.9 ? "#33ff33" : "#ffaa00" }}>{(selected.confidence * 100).toFixed(1)}%</span></div>
                  <div><span style={{ color: "#666" }}>Retrievals: </span><span style={{ color: "#e0e0e0" }}>{selected.retrieval_count}</span></div>
                </div>
                <div style={{ color: "#e0e0e0", lineHeight: 1.6, padding: "6px 0", borderTop: "1px solid #2a2a4a" }}>
                  {selected.content}
                </div>
                <div style={{ color: "#666", fontSize: 9 }}>Recorded: {selected.timestamp.replace("T", " ").slice(0, 19)}</div>
              </div>
            </Panel>

            {/* Influence Graph */}
            <Panel title="Memory Influences" style={{ flex: 1 }}>
              {influences.length === 0 ? (
                <div style={{ color: "#666", fontFamily: "var(--font-mono)", fontSize: 11, padding: 20, textAlign: "center" }}>
                  No tracked influences for this memory
                </div>
              ) : (
                <DataTable
                  columns={[
                    { key: "influence_id", header: "ID", width: "70px" },
                    { key: "influence_type", header: "Type", width: "110px" },
                    {
                      key: "strength",
                      header: "Strength",
                      width: "70px",
                      render: (row: MemoryInfluence) => (
                        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                          <div style={{ width: 30, height: 4, background: "#2a2a4a" }}>
                            <div style={{ width: `${row.strength * 30}px`, height: 4, background: row.strength > 0.8 ? "#33ff33" : row.strength > 0.5 ? "#ffaa00" : "#ff3333" }} />
                          </div>
                          <span style={{ color: "#8888aa", fontSize: 9 }}>{(row.strength * 100).toFixed(0)}%</span>
                        </div>
                      ),
                    },
                    {
                      key: "trace_visible",
                      header: "Visible",
                      width: "60px",
                      render: (row: MemoryInfluence) => <Badge label={row.trace_visible ? "YES" : "NO"} variant={row.trace_visible ? "pass" : "default"} size="sm" />,
                    },
                    { key: "target_inference_id", header: "Target Inference", width: "120px" },
                  ]}
                  data={influences}
                  keyExtractor={(row) => row.influence_id}
                />
              )}
            </Panel>
          </>
        ) : (
          <Panel title="Memory Detail" style={{ flex: 1 }}>
            <div style={{ color: "#666", fontFamily: "var(--font-mono)", fontSize: 11, padding: 40, textAlign: "center" }}>
              Select a memory to view details and influence graph
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
};

export default MemoryExplorer;
