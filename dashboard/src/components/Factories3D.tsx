import { useRef, useMemo, useState, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Text, MeshReflectorMaterial, RoundedBox, Edges, Environment, Lightformer } from "@react-three/drei";
import { EffectComposer, Bloom, SMAA, Vignette, SSAO, HueSaturation, BrightnessContrast } from "@react-three/postprocessing";
import * as THREE from "three";
import type { Factory } from "../data/missionControl";

// Holographic Factory Cards — built to the design breakdown: 8 layers, exact neon colors,
// glowing pedestals, light beams, floating particles, and a holographic factory model above.
// A LIVING R3F scene (not a background image). Factories page only. Honest status.

const FIVE = ["youtube", "faceless", "education", "novagame", "alphaflow"];
const ACCENT: Record<string, string> = {
  youtube: "#ff3d3d", faceless: "#a855ff", education: "#38b6ff", novagame: "#3d6bff", alphaflow: "#d6ff3d",
};
const STATUS_COLOR: Record<string, string> = {
  Concept: "#9ab0c4", Blueprint: "#38b6ff", Prototype: "#ffb800", Ready: "#3ddc84", Active: "#3ddc84",
};
const HOLO = "#00e6ff";   // factory-model holographic blue

// flat rounded-rect helpers (avoid RoundedBox ballooning when radius > depth/2)
const CW = 1.5, CH = 2.96;
function rrShape(w: number, h: number, r: number) {
  const s = new THREE.Shape();
  const x = -w / 2, y = -h / 2;
  s.moveTo(x + r, y);
  s.lineTo(x + w - r, y); s.absarc(x + w - r, y + r, r, -Math.PI / 2, 0, false);
  s.lineTo(x + w, y + h - r); s.absarc(x + w - r, y + h - r, r, 0, Math.PI / 2, false);
  s.lineTo(x + r, y + h); s.absarc(x + r, y + h - r, r, Math.PI / 2, Math.PI, false);
  s.lineTo(x, y + r); s.absarc(x + r, y + r, r, Math.PI, Math.PI * 1.5, false);
  s.closePath();
  return s;
}
const rrLine = (w: number, h: number, r: number) => new THREE.BufferGeometry().setFromPoints(rrShape(w, h, r).getPoints(6));
const rrFill = (w: number, h: number, r: number) => new THREE.ShapeGeometry(rrShape(w, h, r));
const FRAME_GEO = rrLine(CW, CH, 0.12);            // 1. outer neon frame (matches body radius)
const SECONDARY_GEO = rrLine(CW - 0.14, CH - 0.14, 0.1); // 2. secondary inset frame (depth)
const PANEL_FILL = rrFill(CW - 0.22, CH - 0.28, 0.1);
const PANEL_LINE = rrLine(CW - 0.22, CH - 0.28, 0.1);
const PILL_FILL = rrFill(0.96, 0.26, 0.13);
const PILL_LINE = rrLine(0.96, 0.26, 0.13);
const BTN_FILL = rrFill(1.42, 0.42, 0.1);
const BTN_LINE = rrLine(1.42, 0.42, 0.1);

