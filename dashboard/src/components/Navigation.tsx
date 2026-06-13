// =============================================================================
// Navigation — Left sidebar navigation for view switching
// =============================================================================

import React from "react";
import type { ConsoleView } from "@/types";

interface NavigationProps {
  activeView: ConsoleView;
  onViewChange: (view: ConsoleView) => void;
}

const NAV_ITEMS: { view: ConsoleView; label: string; icon: string }[] = [
  { view: "overview", label: "Overview", icon: "◈" },
  { view: "governance", label: "Governance", icon: "⚖" },
  { view: "cognition", label: "Cognition", icon: "◉" },
  { view: "memory", label: "Memory", icon: "◫" },
  { view: "traceability", label: "Traceability", icon: "◬" },
  { view: "audit", label: "Audit", icon: "▣" },
  { view: "analytics", label: "Analytics", icon: "◧" },
  { view: "ecosystem", label: "Ecosystem", icon: "◐" },
  { view: "alerts", label: "Alerts", icon: "◭" },
  { view: "topology", label: "Topology", icon: "▥" },
];

const Navigation: React.FC<NavigationProps> = ({ activeView, onViewChange }) => {
  return (
    <nav
      style={{
        width: "var(--nav-width)",
        background: "#111118",
        borderRight: "1px solid #2a2a4a",
        display: "flex",
        flexDirection: "column",
        paddingTop: 8,
        flexShrink: 0,
        overflowY: "auto",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 9,
          color: "#444466",
          textTransform: "uppercase",
          letterSpacing: 2,
          padding: "8px 12px 12px",
        }}
      >
        Navigation
      </div>

      {NAV_ITEMS.map((item) => (
        <div
          key={item.view}
          className={`nav-item ${activeView === item.view ? "active" : ""}`}
          onClick={() => onViewChange(item.view)}
        >
          <span style={{ fontSize: 12, width: 16, textAlign: "center" }}>{item.icon}</span>
          <span>{item.label}</span>
        </div>
      ))}

      {/* Separator */}
      <div style={{ flex: 1 }} />

      <div
        style={{
          borderTop: "1px solid #2a2a4a",
          padding: "12px 12px 16px",
          fontFamily: "var(--font-mono)",
          fontSize: 9,
          color: "#444466",
        }}
      >
        <div style={{ textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>
          Phases 3-6
        </div>
        <div style={{ fontSize: 8 }}>
          Governance · Cognition · Memory · Traceability · Audit · Analytics · Continuity · Ecosystem
        </div>
      </div>
    </nav>
  );
};

export default React.memo(Navigation);
