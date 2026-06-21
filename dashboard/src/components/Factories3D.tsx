import { useRef, useMemo, useState, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Text, MeshReflectorMaterial, RoundedBox, Edges } from "@react-three/drei";
import { EffectComposer, Bloom, SMAA, Vignette } from "@react-three/postprocessing";
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
    <group position={[0, 2.75, -0.2]} rotation={[0.62, 0, 0]} scale={1.32}>
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
  const glow = useRef<THREE.MeshBasicMaterial>(null);
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
    if (glow.current) glow.current.opacity += ((hover ? 0.26 : 0.12) - glow.current.opacity) * 0.1;     // ambient glow
    if (dot.current) (dot.current.material as THREE.MeshBasicMaterial).opacity = 0.45 + 0.55 * (0.5 + 0.5 * Math.sin(t * 2.3 + phase));
  });
  const W = 1.5, H = 2.96;
  return (
    <group position={[x, 0.2, 0]}>
      <group ref={grp}
        onPointerOver={(e) => { e.stopPropagation(); setHover(true); document.body.style.cursor = "pointer"; }}
        onPointerOut={() => { setHover(false); document.body.style.cursor = "auto"; }}
      >
        {/* ambient glow (behind) */}
        <mesh position={[0, 0, -0.24]}><planeGeometry args={[W * 1.5, H * 1.2]} /><meshBasicMaterial ref={glow} color={accent} transparent opacity={0.12} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        {/* dark backing plate for depth — NO bright frame (avoids the ghost double-frame) */}
        <RoundedBox args={[W + 0.07, H + 0.07, 0.34]} radius={0.12} smoothness={5} position={[0, 0, -0.1]}>
          <meshStandardMaterial color="#080b12" metalness={0.88} roughness={0.45} />
        </RoundedBox>

        {/* GLASS CAPSULE — dark tinted glass + ONE white edge core */}
        <RoundedBox args={[W, H, 0.3]} radius={0.11} smoothness={5}>
          <meshPhysicalMaterial color="#060608" emissive={new THREE.Color(accent)} emissiveIntensity={0.06} metalness={0.2} roughness={0.28} transparent opacity={hover ? 0.5 : 0.44} clearcoat={1} clearcoatRoughness={0.2} reflectivity={0.6} depthWrite={false} />
          <Edges threshold={15} color="#ffffff" />
        </RoundedBox>
        {/* ONE clean accent neon frame on the same rounded shape */}
        <RoundedBox args={[W, H, 0.3]} radius={0.11} smoothness={5}>
          <meshBasicMaterial transparent opacity={0} depthWrite={false} />
          <Edges threshold={15} color={accent} />
        </RoundedBox>
        {/* glass diagonal reflection sheen */}
        <mesh position={[0, 0, 0.16]}><planeGeometry args={[W * 0.94, H * 0.96]} /><meshBasicMaterial color="#ffffff" transparent opacity={0.05} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>

        {/* 4. INNER PANEL — dark content area */}
        <RoundedBox args={[W - 0.2, H - 0.24, 0.06]} radius={0.08} smoothness={4} position={[0, -0.18, 0.15]}>
          <meshStandardMaterial color="#04060c" metalness={0.3} roughness={0.6} transparent opacity={0.78} depthWrite={false} />
          <Edges threshold={15} color={accent} />
        </RoundedBox>

        {/* 5. HOLOGRAPHIC ICON (glow 80%) */}
        <group position={[0, 1.04, 0.32]}><FactoryIcon id={factory.id} color={accent} /></group>
        <pointLight position={[0, 1.04, 0.8]} color={accent} intensity={1.8} distance={2.6} decay={2} />
        {/* icon base ring */}
        <mesh position={[0, 0.66, 0.22]} rotation={[Math.PI / 2.1, 0, 0]}><torusGeometry args={[0.4, 0.012, 10, 48]} /><meshBasicMaterial color={accent} transparent opacity={0.6} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>

        {/* 6. TYPOGRAPHY */}
        <Text position={[0, 0.18, 0.23]} fontSize={0.155} maxWidth={1.5} lineHeight={1.04} letterSpacing={0.02} textAlign="center" anchorX="center" anchorY="middle" color="#ffffff" outlineWidth={0.005} outlineColor="#000000">
          {factory.name.toUpperCase()}
        </Text>
        <Text position={[0, -0.28, 0.23]} fontSize={0.078} maxWidth={1.45} lineHeight={1.34} textAlign="center" anchorX="center" anchorY="middle" color="#b5b5b5">
          {factory.summary}
        </Text>

        {/* 7. STATUS LAYER — pill (dark bg + accent border + light text) */}
        <group position={[0, -0.86, 0.23]}>
          <RoundedBox args={[0.95, 0.26, 0.04]} radius={0.13} smoothness={4}>
            <meshStandardMaterial color="#150a26" emissive={new THREE.Color(statusCol)} emissiveIntensity={0.25} metalness={0.2} roughness={0.5} transparent opacity={0.92} />
            <Edges threshold={15} color={statusCol} />
          </RoundedBox>
          <mesh ref={dot} position={[-0.32, 0, 0.04]}><circleGeometry args={[0.03, 16]} /><meshBasicMaterial color={statusCol} transparent blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
          <Text position={[0.04, 0, 0.05]} fontSize={0.07} letterSpacing={0.1} anchorX="center" anchorY="middle" color={statusCol}>{factory.status.toUpperCase()}</Text>
        </group>

        {/* 6b. ACTION BUTTON — OPEN FACTORY (bg #0A0A0A + accent border, hover glow+lift) */}
        <group position={[0, -1.28, 0.2]}>
          <RoundedBox args={[1.42, 0.4, 0.1]} radius={0.09} smoothness={4}>
            <meshStandardMaterial color="#0a0a0a" emissive={new THREE.Color(accent)} emissiveIntensity={hover ? 0.7 : 0.32} metalness={0.3} roughness={0.4} />
            <Edges threshold={15} color={accent} />
          </RoundedBox>
          <Text position={[-0.08, 0, 0.08]} fontSize={0.11} letterSpacing={0.16} anchorX="center" anchorY="middle" color="#ffffff">OPEN FACTORY</Text>
          <mesh position={[0.56, 0, 0.08]} rotation={[0, 0, -Math.PI / 2]}><coneGeometry args={[0.055, 0.1, 3]} /><meshBasicMaterial color={accent} /></mesh>
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

      <FactoryModel />
      <Particles />
      {factories.map((f, i) => <FactoryCard key={f.id} factory={f} x={x0 + i * spacing} />)}

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -2.45, 0]}>
        <planeGeometry args={[70, 28]} />
        <MeshReflectorMaterial resolution={1024} mirror={0.5} mixBlur={1.6} mixStrength={1.3} blur={[500, 160]} roughness={0.8} metalness={0.5} color="#04080f" depthScale={1.1} minDepthThreshold={0.4} maxDepthThreshold={1.2} />
      </mesh>

      <EffectComposer multisampling={0} frameBufferType={THREE.HalfFloatType}>
        <SMAA />
        <Bloom intensity={1.35} luminanceThreshold={0.4} luminanceSmoothing={0.9} radius={0.74} mipmapBlur />
        <Vignette offset={0.28} darkness={0.72} />
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