// =================== per-factory glowing 3D logo ===================
function FactoryIcon({ id, color }: { id: string; color: string }) {
  const g = useRef<THREE.Group>(null);
  useFrame(({ clock }) => { if (g.current) g.current.rotation.y = Math.sin(clock.getElapsedTime() * 0.55 + id.length) * 0.4; });
  const P = (o = 1) => <meshBasicMaterial color={color} transparent opacity={o} blending={THREE.AdditiveBlending} depthWrite={false} />;
  const S = (ei = 2.6) => <meshStandardMaterial color="#06080e" emissive={color} emissiveIntensity={ei} metalness={0.5} roughness={0.3} toneMapped={false} />;
  let inner: JSX.Element;
  switch (id) {
    case "youtube":
      inner = <mesh rotation={[Math.PI / 2, 0, -Math.PI / 2]}><cylinderGeometry args={[0.34, 0.34, 0.18, 3]} />{S(2.8)}</mesh>;
      break;
    case "faceless":
      inner = (<group>
        <mesh><sphereGeometry args={[0.34, 26, 26]} /><meshStandardMaterial color="#06080e" emissive={color} emissiveIntensity={0.7} metalness={0.4} roughness={0.4} /></mesh>
        <mesh scale={1.01}><sphereGeometry args={[0.34, 16, 11]} /><meshBasicMaterial color={color} wireframe transparent opacity={0.75} blending={THREE.AdditiveBlending} /></mesh>
        <mesh position={[-0.11, 0.06, 0.31]}><sphereGeometry args={[0.045, 10, 10]} />{P()}</mesh>
        <mesh position={[0.11, 0.06, 0.31]}><sphereGeometry args={[0.045, 10, 10]} />{P()}</mesh>
      </group>);
      break;
    case "education":
      inner = (<group rotation={[0.5, 0, 0]}>
        <mesh><boxGeometry args={[0.7, 0.07, 0.7]} />{S(2.4)}</mesh>
        <mesh position={[0, -0.16, 0]}><cylinderGeometry args={[0.16, 0.2, 0.22, 16]} />{S(1.9)}</mesh>
        <mesh position={[0.32, -0.02, 0]}><boxGeometry args={[0.016, 0.4, 0.016]} />{P()}</mesh>
        <mesh position={[0.32, -0.26, 0]}><sphereGeometry args={[0.045, 8, 8]} />{P()}</mesh>
      </group>);
      break;
    case "novagame":
      inner = (<group rotation={[0.2, 0, 0]}>
        <mesh><boxGeometry args={[0.72, 0.38, 0.16]} />{S(2.2)}</mesh>
        <mesh position={[-0.19, 0.01, 0.1]}><boxGeometry args={[0.05, 0.2, 0.035]} />{P()}</mesh>
        <mesh position={[-0.19, 0.01, 0.1]}><boxGeometry args={[0.2, 0.05, 0.035]} />{P()}</mesh>
        <mesh position={[0.16, 0.06, 0.1]}><sphereGeometry args={[0.04, 10, 10]} />{P()}</mesh>
        <mesh position={[0.24, -0.05, 0.1]}><sphereGeometry args={[0.04, 10, 10]} />{P()}</mesh>
      </group>);
      break;
    default: { // alphaflow — rising bars + arrow
      const bars: [number, number][] = [[-0.26, 0.2], [0, 0.34], [0.26, 0.48]];
      inner = (<group>
        {bars.map(([x, h], i) => <mesh key={i} position={[x, -0.26 + h / 2, 0]}><boxGeometry args={[0.14, h, 0.14]} />{i === 2 ? P() : S()}</mesh>)}
        <mesh position={[0.02, 0.32, 0.09]} rotation={[0, 0, -Math.PI / 4.5]}><boxGeometry args={[0.72, 0.045, 0.045]} />{P()}</mesh>
      </group>);
    }
  }
  return <group ref={g}>{inner}</group>;
}

// =================== floating particles (ambient) ===================
function Particles({ count = 260, color = HOLO }: { count?: number; color?: string }) {
  const ref = useRef<THREE.Points>(null);
  const geo = useMemo(() => {
    const a: number[] = [];
    for (let i = 0; i < count; i++) a.push((Math.random() - 0.5) * 26, (Math.random() - 0.5) * 14, (Math.random() - 0.5) * 10 - 1);
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(a, 3)); return g;
  }, [count]);
  useEffect(() => () => geo.dispose(), [geo]);
  useFrame(({ clock }) => { if (ref.current) { const t = clock.getElapsedTime(); ref.current.rotation.y = t * 0.01; ref.current.position.y = Math.sin(t * 0.1) * 0.25; } });
  return <points ref={ref} geometry={geo}><pointsMaterial color={color} size={0.03} sizeAttenuation transparent opacity={0.5} blending={THREE.AdditiveBlending} depthWrite={false} /></points>;
}

