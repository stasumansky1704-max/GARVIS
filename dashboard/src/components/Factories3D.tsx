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

// =================== holographic factory model (above the cards) ===================
function FactoryModel() {
  const grp = useRef<THREE.Group>(null);
  const nav = useRef<THREE.Group>(null);
  const buildings = useMemo(() => {
    const out: { x: number; z: number; w: number; d: number; h: number }[] = [];
    const rnd = (s: number) => (Math.sin(s * 12.9898) * 43758.5453) % 1;
    for (let i = 0; i < 11; i++) {
      const x = (i % 4 - 1.5) * 0.62 + (i >= 4 ? 0.0 : 0.0);
      const z = (Math.floor(i / 4) - 1) * 0.62;
      out.push({ x, z, w: 0.34 + Math.abs(rnd(i + 1)) * 0.16, d: 0.34, h: 0.4 + Math.abs(rnd(i + 7)) * 0.9 });
    }
    return out;
  }, []);
  const stacks = useMemo(() => [[-0.95, -0.3, 1.5], [0.95, 0.4, 1.9], [-0.2, 0.7, 1.3]] as [number, number, number][], []);
  const navDots = useMemo(() => Array.from({ length: 7 }, (_, i) => [(i % 4 - 1.5) * 0.6, 1.0 + (i % 3) * 0.5, (Math.floor(i / 4) - 0.5) * 0.6] as [number, number, number]), []);
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (grp.current) grp.current.rotation.y = t * 0.12;
    if (nav.current) nav.current.children.forEach((c, i) => { (((c as THREE.Mesh).material) as THREE.MeshBasicMaterial).opacity = 0.4 + 0.6 * (0.5 + 0.5 * Math.sin(t * 2.5 + i)); });
  });
  const holoMetal = <meshStandardMaterial color="#071a2c" emissive={HOLO} emissiveIntensity={0.5} metalness={0.6} roughness={0.4} />;
  return (
    <group ref={grp} position={[0, 3.25, -1]} scale={1.28}>
      {/* platform base */}
      <mesh position={[0, -0.05, 0]}><boxGeometry args={[3.0, 0.12, 2.2]} />{holoMetal}<Edges threshold={15} color={HOLO} /></mesh>
      <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[2.9, 2.1]} /><meshBasicMaterial color={HOLO} transparent opacity={0.08} blending={THREE.AdditiveBlending} /></mesh>
      {/* buildings */}
      {buildings.map((b, i) => (
        <mesh key={i} position={[b.x, b.h / 2 + 0.02, b.z]}><boxGeometry args={[b.w, b.h, b.d]} />{holoMetal}<Edges threshold={15} color={HOLO} /></mesh>
      ))}
      {/* smokestacks */}
      {stacks.map(([x, z, h], i) => (
        <group key={`s${i}`} position={[x, 0, z]}>
          <mesh position={[0, h / 2, 0]}><cylinderGeometry args={[0.09, 0.12, h, 16]} />{holoMetal}<Edges threshold={15} color={HOLO} /></mesh>
          <mesh position={[0, h + 0.12, 0]}><cylinderGeometry args={[0.06, 0.09, 0.4, 12, 1, true]} /><meshBasicMaterial color={HOLO} transparent opacity={0.25} blending={THREE.AdditiveBlending} side={THREE.DoubleSide} depthWrite={false} /></mesh>
        </group>
      ))}
      {/* blinking nav lights */}
      <group ref={nav}>
        {navDots.map((p, i) => <mesh key={i} position={p}><sphereGeometry args={[0.035, 8, 8]} /><meshBasicMaterial color="#bfefff" transparent opacity={0.8} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>)}
      </group>
      <pointLight position={[0, 1.5, 1]} intensity={3} distance={6} decay={2} color={HOLO} />
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
  const frame = useRef<THREE.LineBasicMaterial>(null);
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
    if (frame.current) frame.current.opacity = 0.85 + 0.15 * Math.sin(t * 1.5 + phase);                 // outer neon flicker (slow)
    if (dot.current) (dot.current.material as THREE.MeshBasicMaterial).opacity = 0.45 + 0.55 * (0.5 + 0.5 * Math.sin(t * 2.3 + phase));
  });
  const W = 1.74, H = 3.5;
  return (
    <group position={[x, 0.2, 0]}>
      <group ref={grp}
        onPointerOver={(e) => { e.stopPropagation(); setHover(true); document.body.style.cursor = "pointer"; }}
        onPointerOut={() => { setHover(false); document.body.style.cursor = "auto"; }}
      >
        {/* Ambient glow (Layer behind, 20%) */}
        <mesh position={[0, 0, -0.28]}><planeGeometry args={[W * 1.5, H * 1.25]} /><meshBasicMaterial ref={glow} color={accent} transparent opacity={0.12} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>

        {/* 2. SECONDARY FRAME — depth & structure (brushed metal) */}
        <RoundedBox args={[W + 0.16, H + 0.16, 0.4]} radius={0.14} smoothness={5} position={[0, 0, -0.1]}>
          <meshStandardMaterial color="#0a0e16" metalness={0.9} roughness={0.42} />
          <Edges threshold={15} color={accent} />
        </RoundedBox>

        {/* 3. GLASS CAPSULE — dark tinted glass (you can see the inner glow through it) */}
        <RoundedBox args={[W, H, 0.32]} radius={0.11} smoothness={5}>
          <meshPhysicalMaterial color="#060608" emissive={new THREE.Color(accent)} emissiveIntensity={0.06} metalness={0.2} roughness={0.28} transparent opacity={hover ? 0.5 : 0.44} clearcoat={1} clearcoatRoughness={0.2} reflectivity={0.6} depthWrite={false} />
        </RoundedBox>
        {/* glass diagonal reflection sheen */}
        <mesh position={[0, 0, 0.17]}><planeGeometry args={[W * 0.94, H * 0.96]} /><meshBasicMaterial color="#ffffff" transparent opacity={0.05} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>

        {/* 1. OUTER NEON FRAME — primary glow border (100%) */}
        <lineSegments scale={1.0}><edgesGeometry args={[new THREE.BoxGeometry(W, H, 0.32)]} /><lineBasicMaterial ref={frame} color={accent} transparent opacity={1} blending={THREE.AdditiveBlending} /></lineSegments>
        <RoundedBox args={[W, H, 0.32]} radius={0.11} smoothness={5}><meshBasicMaterial transparent opacity={0} depthWrite={false} /><Edges threshold={15} color="#ffffff" /></RoundedBox>

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
