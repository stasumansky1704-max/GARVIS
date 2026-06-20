import { useRef, useMemo, useState, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Text, MeshReflectorMaterial, RoundedBox, Edges } from "@react-three/drei";
import { EffectComposer, Bloom, SMAA, Vignette } from "@react-three/postprocessing";
import * as THREE from "three";
import type { Factory } from "../data/missionControl";

// Premium 3D Factory cards — tall holographic glass capsules on glowing pedestals, matching
// the concept art. Native R3F + drei + postprocessing. Factories page only. Honest status.

const FIVE = ["youtube", "faceless", "education", "novagame", "alphaflow"];
const ACCENT: Record<string, string> = {
  youtube: "#ff2a39", faceless: "#b15cff", education: "#29a8ff", novagame: "#6a6dff", alphaflow: "#12e6a0",
};
const STATUS_COLOR: Record<string, string> = {
  Concept: "#7c8b9c", Blueprint: "#00a3cc", Prototype: "#ffab22", Ready: "#12e6a0", Active: "#12e6a0",
};

// --- per-factory glowing 3D logo (built from primitives, blooms) ---
function FactoryIcon({ id, color }: { id: string; color: string }) {
  const g = useRef<THREE.Group>(null);
  useFrame(({ clock }) => { if (g.current) g.current.rotation.y = Math.sin(clock.getElapsedTime() * 0.6 + id.length) * 0.4; });
  const P = (o = 1) => <meshBasicMaterial color={color} transparent opacity={o} blending={THREE.AdditiveBlending} depthWrite={false} />;
  const S = (ei = 2.4) => <meshStandardMaterial color="#06080e" emissive={color} emissiveIntensity={ei} metalness={0.5} roughness={0.3} toneMapped={false} />;
  let inner: JSX.Element;
  switch (id) {
    case "youtube":
      inner = <mesh rotation={[Math.PI / 2, 0, -Math.PI / 2]}><cylinderGeometry args={[0.3, 0.3, 0.16, 3]} />{S(2.6)}</mesh>;
      break;
    case "faceless":
      inner = (<group>
        <mesh><sphereGeometry args={[0.3, 24, 24]} /><meshStandardMaterial color="#06080e" emissive={color} emissiveIntensity={0.7} metalness={0.4} roughness={0.4} /></mesh>
        <mesh scale={1.01}><sphereGeometry args={[0.3, 14, 10]} /><meshBasicMaterial color={color} wireframe transparent opacity={0.7} blending={THREE.AdditiveBlending} /></mesh>
        <mesh position={[-0.1, 0.05, 0.27]}><sphereGeometry args={[0.04, 10, 10]} />{P()}</mesh>
        <mesh position={[0.1, 0.05, 0.27]}><sphereGeometry args={[0.04, 10, 10]} />{P()}</mesh>
      </group>);
      break;
    case "education":
      inner = (<group rotation={[0.5, 0, 0]}>
        <mesh><boxGeometry args={[0.6, 0.06, 0.6]} />{S(2.2)}</mesh>
        <mesh position={[0, -0.14, 0]}><cylinderGeometry args={[0.14, 0.18, 0.2, 16]} />{S(1.8)}</mesh>
        <mesh position={[0.28, -0.02, 0]}><boxGeometry args={[0.014, 0.34, 0.014]} />{P()}</mesh>
        <mesh position={[0.28, -0.22, 0]}><sphereGeometry args={[0.04, 8, 8]} />{P()}</mesh>
      </group>);
      break;
    case "novagame":
      inner = (<group rotation={[0.2, 0, 0]}>
        <mesh><boxGeometry args={[0.62, 0.32, 0.14]} />{S(2.0)}</mesh>
        <mesh position={[-0.16, 0.01, 0.09]}><boxGeometry args={[0.045, 0.17, 0.03]} />{P()}</mesh>
        <mesh position={[-0.16, 0.01, 0.09]}><boxGeometry args={[0.17, 0.045, 0.03]} />{P()}</mesh>
        <mesh position={[0.14, 0.05, 0.09]}><sphereGeometry args={[0.036, 10, 10]} />{P()}</mesh>
        <mesh position={[0.2, -0.04, 0.09]}><sphereGeometry args={[0.036, 10, 10]} />{P()}</mesh>
      </group>);
      break;
    default: { // alphaflow — rising bars + arrow
      const bars: [number, number][] = [[-0.22, 0.18], [0, 0.3], [0.22, 0.42]];
      inner = (<group>
        {bars.map(([x, h], i) => <mesh key={i} position={[x, -0.22 + h / 2, 0]}><boxGeometry args={[0.12, h, 0.12]} />{i === 2 ? P() : S()}</mesh>)}
        <mesh position={[0.02, 0.28, 0.08]} rotation={[0, 0, -Math.PI / 4.5]}><boxGeometry args={[0.62, 0.04, 0.04]} />{P()}</mesh>
      </group>);
    }
  }
  return <group ref={g}>{inner}</group>;
}

