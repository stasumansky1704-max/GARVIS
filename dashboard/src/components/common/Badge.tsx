// =============================================================================
// Badge — Colored badge for status indicators
// =============================================================================

import React from "react";
import type { SeverityLevel, SchemaCategory, TraceStatus } from "@/types";

interface BadgeProps {
  label: string;
  variant?: SeverityLevel | SchemaCategory | TraceStatus | "default" | "pass" | "fail" | "warn" | "info" | "governance" | "memory" | "active" | "inactive";
  size?: "sm" | "md";
  style?: React.CSSProperties;
  dot?: boolean;
  dotColor?: string;
}

const variantStyles: Record<string, { border: string; color: string; bg: string }> = {
  default:  { border: "#2a2a4a", color: "#8888aa", bg: "rgba(42,42,74,0.3)" },
  pass:     { border: "#33ff33", color: "#33ff33", bg: "rgba(51,255,51,0.1)" },
  fail:     { border: "#ff3333", color: "#ff3333", bg: "rgba(255,51,51,0.1)" },
  warn:     { border: "#ffaa00", color: "#ffaa00", bg: "rgba(255,170,0,0.1)" },
  info:     { border: "#3388ff", color: "#3388ff", bg: "rgba(51,136,255,0.1)" },
  governance:{ border: "#ff33ff", color: "#ff33ff", bg: "rgba(255,51,255,0.1)" },
  memory:   { border: "#00ffff", color: "#00ffff", bg: "rgba(0,255,255,0.1)" },
  active:   { border: "#33ff33", color: "#33ff33", bg: "rgba(51,255,51,0.1)" },
  inactive: { border: "#444466", color: "#666666", bg: "rgba(68,68,102,0.2)" },
  critical: { border: "#ff3333", color: "#ff3333", bg: "rgba(255,51,51,0.15)" },
  warning:  { border: "#ffaa00", color: "#ffaa00", bg: "rgba(255,170,0,0.1)" },
  low:      { border: "#8888aa", color: "#8888aa", bg: "rgba(136,136,170,0.1)" },
  epistemic:{ border: "#3388ff", color: "#3388ff", bg: "rgba(51,136,255,0.1)" },
  operational:{ border: "#33ff33", color: "#33ff33", bg: "rgba(51,255,51,0.1)" },
  boundary: { border: "#ff3333", color: "#ff3333", bg: "rgba(255,51,51,0.1)" },
  reflective:{ border: "#ffaa00", color: "#ffaa00", bg: "rgba(255,170,0,0.1)" },
  session:  { border: "#00ffff", color: "#00ffff", bg: "rgba(0,255,255,0.1)" },
  completed:{ border: "#33ff33", color: "#33ff33", bg: "rgba(51,255,51,0.1)" },
  violated: { border: "#ff3333", color: "#ff3333", bg: "rgba(255,51,51,0.15)" },
  healthy:  { border: "#33ff33", color: "#33ff33", bg: "rgba(51,255,51,0.1)" },
  degraded: { border: "#ffaa00", color: "#ffaa00", bg: "rgba(255,170,0,0.1)" },
};

const Badge: React.FC<BadgeProps> = ({ label, variant = "default", size = "md", style, dot, dotColor }) => {
  const vs = variantStyles[variant] || variantStyles.default;
  const isSm = size === "sm";

  return (
    <span
      className={`badge ${isSm ? "badge-sm" : ""}`}
      style={{
        borderColor: vs.border,
        color: vs.color,
        background: vs.bg,
        fontSize: isSm ? 9 : 10,
        padding: isSm ? "1px 4px" : "2px 6px",
        ...style,
      }}
    >
      {dot && (
        <span
          style={{
            display: "inline-block",
            width: 6,
            height: 6,
            background: dotColor || vs.color,
            flexShrink: 0,
          }}
        />
      )}
      {label}
    </span>
  );
};

export default React.memo(Badge);
