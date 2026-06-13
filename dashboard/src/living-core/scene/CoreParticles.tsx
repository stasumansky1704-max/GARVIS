import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

/**
 * Thousands of additive points drifting/orbiting the core — a living dust of
 * energy. BufferGeometry, not DOM dots (threejs-webgl-director skill).
 */
export default function CoreParticles({ count = 3500 }: { count?: number }) {
  const points = useRef<THREE.Points>(null!);

  const { positions, sizes } = useMemo(() => {
    const positions = new Float32Array(count * 3);
    const sizes = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      // mix a spherical shell with a flat orbiting disc
      const disc = Math.random() < 0.45;
      let r: number, theta: number, phi: number;
      if (disc) {
        r = 2.2 + Math.random() * 3.2;
        theta = Math.random() * Math.PI * 2;
        const y = (Math.random() - 0.5) * 0.5;
        positions[i * 3] = Math.cos(theta) * r;
        positions[i * 3 + 1] = y;
        positions[i * 3 + 2] = Math.sin(theta) * r;
      } else {
        r = 2.0 + Math.random() * 3.5;
        theta = Math.random() * Math.PI * 2;
        phi = Math.acos(2 * Math.random() - 1);
        positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        positions[i * 3 + 1] = r * Math.cos(phi) * 0.7;
        positions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
      }
      sizes[i] = Math.random() * 0.04 + 0.01;
    }
    return { positions, sizes };
  }, [count]);

  const texture = useMemo(() => {
    const c = document.createElement("canvas");
    c.width = c.height = 64;
    const ctx = c.getContext("2d")!;
    const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, "rgba(234,246,255,1)");
    g.addColorStop(0.3, "rgba(125,211,252,0.7)");
    g.addColorStop(1, "rgba(56,189,248,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 64, 64);
    const tex = new THREE.CanvasTexture(c);
    return tex;
  }, []);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    points.current.rotation.y = t * 0.04;
    points.current.rotation.x = Math.sin(t * 0.1) * 0.08;
    (points.current.material as THREE.PointsMaterial).opacity =
      0.75 + Math.sin(t * 1.5) * 0.12;
  });

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={positions}
          itemSize={3}
        />
        <bufferAttribute
          attach="attributes-size"
          count={count}
          array={sizes}
          itemSize={1}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.05}
        map={texture}
        color="#9fe0ff"
        transparent
        opacity={0.8}
        sizeAttenuation
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        toneMapped={false}
      />
    </points>
  );
}
