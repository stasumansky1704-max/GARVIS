import { useRef, useMemo, useState, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Bloom, Vignette, EffectComposer } from "@react-three/postprocessing";
import * as THREE from "three";

interface EarthProps {
  audioIntensity?: number;
}

const CITIES = [
  { name: "New York", lat: 40.71, lon: -74.0 },
  { name: "London", lat: 51.51, lon: -0.13 },
  { name: "Paris", lat: 48.86, lon: 2.35 },
  { name: "Tokyo", lat: 35.68, lon: 139.69 },
  { name: "Singapore", lat: 1.35, lon: 103.82 },
  { name: "Sydney", lat: -33.87, lon: 151.21 },
  { name: "Dubai", lat: 25.2, lon: 55.27 },
  { name: "Mumbai", lat: 19.08, lon: 72.88 },
  { name: "Sao Paulo", lat: -23.55, lon: -46.63 },
  { name: "San Francisco", lat: 37.77, lon: -122.42 },
  { name: "Berlin", lat: 52.52, lon: 13.41 },
  { name: "Seoul", lat: 37.57, lon: 126.98 },
];

function latLonToVec3(lat: number, lon: number, radius: number): THREE.Vector3 {
  const phi = ((90 - lat) * Math.PI) / 180;
  const theta = ((-lon + 180) * Math.PI) / 180;
  const x = radius * Math.sin(phi) * Math.cos(theta);
  const y = radius * Math.cos(phi);
  const z = radius * Math.sin(phi) * Math.sin(theta);
  return new THREE.Vector3(x, y, z);
}

function EarthSphere({ ai = 0 }: { ai?: number }) {
  const ref = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    if (!ref.current) return;
    ref.current.rotation.y = clock.getElapsedTime() * 0.08;
  });

  return (
    <group ref={ref}>
      <mesh>
        <sphereGeometry args={[2, 64, 64]} />
        <meshStandardMaterial color="#050a14" metalness={0.6} roughness={0.4} />
      </mesh>

      <mesh>
        <sphereGeometry args={[2.005, 32, 32]} />
        <meshBasicMaterial
          color="#006680"
          wireframe
          transparent
          opacity={0.35 + ai * 0.15}
        />
      </mesh>

      {Array.from({ length: 7 }).map((_, i) => {
        const lat = -60 + i * 20;
        const r = 2.02 * Math.cos((lat * Math.PI) / 180);
        const y = 2.02 * Math.sin((lat * Math.PI) / 180);

        return (
          <mesh key={`lat-${i}`} position={[0, y, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[r, 0.004, 8, 64]} />
            <meshBasicMaterial color="#004455" transparent opacity={0.25} />
          </mesh>
        );
      })}

      {Array.from({ length: 8 }).map((_, i) => {
        const lon = (i / 8) * Math.PI;

        return (
          <mesh key={`lon-${i}`} rotation={[0, lon, 0]}>
            <torusGeometry args={[2.02, 0.004, 8, 64]} />
            <meshBasicMaterial color="#004455" transparent opacity={0.2} />
          </mesh>
        );
      })}
    </group>
  );
}

function AtmosphereShell({ ai = 0 }: { ai?: number }) {
  const ref = useRef<THREE.Mesh>(null);

  useFrame(({ clock }) => {
    if (!ref.current) return;
    const pulse = 1 + Math.sin(clock.getElapsedTime() * 1.5) * 0.015 * (1 + ai);
    ref.current.scale.setScalar(pulse);
  });

  return (
    <mesh ref={ref}>
      <sphereGeometry args={[2.3, 64, 64]} />
      <meshBasicMaterial
        color="#00aacc"
        transparent
        opacity={0.06 + ai * 0.04}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        side={THREE.BackSide}
      />
    </mesh>
  );
}