// =================== holographic factory model (architectural 3/4 view) ===================
function FactoryModel() {
  const grp = useRef<THREE.Group>(null);
  const nav = useRef<THREE.Group>(null);
  const smoke = useRef<THREE.Group>(null);
  // modular industrial blocks (x, z, w, d, h)
  const buildings = useMemo(() => ([
    { x: -0.95, z: -0.55, w: 0.52, d: 0.5, h: 0.62 },
    { x: -0.3, z: -0.55, w: 0.5, d: 0.5, h: 0.95 },
    { x: 0.4, z: -0.55, w: 0.55, d: 0.5, h: 0.5 },
    { x: -0.95, z: 0.25, w: 0.46, d: 0.5, h: 0.8 },
    { x: -0.25, z: 0.3, w: 0.62, d: 0.55, h: 0.55 },
    { x: 0.55, z: 0.3, w: 0.5, d: 0.5, h: 0.7 },
    { x: 1.0, z: -0.15, w: 0.4, d: 0.4, h: 0.45 },
    { x: -1.45, z: -0.1, w: 0.36, d: 0.4, h: 0.4 },
  ]), []);
  // tall thin towers (x, z, h)
  const towers = useMemo(() => [[-0.55, -0.1, 2.05], [0.65, -0.35, 2.45], [0.15, 0.55, 1.7], [-1.1, 0.6, 1.4]] as [number, number, number][], []);
  // emissive windows on the front + side faces
  const windows = useMemo(() => {
    const out: [number, number, number, number][] = []; // x,y,z, faceRot(0 front /1 side)
    buildings.forEach((b) => {
      const rows = Math.max(1, Math.floor(b.h / 0.2));
      const cols = b.w > 0.5 ? 2 : 1;
      for (let r = 0; r < rows; r++) {
        const wy = 0.14 + r * 0.2;
        for (let c = 0; c < cols; c++) {
          const ox = cols === 1 ? 0 : (c - 0.5) * b.w * 0.46;
          out.push([b.x + ox, wy, b.z + b.d / 2 + 0.006, 0]);
        }
        out.push([b.x + b.w / 2 + 0.006, wy, b.z, 1]);
      }
    });
    return out;
  }, [buildings]);
  const navDots = useMemo(() => towers.map(([x, z, h]) => [x, h + 0.06, z] as [number, number, number]).concat([[0, 1.3, 0], [1.0, 0.6, -0.15]]), [towers]);
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (grp.current) grp.current.rotation.y = t * 0.1;
    if (nav.current) nav.current.children.forEach((c, i) => { ((c as THREE.Mesh).material as THREE.MeshBasicMaterial).opacity = 0.35 + 0.65 * Math.pow(0.5 + 0.5 * Math.sin(t * 2.2 + i * 1.3), 2); });
    if (smoke.current) smoke.current.children.forEach((c, i) => { const m = c as THREE.Mesh; m.position.y = (m.userData.base ?? 0) + ((t * 0.4 + i) % 1) * 0.5; (m.material as THREE.MeshBasicMaterial).opacity = 0.25 * (1 - ((t * 0.4 + i) % 1)); });
  });
  const metal = (e = 0.45) => <meshStandardMaterial color="#06182a" emissive={HOLO} emissiveIntensity={e} metalness={0.7} roughness={0.38} />;
  // tilt so we look at the rooftops/front (architectural), not the underside; gentle spin inside
  return (
    <group position={[0, 2.55, -0.6]} rotation={[0.6, 0, 0]} scale={0.82}>
      <group ref={grp}>
        {/* platform with holographic edge + grid */}
        <mesh position={[0, -0.06, 0]}><boxGeometry args={[3.2, 0.13, 2.3]} />{metal(0.35)}<Edges threshold={15} color={HOLO} /></mesh>
        <mesh position={[0, 0.012, 0]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[3.05, 2.15]} /><meshBasicMaterial color={HOLO} transparent opacity={0.09} blending={THREE.AdditiveBlending} /></mesh>
        <mesh position={[0, 0.013, 0]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[3.05, 2.15, 12, 8]} /><meshBasicMaterial color={HOLO} wireframe transparent opacity={0.12} blending={THREE.AdditiveBlending} /></mesh>

        {/* modular buildings */}
        {buildings.map((b, i) => (
          <mesh key={i} position={[b.x, b.h / 2 + 0.005, b.z]}><boxGeometry args={[b.w, b.h, b.d]} />{metal()}<Edges threshold={15} color={HOLO} /></mesh>
        ))}
        {/* tall towers + tapered tops */}
        {towers.map(([x, z, h], i) => (
          <group key={`t${i}`} position={[x, 0, z]}>
            <mesh position={[0, h / 2, 0]}><boxGeometry args={[0.2, h, 0.2]} />{metal(0.5)}<Edges threshold={15} color={HOLO} /></mesh>
            <mesh position={[0, h + 0.12, 0]}><coneGeometry args={[0.14, 0.26, 4]} />{metal(0.7)}</mesh>
          </group>
        ))}
        {/* emissive windows (rooms) */}
        {windows.map((w, i) => (
          <mesh key={`w${i}`} position={[w[0], w[1], w[2]]} rotation={[0, w[3] ? Math.PI / 2 : 0, 0]}>
            <boxGeometry args={[0.045, 0.055, 0.01]} />
            <meshStandardMaterial color="#000000" emissive="#9fe8ff" emissiveIntensity={2.2} toneMapped={false} />
          </mesh>
        ))}
        {/* steam/smoke rising from a couple of towers */}
        <group ref={smoke}>
          {[[0.65, 2.55, -0.35], [-0.55, 2.15, -0.1]].map((p, i) => (
            <mesh key={i} position={[p[0], p[1], p[2]]} userData={{ base: p[1] }}><sphereGeometry args={[0.12, 8, 8]} /><meshBasicMaterial color="#bfe6ff" transparent opacity={0.2} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
          ))}
        </group>
        {/* blinking navigation lights on the tower tops */}
        <group ref={nav}>
          {navDots.map((p, i) => <mesh key={i} position={p}><sphereGeometry args={[0.04, 8, 8]} /><meshBasicMaterial color="#d6f6ff" transparent opacity={0.8} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>)}
        </group>
        <pointLight position={[0, 1.6, 0.8]} intensity={3.2} distance={6} decay={2} color={HOLO} />
        <pointLight position={[0, 0.4, 0]} intensity={1.4} distance={3} decay={2} color="#2979ff" />
      </group>
    </group>
  );
}

