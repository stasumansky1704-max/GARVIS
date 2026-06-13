import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

type RingDef = {
  radius: number;
  tube: number;
  tilt: [number, number, number];
  speed: number;
  color: string;
  opacity: number;
};

const RINGS: RingDef[] = [
  { radius: 2.6, tube: 0.012, tilt: [1.35, 0.2, 0], speed: 0.22, color: "#38bdf8", opacity: 0.7 },
  { radius: 3.2, tube: 0.01, tilt: [1.1, -0.4, 0.3], speed: -0.16, color: "#22d3ee", opacity: 0.55 },
  { radius: 3.9, tube: 0.008, tilt: [1.5, 0.5, -0.2], speed: 0.12, color: "#7dd3fc", opacity: 0.45 },
  { radius: 2.9, tube: 0.02, tilt: [0.2, 0.0, 0.0], speed: 0.3, color: "#38bdf8", opacity: 0.35 },
];

function Ring({ def, index }: { def: RingDef; index: number }) {
  const ref = useRef<THREE.Mesh>(null!);
  useFrame((state) => {
    const t = state.clock.elapsedTime;
    ref.current.rotation.z += def.speed * 0.01;
    // gentle wobble, phase-offset per ring so they don't lockstep
    ref.current.rotation.x = def.tilt[0] + Math.sin(t * 0.4 + index) * 0.05;
    ref.current.rotation.y = def.tilt[1] + Math.cos(t * 0.3 + index) * 0.05;
  });
  return (
    <mesh ref={ref} rotation={def.tilt}>
      <torusGeometry args={[def.radius, def.tube, 16, 160]} />
      <meshBasicMaterial
        color={def.color}
        transparent
        opacity={def.opacity}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        toneMapped={false}
      />
    </mesh>
  );
}

export default function OrbitRings() {
  return (
    <group>
      {RINGS.map((def, i) => (
        <Ring key={i} def={def} index={i} />
      ))}
    </group>
  );
}
