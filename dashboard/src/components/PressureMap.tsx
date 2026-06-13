// =============================================================================
// PressureMap — Phase 4: Governance pressure visualization
// =============================================================================

import React from "react";
import Panel from "./common/Panel";
import { useApi } from "@/hooks/useApi";
import { api } from "@/api";
import type { PressureMetrics } from "@/types";

// =============================================================================
// SVG Bar Chart Component
// =============================================================================

const BarChart: React.FC<{
  data: { label: string; values: [number, number, number]; colors: [string, string, string] }[];
}> = ({ data }) => {
  const maxVal = Math.max(...data.flatMap((d) => d.values), 1);
  const barW = 40;
  const groupW = 140;
  const height = 200;
  const chartW = data.length * groupW;

  return (
    <svg viewBox={`0 0 ${chartW} ${height}`} style={{ width: "100%", height }} preserveAspectRatio="xMidYMid meet">
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map((g) => (
        <line key={g} x1={0} y1={height - g * (height - 30) - 5} x2={chartW} y2={height - g * (height - 30) - 5} stroke="#2a2a4a" strokeWidth={0.5} />
      ))}
      {data.map((group, gi) => {
        const x = gi * groupW + 20;
        return (
          <g key={group.label}>
            {group.values.map((val, vi) => {
              const h = (val / maxVal) * (height - 35);
              return (
                <g key={vi}>
                  <rect
                    x={x + vi * (barW + 4)}
                    y={height - h - 5}
                    width={barW}
                    height={h}
                    fill={`${group.colors[vi]}30`}
                    stroke={group.colors[vi]}
                    strokeWidth={1}
                  />
                  <text
                    x={x + vi * (barW + 4) + barW / 2}
                    y={height - h - 10}
                    fill={group.colors[vi]}
                    fontSize={8}
                    fontFamily="var(--font-mono)"
                    textAnchor="middle"
                  >
                    {(val * 100).toFixed(0)}%
                  </text>
                </g>
              );
            })}
            {/* Label */}
            <text x={x + 60} y={height - 2} fill="#8888aa" fontSize={8} fontFamily="var(--font-mono)" textAnchor="middle">
              {group.label.length > 12 ? group.label.slice(0, 12) + "..." : group.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

// =============================================================================
// Gauge Component
// =============================================================================

const Gauge: React.FC<{ value: number; label: string; color: string; size?: number }> = ({ value, label, color, size = 80 }) => {
  const radius = size / 2 - 6;
  const circumference = 2 * Math.PI * radius;
  const arc = circumference * 0.75;
  const offset = arc - value * arc;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <svg width={size} height={size * 0.75 + 10}>
        {/* Background arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#2a2a4a"
          strokeWidth={6}
          strokeDasharray={`${arc} ${circumference}`}
          strokeDashoffset={-circumference * 0.125}
          transform={`rotate(135 ${size / 2} ${size / 2})`}
        />
        {/* Value arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={6}
          strokeDasharray={`${arc} ${circumference}`}
          strokeDashoffset={-circumference * 0.125 - offset}
          strokeLinecap="square"
          transform={`rotate(135 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dashoffset 0.5s ease" }}
        />
        {/* Value text */}
        <text x={size / 2} y={size / 2 + 4} fill={color} fontSize={14} fontFamily="var(--font-mono)" fontWeight={700} textAnchor="middle">
          {(value * 100).toFixed(0)}%
        </text>
      </svg>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "#8888aa", textTransform: "uppercase", letterSpacing: 1 }}>{label}</span>
    </div>
  );
};

// =============================================================================
// Main Component
// =============================================================================

const PressureMap: React.FC = () => {
  const { data: pressure, loading } = useApi(api.analytics.getGovernancePressure);

  if (loading || !pressure) {
    return <div style={{ color: "#666", fontFamily: "var(--font-mono)", padding: 40, textAlign: "center" }}>Loading pressure metrics...</div>;
  }

  const colors: [string, string, string] = ["#3388ff", "#ff3333", "#ffaa00"];

  const barData = (pressure.schema_pressures || []).map((sp) => ({
    label: sp.schema_name,
    values: [sp.adaptation, sp.enforcement, sp.conflict] as [number, number, number],
    colors,
  }));

  const o = pressure.overall;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)", height: "100%" }}>
      {/* Gauges */}
      <Panel title="Overall Pressure">
        <div style={{ display: "flex", justifyContent: "center", gap: 40, padding: "16px 0" }}>
          <Gauge value={o.adaptation} label="Adaptation" color="#3388ff" />
          <Gauge value={o.enforcement} label="Enforcement" color="#ff3333" />
          <Gauge value={o.conflict} label="Conflict" color="#ffaa00" />
          <Gauge value={o.total} label="Overall" color={o.total > 0.4 ? "#ff3333" : o.total > 0.25 ? "#ffaa00" : "#33ff33"} size={100} />
        </div>
      </Panel>

      {/* Schema Pressure Bars */}
      <Panel title="Schema Pressure Breakdown" style={{ flex: 1 }}>
        <BarChart data={barData} />
        <div style={{ display: "flex", gap: 20, justifyContent: "center", marginTop: 8, fontFamily: "var(--font-mono)", fontSize: 9 }}>
          <span style={{ color: "#3388ff" }}>■ Adaptation</span>
          <span style={{ color: "#ff3333" }}>■ Enforcement</span>
          <span style={{ color: "#ffaa00" }}>■ Conflict</span>
        </div>
      </Panel>

      {/* Pressure History */}
      <Panel title="Pressure History" style={{ maxHeight: 160 }}>
        <svg viewBox="0 0 100 50" style={{ width: "100%", height: 120 }} preserveAspectRatio="none">
          {pressure.history.map((p, i, arr) => {
            if (i === 0) return null;
            const x1 = ((i - 1) / (arr.length - 1)) * 100;
            const x2 = (i / (arr.length - 1)) * 100;
            const y1 = 50 - arr[i - 1].value * 45;
            const y2 = 50 - p.value * 45;
            const isHigh = p.value > 0.4;
            return (
              <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={isHigh ? "#ff3333" : "#3388ff"} strokeWidth={1} />
            );
          })}
        </svg>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "#666", textAlign: "center" }}>
          Overall Pressure Trend (24h)
        </div>
      </Panel>
    </div>
  );
};

export default PressureMap;