// =================== pedestal (rings + light beam) ===================
function Pedestal({ color }: { color: string }) {
  const r = useRef<THREE.Mesh>(null);
  const beam = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (r.current) r.current.rotation.z = t * 0.5;
    if (beam.current) (beam.current.material as THREE.MeshBasicMaterial).opacity = 0.18 + 0.1 * Math.sin(t * 1.4);
  });
  return (
    <group position={[0, -2.0, 0]}>
      {/* upward light beam (from pedestal into the card) */}
      <mesh ref={beam} position={[0, 1.0, 0]}><cylinderGeometry args={[0.5, 0.85, 2.0, 36, 1, true]} /><meshBasicMaterial color={color} transparent opacity={0.18} blending={THREE.AdditiveBlending} side={THREE.DoubleSide} depthWrite={false} /></mesh>
      <group rotation={[-Math.PI / 2, 0, 0]}>
        <mesh><cylinderGeometry args={[1.05, 1.2, 0.14, 56]} /><meshStandardMaterial color="#0a0e16" metalness={0.85} roughness={0.4} /><Edges threshold={15} color={color} /></mesh>
        <mesh position={[0, 0.08, 0]}><torusGeometry args={[0.92, 0.025, 12, 72]} /><meshBasicMaterial color={color} transparent opacity={0.95} blending={THREE.AdditiveBlending} /></mesh>
        <mesh ref={r} position={[0, 0.08, 0]}><torusGeometry args={[0.68, 0.014, 8, 56, Math.PI * 1.3]} /><meshBasicMaterial color={color} transparent opacity={0.8} blending={THREE.AdditiveBlending} /></mesh>
        <mesh position={[0, 0.08, 0]}><torusGeometry args={[0.46, 0.01, 8, 48]} /><meshBasicMaterial color={color} transparent opacity={0.5} blending={THREE.AdditiveBlending} /></mesh>
        <mesh position={[0, 0.085, 0]}><circleGeometry args={[0.9, 56]} /><meshBasicMaterial color={color} transparent opacity={0.14} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
      </group>
    </group>
  );
}

