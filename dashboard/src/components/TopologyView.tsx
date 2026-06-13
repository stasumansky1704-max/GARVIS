// =============================================================================
// TopologyView — System topology visualization with layered architecture
// =============================================================================

import React, { useState, useMemo, useCallback } from "react";
import { MOCK_TOPOLOGY } from "../api";
import type { TopologyNode, TopologyLayer, TopologyNodeStatus, TopologyEdge } from "../types";

// Layer configuration: order top-to-bottom with colors
const LAYER_CONFIG: { layer: TopologyLayer; label: string; color: string; y: number }[] = [
  { layer: "governance", label: "Governance", color: "#ff33ff", y: 0.08 },
  { layer: "cognition", label: "Cognition", color: "#00ffff", y: 0.22 },
  { layer: "inference", label: "Inference", color: "#3388ff", y: 0.36 },
  { layer: "memory", label: "Memory", color: "#ffaa00", y: 0.50 },
  { layer: "traceability", label: "Traceability", color: "#8888aa", y: 0.64 },
  { layer: "runtime", label: "Runtime", color: "#33ff33", y: 0.78 },
  { layer: "analytics", label: "Analytics", color: "#e0e0e0", y: 0.88 },
  { layer: "monitoring", label: "Monitoring", color: "#ff6666", y: 0.96 },
];

const STATUS_COLORS: Record<TopologyNodeStatus, string> = {
  healthy: "#33ff33",
  degraded: "#ffaa00",
  critical: "#ff3333",
  unknown: "#666666",
};

const EDGE_COLORS: Record<string, string> = {
  dependency: "#2a2a4a",
  influence: "#ff33ff",
  mediation: "#3388ff",
  initialization: "#33ff33",
  monitoring: "#ffaa00",
  analysis: "#8888aa",
};

// Compute node positions in a layered layout
function computeLayout(nodes: TopologyNode[], edges: TopologyEdge[], width: number, height: number): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();

  // Group nodes by layer
  const byLayer = new Map<TopologyLayer, TopologyNode[]>();
  nodes.forEach((n) => {
    const arr = byLayer.get(n.layer) || [];
    arr.push(n);
    byLayer.set(n.layer, arr);
  });

  // Position each layer's nodes horizontally centered
  LAYER_CONFIG.forEach(({ layer, y }) => {
    const layerNodes = byLayer.get(layer) || [];
    const count = layerNodes.length;
    layerNodes.forEach((n, i) => {
      const x = count === 1 ? 0.5 : 0.12 + (i / (count - 1)) * 0.76;
      positions.set(n.id, { x: x * width, y: y * height });
    });
  });

  return positions;
}

