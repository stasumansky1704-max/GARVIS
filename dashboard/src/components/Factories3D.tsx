import { useRef, useMemo, useState, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Text, MeshReflectorMaterial } from "@react-three/drei";
import { EffectComposer, Bloom, SMAA, Vignette } from "@react-three/postprocessing";
import * as THREE from "three";
import type { Factory } from "../data/missionControl";

// Premium 3D Factory cards — the SAME hexagonal holographic-monitor language we landed on
// in the Intelligence Hub, here on glowing pedestals. Only the 5 flagship business factories.
// Native R3F + drei + postprocessing. Factories page only. Honest status only.

const FIVE = ["youtube", "faceless", "education", "novagame", "alphaflow"];
const ACCENT: Record<string, string> = {
  youtube: "#ff2a39", faceless: "#b15cff", education: "#29a8ff", novagame: "#6a6dff", alphaflow: "#12e6a0",
};
const STATUS_COLOR: Record<string, string> = {
  Concept: "#7c8b9c", Blueprint: "#00a3cc", Prototype: "#ffab22", Ready: "#12e6a0", Active: "#12e6a0",
};

// flat-top hexagon (points left/right) — same shape family as the Intel Hub cards
const HEX_SHAPE = (() => {
  const w = 0.86, h = 0.94;
  const s = new THREE.Shape();
  s.moveTo(-w, 0); s.lineTo(-w * 0.5, h); s.lineTo(w * 0.5, h); s.lineTo(w, 0);
  s.lineTo(w * 0.5, -h); s.lineTo(-w * 0.5, -h); s.closePath();
  return s;
})();
const HEX_GEO = new THREE.ExtrudeGeometry(HEX_SHAPE, { depth: 0.18, bevelEnabled: true, bevelThickness: 0.05, bevelSize: 0.05, bevelSegments: 2 });
const HEX_VERTS: [number, number][] = [[-0.86, 0], [-0.43, 0.94], [0.43, 0.94], [0.86, 0], [0.43, -0.94], [-0.43, -0.94]];

// --- per-factory glowing 3D logo (built from primitives, blooms) ---
function FactoryIcon({ id, color }: { id: string; color: string }) {
  const g = useRef<THREE.Group>(null);
  useFrame(({ clock }) => { if (g.current) g.current.rotation.y = Math.sin(clock.getElapsedTime() * 0.6 + id.length) * 0.4; });
  const P = (o = 1) => <meshBasicMaterial color={color} transparent opacity={o} blending={THREE.AdditiveBlending} depthWrite={false} />;
  const S = (ei = 2.4) => <meshStandardMaterial color="#06080e" emissive={color} emissiveIntensity={ei} metalness={0.5} roughness={0.3} toneMapped={false} />;
  let inner: JSX.Element;
  switch (id) {
    case "youtube":
      inner = <mesh rotation={[Math.PI / 2, 0, -Math.PI / 2]}><cylinderGeometry args={[0.26, 0.26, 0.14, 3]} />{S(2.6)}</mesh>;
      break;
    case "faceless":
      inner = (<group>
        <mesh><sphereGeometry args={[0.26, 24, 24]} /><meshStandardMaterial color="#06080e" emissive={color} emissiveIntensity={0.7} metalness={0.4} roughness={0.4} /></mesh>
        <mesh scale={1.01}><sphereGeometry args={[0.26, 14, 10]} /><meshBasicMaterial color={color} wireframe transparent opacity={0.7} blending={THREE.AdditiveBlending} /></mesh>
        <mesh position={[-0.09, 0.04, 0.24]}><sphereGeometry args={[0.035, 10, 10]} />{P()}</mesh>
        <mesh position={[0.09, 0.04, 0.24]}><sphereGeometry args={[0.035, 10, 10]} />{P()}</mesh>
      </group>);
      break;
    case "education":
      inner = (<group rotation={[0.5, 0, 0]}>
        <mesh><boxGeometry args={[0.52, 0.05, 0.52]} />{S(2.2)}</mesh>
        <mesh position={[0, -0.12, 0]}><cylinderGeometry args={[0.12, 0.16, 0.18, 16]} />{S(1.8)}</mesh>
        <mesh position={[0.24, -0.02, 0]}><boxGeometry args={[0.012, 0.3, 0.012]} />{P()}</mesh>
        <mesh position={[0.24, -0.2, 0]}><sphereGeometry args={[0.035, 8, 8]} />{P()}</mesh>
      </group>);
      break;
    case "novagame":
      inner = (<group rotation={[0.2, 0, 0]}>
        <mesh><boxGeometry args={[0.54, 0.28, 0.12]} />{S(2.0)}</mesh>
        <mesh position={[-0.14, 0.01, 0.08]}><boxGeometry args={[0.04, 0.15, 0.03]} />{P()}</mesh>
        <mesh position={[-0.14, 0.01, 0.08]}><boxGeometry args={[0.15, 0.04, 0.03]} />{P()}</mesh>
        <mesh position={[0.12, 0.04, 0.08]}><sphereGeometry args={[0.032, 10, 10]} />{P()}</mesh>
        <mesh position={[0.18, -0.03, 0.08]}><sphereGeometry args={[0.032, 10, 10]} />{P()}</mesh>
      </group>);
      break;
    default: { // alphaflow — rising bars + arrow
      const bars: [number, number][] = [[-0.2, 0.16], [0, 0.26], [0.2, 0.36]];
      inner = (<group>
        {bars.map(([x, h], i) => <mesh key={i} position={[x, -0.2 + h / 2, 0]}><boxGeometry args={[0.11, h, 0.11]} />{i === 2 ? P() : S()}</mesh>)}
        <mesh position={[0.02, 0.24, 0.07]} rotation={[0, 0, -Math.PI / 4.5]}><boxGeometry args={[0.56, 0.035, 0.035]} />{P()}</mesh>
      </group>);
    }
  }
  return <group ref={g} scale={0.78}>{inner}</group>;
}

