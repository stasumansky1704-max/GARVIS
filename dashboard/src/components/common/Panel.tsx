// =============================================================================
// Panel — Reusable panel container with title and optional actions
// =============================================================================

import React from "react";

interface PanelProps {
  title: string;
  children: React.ReactNode;
  className?: string;
  actions?: React.ReactNode;
  style?: React.CSSProperties;
}

const Panel: React.FC<PanelProps> = ({ title, children, className = "", actions, style }) => {
  return (
    <div className={`panel ${className}`} style={style}>
      <div className="panel-header">
        <span className="panel-title">{title}</span>
        {actions && <div style={{ display: "flex", gap: 6, alignItems: "center" }}>{actions}</div>}
      </div>
      <div className="panel-body">{children}</div>
    </div>
  );
};

export default React.memo(Panel);
