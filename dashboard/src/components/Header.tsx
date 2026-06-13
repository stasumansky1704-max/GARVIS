// =============================================================================
// Header — Top bar with title, current state indicator, alert count
// =============================================================================

import React, { useState, useEffect } from "react";
import Badge from "./common/Badge";

interface HeaderProps {
  currentState: string;
  alertCount: number;
  connectionStatus: "connected" | "disconnected" | "degraded";
}

const stateVariantMap: Record<string, string> = {
  standby: "info",
  active: "pass",
  processing: "info",
  governed: "governance",
  blocked: "fail",
  recovery: "warn",
  output: "pass",
  error: "fail",
  operational: "pass",
};

const Header: React.FC<HeaderProps> = ({ currentState, alertCount, connectionStatus }) => {
  const [timestamp, setTimestamp] = useState(new Date().toISOString());

  useEffect(() => {
    const timer = setInterval(() => setTimestamp(new Date().toISOString()), 1000);
    return () => clearInterval(timer);
  }, []);

  const stateVariant = (stateVariantMap[currentState] || "info") as
    | "pass"
    | "fail"
    | "warn"
    | "info"
    | "governance"
    | "memory"
    | "default";

  return (
    <header
      style={{
        height: "var(--header-height)",
        background: "#111118",
        borderBottom: "1px solid #2a2a4a",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 16px",
        flexShrink: 0,
        gap: 16,
      }}
    >
      {/* Title */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 13,
            fontWeight: 700,
            letterSpacing: 2,
            color: "#e0e0e0",
            textTransform: "uppercase",
          }}
        >
          GARVIS
        </span>
        <span style={{ color: "#444466", fontSize: 11 }}>|</span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "#8888aa", textTransform: "uppercase", letterSpacing: 1.5 }}>
          Operator Governance Console
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 9,
            color: "#ff33ff",
            marginLeft: 4,
            textTransform: "uppercase",
            letterSpacing: 1,
          }}
        >
          v2.0.0
        </span>
      </div>

      {/* Center indicators */}
      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        {/* Current state */}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "#666", textTransform: "uppercase", letterSpacing: 1 }}>
            State
          </span>
          <Badge label={currentState.toUpperCase()} variant={stateVariant} dot dotColor={stateVariant === "pass" ? "#33ff33" : stateVariant === "fail" ? "#ff3333" : "#3388ff"} />
        </div>

        {/* Alert count */}
        {alertCount > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "#666", textTransform: "uppercase", letterSpacing: 1 }}>
              Alerts
            </span>
            <Badge label={String(alertCount)} variant={alertCount > 5 ? "critical" : "warn"} />
          </div>
        )}
      </div>

      {/* Right side */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {/* Connection status */}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "#666", textTransform: "uppercase" }}>
            WS
          </span>
          <span
            style={{
              width: 7,
              height: 7,
              background:
                connectionStatus === "connected"
                  ? "#33ff33"
                  : connectionStatus === "degraded"
                  ? "#ffaa00"
                  : "#ff3333",
              display: "inline-block",
            }}
          />
        </div>

        {/* Timestamp */}
        <span className="mono" style={{ color: "#8888aa", fontSize: 10, minWidth: 170, textAlign: "right" }}>
          {timestamp.replace("T", " ").slice(0, 19)} UTC
        </span>
      </div>
    </header>
  );
};

export default React.memo(Header);
