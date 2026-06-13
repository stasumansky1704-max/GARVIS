// =============================================================================
// StatusBar — Bottom status bar with component health and connection status
// =============================================================================

import React from "react";
import Badge from "./common/Badge";
import { useApi } from "@/hooks/useApi";
import { api } from "@/api";
import type { ComponentStatus } from "@/types";

interface StatusBarProps {
  wsConnected: boolean;
}

const statusVariant = (s: string) => s as "pass" | "warn" | "fail" | "default";

const StatusBar: React.FC<StatusBarProps> = ({ wsConnected }) => {
  const { data: runtime } = useApi(api.status.getStatus);

  const formatUptime = (seconds: number) => {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (d > 0) return `${d}d ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  };

  return (
    <footer
      style={{
        height: "var(--status-height)",
        background: "#111118",
        borderTop: "1px solid #2a2a4a",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 12px",
        flexShrink: 0,
        fontFamily: "var(--font-mono)",
        fontSize: 9,
        gap: 12,
      }}
    >
      {/* Left: State & Uptime */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ color: "#666", textTransform: "uppercase" }}>State</span>
          <Badge
            label={(runtime?.state ?? "unknown").toUpperCase()}
            variant={runtime?.state === "operational" ? "pass" : "warn"}
            size="sm"
            dot
            dotColor={runtime?.state === "operational" ? "#33ff33" : "#ffaa00"}
          />
        </div>
        <div style={{ color: "#666" }}>
          Uptime: <span style={{ color: "#8888aa" }}>{runtime ? formatUptime(runtime.uptime_seconds) : "—"}</span>
        </div>
      </div>

      {/* Center: Component Health */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, overflow: "hidden" }}>
        <span style={{ color: "#666", textTransform: "uppercase", flexShrink: 0 }}>Components:</span>
        <div style={{ display: "flex", gap: 6, overflow: "hidden" }}>
          {(runtime?.components || []).map((comp) => (
            <div key={comp.name} style={{ display: "flex", alignItems: "center", gap: 3, flexShrink: 0 }}>
              <span
                style={{
                  width: 5,
                  height: 5,
                  background:
                    comp.status === "healthy" ? "#33ff33"
                      : comp.status === "degraded" ? "#ffaa00"
                      : comp.status === "critical" ? "#ff3333"
                      : "#666",
                  display: "inline-block",
                }}
              />
              <span style={{
                color:
                  comp.status === "healthy" ? "#8888aa"
                    : comp.status === "degraded" ? "#ffaa00"
                    : comp.status === "critical" ? "#ff3333"
                    : "#666",
                textTransform: "uppercase",
              }}>
                {comp.name}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Right: Connections & Version */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ color: "#666" }}>API</span>
          <span style={{
            width: 5, height: 5,
            background: "#33ff33",
            display: "inline-block",
          }} />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ color: "#666" }}>WS</span>
          <span style={{
            width: 5, height: 5,
            background: wsConnected ? "#33ff33" : "#ff3333",
            display: "inline-block",
          }} />
        </div>
        <span style={{ color: "#444466" }}>{runtime?.version ?? "—"}</span>
      </div>
    </footer>
  );
};

export default React.memo(StatusBar);
