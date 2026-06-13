import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

/**
 * The dense tech-ring portal that frames the core (the reference's big concentric
 * "stargate"). Multiple coaxial rings of varied thickness, two of them ticked
 * like a HUD dial, set behind the core and facing the camera. Counter-rotating
 * layers + a soft fill disc. Room element — the frozen core is not modified.
 */

function TickRing({
  radius,
  count,
  color,
  z,
  spin,
  long = false,
}: {
  radius: number;
  count: number;
  color: string;
  z: number;
  spin: number;
  long?: boolean;
}) {
  const ref = useRef<THREE.Group>(null!);
  useFrame((state) => {
    ref.current.rotation.z = state.clock.elapsedTime * spin;
  });
  const ticks = useMemo(() => {
    const arr: { a: number }[] = [];
    for (let i = 0; i < count; i++) arr.push({ a: (i / count) * Math.PI * 2 });
    return arr;
  }, [count]);
  return (
    <group ref={ref} position={[0, 0, z]}>
      {ticks.map((t, i) => {
        const len = long && i % 4 === 0 ? 0.42 : 0.2;
        return (
          <mesh key={i} position={[Math.cos(t.a) * radius, Math.sin(t.a) * radius, 0]} rotation={[0, 0, t.a]}>
            <planeGeometry args={[len, 0.05]} />
            <meshBasicMaterial color={color} transparent opacity={0.85} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} toneMapped={false} />
          </mesh>
        );
      })}
    </group>
  );
}

export default function Portal() {
  const breathe = useRef<THREE.Group>(null!);
  const disc = useRef<THREE.Mesh>(null!);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const p = 1 + Math.sin(t * 1.1) * 0.015;
    breathe.current.scale.set(p, p, p);
    (disc.current.material as THREE.MeshBasicMaterial).opacity = 0.16 + Math.sin(t * 0.9) * 0.05;
  });

  return (
    <group position={[0, 0.35, -3.0]}>
      {/* soft fill disc behind the core */}
      <mesh ref={disc} position={[0, 0, -0.6]}>
        <circleGeometry args={[4.4, 64]} />
        <meshBasicMaterial color="#1c84c0" transparent opacity={0.18} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
      </mesh>

      <group ref={breathe}>
        {/* solid bright rings — bolder primary, but kept behind the core in glow */}
        <mesh>
          <torusGeometry args={[4.0, 0.2, 24, 180]} />
          <meshBasicMaterial color="#7fd9ff" transparent opacity={0.95} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
        </mesh>
        <mesh>
          <torusGeometry args={[3.55, 0.08, 16, 160]} />
          <meshBasicMaterial color="#bfeaff" transparent opacity={0.88} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
        </mesh>
        <mesh>
          <torusGeometry args={[4.78, 0.07, 14, 200]} />
          <meshBasicMaterial color="#38bdf8" transparent opacity={0.65} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
        </mesh>
        <mesh>
          <torusGeometry args={[5.15, 0.035, 10, 200]} />
          <meshBasicMaterial color="#2f9fd0" transparent opacity={0.45} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
        </mesh>
      </group>

      {/* counter-rotating ticked HUD dials */}
      <TickRing radius={4.35} count={72} color="#9fe4ff" z={0.05} spin={0.05} long />
      <TickRing radius={4.95} count={48} color="#4fb8e6" z={0.05} spin={-0.035} />
      <TickRing radius={3.3} count={36} color="#bfeaff" z={0.05} spin={0.07} />
    </group>
  );
}
