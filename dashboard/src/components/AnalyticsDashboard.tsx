// =============================================================================
// AnalyticsDashboard — Phase 4: Cognition analytics with SVG sparklines
// =============================================================================

import React, { useMemo } from "react";
import Panel from "./common/Panel";
import Badge from "./common/Badge";
import { useApi } from "@/hooks/useApi";
import { api } from "@/api";
import type { TrendPoint } from "@/types";

// =============================================================================
// SVG Sparkline Component
// =============================================================================

const Sparkline: React.FC<{ data: TrendPoint[]; color: string; height?: number; width?: number }> = ({
  data,
  color,
  height = 32,
  width = 120,
}) => {
  if (!data.length) return <div style={{ height, width }} />;

  const values = data.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  }).join(" ");

  const areaPoints = `${points} ${width},${height} 0,${height}`;

  return (
    <svg width={width} height={height} style={{ overflow: "visible" }}>
      <polygon points={areaPoints} fill={`${color}15`} stroke="none" />
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} />
      {/* End dot */}
      <circle
        cx={width}
        cy={height - ((values[values.length - 1] - min) / range) * (height - 4) - 2}
        r={2.5}
        fill={color}
      />
    </svg>
  );
};

// =============================================================================
// SVG Line Chart for Trends
// =============================================================================

const LineChart: React.FC<{ data: TrendPoint[]; color: string; height?: number }> = ({
  data,
  color,
  height = 120,
}) => {
  if (!data.length) return <div style={{ height }} />;

  const values = data.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const width = 100;

  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = 100 - ((v - min) / range) * 90 - 5;
    return `${x},${y}`;
  }).join(" ");

  const gridLines = [0, 25, 50, 75, 100];

  return (
    <svg viewBox={`0 0 ${width} 100`} style={{ width: "100%", height }} preserveAspectRatio="none">
      {/* Grid */}
      {gridLines.map((g) => (
        <line key={g} x1={0} y1={g} x2={width} y2={g} stroke="#2a2a4a" strokeWidth={0.5} />
      ))}
      {/* Area */}
      <polygon points={`${points} ${width},100 0,100`} fill={`${color}08`} stroke="none" />
      {/* Line */}
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} />
      {/* Current value dot */}
      <circle
        cx={width}
        cy={100 - ((values[values.length - 1] - min) / range) * 90 - 5}
        r={2}
        fill={color}
      />
    </svg>
  );
};

// =============================================================================
// Metric Card
// =============================================================================

const MetricCard: React.FC<{
  label: string;
  value: string | number;
  sub?: string;
  color: string;
  sparkline?: TrendPoint[];
}> = ({ label, value, sub, color, sparkline }) => (
  <div className="metric-card">
    <div className="metric-label">{label}</div>
    <div className="metric-value" style={{ color }}>{value}</div>
    {sparkline && <Sparkline data={sparkline} color={color} />}
    {sub && <div className="metric-sub">{sub}</div>}
  </div>
);

// =============================================================================
// Main Component
// =============================================================================

