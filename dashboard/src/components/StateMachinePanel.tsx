// =============================================================================
// StateMachinePanel — Phase 3: Active state machine visualization
// =============================================================================

import React from "react";
import Panel from "./common/Panel";
import Badge from "./common/Badge";
import Timeline from "./common/Timeline";
import type { TimelineEntry } from "./common/Timeline";
import { useApi } from "@/hooks/useApi";
import { api, MOCK_FORBIDDEN_PATTERNS } from "@/api";

const STATES = ["standby", "active", "processing", "governed", "blocked", "recovery", "output"];

const stateColors: Record<string, string> = {
  standby: "#666",
  active: "#33ff33",
  processing: "#3388ff",
  governed: "#ff33ff",
  blocked: "#ff3333",
  recovery: "#ffaa00",
  output: "#33ff33",
};

const StateMachinePanel: React.FC = () => {
  const { data: opState } = useApi(api.cognition.getState);
  const { data: transitions } = useApi(api.cognition.getTransitions);

  const timelineEntries: TimelineEntry[] = (transitions || []).slice(-10).reverse().map((t, i) => ({
    id: `st-${i}`,
    timestamp: t.timestamp.slice(11, 19),
    label: `${t.from_state} → ${t.to_state}`,
    detail: `trigger: ${t.trigger}`,
    status: t.governance_check_passed ? "pass" : "fail",
  }));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gridTemplateRows: "auto 1fr", gap: "var(--gap)", height: "100%" }}>
      {/* Current State */}
      <Panel title="Current State">
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, padding: "16px 0" }}>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 28,
              fontWeight: 700,
              color: stateColors[opState?.state ?? "standby"] || "#e0e0e0",
              textTransform: "uppercase",
              letterSpacing: 3,
              textShadow: `0 0 20px ${stateColors[opState?.state ?? "standby"]}40`,
            }}
          >
            {opState?.state ?? "UNKNOWN"}
          </div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "#8888aa" }}>
            Since: {opState?.since?.replace("T", " ").slice(0, 19) ?? "—"}
          </div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "#666" }}>
            Transitions today: <span style={{ color: "#3388ff" }}>{opState?.transitions_today ?? 0}</span>
          </div>
        </div>
      </Panel>

      {/* State Diagram */}
      <Panel title="State Machine">
        <svg viewBox="0 0 300 180" style={{ width: "100%", height: 160 }}>
          {/* Simple state machine visualization */}
          {/* standby */}
          <rect x="10" y="70" width="60" height="30" fill="#1a1a2e" stroke={stateColors.standby} strokeWidth={opState?.state === "standby" ? 2 : 1} rx="0" />
          <text x="40" y="89" fill={stateColors.standby} fontSize={8} fontFamily="var(--font-mono)" textAnchor="middle">STANDBY</text>

          {/* active */}
          <rect x="100" y="20" width="60" height="30" fill="#1a1a2e" stroke={stateColors.active} strokeWidth={opState?.state === "active" ? 2 : 1} rx="0" />
          <text x="130" y="39" fill={stateColors.active} fontSize={8} fontFamily="var(--font-mono)" textAnchor="middle">ACTIVE</text>

          {/* processing */}
          <rect x="100" y="70" width="60" height="30" fill="#1a1a2e" stroke={stateColors.processing} strokeWidth={opState?.state === "processing" ? 2 : 1} rx="0" />
          <text x="130" y="89" fill={stateColors.processing} fontSize={8} fontFamily="var(--font-mono)" textAnchor="middle">PROCESS</text>

          {/* governed */}
          <rect x="100" y="120" width="60" height="30" fill="#1a1a2e" stroke={stateColors.governed} strokeWidth={opState?.state === "governed" ? 2 : 1} rx="0" />
          <text x="130" y="139" fill={stateColors.governed} fontSize={8} fontFamily="var(--font-mono)" textAnchor="middle">GOVERNED</text>

          {/* blocked */}
          <rect x="200" y="70" width="60" height="30" fill="#1a1a2e" stroke={stateColors.blocked} strokeWidth={opState?.state === "blocked" ? 2 : 1} rx="0" />
          <text x="230" y="89" fill={stateColors.blocked} fontSize={8} fontFamily="var(--font-mono)" textAnchor="middle">BLOCKED</text>

          {/* recovery */}
          <rect x="200" y="120" width="60" height="30" fill="#1a1a2e" stroke={stateColors.recovery} strokeWidth={opState?.state === "recovery" ? 2 : 1} rx="0" />
          <text x="230" y="139" fill={stateColors.recovery} fontSize={8} fontFamily="var(--font-mono)" textAnchor="middle">RECOVERY</text>

          {/* output */}
          <rect x="10" y="120" width="60" height="30" fill="#1a1a2e" stroke={stateColors.output} strokeWidth={opState?.state === "output" ? 2 : 1} rx="0" />
          <text x="40" y="139" fill={stateColors.output} fontSize={8} fontFamily="var(--font-mono)" textAnchor="middle">OUTPUT</text>

          {/* Arrows */}
          <line x1="70" y1="85" x2="100" y2="85" stroke="#2a2a4a" strokeWidth={1} markerEnd="url(#arrow-sm)" />
          <line x1="130" y1="50" x2="130" y2="70" stroke="#2a2a4a" strokeWidth={1} markerEnd="url(#arrow-sm)" />
          <line x1="130" y1="100" x2="130" y2="120" stroke="#2a2a4a" strokeWidth={1} markerEnd="url(#arrow-sm)" />
          <line x1="160" y1="85" x2="200" y2="85" stroke="#2a2a4a" strokeWidth={1} markerEnd="url(#arrow-sm)" />
          <line x1="230" y1="100" x2="230" y2="120" stroke="#2a2a4a" strokeWidth={1} markerEnd="url(#arrow-sm)" />
          <line x1="100" y1="135" x2="70" y2="135" stroke="#2a2a4a" strokeWidth={1} markerEnd="url(#arrow-sm)" />
          <line x1="200" y1="135" x2="160" y2="135" stroke="#2a2a4a" strokeWidth={1} markerEnd="url(#arrow-sm)" />

          <defs>
            <marker id="arrow-sm" markerWidth="6" markerHeight="4" refX="6" refY="2" orient="auto">
              <polygon points="0 0, 6 2, 0 4" fill="#2a2a4a" />
            </marker>
          </defs>
        </svg>
      </Panel>

      {/* Transition History */}
      <Panel title="Transition History" style={{ maxHeight: 320 }}>
        <Timeline entries={timelineEntries} maxHeight={260} />
      </Panel>

      {/* Forbidden Patterns */}
      <Panel title="Forbidden Patterns">
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {MOCK_FORBIDDEN_PATTERNS.map((fp) => (
            <div
              key={fp.pattern_id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "6px 8px",
                background: fp.violation_count > 0 ? "rgba(255,51,51,0.05)" : "rgba(51,255,51,0.03)",
                border: `1px solid ${fp.violation_count > 0 ? "#2a1a1a" : "#1a2a1a"}`,
              }}
            >
              <div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "#e0e0e0" }}>
                  {fp.pattern_id}: {fp.description}
                </div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "#666", marginTop: 2 }}>
                  category: {fp.category}
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                {fp.violation_count > 0 ? (
                  <Badge label={`${fp.violation_count} hits`} variant="warn" size="sm" />
                ) : (
                  <Badge label="CLEAR" variant="pass" size="sm" />
                )}
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
};

export default StateMachinePanel;
