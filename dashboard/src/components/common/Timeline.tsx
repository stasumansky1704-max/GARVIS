// =============================================================================
// Timeline — Vertical timeline component for state transitions and events
// =============================================================================

import React from "react";

export interface TimelineEntry {
  id: string;
  timestamp: string;
  label: string;
  detail?: string;
  status: "pass" | "fail" | "warn" | "info" | "governance" | "memory";
}

interface TimelineProps {
  entries: TimelineEntry[];
  maxHeight?: number;
}

const statusColors: Record<string, string> = {
  pass: "#33ff33",
  fail: "#ff3333",
  warn: "#ffaa00",
  info: "#3388ff",
  governance: "#ff33ff",
  memory: "#00ffff",
};

const Timeline: React.FC<TimelineProps> = ({ entries, maxHeight }) => {
  return (
    <div className="timeline" style={maxHeight ? { maxHeight, overflowY: "auto" } : undefined}>
      {entries.map((entry) => (
        <div key={entry.id} className={`timeline-entry ${entry.status}`}>
          <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
            <span
              className="mono"
              style={{ color: "#666", fontSize: 10, minWidth: 72 }}
            >
              {entry.timestamp}
            </span>
            <span style={{ color: statusColors[entry.status] || "#e0e0e0", fontWeight: 600, fontSize: 11 }}>
              {entry.label}
            </span>
          </div>
          {entry.detail && (
            <div style={{ color: "#8888aa", fontSize: 10, marginTop: 2, paddingLeft: 80, wordBreak: "break-word" }}>
              {entry.detail}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default React.memo(Timeline);
