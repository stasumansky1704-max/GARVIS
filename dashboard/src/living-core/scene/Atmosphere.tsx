import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

/**
 * Volumetric atmosphere for the chamber: slow-drifting dust motes that catch the
 * cyan light, plus two soft god-ray light cones descending from the ceiling.
 * Sells real depth and "air" in the room (motion-designer + threejs-webgl-
 * director). Separate from the core's own particle field.
 */

function Dust({ count = 1400 }: { count?: number }) {
  const points = useRef<THREE.Points>(null!);

  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (Math.random() - 0.5) * 26; // x across the room
      arr[i * 3 + 1] = (Math.random() - 0.5) * 16 + 1; // y
      arr[i * 3 + 2] = -Math.random() * 44 + 4; // z into corridor
    }
    return arr;
  }, [count]);

  const texture = useMemo(() => {
    const c = document.createElement("canvas");
    c.width = c.height = 32;
    const ctx = c.getContext("2d")!;
    const g = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
    g.addColorStop(0, "rgba(200,235,255,0.9)");
    g.addColorStop(1, "rgba(120,190,240,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 32, 32);
    return new THREE.CanvasTexture(c);
  }, []);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    points.current.position.y = Math.sin(t * 0.08) * 0.6;
    points.current.rotation.y = t * 0.01;
    (points.current.material as THREE.PointsMaterial).opacity =
      0.35 + Math.sin(t * 0.6) * 0.08;
  });

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" count={count} array={positions} itemSize={3} />
      </bufferGeometry>
      <pointsMaterial
        size={0.07}
        map={texture}
        color="#9fd4ff"
        transparent
        opacity={0.4}
        sizeAttenuation
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        toneMapped={false}
      />
    </points>
  );
}

export default function Atmosphere() {
  // god-ray light cones removed — only drifting dust remains
  return (
    <group>
      <Dust />
    </group>
  );
}
