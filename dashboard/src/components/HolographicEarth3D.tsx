import { useRef, useMemo, useState, useEffect, Suspense } from "react";
import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import { Bloom, Vignette, EffectComposer, SMAA } from "@react-three/postprocessing";
import * as THREE from "three";

// Intelligence Hub holographic Earth.
// Recreated as a LIVING WebGL scene from the GARVIS CORE reference (textured Earth +
// particle shell + overhead light beam + dot-grid energy platform). The reference image is
// used only as a baked detail map on the live globe material (earth.jpg) - never as a
// background image. Same export + props as before; this component is used ONLY by the
// Intelligence Hub (Home / Living Core are untouched).

interface EarthProps {
  audioIntensity?: number;
}

const EARTH_R = 2;

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
  return new THREE.Vector3(
    radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta)
  );
}

// --- Textured, glowing Earth (real continents from earth.jpg, holographic cyan grade) ---
function TexturedEarth({ ai = 0 }: { ai?: number }) {
  const ref = useRef<THREE.Group>(null);
  // Real equirectangular Blue Marble map (continents + oceans), not a scene render.
  const texture = useLoader(THREE.TextureLoader, "/textures/earth_map.jpg");
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 16;            // crisp continents at grazing angles
  texture.generateMipmaps = true;
  texture.minFilter = THREE.LinearMipmapLinearFilter;

  useFrame(({ clock }) => {
    if (ref.current) ref.current.rotation.y = clock.getElapsedTime() * 0.06;
  });

  return (
    <group ref={ref}>
      {/* Surface: real continents, emissive so land reads as holographic light */}
      <mesh>
        <sphereGeometry args={[EARTH_R, 96, 96]} />
        <meshStandardMaterial
          map={texture}
          emissiveMap={texture}
          emissive={new THREE.Color("#ffffff")}
          emissiveIntensity={0.85 + ai * 0.25}
          metalness={0}
          roughness={1}
          color={new THREE.Color("#bcd9ee")}
          transparent={false}
          depthWrite
        />
      </mesh>

      {/* Very subtle graticule sits ON the opaque surface (no see-through) */}
      <mesh scale={1.003}>
        <sphereGeometry args={[EARTH_R, 36, 24]} />
        <meshBasicMaterial
          color="#0bd5ff"
          wireframe
          transparent
          opacity={0.025 + ai * 0.02}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}

// --- Dense particle shell (the holographic "dots" hugging the globe) ---
function ParticleShell({ ai = 0 }: { ai?: number }) {
  const ref = useRef<THREE.Points>(null);
  const positions = useMemo(() => {
    const N = 2600;
    const arr = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      // even sphere distribution (golden spiral)
      const y = 1 - (i / (N - 1)) * 2;
      const r = Math.sqrt(1 - y * y);
      const phi = i * Math.PI * (3 - Math.sqrt(5));
      const rad = EARTH_R * 1.045;
      arr[i * 3] = Math.cos(phi) * r * rad;
      arr[i * 3 + 1] = y * rad;
      arr[i * 3 + 2] = Math.sin(phi) * r * rad;
    }
    return arr;
  }, []);

  useFrame(({ clock }) => {
    if (ref.current) ref.current.rotation.y = -clock.getElapsedTime() * 0.04;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        color="#7fe9ff"
        size={0.018}
        sizeAttenuation
        transparent
        opacity={0.5 + ai * 0.3}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}

// --- Overhead light beam (the fixture + shaft bathing the globe from above) ---
function LightBeam({ ai = 0 }: { ai?: number }) {
  const beam = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    if (beam.current) {
      const m = beam.current.material as THREE.MeshBasicMaterial;
      m.opacity = 0.05 + (0.5 + 0.5 * Math.sin(clock.getElapsedTime() * 2)) * (0.04 + ai * 0.05);
    }
  });
  return (
    <group>
      {/* shaft: narrow at top (apex), widening down onto the globe */}
      <mesh ref={beam} position={[0, 3.7, 0]}>
        <coneGeometry args={[1.5, 3.4, 48, 1, true]} />
        <meshBasicMaterial
          color="#bff0ff"
          transparent
          opacity={0.07}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          side={THREE.DoubleSide}
        />
      </mesh>
      {/* fixture ring + glowing disc at the top */}
      <mesh position={[0, 5.4, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.62, 0.05, 12, 48]} />
        <meshBasicMaterial color="#dff6ff" transparent opacity={0.9} blending={THREE.AdditiveBlending} />
      </mesh>
      <mesh position={[0, 5.4, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.55, 48]} />
        <meshBasicMaterial color="#9fe9ff" transparent opacity={0.4} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
    </group>
  );
}