function Pedestal({ color }: { color: string }) {
  const r = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => { if (r.current) r.current.rotation.z = clock.getElapsedTime() * 0.4; });
  return (
    <group position={[0, -1.72, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <mesh><cylinderGeometry args={[0.96, 1.1, 0.13, 48]} /><meshStandardMaterial color="#0a0e16" metalness={0.85} roughness={0.4} /></mesh>
      <mesh position={[0, 0.075, 0]}><torusGeometry args={[0.84, 0.022, 10, 64]} /><meshBasicMaterial color={color} transparent opacity={0.85} blending={THREE.AdditiveBlending} /></mesh>
      <mesh ref={r} position={[0, 0.075, 0]}><torusGeometry args={[0.62, 0.012, 8, 48, Math.PI * 1.3]} /><meshBasicMaterial color={color} transparent opacity={0.7} blending={THREE.AdditiveBlending} /></mesh>
      <mesh position={[0, 0.075, 0]}><circleGeometry args={[0.82, 48]} /><meshBasicMaterial color={color} transparent opacity={0.13} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
    </group>
  );
}

// Tall rectangular holographic glass capsule (concept-art style).
function FactoryCard({ factory, x }: { factory: Factory; x: number }) {
  const grp = useRef<THREE.Group>(null);
  const glow = useRef<THREE.MeshBasicMaterial>(null);
  const dot = useRef<THREE.Mesh>(null);
  const [hover, setHover] = useState(false);
  const accent = ACCENT[factory.id] ?? "#29d4ff";
  const statusCol = STATUS_COLOR[factory.status] ?? "#7c8b9c";
  const phase = useMemo(() => Math.random() * 6, []);
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (grp.current) {
      grp.current.position.y = Math.sin(t * 0.8 + phase) * 0.05 + (hover ? 0.16 : 0);
      const s = grp.current.scale.x + ((hover ? 1.05 : 1.0) - grp.current.scale.x) * 0.15;
      grp.current.scale.set(s, s, s);
    }
    if (glow.current) glow.current.opacity += ((hover ? 0.2 : 0.08) - glow.current.opacity) * 0.1;
    if (dot.current) (dot.current.material as THREE.MeshBasicMaterial).opacity = 0.45 + 0.55 * (0.5 + 0.5 * Math.sin(t * 2.4 + phase));
  });
  return (
    <group position={[x, 0.15, 0]}>
      <group ref={grp}
        onPointerOver={(e) => { e.stopPropagation(); setHover(true); document.body.style.cursor = "pointer"; }}
        onPointerOut={() => { setHover(false); document.body.style.cursor = "auto"; }}
      >
        {/* soft back-halo */}
        <mesh position={[0, 0, -0.2]}><planeGeometry args={[2.1, 3.5]} /><meshBasicMaterial ref={glow} color={accent} transparent opacity={0.08} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        {/* outer metal frame */}
        <RoundedBox args={[1.62, 2.96, 0.34]} radius={0.12} smoothness={5} position={[0, 0, -0.06]}>
          <meshStandardMaterial color="#070b12" metalness={0.88} roughness={0.4} />
          <Edges threshold={15} color={accent} />
        </RoundedBox>
        {/* black holographic glass body */}
        <RoundedBox args={[1.5, 2.84, 0.3]} radius={0.1} smoothness={5}>
          <meshStandardMaterial color="#000000" emissive="#000000" emissiveIntensity={0} metalness={0.25} roughness={0.5} transparent opacity={hover ? 0.5 : 0.42} depthWrite={false} />
          <Edges threshold={15} color="#ffffff" />
        </RoundedBox>
        {/* accent inner edge */}
        <RoundedBox args={[1.42, 2.76, 0.32]} radius={0.09} smoothness={4}>
          <meshBasicMaterial transparent opacity={0} depthWrite={false} />
          <Edges threshold={15} color={accent} />
        </RoundedBox>
        {/* recessed screen panel */}
        <RoundedBox args={[1.34, 2.62, 0.06]} radius={0.08} smoothness={4} position={[0, 0, 0.14]}>
          <meshStandardMaterial color="#03060c" metalness={0.3} roughness={0.6} transparent opacity={0.6} depthWrite={false} />
        </RoundedBox>

        {/* glowing logo + light */}
        <group position={[0, 0.92, 0.3]}><FactoryIcon id={factory.id} color={accent} /></group>
        <pointLight position={[0, 0.92, 0.7]} color={accent} intensity={1.5} distance={2.4} decay={2} />
        {/* divider under the icon */}
        <mesh position={[0, 0.5, 0.22]}><boxGeometry args={[1.05, 0.006, 0.004]} /><meshBasicMaterial color={accent} transparent opacity={0.4} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>

        {/* title */}
        <Text position={[0, 0.26, 0.22]} fontSize={0.13} maxWidth={1.3} lineHeight={1.05} textAlign="center" anchorX="center" anchorY="middle" color="#ffffff" outlineWidth={0.004} outlineColor="#000000">
          {factory.name.toUpperCase()}
        </Text>
        {/* summary */}
        <Text position={[0, -0.12, 0.22]} fontSize={0.07} maxWidth={1.28} lineHeight={1.32} textAlign="center" anchorX="center" anchorY="middle" color="#a8bcd2">
          {factory.summary}
        </Text>
        {/* status */}
        <mesh ref={dot} position={[-0.44, -0.58, 0.22]}><circleGeometry args={[0.032, 16]} /><meshBasicMaterial color={statusCol} transparent blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        <Text position={[-0.38, -0.58, 0.22]} fontSize={0.07} letterSpacing={0.08} anchorX="left" anchorY="middle" color={statusCol}>
          {factory.status.toUpperCase()}
        </Text>

        {/* OPEN FACTORY button */}
        <group position={[0, -1.02, 0.2]}>
          <RoundedBox args={[1.22, 0.36, 0.08]} radius={0.08} smoothness={4}>
            <meshStandardMaterial color="#04121c" emissive={new THREE.Color(accent)} emissiveIntensity={hover ? 0.65 : 0.34} metalness={0.3} roughness={0.4} transparent opacity={0.92} />
            <Edges threshold={15} color={accent} />
          </RoundedBox>
          <Text position={[-0.07, 0, 0.07]} fontSize={0.1} letterSpacing={0.14} anchorX="center" anchorY="middle" color="#eafdff">OPEN FACTORY</Text>
          <mesh position={[0.47, 0, 0.07]} rotation={[0, 0, -Math.PI / 2]}><coneGeometry args={[0.05, 0.09, 3]} /><meshBasicMaterial color={accent} /></mesh>
        </group>
      </group>
      <Pedestal color={accent} />
    </group>
  );
}

function Scene({ factories }: { factories: Factory[] }) {
  const spacing = 2.05;
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
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -2.0, 0]}>
        <planeGeometry args={[60, 24]} />
        <MeshReflectorMaterial resolution={512} mirror={0.42} mixBlur={1.7} mixStrength={1.1} blur={[400, 120]} roughness={0.85} metalness={0.5} color="#050a12" depthScale={1.0} minDepthThreshold={0.4} maxDepthThreshold={1.2} />
      </mesh>
      <EffectComposer multisampling={0} frameBufferType={THREE.HalfFloatType}>
        <SMAA />
        <Bloom intensity={1.2} luminanceThreshold={0.42} luminanceSmoothing={0.9} radius={0.7} mipmapBlur />
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
        camera={{ position: [0, 0.1, 7.8], fov: 44 }}
        dpr={[1, 1.6]}
        gl={{ antialias: false, alpha: true, powerPreference: "high-performance" }}
        onCreated={({ gl, camera }) => { gl.toneMapping = THREE.ACESFilmicToneMapping; gl.toneMappingExposure = 1.5; camera.lookAt(0, -0.1, 0); }}
        style={{ background: "transparent" }}
      >
        <Scene factories={five} />
      </Canvas>
    </div>
  );
}