// =================== 8-layer holographic card ===================
function FactoryCard({ factory, x }: { factory: Factory; x: number }) {
  const grp = useRef<THREE.Group>(null);
  const dot = useRef<THREE.Mesh>(null);
  const [hover, setHover] = useState(false);
  const accent = ACCENT[factory.id] ?? HOLO;
  const statusCol = STATUS_COLOR[factory.status] ?? "#9ab0c4";
  const phase = useMemo(() => Math.random() * 6, []);
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (grp.current) {
      grp.current.position.y = Math.sin(t * 0.7 + phase) * 0.05 + (hover ? 0.2 : 0);
      const s = grp.current.scale.x + ((hover ? 1.05 : 1.0) - grp.current.scale.x) * 0.15;
      grp.current.scale.set(s, s, s);
    }
    if (dot.current) (dot.current.material as THREE.MeshBasicMaterial).opacity = 0.45 + 0.55 * (0.5 + 0.5 * Math.sin(t * 2.3 + phase));
  });
  return (
    <group position={[x, 0.2, -Math.abs(x) * 0.12]} rotation={[0, -x * 0.1, 0]}>
      <group ref={grp}
        onPointerOver={(e) => { e.stopPropagation(); setHover(true); document.body.style.cursor = "pointer"; }}
        onPointerOut={() => { setHover(false); document.body.style.cursor = "auto"; }}
      >
        {/* SOLID 3D card body — thick dark (depth 0.44 > 2*radius → valid RoundedBox) */}
        <RoundedBox args={[CW, CH, 0.44]} radius={0.12} smoothness={6}>
          <meshPhysicalMaterial color="#0a0c13" emissive={new THREE.Color(accent)} emissiveIntensity={0.05} metalness={0.5} roughness={0.34} clearcoat={1} clearcoatRoughness={0.16} reflectivity={0.7} />
        </RoundedBox>
        {/* 1. OUTER NEON FRAME — coincident with the card edge (accent + white core) — glow 100% */}
        <lineLoop geometry={FRAME_GEO} position={[0, 0, 0.221]}><lineBasicMaterial color={accent} transparent opacity={1} blending={THREE.AdditiveBlending} /></lineLoop>
        <lineLoop geometry={FRAME_GEO} position={[0, 0, 0.223]}><lineBasicMaterial color="#ffffff" transparent opacity={0.85} blending={THREE.AdditiveBlending} /></lineLoop>
        {/* 2. SECONDARY inset frame — depth & structure (medium 60%) */}
        <lineLoop geometry={SECONDARY_GEO} position={[0, 0, 0.222]}><lineBasicMaterial color={accent} transparent opacity={0.55} blending={THREE.AdditiveBlending} /></lineLoop>
        {/* inner accent glow (medium) — soft wash inside the glass behind the content */}
        <mesh position={[0, 0.1, 0.04]}><planeGeometry args={[CW * 0.78, CH * 0.78]} /><meshBasicMaterial color={accent} transparent opacity={0.06} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        {/* top-edge light line */}
        <mesh position={[0, CH / 2 - 0.06, 0.232]}><boxGeometry args={[CW * 0.82, 0.018, 0.005]} /><meshBasicMaterial color={accent} transparent opacity={0.85} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>

        {/* 4. INNER PANEL — flat dark recessed content area */}
        <mesh geometry={PANEL_FILL} position={[0, -0.18, 0.225]}><meshBasicMaterial color="#04060c" transparent opacity={0.5} depthWrite={false} /></mesh>
        <lineLoop geometry={PANEL_LINE} position={[0, -0.18, 0.232]}><lineBasicMaterial color={accent} transparent opacity={0.4} blending={THREE.AdditiveBlending} /></lineLoop>

        {/* 5. HOLOGRAPHIC ICON */}
        <group position={[0, 1.0, 0.36]}><FactoryIcon id={factory.id} color={accent} /></group>
        <pointLight position={[0, 1.0, 0.85]} color={accent} intensity={1.9} distance={2.6} decay={2} />
        <mesh position={[0, 0.62, 0.25]} rotation={[Math.PI / 2.1, 0, 0]}><torusGeometry args={[0.4, 0.012, 10, 48]} /><meshBasicMaterial color={accent} transparent opacity={0.6} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>

        {/* 6. TYPOGRAPHY */}
        <Text position={[0, 0.16, 0.25]} fontSize={0.135} maxWidth={1.3} lineHeight={1.05} letterSpacing={0.02} textAlign="center" anchorX="center" anchorY="middle" color="#ffffff" outlineWidth={0.004} outlineColor="#000000">
          {factory.name.toUpperCase()}
        </Text>
        <Text position={[0, -0.26, 0.25]} fontSize={0.07} maxWidth={1.26} lineHeight={1.35} textAlign="center" anchorX="center" anchorY="middle" color="#b5b5b5">
          {factory.summary}
        </Text>

        {/* 7. STATUS LAYER — flat pill */}
        <group position={[0, -0.84, 0.25]}>
          <mesh geometry={PILL_FILL}><meshBasicMaterial color="#140a22" transparent opacity={0.9} depthWrite={false} /></mesh>
          <lineLoop geometry={PILL_LINE}><lineBasicMaterial color={statusCol} transparent opacity={0.95} blending={THREE.AdditiveBlending} /></lineLoop>
          <mesh ref={dot} position={[-0.33, 0, 0.01]}><circleGeometry args={[0.03, 16]} /><meshBasicMaterial color={statusCol} transparent blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
          <Text position={[0.04, 0, 0.02]} fontSize={0.07} letterSpacing={0.1} anchorX="center" anchorY="middle" color={statusCol}>{factory.status.toUpperCase()}</Text>
        </group>

        {/* 6b. ACTION BUTTON — OPEN FACTORY (flat, accent border, hover glow) */}
        <group position={[0, -1.24, 0.25]}>
          <mesh geometry={BTN_FILL}><meshStandardMaterial color="#0a0a0a" emissive={new THREE.Color(accent)} emissiveIntensity={hover ? 0.55 : 0.26} metalness={0.3} roughness={0.45} /></mesh>
          <lineLoop geometry={BTN_LINE} position={[0, 0, 0.01]}><lineBasicMaterial color={accent} transparent opacity={1} blending={THREE.AdditiveBlending} /></lineLoop>
          <Text position={[-0.08, 0, 0.02]} fontSize={0.105} letterSpacing={0.16} anchorX="center" anchorY="middle" color="#ffffff">OPEN FACTORY</Text>
          <mesh position={[0.56, 0, 0.02]} rotation={[0, 0, -Math.PI / 2]}><coneGeometry args={[0.05, 0.09, 3]} /><meshBasicMaterial color={accent} /></mesh>
        </group>
      </group>
      {/* 8. PEDESTAL BASE */}
      <Pedestal color={accent} />
    </group>
  );
}

