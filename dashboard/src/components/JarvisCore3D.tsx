import { useRef, useState, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Sparkles, Stars, MeshDistortMaterial } from "@react-three/drei";
import { Bloom, Vignette, EffectComposer } from "@react-three/postprocessing";
import * as THREE from "three";

interface CoreProps {
  audioIntensity?: number;
}

function CoreSphere({ ai = 0 }: { ai?: number }) {
  const ref = useRef<THREE.Mesh>(null);

  useFrame(({ clock }) => {
    if (!ref.current) return;
    const beat = 1 + Math.sin(clock.getElapsedTime() * 3) * 0.06 * (1 + ai);
    ref.current.scale.setScalar(beat);
    ref.current.rotation.y += 0.005;
    ref.current.rotation.x += 0.003;
  });

  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.9, 64, 64]} />
      <MeshDistortMaterial
        color="#00e5ff"
        emissive="#00e5ff"
        emissiveIntensity={2 + ai * 3}
        roughness={0.2}
        metalness={0.8}
        distort={0.15 + ai * 0.1}
        speed={2 + ai * 2}
      />
    </mesh>
  );
}

function OrbitalRing({
  radius,
  speed,
  ai = 0,
  axis = "z",
}: {
  radius: number;
  speed: number;
  ai?: number;
  axis?: "x" | "y" | "z";
}) {
  const ref = useRef<THREE.Mesh>(null);

  useFrame(({ clock }) => {
    if (!ref.current) return;
    const t = clock.getElapsedTime();
    const s = speed * (1 + ai * 1.5);

    if (axis === "x") ref.current.rotation.x = t * s;
    else if (axis === "y") ref.current.rotation.y = t * s;
    else ref.current.rotation.z = t * s;
  });

  return (
    <mesh ref={ref} rotation={[Math.PI / 2.2, 0, 0]}>
      <torusGeometry args={[radius, 0.012, 16, 100]} />
      <meshStandardMaterial
        color="#00e5ff"
        emissive="#00e5ff"
        emissiveIntensity={1.2 + ai * 2}
        metalness={0.9}
        roughness={0.15}
        transparent
        opacity={0.6 + ai * 0.3}
      />
    </mesh>
  );
}

function SegmentedRing({ ai = 0 }: { ai?: number }) {
  const ref = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    if (!ref.current) return;
    ref.current.rotation.z = clock.getElapsedTime() * 0.15 * (1 + ai * 1.5);
  });

  const segments = Array.from({ length: 12 });

  return (
    <group ref={ref}>
      {segments.map((_, i) => {
        const angle = (i / 12) * Math.PI * 2;
        const radius = 2.8;
        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius;

        return (
          <mesh
            key={i}
            position={[x, y, 0]}
            rotation={[0, 0, angle]}
          >
            <boxGeometry args={[0.48, 0.045, 0.045]} />
            <meshStandardMaterial
              color="#00e5ff"
              emissive="#00e5ff"
              emissiveIntensity={1.6 + ai * 2.4}
              metalness={0.95}
              roughness={0.1}
              transparent
              opacity={0.7 + ai * 0.25}
            />
          </mesh>
        );
      })}
    </group>
  );
}

function RadialBeams({ ai = 0 }: { ai?: number }) {
  const ref = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    if (!ref.current) return;
    ref.current.rotation.z = -clock.getElapsedTime() * 0.25 * (1 + ai * 1.2);
  });

  return (
    <group ref={ref}>
      {Array.from({ length: 6 }).map((_, i) => {
        const angle = (i / 6) * Math.PI * 2;
        const innerR = 1.1;
        const outerR = 2.6;

        const x1 = Math.cos(angle) * innerR;
        const y1 = Math.sin(angle) * innerR;
        const x2 = Math.cos(angle) * outerR;
        const y2 = Math.sin(angle) * outerR;

        const length = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
        const midX = (x1 + x2) / 2;
        const midY = (y1 + y2) / 2;
        const rotZ = Math.atan2(y2 - y1, x2 - x1);

        return (
          <mesh key={i} position={[midX, midY, 0]} rotation={[0, 0, rotZ]}>
            <boxGeometry args={[length, 0.025, 0.025]} />
            <meshStandardMaterial
              color="#00e5ff"
              emissive="#00e5ff"
              emissiveIntensity={1.8 + ai * 2.5}
              metalness={0.9}
              roughness={0.1}
              transparent
              opacity={0.5 + ai * 0.3}
            />
          </mesh>
        );
      })}
    </group>
  );
}