const TopologyView: React.FC = () => {
  const [selectedNode, setSelectedNode] = useState<TopologyNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [lastMouse, setLastMouse] = useState({ x: 0, y: 0 });

  const { nodes, edges } = MOCK_TOPOLOGY;

  const width = 900;
  const height = 600;

  const positions = useMemo(() => computeLayout(nodes, edges, width, height), [nodes, edges]);

  const nodePos = useCallback((id: string) => {
    const p = positions.get(id);
    if (!p) return { x: width / 2, y: height / 2 };
    return { x: p.x * zoom + pan.x, y: p.y * zoom + pan.y };
  }, [positions, zoom, pan]);

  // Find connected edges for a node
  const getConnectedEdges = useCallback((nodeId: string) => {
    return edges.filter((e) => e.from === nodeId || e.to === nodeId);
  }, [edges]);

  // Find neighbors of a node
  const getNeighbors = useCallback((nodeId: string) => {
    const neighborIds = new Set<string>();
    edges.forEach((e) => {
      if (e.from === nodeId) neighborIds.add(e.to);
      if (e.to === nodeId) neighborIds.add(e.from);
    });
    return Array.from(neighborIds);
  }, [edges]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    setIsDragging(true);
    setLastMouse({ x: e.clientX, y: e.clientY });
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging) return;
    const dx = e.clientX - lastMouse.x;
    const dy = e.clientY - lastMouse.y;
    setPan((p) => ({ x: p.x + dx, y: p.y + dy }));
    setLastMouse({ x: e.clientX, y: e.clientY });
  }, [isDragging, lastMouse]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Summary stats
  const stats = useMemo(() => {
    const total = nodes.length;
    const healthy = nodes.filter((n) => n.status === "healthy").length;
    const degraded = nodes.filter((n) => n.status === "degraded").length;
    const critical = nodes.filter((n) => n.status === "critical").length;
    return { total, healthy, degraded, critical };
  }, [nodes]);

  // Selected node info
  const selectedNeighbors = useMemo(() => {
    if (!selectedNode) return [];
    return getNeighbors(selectedNode.id).map((id) => nodes.find((n) => n.id === id)).filter(Boolean) as TopologyNode[];
  }, [selectedNode, getNeighbors, nodes]);

  const selectedEdges = useMemo(() => {
    if (!selectedNode) return [];
    return getConnectedEdges(selectedNode.id);
  }, [selectedNode, getConnectedEdges]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)", height: "100%", overflow: "hidden" }}>
      {/* Stats Bar */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "var(--gap)" }}>
        <div className="metric-card" style={{ borderLeft: "3px solid #33ff33" }}>
          <div className="metric-label">Components</div>
          <div className="metric-value" style={{ color: "#e0e0e0" }}>{stats.total}</div>
          <div className="metric-sub">total nodes</div>
        </div>
        <div className="metric-card" style={{ borderLeft: "3px solid #33ff33" }}>
          <div className="metric-label">Healthy</div>
          <div className="metric-value" style={{ color: "#33ff33" }}>{stats.healthy}</div>
          <div className="metric-sub">operational</div>
        </div>
        <div className="metric-card" style={{ borderLeft: "3px solid #ffaa00" }}>
          <div className="metric-label">Degraded</div>
          <div className="metric-value" style={{ color: "#ffaa00" }}>{stats.degraded}</div>
          <div className="metric-sub">needs attention</div>
        </div>
        <div className="metric-card" style={{ borderLeft: "3px solid #ff3333" }}>
          <div className="metric-label">Critical</div>
          <div className="metric-value" style={{ color: "#ff3333" }}>{stats.critical}</div>
          <div className="metric-sub">failure</div>
        </div>
      </div>

      {/* Main: Graph + Info Panel */}
      <div style={{ display: "grid", gridTemplateColumns: selectedNode ? "1.4fr 1fr" : "1fr", gap: "var(--gap)", flex: 1, minHeight: 0 }}>
        {/* SVG Topology Graph */}
        <div className="panel" style={{ overflow: "hidden", position: "relative", padding: 0 }}>
          <div className="panel-header" style={{ padding: "8px 12px" }}>
            <span className="panel-title">System Architecture</span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)" }}>
              {edges.length} connections across {LAYER_CONFIG.length} layers
            </span>
          </div>
          <div className="panel-body" style={{ position: "relative", overflow: "hidden" }}>
            <svg
              viewBox={`0 0 ${width} ${height}`}
              style={{ width: "100%", height: "100%", cursor: isDragging ? "grabbing" : "grab" }}
              onWheel={(e) => {
                e.preventDefault();
                setZoom((z) => Math.max(0.3, Math.min(3, z - e.deltaY * 0.001)));
              }}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
            >
              {/* Layer backgrounds */}
              {LAYER_CONFIG.map(({ layer, y, color, label }, i) => {
                const nextY = i < LAYER_CONFIG.length - 1 ? LAYER_CONFIG[i + 1].y : 1.05;
                const layerHeight = (nextY - y - 0.01) * height;
                return (
                  <g key={layer}>
                    <rect
                      x={0}
                      y={y * height - 8}
                      width={width}
                      height={layerHeight + 4}
                      fill={`${color}06`}
                      stroke={color}
                      strokeWidth={0.5}
                      opacity={0.4}
                    />
                    <text
                      x={12}
                      y={y * height + layerHeight / 2 + 2}
                      fill={color}
                      fontSize={10}
                      fontFamily="var(--font-mono)"
                      fontWeight={600}
                      textAnchor="start"
                      opacity={0.3}
                      style={{ textTransform: "uppercase", letterSpacing: 2 }}
                    >
                      {label}
                    </text>
                  </g>
                );
              })}

              {/* Edge arrows */}
              <defs>
                {Object.entries(EDGE_COLORS).map(([type, color]) => (
                  <marker key={type} id={`arrow-${type}`} markerWidth="8" markerHeight="6" refX="24" refY="3" orient="auto">
                    <polygon points="0 0, 8 3, 0 6" fill={color} />
                  </marker>
                ))}
              </defs>

              {/* Edges */}
              {edges.map((edge, i) => {
                const src = nodePos(edge.from);
                const tgt = nodePos(edge.to);
                const isHighlighted = selectedNode && (edge.from === selectedNode.id || edge.to === selectedNode.id);
                const isHovered = hoveredNode && (edge.from === hoveredNode || edge.to === hoveredNode);
                const isDimmed = (selectedNode || hoveredNode) && !isHighlighted && !isHovered;
                const edgeColor = EDGE_COLORS[edge.type] || "#2a2a4a";

                return (
                  <g key={`edge-${i}`}>
                    <line
                      x1={src.x}
                      y1={src.y}
                      x2={tgt.x}
                      y2={tgt.y}
                      stroke={isHighlighted || isHovered ? "#3388ff" : edgeColor}
                      strokeWidth={isHighlighted ? 2.5 : isHovered ? 2 : 1.5}
                      opacity={isDimmed ? 0.08 : isHighlighted || isHovered ? 0.9 : 0.5}
                      markerEnd={`url(#arrow-${edge.type})`}
                      style={{ transition: "all 0.2s" }}
                    />
                  </g>
                );
              })}

              {/* Nodes */}
              {nodes.map((node) => {
                const pos = nodePos(node.id);
                const layerConfig = LAYER_CONFIG.find((l) => l.layer === node.layer);
                const layerColor = layerConfig?.color || "#8888aa";
                const statusColor = STATUS_COLORS[node.status];
                const isSelected = selectedNode?.id === node.id;
                const isHovered = hoveredNode === node.id;
                const isNeighbor = selectedNode && getNeighbors(selectedNode.id).includes(node.id);
                const isDimmed = selectedNode && !isSelected && !isNeighbor;
                const nodeWidth = 90;
                const nodeHeight = 36;

                return (
                  <g
                    key={node.id}
                    transform={`translate(${pos.x}, ${pos.y})`}
                    onMouseEnter={() => setHoveredNode(node.id)}
                    onMouseLeave={() => setHoveredNode(null)}
                    onClick={() => setSelectedNode(isSelected ? null : node)}
                    style={{ cursor: "pointer" }}
                  >
                    {/* Glow for selected/hovered */}
                    {(isSelected || isHovered) && (
                      <rect
                        x={-nodeWidth / 2 - 6}
                        y={-nodeHeight / 2 - 6}
                        width={nodeWidth + 12}
                        height={nodeHeight + 12}
                        fill="none"
                        stroke={layerColor}
                        strokeWidth={1.5}
                        opacity={0.3}
                        rx={2}
                      >
                        <animate attributeName="opacity" values="0.3;0.1;0.3" dur="2s" repeatCount="indefinite" />
                      </rect>
                    )}

                    {/* Node body */}
                    <rect
                      x={-nodeWidth / 2}
                      y={-nodeHeight / 2}
                      width={nodeWidth}
                      height={nodeHeight}
                      fill={isSelected ? `${layerColor}30` : `${layerColor}15`}
                      stroke={isSelected ? layerColor : isHovered ? "#e0e0e0" : `${layerColor}80`}
                      strokeWidth={isSelected ? 2 : 1}
                      opacity={isDimmed ? 0.25 : 1}
                      rx={2}
                    />

                    {/* Status dot */}
                    <circle
                      cx={nodeWidth / 2 - 8}
                      cy={-nodeHeight / 2 + 8}
                      r={4}
                      fill={statusColor}
                      opacity={isDimmed ? 0.3 : 1}
                    >
                      {node.status === "healthy" && (
                        <animate attributeName="opacity" values="1;0.5;1" dur="2s" repeatCount="indefinite" />
                      )}
                    </circle>

                    {/* Label */}
                    <text
                      y={-2}
                      fill={isSelected ? "#e0e0e0" : layerColor}
                      fontSize={9}
                      fontFamily="var(--font-mono)"
                      fontWeight={isSelected ? 700 : 600}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      opacity={isDimmed ? 0.25 : 1}
                      style={{ pointerEvents: "none" }}
                    >
                      {node.label}
                    </text>

                    {/* Layer label */}
                    <text
                      y={10}
                      fill={isHovered ? "#e0e0e0" : "#666666"}
                      fontSize={7}
                      fontFamily="var(--font-mono)"
                      textAnchor="middle"
                      dominantBaseline="middle"
                      opacity={isDimmed ? 0.2 : 0.8}
                      style={{ pointerEvents: "none", textTransform: "uppercase" }}
                    >
                      {node.layer}
                    </text>
                  </g>
                );
              })}
            </svg>

            {/* Zoom controls */}
            <div style={{ position: "absolute", bottom: 8, right: 8, display: "flex", gap: 4 }}>
              <button className="btn" onClick={() => setZoom((z) => Math.min(3, z + 0.2))}>+</button>
              <button className="btn" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>Reset</button>
              <button className="btn" onClick={() => setZoom((z) => Math.max(0.3, z - 0.2))}>-</button>
            </div>

            {/* Legend */}
            <div
              style={{
                position: "absolute",
                bottom: 8,
                left: 8,
                background: "rgba(10,10,15,0.9)",
                border: "1px solid var(--border-color)",
                padding: "6px 10px",
                fontFamily: "var(--font-mono)",
                fontSize: 9,
              }}
            >
              <div style={{ color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>Status</div>
              <div style={{ display: "flex", gap: 10 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}><span style={{ width: 6, height: 6, borderRadius: "50%", background: "#33ff33" }} />Healthy</span>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}><span style={{ width: 6, height: 6, borderRadius: "50%", background: "#ffaa00" }} />Degraded</span>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}><span style={{ width: 6, height: 6, borderRadius: "50%", background: "#ff3333" }} />Critical</span>
              </div>
            </div>
          </div>
        </div>

        {/* Component Detail Panel */}
        {selectedNode && (
          <div className="panel" style={{ overflow: "hidden", animation: "fadeIn 0.2s ease-out" }}>
            <div className="panel-header" style={{ justifyContent: "space-between" }}>
              <span className="panel-title">Component Detail</span>
              <button className="btn" onClick={() => setSelectedNode(null)}>Close</button>
            </div>
            <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {/* Header with status */}
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span
                  style={{
                    width: 12,
                    height: 12,
                    borderRadius: "50%",
                    background: STATUS_COLORS[selectedNode.status],
                    display: "inline-block",
                    boxShadow: `0 0 8px ${STATUS_COLORS[selectedNode.status]}40`,
                  }}
                />
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                    {selectedNode.label}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                    {selectedNode.id}
                  </div>
                </div>
              </div>

              {/* Metadata */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase" }}>Layer</div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: LAYER_CONFIG.find((l) => l.layer === selectedNode.layer)?.color || "var(--text-primary)" }}>
                    {selectedNode.layer}
                  </div>
                </div>
                <div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase" }}>Status</div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: STATUS_COLORS[selectedNode.status], textTransform: "uppercase" }}>
                    {selectedNode.status}
                  </div>
                </div>
                {selectedNode.version && (
                  <div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase" }}>Version</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-primary)" }}>{selectedNode.version}</div>
                  </div>
                )}
                {selectedNode.last_check && (
                  <div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase" }}>Last Check</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-primary)" }}>{selectedNode.last_check}</div>
                  </div>
                )}
              </div>

              {/* Description */}
              {selectedNode.description && (
                <div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>
                    Description
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>
                    {selectedNode.description}
                  </div>
                </div>
              )}

              {/* Connected edges */}
              <div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>
                  Connections ({selectedEdges.length})
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {selectedEdges.map((edge, i) => {
                    const isOutgoing = edge.from === selectedNode.id;
                    const otherNode = nodes.find((n) => n.id === (isOutgoing ? edge.to : edge.from));
                    const edgeColor = EDGE_COLORS[edge.type] || "#2a2a4a";
                    return (
                      <div
                        key={i}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          fontFamily: "var(--font-mono)",
                          fontSize: 10,
                          padding: "4px 6px",
                          background: "var(--bg-primary)",
                          border: `1px solid ${edgeColor}40`,
                        }}
                      >
                        <span style={{ color: isOutgoing ? "#3388ff" : "#ff33ff", fontSize: 12 }}>{isOutgoing ? "→" : "←"}</span>
                        <span style={{ color: "var(--text-primary)", flex: 1 }}>{otherNode?.label || "?"}</span>
                        <span className="badge badge-sm" style={{ borderColor: edgeColor, color: edgeColor, background: `${edgeColor}15` }}>
                          {edge.type}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Neighbor nodes */}
              {selectedNeighbors.length > 0 && (
                <div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>
                    Neighbors ({selectedNeighbors.length})
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                    {selectedNeighbors.map((n) => {
                      const nLayerColor = LAYER_CONFIG.find((l) => l.layer === n.layer)?.color || "#8888aa";
                      return (
                        <button
                          key={n.id}
                          className="btn"
                          style={{ fontSize: 9, padding: "3px 6px", borderColor: nLayerColor, color: nLayerColor }}
                          onClick={() => setSelectedNode(n)}
                        >
                          {n.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TopologyView;
