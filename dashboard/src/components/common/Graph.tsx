// =============================================================================
// Graph — SVG-based force-directed graph component (nodes + edges)
// =============================================================================

import React, { useState, useCallback, useMemo, useRef } from "react";

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  x?: number;
  y?: number;
  radius?: number;
  color?: string;
  metadata?: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  label?: string;
  strength?: number;
  type: string;
  color?: string;
}

interface GraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  width?: number;
  height?: number;
  onNodeClick?: (node: GraphNode) => void;
  onNodeHover?: (node: GraphNode | null) => void;
}

const typeColors: Record<string, string> = {
  governance: "#ff33ff",
  memory: "#00ffff",
  reasoning: "#3388ff",
  session: "#33ff33",
  epistemic: "#3388ff",
  operational: "#33ff33",
  boundary: "#ff3333",
  reflective: "#ffaa00",
};

function simpleLayout(nodes: GraphNode[], edges: GraphEdge[], width: number, height: number): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  const cx = width / 2;
  const cy = height / 2;

  // Group nodes by type
  const byType = new Map<string, GraphNode[]>();
  nodes.forEach((n) => {
    const arr = byType.get(n.type) || [];
    arr.push(n);
    byType.set(n.type, arr);
  });

  // Place governance nodes in a circle at top-left
  const govNodes = byType.get("governance") || [];
  govNodes.forEach((n, i) => {
    const angle = (i / Math.max(govNodes.length, 1)) * Math.PI * 0.8 - Math.PI * 0.4;
    const r = Math.min(width, height) * 0.22;
    positions.set(n.id, { x: cx * 0.7 + Math.cos(angle) * r, y: cy * 0.6 + Math.sin(angle) * r });
  });

  // Place memory nodes in a circle at bottom
  const memNodes = byType.get("memory") || [];
  memNodes.forEach((n, i) => {
    const angle = Math.PI * 0.3 + (i / Math.max(memNodes.length, 1)) * Math.PI * 0.4;
    const r = Math.min(width, height) * 0.2;
    positions.set(n.id, { x: cx + Math.cos(angle) * r, y: cy * 1.3 + Math.sin(angle) * r * 0.5 });
  });

  // Place reasoning nodes in a circle at right
  const infNodes = byType.get("reasoning") || [];
  infNodes.forEach((n, i) => {
    const angle = -Math.PI * 0.3 + (i / Math.max(infNodes.length, 1)) * Math.PI * 0.4;
    const r = Math.min(width, height) * 0.2;
    positions.set(n.id, { x: cx * 1.3 + Math.cos(angle) * r, y: cy * 0.7 + Math.sin(angle) * r });
  });

  // Place session nodes at center
  const sesNodes = byType.get("session") || [];
  sesNodes.forEach((n) => {
    positions.set(n.id, { x: cx, y: cy });
  });

  // Place any remaining nodes randomly
  nodes.forEach((n) => {
    if (!positions.has(n.id)) {
      positions.set(n.id, { x: cx + (Math.random() - 0.5) * width * 0.4, y: cy + (Math.random() - 0.5) * height * 0.4 });
    }
  });

  return positions;
}