// --- Dot-grid energy platform beneath the globe ---
function EnergyPlatform({ ai = 0 }: { ai?: number }) {
  const ref = useRef<THREE.Points>(null);
  const positions = useMemo(() => {
    const step = 0.16;
    const half = 3.0;
    const pts: number[] = [];
    for (let x = -half; x <= half; x += step) {
      for (let z = -half; z <= half; z += step) {
        if (Math.sqrt(x * x + z * z) <= half) pts.push(x, 0, z);
      }
    }
    return new Float32Array(pts);
  }, []);

  useFrame(({ clock }) => {
    if (ref.current) {
      const m = ref.current.material as THREE.PointsMaterial;
      m.opacity = 0.35 + (0.5 + 0.5 * Math.sin(clock.getElapsedTime() * 1.6)) * (0.2 + ai * 0.2);
    }
  });

  return (
    <points ref={ref} position={[0, -2.75, 0]}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        color="#28c8ff"
        size={0.05}
        sizeAttenuation
        transparent
        opacity={0.5}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}

function CityMarkers({ ai = 0 }: { ai?: number }) {
  const groupRef = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    if (!groupRef.current) return;
    groupRef.current.children.forEach((child, i) => {
      const pulse = 1 + Math.sin(clock.getElapsedTime() * 2 + i * 0.8) * 0.25 * (1 + ai);
      (child as THREE.Mesh).scale.setScalar(pulse);
    });
  });
  const markers = useMemo(
    () => CITIES.map((c) => ({ pos: latLonToVec3(c.lat, c.lon, EARTH_R * 1.04) })),
    []
  );
  return (
    <group ref={groupRef}>
      {markers.map((m, i) => (
        <mesh key={i} position={m.pos}>
          <sphereGeometry args={[0.03, 12, 12]} />
          <meshStandardMaterial color="#aef6ff" emissive="#00e5ff" emissiveIntensity={2.5 + ai * 3} />
        </mesh>
      ))}
    </group>
  );
}

function ArcLines({ ai = 0 }: { ai?: number }) {
  const connections = useMemo(() => {
    const pairs = [[0, 1], [1, 3], [3, 4], [4, 7], [7, 6], [6, 11], [9, 0]];
    return pairs.map(([a, b]) => {
      const start = latLonToVec3(CITIES[a].lat, CITIES[a].lon, EARTH_R * 1.04);
      const end = latLonToVec3(CITIES[b].lat, CITIES[b].lon, EARTH_R * 1.04);
      const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5).normalize().multiplyScalar(EARTH_R * 1.6);
      const geometry = new THREE.BufferGeometry().setFromPoints(
        new THREE.QuadraticBezierCurve3(start, mid, end).getPoints(50)
      );
      return { key: `${a}-${b}`, geometry };
    });
  }, []);
  return (
    <group>
      {connections.map((c) => (
        <lineSegments key={c.key} geometry={c.geometry}>
          <lineBasicMaterial color="#3fe0ff" transparent opacity={0.22 + ai * 0.2} blending={THREE.AdditiveBlending} />
        </lineSegments>
      ))}
    </group>
  );
}

function FallbackGlobe() {
  return (
    <mesh>
      <sphereGeometry args={[EARTH_R, 48, 48]} />
      <meshStandardMaterial color="#0a2233" emissive="#0a4a66" emissiveIntensity={0.4} />
    </mesh>
  );
}

function EarthScene({ audioIntensity = 0 }: EarthProps) {
  return (
    <>
      {/* even, bright illumination so the whole visible hemisphere reads (no dark night side) */}
      <hemisphereLight args={["#eaf7ff", "#0a2740", 1.5]} />
      <ambientLight intensity={0.65} />
      <pointLight position={[0, 1.5, 7]} intensity={3.4} color="#f2faff" />
      <pointLight position={[0, 6, 1.5]} intensity={2.0} color="#ffffff" />
      <pointLight position={[-5, -1, -4]} intensity={1.2} color="#1a8fff" />

      <Suspense fallback={<FallbackGlobe />}>
        <TexturedEarth ai={audioIntensity} />
      </Suspense>
      <ParticleShell ai={audioIntensity} />
      <LightBeam ai={audioIntensity} />
      <EnergyPlatform ai={audioIntensity} />
      <CityMarkers ai={audioIntensity} />
      <ArcLines ai={audioIntensity} />

      <EffectComposer multisampling={0} frameBufferType={THREE.HalfFloatType}>
        <SMAA />
        <Bloom
          intensity={0.85 + audioIntensity * 1.1}
          luminanceThreshold={0.45}
          luminanceSmoothing={0.9}
          mipmapBlur
        />
        <Vignette offset={0.32} darkness={0.7} />
      </EffectComposer>
    </>
  );
}

export default function HolographicEarth3D({ audioIntensity = 0 }: EarthProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: "radial-gradient(circle at 50% 45%, #0a1c30 0%, #020617 100%)",
        }}
      />
    );
  }

  return (
    <Canvas
      camera={{ position: [0, 0.5, 6.0], fov: 45 }}
      dpr={[1, 2]}
      gl={{ antialias: false, alpha: true, powerPreference: "high-performance" }}
      onCreated={({ gl }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping;
        gl.toneMappingExposure = 1.4;
      }}
      style={{ background: "transparent" }}
    >
      <EarthScene audioIntensity={audioIntensity} />
    </Canvas>
  );
}