function ParticleRing({ ai = 0 }: { ai?: number }) {
  const pointsRef = useRef<THREE.Points>(null);
  const count = 300;

  const positions = new Float32Array(count * 3);
  const speeds = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2;
    const r = 1.8 + Math.random() * 1.2;
    positions[i * 3] = Math.cos(angle) * r;
    positions[i * 3 + 1] = Math.sin(angle) * r;
    positions[i * 3 + 2] = (Math.random() - 0.5) * 0.6;
    speeds[i] = 0.1 + Math.random() * 0.4;
  }

  useFrame(({ clock }) => {
    if (!pointsRef.current) return;

    const t = clock.getElapsedTime();
    const geo = pointsRef.current.geometry;
    const posAttr = geo.attributes.position;
    const arr = posAttr.array as Float32Array;

    for (let i = 0; i < count; i++) {
      const baseAngle = Math.atan2(arr[i * 3 + 1], arr[i * 3]);
      const r = Math.sqrt(arr[i * 3] ** 2 + arr[i * 3 + 1] ** 2);
      const angle = baseAngle + t * speeds[i] * 0.3 * (1 + ai);

      arr[i * 3] = Math.cos(angle) * r;
      arr[i * 3 + 1] = Math.sin(angle) * r;
    }

    posAttr.needsUpdate = true;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        color="#00e5ff"
        size={0.04}
        transparent
        opacity={0.6 + ai * 0.3}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}

function GlowLayers({ ai = 0 }: { ai?: number }) {
  const ref = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    if (!ref.current) return;
    const pulse = 1 + Math.sin(clock.getElapsedTime() * 2) * 0.04 * (1 + ai);
    ref.current.scale.setScalar(pulse);
  });

  return (
    <group ref={ref}>
      {[3.2, 3.6, 4.0, 4.5].map((r, i) => {
        const opacity = [0.25, 0.12, 0.06, 0.03][i] * (1 + ai * 0.5);
        const color = i === 0 ? "#ffffff" : "#00e5ff";

        return (
          <mesh key={i} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[r, 0.25, 32, 64]} />
            <meshBasicMaterial
              color={color}
              transparent
              opacity={opacity}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
              side={THREE.DoubleSide}
            />
          </mesh>
        );
      })}
    </group>
  );
}

function SparkleField({ ai = 0 }: { ai?: number }) {
  return (
    <>
      <Sparkles
        count={80}
        scale={12}
        size={3}
        speed={0.4}
        opacity={0.15 + ai * 0.15}
        color="#00e5ff"
      />
      <Stars
        radius={20}
        depth={30}
        count={1200}
        factor={2}
        saturation={0}
        fade
        speed={0.8}
      />
    </>
  );
}

function CoreScene({ audioIntensity = 0 }: CoreProps) {
  return (
    <>
      <ambientLight intensity={0.15} />
      <pointLight position={[0, 0, 4]} intensity={3 + audioIntensity * 4} color="#00e5ff" />
      <pointLight position={[0, 0, -4]} intensity={1} color="#0044aa" />
      <pointLight position={[4, 0, 0]} intensity={0.5} color="#ffffff" />
      <pointLight position={[-4, 0, 0]} intensity={0.5} color="#ffffff" />

      <CoreSphere ai={audioIntensity} />
      <OrbitalRing radius={1.4} speed={0.4} axis="z" ai={audioIntensity} />
      <OrbitalRing radius={1.9} speed={-0.25} axis="y" ai={audioIntensity} />
      <OrbitalRing radius={2.3} speed={0.15} axis="x" ai={audioIntensity} />
      <SegmentedRing ai={audioIntensity} />
      <RadialBeams ai={audioIntensity} />
      <ParticleRing ai={audioIntensity} />
      <GlowLayers ai={audioIntensity} />
      <SparkleField ai={audioIntensity} />

      <EffectComposer>
        <Bloom
          intensity={1.2 + audioIntensity * 1.5}
          luminanceThreshold={0.2}
          luminanceSmoothing={0.9}
          mipmapBlur
        />
        <Vignette offset={0.35} darkness={0.8} />
      </EffectComposer>
    </>
  );
}

export default function JarvisCore3D({ audioIntensity = 0 }: CoreProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: "radial-gradient(circle at 50% 50%, #0a1628 0%, #020617 100%)",
        }}
      />
    );
  }

  return (
    <Canvas
      camera={{ position: [0, 0, 7], fov: 50 }}
      gl={{
        antialias: true,
        alpha: true,
        powerPreference: "high-performance",
      }}
      style={{ background: "transparent" }}
    >
      <CoreScene audioIntensity={audioIntensity} />
    </Canvas>
  );
}