const Graph: React.FC<GraphProps> = ({ nodes, edges, width = 600, height = 400, onNodeClick, onNodeHover }) => {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const isDragging = useRef(false);
  const lastMouse = useRef({ x: 0, y: 0 });

  const positions = useMemo(() => simpleLayout(nodes, edges, width, height), [nodes, edges, width, height]);

  const handleMouseEnter = useCallback((node: GraphNode) => {
    setHoveredNode(node.id);
    onNodeHover?.(node);
  }, [onNodeHover]);

  const handleMouseLeave = useCallback(() => {
    setHoveredNode(null);
    onNodeHover?.(null);
  }, [onNodeHover]);

  const nodePos = (id: string) => {
    const p = positions.get(id);
    if (!p) return { x: width / 2, y: height / 2 };
    return { x: p.x * zoom + pan.x, y: p.y * zoom + pan.y };
  };

  const getNode = (id: string) => nodes.find((n) => n.id === id);

  // Split label into lines
  const formatLabel = (label: string): string[] => label.split("\\n");

  return (
    <div className="graph-container" style={{ width, height }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        onWheel={(e) => {
          e.preventDefault();
          setZoom((z) => Math.max(0.3, Math.min(3, z - e.deltaY * 0.001)));
        }}
        onMouseDown={(e) => {
          isDragging.current = true;
          lastMouse.current = { x: e.clientX, y: e.clientY };
        }}
        onMouseMove={(e) => {
          if (!isDragging.current) return;
          const dx = e.clientX - lastMouse.current.x;
          const dy = e.clientY - lastMouse.current.y;
          setPan((p) => ({ x: p.x + dx, y: p.y + dy }));
          lastMouse.current = { x: e.clientX, y: e.clientY };
        }}
        onMouseUp={() => { isDragging.current = false; }}
        onMouseLeave={() => { isDragging.current = false; }}
        style={{ cursor: isDragging.current ? "grabbing" : "grab" }}
      >
        <defs>
          <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#2a2a4a" />
          </marker>
        </defs>

        {/* Edges */}
        {edges.map((edge, i) => {
          const src = nodePos(edge.source);
          const tgt = nodePos(edge.target);
          const isHovered = hoveredNode && (edge.source === hoveredNode || edge.target === hoveredNode);
          return (
            <g key={`edge-${i}`}>
              <line
                x1={src.x} y1={src.y} x2={tgt.x} y2={tgt.y}
                stroke={isHovered ? "#3388ff" : (edge.color || "#2a2a4a")}
                strokeWidth={isHovered ? 2 : Math.max(1, (edge.strength || 0.5) * 2.5)}
                opacity={hoveredNode && !isHovered ? 0.15 : (edge.strength || 0.5) * 0.8 + 0.2}
                markerEnd="url(#arrowhead)"
              />
              {edge.label && (
                <text
                  x={(src.x + tgt.x) / 2}
                  y={(src.y + tgt.y) / 2 - 4}
                  fill={isHovered ? "#3388ff" : "#444466"}
                  fontSize={8}
                  fontFamily="var(--font-mono)"
                  textAnchor="middle"
                  opacity={hoveredNode && !isHovered ? 0.1 : 0.7}
                >
                  {edge.label}
                </text>
              )}
            </g>
          );
        })}

        {/* Nodes */}
        {nodes.map((node) => {
          const pos = nodePos(node.id);
          const r = (node.radius || 20) * zoom;
          const color = node.color || typeColors[node.type] || "#8888aa";
          const isHovered = hoveredNode === node.id;

          return (
            <g
              key={node.id}
              transform={`translate(${pos.x}, ${pos.y})`}
              onMouseEnter={() => handleMouseEnter(node)}
              onMouseLeave={handleMouseLeave}
              onClick={() => onNodeClick?.(node)}
              style={{ cursor: onNodeClick ? "pointer" : "default" }}
            >
              {/* Glow effect */}
              {isHovered && (
                <circle r={r + 6} fill="none" stroke={color} strokeWidth={1} opacity={0.3}>
                  <animate attributeName="r" values={`${r + 4};${r + 10};${r + 4}`} dur="2s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.3;0.1;0.3" dur="2s" repeatCount="indefinite" />
                </circle>
              )}
              {/* Node body */}
              <rect
                x={-r} y={-r * 0.65}
                width={r * 2} height={r * 1.3}
                fill={`${color}15`}
                stroke={color}
                strokeWidth={isHovered ? 2 : 1}
                opacity={hoveredNode && !isHovered ? 0.2 : 1}
              />
              {/* Label */}
              {formatLabel(node.label).map((line, li) => (
                <text
                  key={li}
                  y={li * 10 - (formatLabel(node.label).length - 1) * 5}
                  fill={color}
                  fontSize={8}
                  fontFamily="var(--font-mono)"
                  fontWeight={600}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  opacity={hoveredNode && !isHovered ? 0.2 : 1}
                  style={{ pointerEvents: "none" }}
                >
                  {line}
                </text>
              ))}
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

      {/* Node hover tooltip */}
      {hoveredNode && (() => {
        const node = getNode(hoveredNode);
        if (!node) return null;
        const pos = nodePos(hoveredNode);
        return (
          <div
            style={{
              position: "absolute",
              left: Math.min(pos.x + 20, width - 200),
              top: Math.max(pos.y - 60, 0),
              background: "#111118",
              border: "1px solid #2a2a4a",
              padding: "8px 12px",
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              zIndex: 10,
              pointerEvents: "none",
              maxWidth: 220,
            }}
          >
            <div style={{ color: typeColors[node.type] || "#e0e0e0", fontWeight: 700, marginBottom: 4 }}>
              {node.id}
            </div>
            <div style={{ color: "#8888aa" }}>{node.type}</div>
            {node.metadata && Object.entries(node.metadata).map(([k, v]) => (
              <div key={k} style={{ color: "#666" }}>{k}: {String(v)}</div>
            ))}
          </div>
        );
      })()}
    </div>
  );
};

export default React.memo(Graph);