function EquatorRing({ ai = 0 }: { ai?: number }) {
  const ref = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    if (!ref.current) return;
    ref.current.rotation.z = Math.sin(clock.getElapsedTime() * 0.5) * 0.05;
    ref.current.rotation.x = Math.sin(clock.getElapsedTime() * 0.3) * 0.03;
  });

  const ticks = useMemo(() => {
    return Array.from({ length: 36 }).map((_, i) => {
      const angle = (i / 36) * Math.PI * 2;
      const isMajor = i % 6 === 0;
      return { key: i, angle, isMajor };
    });
  }, []);

  return (
    <group ref={ref}>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[2.6, 0.008, 8, 100]} />
        <meshBasicMaterial
          color="#00e5ff"
          transparent
          opacity={0.35 + ai * 0.2}
          blending={THREE.AdditiveBlending}
        />
      </mesh>

      {ticks.map((t) => {
        const innerR = 2.6;
        const outerR = t.isMajor ? 2.72 : 2.66;
        const x1 = Math.cos(t.angle) * innerR;
        const y1 = Math.sin(t.angle) * innerR;
        const x2 = Math.cos(t.angle) * outerR;
        const y2 = Math.sin(t.angle) * outerR;

        return (
          <mesh key={t.key} position={[(x1 + x2) / 2, (y1 + y2) / 2, 0]} rotation={[0, 0, t.angle]}>
            <boxGeometry args={[outerR - innerR, 0.004, 0.004]} />
            <meshBasicMaterial
              color={t.isMajor ? "#00e5ff" : "#006688"}
              transparent
              opacity={t.isMajor ? 0.8 : 0.4}
            />
          </mesh>
        );
      })}
    </group>
  );
}

function CityMarkers({ ai = 0 }: { ai?: number }) {
  const groupRef = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    if (!groupRef.current) return;
    groupRef.current.children.forEach((child, i) => {
      const mesh = child as THREE.Mesh;
      const pulse = 1 + Math.sin(clock.getElapsedTime() * 2 + i * 0.8) * 0.25 * (1 + ai);
      mesh.scale.setScalar(pulse);
    });
  });

  const markers = useMemo(() => {
    return CITIES.map((city) => ({
      ...city,
      pos: latLonToVec3(city.lat, city.lon, 2.08),
    }));
  }, []);

  return (
    <group ref={groupRef}>
      {markers.map((m, i) => (
        <mesh key={i} position={m.pos}>
          <sphereGeometry args={[0.035, 12, 12]} />
          <meshStandardMaterial
            color="#00e5ff"
            emissive="#00e5ff"
            emissiveIntensity={2 + ai * 3}
            transparent
            opacity={0.9}
          />
        </mesh>
      ))}
    </group>
  );
}

function ArcLines({ ai = 0 }: { ai?: number }) {
  const connections = useMemo(() => {
    const pairs = [
      [0, 1],
      [1, 3],
      [3, 4],
      [4, 7],
      [7, 6],
      [6, 11],
    ];

    return pairs.map(([a, b]) => {
      const start = latLonToVec3(CITIES[a].lat, CITIES[a].lon, 2.08);
      const end = latLonToVec3(CITIES[b].lat, CITIES[b].lon, 2.08);
      const mid = new THREE.Vector3()
        .addVectors(start, end)
        .multiplyScalar(0.5)
        .normalize()
        .multiplyScalar(3.2);

      const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
      const points = curve.getPoints(50);
      const geometry = new THREE.BufferGeometry().setFromPoints(points);

      return { key: `${a}-${b}`, geometry };
    });
  }, []);

  return (
    <group>
      {connections.map((c) => (
        <lineSegments key={c.key} geometry={c.geometry}>
          <lineBasicMaterial
            color="#00e5ff"
            transparent
            opacity={0.25 + ai * 0.2}
            blending={THREE.AdditiveBlending}
          />
        </lineSegments>
      ))}
    </group>
  );
}

function EarthScene({ audioIntensity = 0 }: EarthProps) {
  return (
    <>
      <ambientLight intensity={0.2} />
      <pointLight position={[5, 3, 5]} intensity={1.5} color="#00e5ff" />
      <pointLight position={[-5, -3, -5]} intensity={0.5} color="#0044aa" />
      <pointLight position={[0, 0, 6]} intensity={1} color="#ffffff" />

      <EarthSphere ai={audioIntensity} />
      <AtmosphereShell ai={audioIntensity} />
      <EquatorRing ai={audioIntensity} />
      <CityMarkers ai={audioIntensity} />
      <ArcLines ai={audioIntensity} />

      <EffectComposer>
        <Bloom
          intensity={1.0 + audioIntensity * 1.2}
          luminanceThreshold={0.25}
          luminanceSmoothing={0.9}
          mipmapBlur
        />
        <Vignette offset={0.4} darkness={0.75} />
      </EffectComposer>
    </>
  );
}

export default function HolographicEarth3D({ audioIntensity = 0 }: EarthProps) {
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
      camera={{ position: [0, 0, 8], fov: 45 }}
      gl={{
        antialias: true,
        alpha: true,
        powerPreference: "high-performance",
      }}
      style={{ background: "transparent" }}
    >
      <EarthScene audioIntensity={audioIntensity} />
    </Canvas>
  );
}
