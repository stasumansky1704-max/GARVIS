import { useRef, useMemo, useState, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { RoundedBox, Edges, Text, MeshReflectorMaterial } from "@react-three/drei";
import { EffectComposer, Bloom, SMAA, Vignette } from "@react-three/postprocessing";
import * as THREE from "three";
import type { Factory } from "../data/missionControl";

// Premium 3D Factory cards (Factories page only). Native R3F + drei + postprocessing.
// Same language as the Intelligence Hub cards: black glass + neon edges + glowing 3D logo,
// here as upright rectangular monitors on glowing pedestals. Honest status only.

const ACCENT: Record<string, string> = {
  youtube: "#ff2a39", faceless: "#b15cff", education: "#29a8ff", novagame: "#6a6dff",
  alphaflow: "#12e6a0", marketing: "#ff5ca8", leadgen: "#ffab22", products: "#1fe2ff",
  newsletter: "#2ee6c0", social: "#ff7a3c",
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
    case "youtube": // play triangle
      inner = <mesh rotation={[Math.PI / 2, 0, -Math.PI / 2]}><cylinderGeometry args={[0.26, 0.26, 0.14, 3]} />{S(2.6)}</mesh>;
      break;
    case "faceless": // head + eyes
      inner = (<group>
        <mesh><sphereGeometry args={[0.26, 24, 24]} /><meshStandardMaterial color="#06080e" emissive={color} emissiveIntensity={0.7} metalness={0.4} roughness={0.4} /></mesh>
        <mesh scale={1.01}><sphereGeometry args={[0.26, 14, 10]} /><meshBasicMaterial color={color} wireframe transparent opacity={0.7} blending={THREE.AdditiveBlending} /></mesh>
        <mesh position={[-0.09, 0.04, 0.24]}><sphereGeometry args={[0.035, 10, 10]} />{P()}</mesh>
        <mesh position={[0.09, 0.04, 0.24]}><sphereGeometry args={[0.035, 10, 10]} />{P()}</mesh>
      </group>);
      break;
    case "education": // mortarboard + tassel
      inner = (<group rotation={[0.5, 0, 0]}>
        <mesh><boxGeometry args={[0.5, 0.05, 0.5]} />{S(2.2)}</mesh>
        <mesh position={[0, -0.12, 0]}><cylinderGeometry args={[0.12, 0.16, 0.18, 16]} />{S(1.8)}</mesh>
        <mesh position={[0.22, -0.02, 0]}><boxGeometry args={[0.012, 0.28, 0.012]} />{P()}</mesh>
        <mesh position={[0.22, -0.18, 0]}><sphereGeometry args={[0.035, 8, 8]} />{P()}</mesh>
      </group>);
      break;
    case "novagame": // controller
      inner = (<group rotation={[0.2, 0, 0]}>
        <mesh><boxGeometry args={[0.5, 0.26, 0.12]} /><group>{S(2.0)}</group></mesh>
        <mesh position={[-0.13, 0.01, 0.08]}><boxGeometry args={[0.04, 0.14, 0.03]} />{P()}</mesh>
        <mesh position={[-0.13, 0.01, 0.08]}><boxGeometry args={[0.14, 0.04, 0.03]} />{P()}</mesh>
        <mesh position={[0.11, 0.04, 0.08]}><sphereGeometry args={[0.03, 10, 10]} />{P()}</mesh>
        <mesh position={[0.17, -0.03, 0.08]}><sphereGeometry args={[0.03, 10, 10]} />{P()}</mesh>
      </group>);
      break;
    case "alphaflow": { // rising bars + arrow + $
      const bars: [number, number][] = [[-0.18, 0.14], [0, 0.22], [0.18, 0.32]];
      inner = (<group>
        {bars.map(([x, h], i) => <mesh key={i} position={[x, -0.18 + h / 2, 0]}><boxGeometry args={[0.1, h, 0.1]} />{i === 2 ? P() : S()}</mesh>)}
        <mesh position={[0.02, 0.2, 0.06]} rotation={[0, 0, -Math.PI / 4.5]}><boxGeometry args={[0.5, 0.03, 0.03]} />{P()}</mesh>
      </group>);
      break;
    }
    case "marketing": // 4-point star
      inner = (<group>
        <mesh><boxGeometry args={[0.55, 0.06, 0.06]} />{P()}</mesh>
        <mesh><boxGeometry args={[0.06, 0.55, 0.06]} />{P()}</mesh>
        <mesh rotation={[0, 0, Math.PI / 4]}><boxGeometry args={[0.32, 0.04, 0.04]} />{P(0.6)}</mesh>
        <mesh rotation={[0, 0, -Math.PI / 4]}><boxGeometry args={[0.32, 0.04, 0.04]} />{P(0.6)}</mesh>
      </group>);
      break;
    case "leadgen": // target
      inner = (<group>
        <mesh><torusGeometry args={[0.26, 0.022, 10, 40]} />{P()}</mesh>
        <mesh><torusGeometry args={[0.14, 0.018, 10, 32]} />{P(0.8)}</mesh>
        <mesh><sphereGeometry args={[0.04, 10, 10]} />{P()}</mesh>
        <mesh><boxGeometry args={[0.62, 0.018, 0.018]} />{P(0.6)}</mesh>
        <mesh><boxGeometry args={[0.018, 0.62, 0.018]} />{P(0.6)}</mesh>
      </group>);
      break;
    case "products": // diamond
      inner = <mesh rotation={[0, 0, 0]}><octahedronGeometry args={[0.3, 0]} />{S(2.2)}</mesh>;
      break;
    case "newsletter": // envelope
      inner = (<group>
        <mesh><boxGeometry args={[0.5, 0.34, 0.06]} />{S(2.0)}</mesh>
        <mesh position={[0, 0.04, 0.05]} rotation={[0, 0, Math.PI]}><coneGeometry args={[0.26, 0.2, 3]} />{P(0.7)}</mesh>
      </group>);
      break;
    default: // social — connected nodes
      inner = (<group>
        <mesh position={[-0.2, 0.12, 0]}><sphereGeometry args={[0.06, 12, 12]} />{P()}</mesh>
        <mesh position={[0.22, 0.06, 0]}><sphereGeometry args={[0.06, 12, 12]} />{P()}</mesh>
        <mesh position={[0, -0.2, 0]}><sphereGeometry args={[0.06, 12, 12]} />{P()}</mesh>
        <mesh position={[-0.1, 0.06, 0]} rotation={[0, 0, 0.5]}><boxGeometry args={[0.34, 0.016, 0.016]} />{P(0.6)}</mesh>
        <mesh position={[0.11, -0.07, 0]} rotation={[0, 0, -0.7]}><boxGeometry args={[0.34, 0.016, 0.016]} />{P(0.6)}</mesh>
      </group>);
  }
  return <group ref={g}>{inner}</group>;
}