function Pedestal({ color }: { color: string }) {
  const r = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => { if (r.current) r.current.rotation.z = clock.getElapsedTime() * 0.4; });
  return (
    <group position={[0, -1.55, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <mesh><cylinderGeometry args={[0.95, 1.08, 0.12, 48]} /><meshStandardMaterial color="#0a0e16" metalness={0.85} roughness={0.4} /></mesh>
      <mesh position={[0, 0.07, 0]}><torusGeometry args={[0.82, 0.02, 10, 64]} /><meshBasicMaterial color={color} transparent opacity={0.85} blending={THREE.AdditiveBlending} /></mesh>
      <mesh ref={r} position={[0, 0.07, 0]}><torusGeometry args={[0.62, 0.012, 8, 48, Math.PI * 1.3]} /><meshBasicMaterial color={color} transparent opacity={0.7} blending={THREE.AdditiveBlending} /></mesh>
      <mesh position={[0, 0.07, 0]}><circleGeometry args={[0.8, 48]} /><meshBasicMaterial color={color} transparent opacity={0.12} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
    </group>
  );
}

// Hexagonal premium card — same construction as the Intelligence Hub Card3DItem.
function FactoryCard({ factory, x }: { factory: Factory; x: number }) {
  const grp = useRef<THREE.Group>(null);
  const dot = useRef<THREE.Mesh>(null);
  const sheen = useRef<THREE.Mesh>(null);
  const border = useRef<THREE.LineBasicMaterial>(null);
  const glow = useRef<THREE.MeshBasicMaterial>(null);
  const [hover, setHover] = useState(false);
  const accent = ACCENT[factory.id] ?? "#29d4ff";
  const statusCol = STATUS_COLOR[factory.status] ?? "#7c8b9c";
  const phase = useMemo(() => Math.random() * 6, []);
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (grp.current) {
      grp.current.position.y = Math.sin(t * 0.8 + phase) * 0.05 + (hover ? 0.18 : 0);
      const s = grp.current.scale.x + ((hover ? 1.07 : 1.0) - grp.current.scale.x) * 0.15;
      grp.current.scale.set(s, s, s);
    }
    if (dot.current) (dot.current.material as THREE.MeshBasicMaterial).opacity = 0.45 + 0.55 * (0.5 + 0.5 * Math.sin(t * 2.4 + phase));
    if (border.current) border.current.opacity = 0.86 + 0.14 * Math.sin(t * 1.6 + phase);
    if (glow.current) glow.current.opacity += ((hover ? 0.18 : 0.06) - glow.current.opacity) * 0.1;
    if (sheen.current) {
      const p = (t * 0.35 + phase) % 1;
      sheen.current.position.y = 0.8 - p * 1.6;
      (sheen.current.material as THREE.MeshBasicMaterial).opacity = 0.1 * Math.sin(p * Math.PI);
    }
  });
  return (
    <group position={[x, 0.15, 0]}>
      <group ref={grp}
        onPointerOver={(e) => { e.stopPropagation(); setHover(true); document.body.style.cursor = "pointer"; }}
        onPointerOut={() => { setHover(false); document.body.style.cursor = "auto"; }}
      >
        {/* back-halo */}
        <mesh geometry={HEX_GEO} position={[0, 0, -0.18]} scale={1.2}><meshBasicMaterial ref={glow} color={accent} transparent opacity={0.06} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        {/* outer bezel */}
        <mesh geometry={HEX_GEO} position={[0, 0, -0.08]} scale={1.07}><meshStandardMaterial color="#05080f" metalness={0.6} roughness={0.5} transparent opacity={0.92} depthWrite={false} /></mesh>
        {/* black glass body */}
        <mesh geometry={HEX_GEO}><meshStandardMaterial color="#000000" emissive="#000000" emissiveIntensity={0} metalness={0.25} roughness={0.5} transparent opacity={hover ? 0.5 : 0.42} depthWrite={false} /></mesh>
        {/* inner screen */}
        <mesh geometry={HEX_GEO} scale={0.84} position={[0, 0, 0.04]}><meshStandardMaterial color="#03060c" metalness={0.3} roughness={0.6} transparent opacity={0.64} depthWrite={false} /></mesh>
        {/* sheen */}
        <mesh ref={sheen} position={[0, 0.4, 0.2]}><planeGeometry args={[1.3, 0.18]} /><meshBasicMaterial color={accent} transparent opacity={0.08} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>

        {/* neon borders */}
        <lineSegments position={[0, 0, -0.08]} scale={1.07}><edgesGeometry args={[HEX_GEO]} /><lineBasicMaterial color={accent} transparent opacity={hover ? 0.65 : 0.42} blending={THREE.AdditiveBlending} /></lineSegments>
        <lineSegments><edgesGeometry args={[HEX_GEO]} /><lineBasicMaterial color="#ffffff" transparent opacity={hover ? 0.9 : 0.6} blending={THREE.AdditiveBlending} /></lineSegments>
        <lineSegments scale={1.012}><edgesGeometry args={[HEX_GEO]} /><lineBasicMaterial ref={border} color={accent} transparent opacity={1} blending={THREE.AdditiveBlending} /></lineSegments>
        <lineSegments scale={0.84} position={[0, 0, 0.05]}><edgesGeometry args={[HEX_GEO]} /><lineBasicMaterial color={accent} transparent opacity={hover ? 0.5 : 0.3} blending={THREE.AdditiveBlending} /></lineSegments>
        {/* connector nodes */}
        {HEX_VERTS.map((v, i) => (
          <group key={i} position={[v[0], v[1], 0.06]}>
            <mesh><sphereGeometry args={[0.03, 10, 10]} /><meshBasicMaterial color="#ffffff" transparent opacity={0.95} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
            <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[0.055, 0.007, 8, 24]} /><meshBasicMaterial color={accent} transparent opacity={0.7} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
          </group>
        ))}

        {/* icon badge */}
        <mesh position={[0, 0.52, 0.24]}><circleGeometry args={[0.2, 32]} /><meshBasicMaterial color="#02050b" transparent opacity={0.85} depthWrite={false} /></mesh>
        <mesh position={[0, 0.52, 0.25]} rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[0.21, 0.013, 10, 44]} /><meshBasicMaterial color={accent} transparent opacity={0.95} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        <group position={[0, 0.52, 0.3]}><FactoryIcon id={factory.id} color={accent} /></group>
        <pointLight position={[0, 0.52, 0.7]} color={accent} intensity={1.3} distance={2.2} decay={2} />

        {/* title */}
        <Text position={[0, 0.12, 0.27]} fontSize={0.12} maxWidth={1.45} lineHeight={1.02} letterSpacing={0.02} textAlign="center" anchorX="center" anchorY="middle" color="#ffffff" outlineWidth={0.005} outlineColor="#000000">
          {factory.name.toUpperCase()}
        </Text>
        {/* summary */}
        <Text position={[0, -0.2, 0.27]} fontSize={0.062} maxWidth={1.35} lineHeight={1.25} textAlign="center" anchorX="center" anchorY="middle" color="#a8bcd2">
          {factory.summary}
        </Text>
        {/* divider + diamond */}
        <mesh position={[0, -0.46, 0.26]}><boxGeometry args={[0.95, 0.005, 0.004]} /><meshBasicMaterial color={accent} transparent opacity={0.45} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        <mesh position={[0, -0.46, 0.265]} rotation={[0, 0, Math.PI / 4]}><boxGeometry args={[0.05, 0.05, 0.004]} /><meshBasicMaterial color={accent} transparent opacity={0.9} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        {/* status */}
        <mesh ref={dot} position={[-0.5, -0.6, 0.27]}><circleGeometry args={[0.03, 16]} /><meshBasicMaterial color={statusCol} transparent opacity={1} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        <Text position={[-0.44, -0.6, 0.27]} fontSize={0.06} letterSpacing={0.08} anchorX="left" anchorY="middle" color={statusCol}>{factory.status.toUpperCase()}</Text>
        {/* open factory */}
        <Text position={[0.04, -0.78, 0.27]} fontSize={0.058} letterSpacing={0.14} anchorX="center" anchorY="middle" color="#cfe6ff">OPEN FACTORY ›</Text>
      </group>
      <Pedestal color={accent} />
    </group>
  );
}

