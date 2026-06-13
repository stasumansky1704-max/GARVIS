// =============================================================================
// EcosystemGraph — Phase 5: Cognition ecosystem force-directed graph
// =============================================================================

import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import Panel from "./common/Panel";
import { useApi } from "@/hooks/useApi";
import { api } from "@/api";
import type { EcosystemData, EcosystemNode } from "@/types";

const NODE_COLORS: Record<string, string> = {
  governance: "#ff33ff",
  memory: "#00ffff",
  reasoning: "#3388ff",
  session: "#33ff33",
};

const EDGE_COLORS: Record<string, string> = {
  reinforcement: "#33ff33",
  dependency: "#ff3333",
  override: "#ffaa00",
  influence: "#ff33ff",
  feeds: "#3388ff",
  informs: "#00ffff",
  checks: "#8888aa",
  blocked: "#ff3333",
  contains: "#e0e0e0",
  uses: "#666",
  protects: "#33ff33",
};

// Simple force-directed layout
function computeLayout(
  nodes: EcosystemNode[],
  edges: { source: string; target: string }[],
  width: number,
  height: number,
  iterations = 80
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number; vx: number; vy: number }>();

  // Initialize with random positions near center
  nodes.forEach((n) => {
    positions.set(n.id, {
      x: width / 2 + (Math.random() - 0.5) * width * 0.3,
      y: height / 2 + (Math.random() - 0.5) * height * 0.3,
      vx: 0,
      vy: 0,
    });
  });

  const k = Math.sqrt((width * height) / nodes.length) * 0.4;
  const c = 0.04;

  for (let iter = 0; iter < iterations; iter++) {
    // Repulsion
    nodes.forEach((n1) => {
      nodes.forEach((n2) => {
        if (n1.id === n2.id) return;
        const p1 = positions.get(n1.id)!;
        const p2 = positions.get(n2.id)!;
        let dx = p1.x - p2.x;
        let dy = p1.y - p2.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (k * k) / dist;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        p1.vx += fx * c;
        p1.vy += fy * c;
        p2.vx -= fx * c;
        p2.vy -= fy * c;
      });
    });

    // Attraction along edges
    edges.forEach((e) => {
      const p1 = positions.get(e.source);
      const p2 = positions.get(e.target);
      if (!p1 || !p2) return;
      let dx = p2.x - p1.x;
      let dy = p2.y - p1.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist * dist) / k;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      p1.vx += fx * c;
      p1.vy += fy * c;
      p2.vx -= fx * c;
      p2.vy -= fy * c;
    });

    // Center gravity
    nodes.forEach((n) => {
      const p = positions.get(n.id)!;
      p.vx += (width / 2 - p.x) * 0.005;
      p.vy += (height / 2 - p.y) * 0.005;
    });

    // Apply velocity with damping
    nodes.forEach((n) => {
      const p = positions.get(n.id)!;
      p.vx *= 0.5;
      p.vy *= 0.5;
      p.x += p.vx;
      p.y += p.vy;
      // Clamp to bounds
      p.x = Math.max(30, Math.min(width - 30, p.x));
      p.y = Math.max(30, Math.min(height - 30, p.y));
    });
  }

  const result = new Map<string, { x: number; y: number }>();
  positions.forEach((p, id) => result.set(id, { x: p.x, y: p.y }));
  return result;
}