const AnalyticsDashboard: React.FC = () => {
  const { data: overview, loading } = useApi(api.analytics.getOverview);

  if (loading || !overview) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#666", fontFamily: "var(--font-mono)" }}>
        Loading analytics...
      </div>
    );
  }

  const g = overview.governance;
  const c = overview.cognition;
  const m = overview.memory;
  const t = overview.traceability;
  const cont = overview.continuity;
  const p = overview.pressure;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)", height: "100%", overflowY: "auto" }}>
      {/* Governance Section */}
      <Panel title="Governance Metrics">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "var(--gap)" }}>
          <MetricCard label="Active Schemas" value={g.active_schemas} color="#33ff33" sparkline={overview.trends.governance_trend} />
          <MetricCard label="Constraints" value={g.total_constraints} color="#ff33ff" />
          <MetricCard label="Hard Stop Rate" value={`${(g.hard_stop_rate * 100).toFixed(1)}%`} color={g.hard_stop_rate > 0.05 ? "#ff3333" : "#33ff33"} />
          <MetricCard label="Coverage Score" value={`${(g.coverage_score * 100).toFixed(0)}%`} color={g.coverage_score > 0.9 ? "#33ff33" : "#ffaa00"} />
          <MetricCard label="Pressure" value={`${(g.pressure * 100).toFixed(0)}%`} color={g.pressure > 0.5 ? "#ff3333" : g.pressure > 0.3 ? "#ffaa00" : "#33ff33"} />
        </div>
      </Panel>

      {/* Cognition & Memory Row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--gap)" }}>
        <Panel title="Cognition Metrics">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--gap)" }}>
            <MetricCard label="Success Rate" value={`${(c.success_rate * 100).toFixed(0)}%`} color={c.success_rate > 0.95 ? "#33ff33" : "#ffaa00"} sparkline={overview.trends.quality_trend} />
            <MetricCard label="Avg Response" value={`${c.avg_response_time_ms}ms`} color={c.avg_response_time_ms < 5000 ? "#33ff33" : "#ffaa00"} />
            <MetricCard label="Quality Score" value={`${(c.quality_score * 100).toFixed(0)}%`} color={c.quality_score > 0.85 ? "#33ff33" : "#ffaa00"} />
          </div>
          <div style={{ marginTop: 8 }}>
            <LineChart data={overview.trends.state_stability_trend} color="#3388ff" height={80} />
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "#666", textAlign: "center", marginTop: 4 }}>
              State Stability Trend (24h)
            </div>
          </div>
        </Panel>

        <Panel title="Memory Metrics">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--gap)" }}>
            <MetricCard label="Total Memories" value={m.total_memories.toLocaleString()} color="#00ffff" />
            <MetricCard label="Avg Retrievals" value={m.avg_retrievals.toFixed(1)} color="#3388ff" />
            <MetricCard label="Trace Visible" value={`${(m.trace_visible_rate * 100).toFixed(0)}%`} color={m.trace_visible_rate > 0.8 ? "#33ff33" : "#ffaa00"} />
          </div>
          <div style={{ marginTop: 8 }}>
            <LineChart data={overview.trends.quality_trend} color="#00ffff" height={80} />
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "#666", textAlign: "center", marginTop: 4 }}>
              Memory Quality Trend (24h)
            </div>
          </div>
        </Panel>
      </div>

      {/* Continuity & Pressure Row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--gap)" }}>
        <Panel title="Continuity Metrics">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--gap)" }}>
            <div className="metric-card">
              <div className="metric-label">Continuity Score</div>
              <div className="metric-value" style={{ color: cont.continuity_score > 0.85 ? "#33ff33" : "#ffaa00" }}>{(cont.continuity_score * 100).toFixed(0)}%</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Alignment Drift</div>
              <div className="metric-value" style={{ color: cont.alignment_drift > 0.15 ? "#ff3333" : "#ffaa00" }}>{(cont.alignment_drift * 100).toFixed(1)}%</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Resilience</div>
              <div className="metric-value" style={{ color: cont.resilience_score > 0.85 ? "#33ff33" : "#ffaa00" }}>{(cont.resilience_score * 100).toFixed(0)}%</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Equilibrium</div>
              <div className="metric-value" style={{ color: cont.equilibrium_stability > 0.8 ? "#33ff33" : "#ffaa00" }}>{(cont.equilibrium_stability * 100).toFixed(0)}%</div>
            </div>
          </div>
        </Panel>

        <Panel title="Pressure Metrics">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--gap)" }}>
            <div className="metric-card">
              <div className="metric-label">Adaptation</div>
              <div className="metric-value" style={{ color: p.adaptation_pressure > 0.4 ? "#ffaa00" : "#33ff33" }}>{(p.adaptation_pressure * 100).toFixed(0)}%</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Enforcement</div>
              <div className="metric-value" style={{ color: p.enforcement_pressure > 0.4 ? "#ffaa00" : "#33ff33" }}>{(p.enforcement_pressure * 100).toFixed(0)}%</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Conflict</div>
              <div className="metric-value" style={{ color: p.conflict_pressure > 0.3 ? "#ff3333" : "#33ff33" }}>{(p.conflict_pressure * 100).toFixed(0)}%</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Overall</div>
              <div className="metric-value" style={{ color: p.overall_pressure > 0.4 ? "#ffaa00" : "#33ff33" }}>{(p.overall_pressure * 100).toFixed(0)}%</div>
            </div>
          </div>
        </Panel>
      </div>

      {/* Degradation Trend */}
      <Panel title="Degradation Trend" style={{ maxHeight: 160 }}>
        <LineChart data={overview.trends.degradation_trend} color="#ff3333" height={100} />
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "#666", textAlign: "center", marginTop: 4 }}>
          System Degradation Trend — lower is better (24h)
        </div>
      </Panel>
    </div>
  );
};

export default AnalyticsDashboard;