function Scene({ factories }: { factories: Factory[] }) {
  const spacing = 2.7;
  const x0 = -((factories.length - 1) * spacing) / 2;
  return (
    <>
      <hemisphereLight args={["#bcd6ff", "#0a0f18", 0.8]} />
      <ambientLight intensity={0.4} />
      <pointLight position={[0, 5, 7]} intensity={1.5} color="#cfe2ff" />
      <pointLight position={[-9, 2, 5]} intensity={0.9} color="#7fb6ff" />
      <pointLight position={[9, 2, 5]} intensity={0.9} color="#7fb6ff" />
      <fogExp2 attach="fog" args={["#03060e", 0.02]} />
      {factories.map((f, i) => <FactoryCard key={f.id} factory={f} x={x0 + i * spacing} />)}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.85, 0]}>
        <planeGeometry args={[60, 24]} />
        <MeshReflectorMaterial resolution={512} mirror={0.42} mixBlur={1.7} mixStrength={1.1} blur={[400, 120]} roughness={0.85} metalness={0.5} color="#050a12" depthScale={1.0} minDepthThreshold={0.4} maxDepthThreshold={1.2} />
      </mesh>
      <EffectComposer multisampling={0} frameBufferType={THREE.HalfFloatType}>
        <SMAA />
        <Bloom intensity={1.25} luminanceThreshold={0.4} luminanceSmoothing={0.9} radius={0.72} mipmapBlur />
        <Vignette offset={0.3} darkness={0.7} />
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
        camera={{ position: [0, 0.05, 8.0], fov: 42 }}
        dpr={[1, 1.6]}
        gl={{ antialias: false, alpha: true, powerPreference: "high-performance" }}
        onCreated={({ gl, camera }) => { gl.toneMapping = THREE.ACESFilmicToneMapping; gl.toneMappingExposure = 1.5; camera.lookAt(0, -0.05, 0); }}
        style={{ background: "transparent" }}
      >
        <Scene factories={five} />
      </Canvas>
    </div>
  );
}
