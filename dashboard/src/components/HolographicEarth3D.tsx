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
        <sphereGeometry args={[EARTH_R, 128, 128]} />
        <meshStandardMaterial
          map={texture}
          emissiveMap={texture}
          emissive={new THREE.Color("#ffffff")}
          emissiveIntensity={1.05 + ai * 0.25}
          bumpMap={texture}
          bumpScale={0.8}            /* subtle relief so terrain reads 3D, keeps brightness */
          metalness={0}
          roughness={1}
          color={new THREE.Color("#ffffff")}
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

// --- Vertical light streaks rising from the floor (like the reference) ---
const FLOOR_Y = -3.4;            // floor sits well below the globe (visible gap)

function FloorStreaks({ ai = 0 }: { ai?: number }) {
  // a soft vertical gradient used by every streak (bright at the floor, fading up)
  const grad = useMemo(() => {
    const c = document.createElement("canvas");
    c.width = 8;
    c.height = 128;
    const ctx = c.getContext("2d")!;
    const g = ctx.createLinearGradient(0, 128, 0, 0);
    g.addColorStop(0, "rgba(150,220,255,0.9)");
    g.addColorStop(0.5, "rgba(90,180,255,0.28)");
    g.addColorStop(1, "rgba(90,180,255,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 8, 128);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, []);
  useEffect(() => () => grad.dispose(), [grad]);

  const streaks = useMemo(() => {
    const out: { x: number; z: number; h: number; w: number }[] = [];
    for (let i = 0; i < 16; i++) {
      const x = (Math.random() - 0.5) * 16;
      const z = -1 - Math.random() * 9;        // spread into the distance
      out.push({ x, z, h: 2.6 + Math.random() * 2.2, w: 0.18 + Math.random() * 0.18 });
    }
    return out;
  }, []);

  const group = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    if (!group.current) return;
    group.current.children.forEach((c, i) => {
      const m = (c as THREE.Mesh).material as THREE.MeshBasicMaterial;
      m.opacity = 0.35 + 0.3 * Math.sin(clock.getElapsedTime() * 1.3 + i) + ai * 0.3;
    });
  });

  return (
    <group ref={group}>
      {streaks.map((s, i) => (
        <mesh key={i} position={[s.x, FLOOR_Y + s.h / 2, s.z]}>
          <planeGeometry args={[s.w, s.h]} />
          <meshBasicMaterial
            map={grad}
            transparent
            opacity={0.4}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            side={THREE.DoubleSide}
          />
        </mesh>
      ))}
    </group>
  );
}

// --- Bright glow band where the globe's light meets the floor ---
function FloorGlow({ ai = 0 }: { ai?: number }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    if (ref.current) {
      const m = ref.current.material as THREE.MeshBasicMaterial;
      m.opacity = 0.45 + Math.sin(clock.getElapsedTime() * 1.5) * 0.08 + ai * 0.2;
    }
  });
  return (
    <mesh ref={ref} rotation={[-Math.PI / 2, 0, 0]} position={[0, FLOOR_Y + 0.05, -0.5]}>
      <circleGeometry args={[3.2, 48]} />
      <meshBasicMaterial color="#bfeaff" transparent opacity={0.5} blending={THREE.AdditiveBlending} depthWrite={false} />
    </mesh>
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

// --- Glowing hexagon-grid floor beneath the globe (perspective tech floor) ---
const HEX_VERT = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;
const HEX_FRAG = `
  uniform float uTime; uniform vec3 uColor; uniform float uIntensity;
  varying vec2 vUv;
  float hexDist(vec2 p){ p = abs(p); return max(dot(p, normalize(vec2(1.0, 1.7320508))), p.x); }
  vec2 hexCell(vec2 uv){
    vec2 r = vec2(1.0, 1.7320508); vec2 h = r * 0.5;
    vec2 a = mod(uv, r) - h;
    vec2 b = mod(uv - h, r) - h;
    return dot(a, a) < dot(b, b) ? a : b;
  }
  void main(){
    vec2 uv = (vUv - 0.5) * 82.0;            // smaller, denser hex cells
    vec2 gv = hexCell(uv);
    float d = hexDist(gv);
    float edge = smoothstep(0.44, 0.50, d);  // thin bright cell border
    float fill = smoothstep(0.50, 0.28, d) * 0.05;
    float dist = distance(vUv, vec2(0.5)) * 2.0;
    float fade = 1.0 - smoothstep(0.40, 0.95, dist);   // melt into the dark
    float pulse = 0.82 + 0.18 * sin(uTime * 1.4 - dist * 7.0);
    float a = (edge + fill) * fade * pulse * uIntensity;
    gl_FragColor = vec4(uColor * (edge * 1.5 + fill * 0.6), a);
  }
`;

function HexFloor({ ai = 0 }: { ai?: number }) {
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          uTime: { value: 0 },
          uColor: { value: new THREE.Color("#33b8ff") },
          uIntensity: { value: 1.0 },
        },
        vertexShader: HEX_VERT,
        fragmentShader: HEX_FRAG,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    []
  );
  useEffect(() => () => material.dispose(), [material]);
  useFrame(({ clock }) => {
    material.uniforms.uTime.value = clock.getElapsedTime();
    material.uniforms.uIntensity.value = 1.0 + ai * 0.6;
  });
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, FLOOR_Y, 0]}>
      <planeGeometry args={[64, 64, 1, 1]} />
      <primitive object={material} attach="material" />
    </mesh>
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
      <LightBeam ai={audioIntensity} />
      <HexFloor ai={audioIntensity} />
      <FloorStreaks ai={audioIntensity} />
      <FloorGlow ai={audioIntensity} />
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
        gl.toneMappingExposure = 1.7;
      }}
      style={{ background: "transparent" }}
    >
      <EarthScene audioIntensity={audioIntensity} />
    </Canvas>
  );
}