function Scene({ factories }: { factories: Factory[] }) {
  const spacing = 2.35;
  const x0 = -((factories.length - 1) * spacing) / 2;
  return (
    <>
      <hemisphereLight args={["#bcd6ff", "#080c14", 0.75]} />
      <ambientLight intensity={0.35} />
      <pointLight position={[0, 7, 8]} intensity={1.6} color="#cfe2ff" />
      <pointLight position={[-11, 3, 6]} intensity={0.8} color="#7fb6ff" />
      <pointLight position={[11, 3, 6]} intensity={0.8} color="#7fb6ff" />
      <fogExp2 attach="fog" args={["#03060e", 0.016]} />

      {/* in-engine environment (no network HDR) → real reflections on glass + metal */}
      <Environment resolution={64} frames={1}>
        <Lightformer intensity={1.6} color="#cfe2ff" position={[0, 4, 4]} scale={[8, 4, 1]} />
        <Lightformer intensity={1.0} color="#5a9bff" position={[-6, 1, 2]} scale={[3, 6, 1]} />
        <Lightformer intensity={1.0} color="#5a9bff" position={[6, 1, 2]} scale={[3, 6, 1]} />
        <Lightformer intensity={0.6} color="#1a3a6a" position={[0, -3, -4]} scale={[10, 4, 1]} />
      </Environment>

      <FactoryModel />
      <Particles />
      {factories.map((f, i) => <FactoryCard key={f.id} factory={f} x={x0 + i * spacing} />)}

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -2.45, 0]}>
        <planeGeometry args={[70, 28]} />
        <MeshReflectorMaterial resolution={1024} mirror={0.5} mixBlur={1.6} mixStrength={1.3} blur={[500, 160]} roughness={0.8} metalness={0.5} color="#04080f" depthScale={1.1} minDepthThreshold={0.4} maxDepthThreshold={1.2} />
      </mesh>

      {/* cinematic post chain: SMAA -> SSAO (contact depth) -> Bloom -> color grade -> Vignette */}
      <EffectComposer multisampling={0} frameBufferType={THREE.HalfFloatType}>
        <SMAA />
        <SSAO samples={24} radius={0.12} intensity={18} luminanceInfluence={0.5} color={new THREE.Color("#000000")} worldDistanceThreshold={1} worldDistanceFalloff={1} worldProximityThreshold={1} worldProximityFalloff={1} />
        <Bloom intensity={1.3} luminanceThreshold={0.42} luminanceSmoothing={0.9} radius={0.74} mipmapBlur />
        <HueSaturation saturation={0.12} />
        <BrightnessContrast brightness={0.0} contrast={0.12} />
        <Vignette offset={0.28} darkness={0.74} />
      </EffectComposer>
    </>
  );
}

export default function Factories3D({ factories }: { factories: Factory[] }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const five = useMemo(
    () => FIVE.map((id) => factories.find((f) => f.id === id)).filter(Boolean) as Factory[],
    [factories]
  );
  if (!mounted) return <div className="factories3d-stage" />;
  return (
    <div className="factories3d-stage">
      <Canvas
        camera={{ position: [0, 0.45, 7.1], fov: 49 }}
        dpr={[1, 1.6]}
        gl={{ antialias: false, alpha: true, powerPreference: "high-performance" }}
        onCreated={({ gl, camera }) => { gl.toneMapping = THREE.ACESFilmicToneMapping; gl.toneMappingExposure = 1.5; camera.lookAt(0, 0.6, 0); }}
        style={{ background: "transparent" }}
      >
        <Scene factories={five} />
      </Canvas>
    </div>
  );
}