function Pedestal({ color }: { color: string }) {
  const r = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => { if (r.current) r.current.rotation.z = clock.getElapsedTime() * 0.4; });
  return (
    <group position={[0, -1.7, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <mesh><cylinderGeometry args={[0.95, 1.05, 0.12, 48]} /><meshStandardMaterial color="#0a0e16" metalness={0.85} roughness={0.4} /></mesh>
      <mesh position={[0, 0.07, 0]}><torusGeometry args={[0.8, 0.02, 10, 64]} /><meshBasicMaterial color={color} transparent opacity={0.85} blending={THREE.AdditiveBlending} /></mesh>
      <mesh ref={r} position={[0, 0.07, 0]}><torusGeometry args={[0.6, 0.012, 8, 48, Math.PI * 1.3]} /><meshBasicMaterial color={color} transparent opacity={0.7} blending={THREE.AdditiveBlending} /></mesh>
      <mesh position={[0, 0.07, 0]}><circleGeometry args={[0.78, 48]} /><meshBasicMaterial color={color} transparent opacity={0.12} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
    </group>
  );
}

function FactoryCard({ factory, x, onOpen }: { factory: Factory; x: number; onOpen?: (id: string) => void }) {
  const grp = useRef<THREE.Group>(null);
  const [hover, setHover] = useState(false);
  const accent = ACCENT[factory.id] ?? "#29d4ff";
  const statusCol = STATUS_COLOR[factory.status] ?? "#7c8b9c";
  const phase = useMemo(() => Math.random() * 6, []);
  useFrame(({ clock }) => {
    if (!grp.current) return;
    const t = clock.getElapsedTime();
    grp.current.position.y = Math.sin(t * 0.8 + phase) * 0.06 + (hover ? 0.2 : 0);
    const s = grp.current.scale.x + ((hover ? 1.05 : 1.0) - grp.current.scale.x) * 0.15;
    grp.current.scale.set(s, s, s);
  });
  return (
    <group position={[x, 0, 0]}>
      <group ref={grp}
        onPointerOver={(e) => { e.stopPropagation(); setHover(true); document.body.style.cursor = "pointer"; }}
        onPointerOut={() => { setHover(false); document.body.style.cursor = "auto"; }}
        onClick={(e) => { e.stopPropagation(); onOpen?.(factory.id); }}
      >
        {/* outer frame */}
        <RoundedBox args={[1.62, 2.9, 0.34]} radius={0.12} smoothness={5} position={[0, 0, -0.06]}>
          <meshStandardMaterial color="#070b10" metalness={0.85} roughness={0.4} />
          <Edges threshold={15} color={accent} />
        </RoundedBox>
        {/* black glass body */}
        <RoundedBox args={[1.5, 2.78, 0.3]} radius={0.1} smoothness={5}>
          <meshStandardMaterial color="#000000" emissive="#000000" emissiveIntensity={0} metalness={0.25} roughness={0.5} transparent opacity={hover ? 0.55 : 0.46} depthWrite={false} />
          <Edges threshold={15} color={accent} />
        </RoundedBox>
        {/* inner screen panel */}
        <RoundedBox args={[1.32, 2.58, 0.06]} radius={0.08} smoothness={4} position={[0, 0, 0.14]}>
          <meshStandardMaterial color="#03060c" metalness={0.3} roughness={0.6} transparent opacity={0.6} depthWrite={false} />
        </RoundedBox>

        {/* glowing logo */}
        <group position={[0, 0.86, 0.3]}><FactoryIcon id={factory.id} color={accent} /></group>
        {/* light that energizes the card */}
        <pointLight position={[0, 0.86, 0.6]} color={accent} intensity={1.4} distance={2.2} decay={2} />

        {/* title */}
        <Text position={[0, 0.28, 0.22]} fontSize={0.135} maxWidth={1.3} lineHeight={1.05} textAlign="center" anchorX="center" anchorY="middle" color="#ffffff" outlineWidth={0.004} outlineColor="#000000">
          {factory.name.toUpperCase()}
        </Text>
        {/* summary */}
        <Text position={[0, -0.18, 0.22]} fontSize={0.072} maxWidth={1.28} lineHeight={1.3} textAlign="center" anchorX="center" anchorY="middle" color="#a8bcd2">
          {factory.summary}
        </Text>
        {/* status pill */}
        <mesh position={[-0.42, -0.74, 0.22]}><circleGeometry args={[0.035, 16]} /><meshBasicMaterial color={statusCol} transparent blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        <Text position={[-0.36, -0.74, 0.22]} fontSize={0.075} letterSpacing={0.1} anchorX="left" anchorY="middle" color={statusCol}>
          {factory.status.toUpperCase()}
        </Text>

        {/* OPEN FACTORY button */}
        <group position={[0, -1.12, 0.2]}>
          <RoundedBox args={[1.2, 0.34, 0.08]} radius={0.08} smoothness={4}>
            <meshStandardMaterial color="#04121c" emissive={new THREE.Color(accent)} emissiveIntensity={hover ? 0.6 : 0.32} metalness={0.3} roughness={0.4} transparent opacity={0.9} />
            <Edges threshold={15} color={accent} />
          </RoundedBox>
          <Text position={[-0.06, 0, 0.07]} fontSize={0.1} letterSpacing={0.14} anchorX="center" anchorY="middle" color="#eafdff">
            OPEN FACTORY
          </Text>
          <mesh position={[0.46, 0, 0.07]} rotation={[0, 0, -Math.PI / 2]}><coneGeometry args={[0.05, 0.09, 3]} /><meshBasicMaterial color={accent} /></mesh>
        </group>
      </group>
      <Pedestal color={accent} />
    </group>
  );
}

function Scene({ factories, onOpen }: { factories: Factory[]; onOpen?: (id: string) => void }) {
  const perRow = Math.min(5, factories.length);
  const rows = Math.ceil(factories.length / perRow);
  const spacing = 2.5;
  const rowGap = 4.4;
  return (
    <>
      <hemisphereLight args={["#bcd6ff", "#0a0f18", 0.8]} />
      <ambientLight intensity={0.4} />
      <pointLight position={[0, 5, 7]} intensity={1.6} color="#cfe2ff" />
      <pointLight position={[-9, 2, 5]} intensity={1.0} color="#7fb6ff" />
      <pointLight position={[9, 2, 5]} intensity={1.0} color="#7fb6ff" />
      <fogExp2 attach="fog" args={["#03060e", 0.02]} />

      {factories.map((f, i) => {
        const row = Math.floor(i / perRow);
        const col = i % perRow;
        const countInRow = Math.min(perRow, factories.length - row * perRow);
        const x = (col - (countInRow - 1) / 2) * spacing;
        const y = ((rows - 1) / 2 - row) * rowGap;
        return <group key={f.id} position={[0, y, 0]}><FactoryCard factory={f} x={x} onOpen={onOpen} /></group>;
      })}

      {/* reflective floor under the bottom row */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -((rows - 1) / 2) * rowGap - 1.95, 0]}>
        <planeGeometry args={[80, 30]} />
        <MeshReflectorMaterial resolution={512} mirror={0.4} mixBlur={1.8} mixStrength={1.1} blur={[400, 120]} roughness={0.85} metalness={0.5} color="#050a12" depthScale={1.0} minDepthThreshold={0.4} maxDepthThreshold={1.2} />
      </mesh>

      <EffectComposer multisampling={0} frameBufferType={THREE.HalfFloatType}>
        <SMAA />
        <Bloom intensity={1.25} luminanceThreshold={0.4} luminanceSmoothing={0.9} radius={0.7} mipmapBlur />
        <Vignette offset={0.3} darkness={0.7} />
      </EffectComposer>
    </>
  );
}

export default function Factories3D({ factories, onOpen }: { factories: Factory[]; onOpen?: (id: string) => void }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="factories3d-stage" />;
  return (
    <div className="factories3d-stage">
      <Canvas
        camera={{ position: [0, -0.2, 13], fov: 40 }}
        dpr={[1, 1.6]}
        gl={{ antialias: false, alpha: true, powerPreference: "high-performance" }}
        onCreated={({ gl, camera }) => { gl.toneMapping = THREE.ACESFilmicToneMapping; gl.toneMappingExposure = 1.5; camera.lookAt(0, -0.2, 0); }}
        style={{ background: "transparent" }}
      >
        <Scene factories={factories} onOpen={onOpen} />
      </Canvas>
    </div>
  );
}
