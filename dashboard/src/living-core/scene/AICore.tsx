import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { MeshDistortMaterial } from "@react-three/drei";
import * as THREE from "three";

/**
 * The living holographic AI core: a distorting emissive heart, an additive
 * fresnel-style halo shell, and a bright camera-facing energy ring.
 * Everything breathes and pulses (see motion-designer skill).
 */
export default function AICore() {
  const group = useRef<THREE.Group>(null!);
  const heart = useRef<THREE.Mesh>(null!);
  const halo = useRef<THREE.Mesh>(null!);
  const ring = useRef<THREE.Mesh>(null!);
  const mat = useRef<any>(null!);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    // slow breathe
    const breathe = 1 + Math.sin(t * 0.9) * 0.04;
    heart.current.scale.setScalar(breathe);
    // emissive pulse (layered timescales for organic feel)
    if (mat.current) {
      mat.current.emissiveIntensity =
        2.1 + Math.sin(t * 1.7) * 0.5 + Math.sin(t * 5.3) * 0.12;
    }
    // halo shimmer
    const h = 1.18 + Math.sin(t * 1.3 + 1.2) * 0.05;
    halo.current.scale.setScalar(h);
    (halo.current.material as THREE.MeshBasicMaterial).opacity =
      0.22 + Math.sin(t * 2.1) * 0.06;
    // ring face the camera, gentle spin + pulse
    ring.current.lookAt(state.camera.position);
    ring.current.rotation.z += 0.0025;
    const rs = 1 + Math.sin(t * 1.1 + 0.5) * 0.03;
    ring.current.scale.set(rs, rs, rs);
    // whole group slow drift
    group.current.rotation.y = Math.sin(t * 0.15) * 0.12;
  });

  return (
    <group ref={group}>
      {/* distorting living heart */}
      <mesh ref={heart}>
        <icosahedronGeometry args={[1, 12]} />
        <MeshDistortMaterial
          ref={mat}
          color="#0a3a52"
          emissive="#27c6f0"
          emissiveIntensity={2.2}
          roughness={0.25}
          metalness={0.1}
          distort={0.35}
          speed={1.6}
        />
      </mesh>

      {/* inner white-hot point */}
      <mesh scale={0.45}>
        <sphereGeometry args={[1, 32, 32]} />
        <meshBasicMaterial color="#eaf6ff" toneMapped={false} />
      </mesh>

      {/* additive halo shell */}
      <mesh ref={halo}>
        <sphereGeometry args={[1, 48, 48]} />
        <meshBasicMaterial
          color="#38bdf8"
          transparent
          opacity={0.25}
          side={THREE.BackSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>

      {/* bright energy ring facing camera */}
      <mesh ref={ring}>
        <ringGeometry args={[1.55, 1.72, 96]} />
        <meshBasicMaterial
          color="#7dd3fc"
          transparent
          opacity={0.9}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>

      {/* thin outer ring */}
      <mesh>
        <ringGeometry args={[1.9, 1.94, 128]} />
        <meshBasicMaterial
          color="#22d3ee"
          transparent
          opacity={0.55}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>
    </group>
  );
}