const EcosystemGraph: React.FC = () => {
  const { data: ecosystem, loading } = useApi(api.analytics.getCognitionEcosystem);
  const [selectedNode, setSelectedNode] = useState<EcosystemNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 800, height: 500 });

  useEffect(() => {
    if (!containerRef.current) return;
    const el = containerRef.current;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setSize({ width: entry.contentRect.width, height: entry.contentRect.height });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const positions = useMemo(() => {
    if (!ecosystem) return new Map();
    return computeLayout(ecosystem.nodes, ecosystem.edges, size.width, size.height);
  }, [ecosystem, size.width, size.height]);

  if (loading || !ecosystem) {
    return <div style={{ color: "#666", fontFamily: "var(--font-mono)", padding: 40, textAlign: "center" }}>Loading ecosystem...</div>;
  }

  const { nodes, edges } = ecosystem;

  const getPos = (id: string) => positions.get(id) || { x: size.width / 2, y: size.height / 2 };

  // Find connected edges for hovered node
  const connectedEdges = hoveredNode
    ? edges.filter((e) => e.source === hoveredNode || e.target === hoveredNode)
    : [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--gap)", height: "100%" }}>
      <Panel title="Cognition Ecosystem" style={{ flex: 1 }}>
        <div ref={containerRef} style={{ width: "100%", height: "100%", position: "relative" }}>
          <svg width={size.width} height={size.height} style={{ position: "absolute", top: 0, left: 0 }}>
            <defs>
              <marker id="eco-arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                <polygon points="0 0, 8 3, 0 6" fill="#2a2a4a" />
              </marker>
              <marker id="eco-arrow-hl" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                <polygon points="0 0, 8 3, 0 6" fill="#3388ff" />
              </marker>
            </defs>

            {/* Edges */}
            {edges.map((edge, i) => {
              const src = getPos(edge.source);
              const tgt = getPos(edge.target);
              const isConnected = hoveredNode && (edge.source === hoveredNode || edge.target === hoveredNode);
              const isDimmed = hoveredNode && !isConnected;

              // Compute angle for arrow placement
              const angle = Math.atan2(tgt.y - src.y, tgt.x - src.x);
              const nodeRadius = 24;
              const srcX = src.x + Math.cos(angle) * nodeRadius;
              const srcY = src.y + Math.sin(angle) * nodeRadius;
              const tgtX = tgt.x - Math.cos(angle) * nodeRadius;
              const tgtY = tgt.y - Math.sin(angle) * nodeRadius;

              return (
                <g key={`edge-${i}`}>
                  <line
                    x1={srcX} y1={srcY} x2={tgtX} y2={tgtY}
                    stroke={isConnected ? EDGE_COLORS[edge.type] || "#3388ff" : "#2a2a4a"}
                    strokeWidth={isConnected ? 2 : Math.max(1, (edge.strength || 0.5) * 2)}
                    opacity={isDimmed ? 0.1 : (edge.strength || 0.5) * 0.8 + 0.2}
                    markerEnd={isConnected ? "url(#eco-arrow-hl)" : "url(#eco-arrow)"}
                  />
                  {edge.label && isConnected && (
                    <text
                      x={(src.x + tgt.x) / 2}
                      y={(src.y + tgt.y) / 2 - 6}
                      fill={EDGE_COLORS[edge.type] || "#8888aa"}
                      fontSize={8}
                      fontFamily="var(--font-mono)"
                      textAnchor="middle"
                    >
                      {edge.label}
                    </text>
                  )}
                </g>
              );
            })}

            {/* Nodes */}
            {nodes.map((node) => {
              const pos = getPos(node.id);
              const color = NODE_COLORS[node.type] || "#8888aa";
              const isHovered = hoveredNode === node.id;
              const isDimmed = hoveredNode && hoveredNode !== node.id && !connectedEdges.some((e) => e.source === node.id || e.target === node.id);
              const r = (node.radius || 24);

              return (
                <g
                  key={node.id}
                  transform={`translate(${pos.x}, ${pos.y})`}
                  onMouseEnter={() => setHoveredNode(node.id)}
                  onMouseLeave={() => setHoveredNode(null)}
                  onClick={() => setSelectedNode(node)}
                  style={{ cursor: "pointer" }}
                >
                  {/* Glow */}
                  {isHovered && (
                    <circle r={r + 8} fill="none" stroke={color} strokeWidth={1} opacity={0.3}>
                      <animate attributeName="r" values={`${r + 4};${r + 12};${r + 4}`} dur="2s" repeatCount="indefinite" />
                      <animate attributeName="opacity" values="0.3;0.1;0.3" dur="2s" repeatCount="indefinite" />
                    </circle>
                  )}
                  {/* Node body */}
                  <rect
                    x={-r} y={-r * 0.6}
                    width={r * 2} height={r * 1.2}
                    fill={`${color}15`}
                    stroke={color}
                    strokeWidth={isHovered ? 2.5 : 1}
                    opacity={isDimmed ? 0.2 : 1}
                    rx={0}
                  />
                  {/* Label */}
                  {node.label.split("\\n").map((line, li) => (
                    <text
                      key={li}
                      y={li * 9 - (node.label.split("\\n").length - 1) * 4.5}
                      fill={color}
                      fontSize={7}
                      fontFamily="var(--font-mono)"
                      fontWeight={isHovered ? 700 : 500}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      opacity={isDimmed ? 0.2 : 1}
                      style={{ pointerEvents: "none" }}
                    >
                      {line}
                    </text>
                  ))}
                </g>
              );
            })}
          </svg>

          {/* Legend */}
          <div style={{
            position: "absolute",
            top: 8,
            right: 8,
            background: "rgba(17,17,24,0.9)",
            border: "1px solid #2a2a4a",
            padding: "8px 12px",
            fontFamily: "var(--font-mono)",
            fontSize: 9,
          }}>
            <div style={{ color: "#8888aa", marginBottom: 4, textTransform: "uppercase", letterSpacing: 1 }}>Legend</div>
            {Object.entries(NODE_COLORS).map(([type, color]) => (
              <div key={type} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                <span style={{ width: 10, height: 10, background: `${color}30`, border: `1px solid ${color}`, display: "inline-block" }} />
                <span style={{ color }}>{type}</span>
              </div>
            ))}
            <div style={{ borderTop: "1px solid #2a2a4a", margin: "6px 0" }} />
            <div style={{ color: "#666" }}>Nodes: {nodes.length}</div>
            <div style={{ color: "#666" }}>Edges: {edges.length}</div>
          </div>

          {/* Selected node info */}
          {selectedNode && (
            <div style={{
              position: "absolute",
              bottom: 8,
              left: 8,
              right: 100,
              background: "rgba(17,17,24,0.95)",
              border: "1px solid #2a2a4a",
              padding: "8px 12px",
              fontFamily: "var(--font-mono)",
              fontSize: 10,
            }}>
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <span style={{ color: NODE_COLORS[selectedNode.type], fontWeight: 700 }}>{selectedNode.id}</span>
                <span style={{ color: "#8888aa" }}>{selectedNode.type}</span>
                {selectedNode.metadata && Object.entries(selectedNode.metadata).map(([k, v]) => (
                  <span key={k} style={{ color: "#666" }}>{k}: <span style={{ color: "#e0e0e0" }}>{String(v)}</span></span>
                ))}
                <button className="btn" style={{ marginLeft: "auto" }} onClick={() => setSelectedNode(null)}>Close</button>
              </div>
            </div>
          )}
        </div>
      </Panel>
    </div>
  );
};

export default EcosystemGraph;
