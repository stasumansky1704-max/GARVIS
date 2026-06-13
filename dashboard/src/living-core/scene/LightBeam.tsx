import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

/**
 * A contained vertical energy column rising from the pedestal below the core,
 * plus a bright base disc on the floor. Additive + flickering, but deliberately
 * subtle so it frames the core instead of flooding the scene (motion-designer).
 */
export default function LightBeam() {
  const beam = useRef<THREE.Mesh>(null!);
  const inner = useRef<THREE.Mesh>(null!);
  const base = useRef<THREE.Mesh>(null!);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const flicker = 0.14 + Math.sin(t * 3.1) * 0.03 + Math.sin(t * 11.0) * 0.015;
    (beam.current.material as THREE.MeshBasicMaterial).opacity = flicker;
    (inner.current.material as THREE.MeshBasicMaterial).opacity =
      0.16 + Math.sin(t * 2.4) * 0.04;
    const bs = 1 + Math.sin(t * 2.2) * 0.06;
    base.current.scale.set(bs, bs, bs);
    (base.current.material as THREE.MeshBasicMaterial).opacity =
      0.45 + Math.sin(t * 2.6) * 0.08;
  });

  return (
    <group>
      {/* soft outer column — short, rising from the pedestal to the core */}
      <mesh ref={beam} position={[0, -3.1, 0]}>
        <cylinderGeometry args={[0.42, 0.95, 5.2, 32, 1, true]} />
        <meshBasicMaterial
          color="#38bdf8"
          transparent
          opacity={0.14}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>

      {/* thin inner glow line */}
      <mesh ref={inner} position={[0, -3.1, 0]}>
        <cylinderGeometry args={[0.07, 0.18, 5.2, 16, 1, true]} />
        <meshBasicMaterial
          color="#bfeaff"
          transparent
          opacity={0.16}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>

      {/* bright base disc on the pedestal/floor */}
      <mesh ref={base} position={[0, -5.7, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[2.0, 64]} />
        <meshBasicMaterial
          color="#38bdf8"
          transparent
          opacity={0.45}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>
    </group>
  );
}
