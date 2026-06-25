import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { MeshReflectorMaterial } from "@react-three/drei";
import * as THREE from "three";

/**
 * Reflective chamber floor + a glowing tech grid and radial spokes laid on top.
 * The grid gives the floor scale and panel lines (reference look); the reflective
 * base still mirrors the core, portal, and walls. Frozen core untouched.
 */

const FLOOR_Y = -4.4;

function Grid() {
  // build a grid of line segments as a single LineSegments geometry
  const geo = useMemo(() => {
    const pts: number[] = [];
    const half = 30;
    const stepGrid = 2.2;
    for (let x = -half; x <= half; x += stepGrid) {
      pts.push(x, 0.01, -half, x, 0.01, half);
    }
    for (let z = -half; z <= half; z += stepGrid) {
      pts.push(-half, 0.01, z, half, 0.01, z);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    return g;
  }, []);

  const mat = useRef<THREE.LineBasicMaterial>(null!);
  useFrame((state) => {
    mat.current.opacity = 0.1 + Math.sin(state.clock.elapsedTime * 0.6) * 0.03;
  });

  return (
    <lineSegments geometry={geo} position={[0, FLOOR_Y + 0.02, 0]}>
      <lineBasicMaterial ref={mat} color="#1c5a82" transparent opacity={0.1} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
    </lineSegments>
  );
}

export default function Floor() {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, FLOOR_Y, 0]}>
        <planeGeometry args={[120, 120]} />
        <MeshReflectorMaterial
          blur={[380, 120]}
          resolution={1024}
          mixBlur={1}
          mixStrength={70}
          roughness={0.62}
          depthScale={1.2}
          minDepthThreshold={0.3}
          maxDepthThreshold={1.4}
          color="#04090f"
          metalness={0.9}
          mirror={0.78}
        />
      </mesh>
      {/* radial spokes removed — no beams/lines spreading from the core */}
      <Grid />
    </group>
  );
}
