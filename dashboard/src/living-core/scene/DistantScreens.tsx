import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

/**
 * Distant holographic panels / screens mounted along the chamber walls, deep in
 * the corridor. Soft emissive rectangles that flicker faintly — they read as a
 * working command center without being readable UI (so this stays an
 * environment, not a dashboard — anti-dashboard-gatekeeper).
 */

type Panel = {
  pos: [number, number, number];
  rotY: number;
  w: number;
  h: number;
  hue: string;
  phase: number;
};

const PANELS: Panel[] = [
  { pos: [-6.6, 2.6, -12], rotY: 0.5, w: 2.4, h: 1.5, hue: "#2aa8d8", phase: 0 },
  { pos: [-7.0, 0.4, -18], rotY: 0.5, w: 2.0, h: 1.2, hue: "#1f8fc4", phase: 1.4 },
  { pos: [-6.4, 3.4, -23], rotY: 0.5, w: 1.6, h: 1.0, hue: "#37c4f0", phase: 2.7 },
  { pos: [6.6, 2.2, -12], rotY: -0.5, w: 2.4, h: 1.5, hue: "#2aa8d8", phase: 0.8 },
  { pos: [7.0, 0.0, -18], rotY: -0.5, w: 2.0, h: 1.3, hue: "#1f8fc4", phase: 2.0 },
  { pos: [6.4, 3.2, -24], rotY: -0.5, w: 1.7, h: 1.05, hue: "#37c4f0", phase: 3.3 },
];

function Screen({ panel }: { panel: Panel }) {
  const glow = useRef<THREE.Mesh>(null!);
  const bars = useRef<THREE.Group>(null!);
  useFrame((state) => {
    const t = state.clock.elapsedTime + panel.phase;
    (glow.current.material as THREE.MeshBasicMaterial).opacity =
      0.32 + Math.sin(t * 1.8) * 0.1 + Math.sin(t * 7) * 0.03;
    if (bars.current) {
      bars.current.children.forEach((c, i) => {
        const m = (c as THREE.Mesh).material as THREE.MeshBasicMaterial;
        m.opacity = 0.4 + Math.sin(t * 2 + i) * 0.25;
      });
    }
  });
  return (
    <group position={panel.pos} rotation={[0, panel.rotY, 0]}>
      {/* bezel */}
      <mesh>
        <planeGeometry args={[panel.w + 0.12, panel.h + 0.12]} />
        <meshStandardMaterial color="#0a141e" roughness={0.4} metalness={0.85} />
      </mesh>
      {/* glowing screen face */}
      <mesh ref={glow} position={[0, 0, 0.02]}>
        <planeGeometry args={[panel.w, panel.h]} />
        <meshBasicMaterial
          color={panel.hue}
          transparent
          opacity={0.32}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>
      {/* faux data bars */}
      <group ref={bars} position={[0, 0, 0.04]}>
        {Array.from({ length: 4 }).map((_, i) => (
          <mesh key={i} position={[-panel.w / 4, panel.h / 2 - 0.25 - i * 0.28, 0]}>
            <planeGeometry args={[panel.w * (0.3 + (i % 3) * 0.18), 0.07]} />
            <meshBasicMaterial
              color="#bfeaff"
              transparent
              opacity={0.5}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
              toneMapped={false}
            />
          </mesh>
        ))}
      </group>
    </group>
  );
}

export default function DistantScreens() {
  return (
    <group>
      {PANELS.map((p, i) => (
        <Screen key={i} panel={p} />
      ))}
    </group>
  );
}
