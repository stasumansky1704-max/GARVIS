// =============================================================================
// ContinuityTimeline — Phase 4: Long-term continuity view
// =============================================================================

import React from "react";
import Panel from "./common/Panel";
import Badge from "./common/Badge";
import { useApi } from "@/hooks/useApi";
import { api, MOCK_TRACES, MOCK_EVENTS } from "@/api";
import type { CognitionTrace, AuditEvent, TrendPoint } from "@/types";

// =============================================================================
// Timeline Event Item
// =============================================================================

const TimelineItem: React.FC<{
  time: string;
  label: string;
  detail?: string;
  color: string;
  side: "left" | "right";
}> = ({ time, label, detail, color, side }) => (
  <div style={{
    display: "flex",
    justifyContent: side === "left" ? "flex-end" : "flex-start",
    padding: "4px 0",
    position: "relative",
  }}>
    <div style={{
      maxWidth: "45%",
      textAlign: side,
      padding: "4px 8px",
      background: `${color}08`,
      borderLeft: side === "left" ? `2px solid ${color}` : undefined,
      borderRight: side === "right" ? `2px solid ${color}` : undefined,
    }}>
      <div className="mono" style={{ fontSize: 9, color: "#666" }}>{time}</div>
      <div style={{ fontSize: 10, color, fontWeight: 600 }}>{label}</div>
      {detail && <div style={{ fontSize: 9, color: "#8888aa" }}>{detail}</div>}
    </div>
  </div>
);

// =============================================================================
// SVG Continuity Line Chart
// =============================================================================

const ContinuityChart: React.FC<{ data: TrendPoint[]; height?: number }> = ({ data, height = 100 }) => {
  if (!data.length) return null;
  const values = data.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * 100;
    const y = 100 - ((v - min) / range) * 85 - 7;
    return `${x},${y}`;
  }).join(" ");

  // Drift threshold
  const thresholdY = 100 - ((0.15 - min) / range) * 85 - 7;

  return (
    <svg viewBox="0 0 100 100" style={{ width: "100%", height }} preserveAspectRatio="none">
      {/* Grid */}
      {[0, 25, 50, 75, 100].map((g) => (
        <line key={g} x1={0} y1={g} x2={100} y2={g} stroke="#2a2a4a" strokeWidth={0.5} />
      ))}
      {/* Threshold */}
      {thresholdY > 0 && thresholdY < 100 && (
        <line x1={0} y1={thresholdY} x2={100} y2={thresholdY} stroke="#ff3333" strokeWidth={0.5} strokeDasharray="2,2" />
      )}
      {/* Area */}
      <polygon points={`${points} 100,100 0,100`} fill="rgba(51,136,255,0.05)" />
      {/* Line */}
      <polyline points={points} fill="none" stroke="#3388ff" strokeWidth={1.2} />
      {/* End dot */}
      <circle cx={100} cy={100 - ((values[values.length - 1] - min) / range) * 85 - 7} r={2} fill="#3388ff" />
    </svg>
  );
};

// =============================================================================
// Main Component
// =============================================================================

const ContinuityTimeline: React.FC = () => {
  const { data: continuity } = useApi(api.analytics.getContinuityStability);
  const { data: overview } = useApi(api.analytics.getOverview);

  // Build timeline from mock traces and events
  const timelineEvents = React.useMemo(() => {
    const items: { time: string; label: string; detail: string; color: string; sortKey: number }[] = [];
    MOCK_TRACES.forEach((t) => {
      items.push({
        time: t.start_time.slice(11, 19),
        label: `Trace ${t.trace_id}`,
        detail: `${t.status} — ${t.duration_ms}ms`,
        color: t.status === "completed" ? "#33ff33" : t.status === "violated" ? "#ff3333" : "#3388ff",
        sortKey: new Date(t.start_time).getTime(),
      });
      t.governance_checks.forEach((gc) => {
        if (!gc.passed) {
          items.push({
            time: (gc.timestamp ?? t.start_time).slice(11, 19),
            label: "Governance Check Failed",
            detail: `${gc.schema_id} / ${gc.policy_id}`,
            color: "#ff3333",
            sortKey: new Date(gc.timestamp ?? t.start_time).getTime(),
          });
        }
      });
    });
    MOCK_EVENTS.filter((e) => e.severity === "critical" || e.severity === "warning").forEach((e) => {
      items.push({
        time: e.timestamp.slice(11, 19),
        label: e.event_type,
        detail: e.message ?? "",
        color: e.severity === "critical" ? "#ff3333" : "#ffaa00",
        sortKey: new Date(e.timestamp).getTime(),
      });
    });
    return items.sort((a, b) => a.sortKey - b.sortKey);
  }, []);

  const cont = continuity;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)", height: "100%", overflowY: "auto" }}>
      {/* Score Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--gap)" }}>
        <div className="metric-card">
          <div className="metric-label">Continuity Score</div>
          <div className="metric-value" style={{ color: cont && cont.continuity_score > 0.85 ? "#33ff33" : "#ffaa00" }}>
            {cont ? `${(cont.continuity_score * 100).toFixed(0)}%` : "—"}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Alignment Drift</div>
          <div className="metric-value" style={{ color: cont && cont.alignment_drift > 0.15 ? "#ff3333" : "#33ff33" }}>
            {cont ? `${(cont.alignment_drift * 100).toFixed(1)}%` : "—"}
          </div>
          <div className="metric-sub">threshold: 15%</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Resilience Score</div>
          <div className="metric-value" style={{ color: "#3388ff" }}>
            {cont ? `${(cont.resilience_score * 100).toFixed(0)}%` : "—"}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Equilibrium</div>
          <div className="metric-value" style={{ color: cont && cont.equilibrium_stability > 0.8 ? "#33ff33" : "#ffaa00" }}>
            {cont ? `${(cont.equilibrium_stability * 100).toFixed(0)}%` : "—"}
          </div>
        </div>
      </div>

      {/* Drift Chart */}
      <Panel title="Alignment Drift History" style={{ maxHeight: 200 }}>
        {overview && <ContinuityChart data={overview.trends.governance_trend} height={120} />}
        <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "var(--font-mono)", fontSize: 9, color: "#666", marginTop: 4 }}>
          <span>-24h</span>
          <span style={{ color: "#ff3333" }}>--- drift threshold (15%)</span>
          <span>now</span>
        </div>
      </Panel>

      {/* Session Timeline */}
      <Panel title="Session & Governance Timeline" style={{ flex: 1 }}>
        <div style={{ position: "relative", padding: "0 20px" }}>
          {/* Center line */}
          <div style={{
            position: "absolute",
            left: "50%",
            top: 0,
            bottom: 0,
            width: 1,
            background: "#2a2a4a",
          }} />
          {timelineEvents.map((evt, i) => (
            <div key={i} style={{ position: "relative", marginBottom: 2 }}>
              {/* Dot on the line */}
              <div style={{
                position: "absolute",
                left: "50%",
                top: 8,
                width: 8,
                height: 8,
                background: evt.color,
                border: `2px solid var(--bg-panel)`,
                transform: "translateX(-50%)",
                zIndex: 1,
              }} />
              <TimelineItem
                time={evt.time}
                label={evt.label}
                detail={evt.detail}
                color={evt.color}
                side={i % 2 === 0 ? "left" : "right"}
              />
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
};

export default ContinuityTimeline;
