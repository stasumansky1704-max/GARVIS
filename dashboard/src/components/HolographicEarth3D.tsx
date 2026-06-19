import { useRef, useMemo, useState, useEffect, Suspense } from "react";
import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import { Bloom, Vignette, EffectComposer, SMAA, HueSaturation, BrightnessContrast } from "@react-three/postprocessing";
import * as THREE from "three";

// Intelligence Hub holographic Earth.
// Recreated as a LIVING WebGL scene from the GARVIS CORE reference (textured Earth +
// overhead light beam + holographic hex platform). The reference is used only as a baked
// detail map on the live globe material (earth_map.jpg) - never as a background image.
// Same export + props as before; this component is used ONLY by the Intelligence Hub
// (Home / Living Core are untouched).

interface EarthProps {
  audioIntensity?: number;
  capture?: boolean; // screenshot-friendly: no post-processing, render-on-demand
  showPillars?: boolean; // toggle the floor light pillars on/off
}

const EARTH_R = 2;

// Globe sits deeper (further from camera) and slightly higher in frame, floating above
// the holographic platform. The light beam + floor glow track this same x/z.
const GLOBE_POS: [number, number, number] = [0, 0.55, -2.4];
const FLOOR_Y = -3.4; // platform sits well below the globe (a clear floating gap)

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

// Initial spin so a recognizable view (Africa / Europe / Atlantic) faces the camera.
const GLOBE_START_ROT = 3.5;

// --- Fresnel atmosphere: a soft view-dependent halo hugging the globe's limb (not a ring).
const ATMO_VERT = `
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  void main() {
    vec4 wp = modelMatrix * vec4(position, 1.0);
    vNormalW = normalize(mat3(modelMatrix) * normal);
    vViewDir = normalize(cameraPosition - wp.xyz);
    gl_Position = projectionMatrix * viewMatrix * wp;
  }
`;
const ATMO_FRAG = `
  uniform vec3 uColor;
  uniform float uPower;
  uniform float uStrength;
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  void main() {
    float f = pow(1.0 - max(dot(vNormalW, vViewDir), 0.0), uPower);
    gl_FragColor = vec4(uColor, f * uStrength);
  }
`;

function Atmosphere({ ai = 0 }: { ai?: number }) {
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          uColor: { value: new THREE.Color("#4aa6f0") },
          uPower: { value: 1.7 },      // broad, diffuse falloff (a soft halo, never a defined ring)
          uStrength: { value: 0.26 },
        },
        vertexShader: ATMO_VERT,
        fragmentShader: ATMO_FRAG,
        transparent: true,
        blending: THREE.AdditiveBlending,
        side: THREE.BackSide,
        depthWrite: false,
      }),
    []
  );
  useEffect(() => () => material.dispose(), [material]);
  useFrame(() => {
    material.uniforms.uStrength.value = 0.24 + ai * 0.14;
  });
  return (
    <mesh position={GLOBE_POS}>
      <sphereGeometry args={[EARTH_R * 1.06, 64, 64]} />
      <primitive object={material} attach="material" />
    </mesh>
  );
}

// --- Realistic Earth: the map is the surface; lighting reveals real continents/oceans.
function TexturedEarth({ ai = 0 }: { ai?: number }) {
  const ref = useRef<THREE.Group>(null);
  // Blue-Marble DAY map + city-lights NIGHT map; blended by sun direction in a shader.
  const [dayTex, nightTex] = useLoader(THREE.TextureLoader, [
    "/textures/earth_day.jpg",
    "/textures/earth_night.jpg",
  ]);
  [dayTex, nightTex].forEach((t) => {
    t.colorSpace = THREE.SRGBColorSpace;
    t.anisotropy = 16;
  });

  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          dayMap: { value: dayTex },
          nightMap: { value: nightTex },
          sunDir: { value: new THREE.Vector3(0.6, 0.22, 0.9).normalize() },
        },
        vertexShader: `
          varying vec2 vUv;
          varying vec3 vNormalW;
          void main() {
            vUv = uv;
            vNormalW = normalize(mat3(modelMatrix) * normal);
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `,
        fragmentShader: `
          uniform sampler2D dayMap;
          uniform sampler2D nightMap;
          uniform vec3 sunDir;
          varying vec2 vUv;
          varying vec3 vNormalW;
          void main() {
            vec3 day = texture2D(dayMap, vUv).rgb;
            vec3 night = texture2D(nightMap, vUv).rgb;
            float d = dot(normalize(vNormalW), normalize(sunDir));
            float mixf = smoothstep(-0.18, 0.38, d);                 // 0 night, 1 day
            vec3 col = mix(night * 1.7, day * 1.35, mixf);           // bright, vivid
            gl_FragColor = vec4(col, 1.0);
          }
        `,
      }),
    [dayTex, nightTex]
  );
  useEffect(() => () => material.dispose(), [material]);

  useFrame(({ clock }) => {
    if (ref.current) ref.current.rotation.y = GLOBE_START_ROT + clock.getElapsedTime() * 0.045;
  });

  return (
    <group position={GLOBE_POS}>
      <group ref={ref} rotation={[0.18, GLOBE_START_ROT, 0]}>
        {/* Surface: real day/night Earth (continents, oceans, city lights). */}
        <mesh>
          <sphereGeometry args={[EARTH_R, 128, 128]} />
          <primitive object={material} attach="material" />
        </mesh>

        {/* very faint holographic graticule overlay */}
        <mesh scale={1.004}>
          <sphereGeometry args={[EARTH_R, 24, 16]} />
          <meshBasicMaterial color="#36c6ff" wireframe transparent opacity={0.03 + ai * 0.02} depthWrite={false} />
        </mesh>
      </group>
    </group>
  );
}

// --- Projector beams: THIN, crisp, well-defined light shafts converging on the globe top
// (sharp — NOT a wide washed-out wall of light). Each beam = a faint narrow halo + a
// bright defined core. ---
function LightBeam() {
  // Emitter at the projector's mouth; many THIN sharp neon rays fan down onto the globe.
  const apex = useMemo(() => new THREE.Vector3(GLOBE_POS[0], GLOBE_POS[1] + 3.4, GLOBE_POS[2]), []);

  // oriented glowing beam shafts (soft halo + bright core) fanning onto the globe
  const beams = useMemo(() => {
    const up = new THREE.Vector3(0, 1, 0);
    const N = 22;
    const out: { pos: [number, number, number]; quat: [number, number, number, number]; h: number }[] = [];
    for (let i = 0; i < N; i++) {
      const a = (i / N) * Math.PI * 2;
      const r = 1.45 + (i % 3) * 0.12;
      const end = new THREE.Vector3(
        GLOBE_POS[0] + Math.cos(a) * r,
        GLOBE_POS[1] + 0.9,
        GLOBE_POS[2] + Math.sin(a) * r
      );
      const mid = apex.clone().add(end).multiplyScalar(0.5);
      const dir = apex.clone().sub(end).normalize(); // cone +Y points back to the emitter
      const q = new THREE.Quaternion().setFromUnitVectors(up, dir);
      out.push({ pos: [mid.x, mid.y, mid.z], quat: [q.x, q.y, q.z, q.w], h: apex.distanceTo(end) });
    }
    return out;
  }, [apex]);

  // sparkle particles drifting inside the beam cone
  const sparkGeo = useMemo(() => {
    const arr: number[] = [];
    for (let i = 0; i < 70; i++) {
      const t = Math.random();
      const a = Math.random() * Math.PI * 2;
      const r = t * 1.4;
      arr.push(GLOBE_POS[0] + Math.cos(a) * r, GLOBE_POS[1] + 3.2 - t * 2.4, GLOBE_POS[2] + Math.sin(a) * r);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(arr, 3));
    return g;
  }, []);
  useEffect(() => () => sparkGeo.dispose(), [sparkGeo]);

  return (
    <group>
      {beams.map((b, i) => (
        <group key={i} position={b.pos} quaternion={b.quat}>
          {/* soft halo gives the beam volume so it reads as light, not a flat line */}
          <mesh>
            <coneGeometry args={[0.14, b.h, 16, 1, true]} />
            <meshBasicMaterial color="#3ba6ff" transparent opacity={0.12} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} />
          </mesh>
          {/* thin bright core (bright enough to cross the bloom threshold → glows as light) */}
          <mesh>
            <coneGeometry args={[0.045, b.h, 12, 1, true]} />
            <meshBasicMaterial color="#f4ffff" transparent opacity={0.9} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} />
          </mesh>
        </group>
      ))}
      {/* sparkles */}
      <points geometry={sparkGeo}>
        <pointsMaterial color="#cfeeff" size={0.045} sizeAttenuation transparent opacity={0.85} blending={THREE.AdditiveBlending} depthWrite={false} />
      </points>
    </group>
  );
}

// --- Sharp vertical light pillars rising from the floor. Each pillar = a thin bright
// defined CORE + a soft halo, so it reads as a crisp 3D projection column. ---
function FloorBeams({ ai = 0 }: { ai?: number }) {
  // crisp vertical gradient: a tight bright core at the base, fading quickly upward
  const grad = useMemo(() => {
    const c = document.createElement("canvas");
    c.width = 8; c.height = 128;
    const ctx = c.getContext("2d")!;
    const g = ctx.createLinearGradient(0, 128, 0, 0);
    g.addColorStop(0, "rgba(225,247,255,1)");        // crisp bright base
    g.addColorStop(0.12, "rgba(170,225,255,0.85)");
    g.addColorStop(0.4, "rgba(110,195,255,0.22)");
    g.addColorStop(1, "rgba(90,180,255,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 8, 128);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, []);
  useEffect(() => () => grad.dispose(), [grad]);

  // framed around the globe (left/right clusters + a few in the distance), avoiding center
  const pillars = useMemo(() => {
    const out: { x: number; z: number; h: number; w: number }[] = [];
    const xs = [-9, -7.4, -6, 6, 7.4, 9, -4.6, 4.6, -8.2, 8.2];
    for (let i = 0; i < xs.length; i++) {
      out.push({ x: xs[i], z: -1.5 - Math.random() * 7, h: 3.0 + Math.random() * 2.4, w: 0.09 + Math.random() * 0.04 });
    }
    return out;
  }, []);

  const group = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    if (!group.current) return;
    const t = clock.getElapsedTime();
    let i = 0;
    group.current.children.forEach((pillar) => {
      pillar.children.forEach((c) => {
        const mesh = c as THREE.Mesh;
        const m = mesh.material as THREE.MeshBasicMaterial;
        const base = (mesh.userData.base as number) ?? 0.6;
        m.opacity = base * (0.82 + 0.18 * Math.sin(t * 1.4 + i)) + ai * 0.15;
        i++;
      });
    });
  });

  return (
    <group ref={group} position={[GLOBE_POS[0], 0, GLOBE_POS[2]]}>
      {pillars.map((p, i) => (
        <group key={i} position={[p.x, FLOOR_Y + p.h / 2, p.z]}>
          {/* soft halo */}
          <mesh userData={{ base: 0.2 }}>
            <planeGeometry args={[p.w * 2.6, p.h]} />
            <meshBasicMaterial map={grad} transparent opacity={0.2} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} />
          </mesh>
          {/* thin crisp defined core */}
          <mesh userData={{ base: 0.95 }}>
            <planeGeometry args={[p.w * 0.7, p.h]} />
            <meshBasicMaterial map={grad} transparent opacity={0.95} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} />
          </mesh>
        </group>
      ))}
    </group>
  );
}

// --- Glowing hexagon-grid platform beneath the globe (sharp perspective tech floor) ---
const HEX_VERT = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;
// Crisp hex borders, faint fill, strong radial fade to darkness, slow pulse, and an
// expanding scan ring that sweeps outward from under the globe.
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
    vec2 uv = (vUv - 0.5) * 82.0;
    vec2 gv = hexCell(uv);
    float d = hexDist(gv);
    float edge = smoothstep(0.465, 0.505, d);          // crisp thin border
    float fill = smoothstep(0.505, 0.30, d) * 0.028;    // very faint fill (low muddiness)
    float dist = distance(vUv, vec2(0.5)) * 2.0;
    float fade = 1.0 - smoothstep(0.28, 0.92, dist);    // strong perspective fade to black
    float pulse = 0.86 + 0.14 * sin(uTime * 1.2 - dist * 6.0);
    float scanR = fract(uTime * 0.16);                  // expanding scan ring
    float scan = smoothstep(0.05, 0.0, abs(dist - scanR * 1.45)) * 0.7;
    float a = (edge * 1.0 + fill) * fade * pulse * uIntensity + edge * scan * fade;
    vec3 col = uColor * (edge * 1.9 + fill * 0.5) + uColor * scan * edge * 1.3;
    gl_FragColor = vec4(col, a);
  }
`;

function HexFloor({ ai = 0 }: { ai?: number }) {
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          uTime: { value: 0 },
          uColor: { value: new THREE.Color("#3cc4ff") },
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
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[GLOBE_POS[0], FLOOR_Y, GLOBE_POS[2]]}>
      <planeGeometry args={[64, 64, 1, 1]} />
      <primitive object={material} attach="material" />
    </mesh>
  );
}

// --- Holographic platform glow: a soft radial pool of light directly under the globe.
// (No emitter rings — they read as a "ring around the planet"; the hex floor + its scan
// wave provide the platform structure instead.)
function Platform({ ai = 0 }: { ai?: number }) {
  const glow = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (glow.current) {
      (glow.current.material as THREE.MeshBasicMaterial).opacity = 0.4 + Math.sin(t * 1.4) * 0.06 + ai * 0.16;
    }
  });
  return (
    <group position={[GLOBE_POS[0], FLOOR_Y + 0.04, GLOBE_POS[2]]} rotation={[-Math.PI / 2, 0, 0]}>
      <mesh ref={glow}>
        <circleGeometry args={[3.2, 64]} />
        <meshBasicMaterial color="#bfeaff" transparent opacity={0.42} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
    </group>
  );
}

// --- Overhead projection ENGINE: a tiered funnel of concentric neon rings narrowing down
// to a bright emitter core (the detailed ceiling projector from the reference). ---
function TopProjector() {
  const grp = useRef<THREE.Group>(null);
  const grp2 = useRef<THREE.Group>(null);
  const rings = useMemo(() => {
    const out: { r: number; z: number; op: number }[] = [];
    for (let i = 0; i < 7; i++) out.push({ r: 2.15 - i * 0.25, z: -i * 0.16, op: 0.88 - i * 0.07 });
    return out;
  }, []);
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (grp.current) grp.current.rotation.z = t * 0.2;
    if (grp2.current) grp2.current.rotation.z = -t * 0.35; // counter-spin inner ring
  });
  return (
    <group position={[GLOBE_POS[0], GLOBE_POS[1] + 4.4, GLOBE_POS[2]]} rotation={[-Math.PI / 2, 0, 0]}>
      {/* tiered funnel of rings (widest at top, narrowing toward the emitter) */}
      {/* soft glow disc behind the fixture so the engine reads as a glowing structure */}
      <mesh position={[0, 0, -0.4]}>
        <circleGeometry args={[2.3, 64]} />
        <meshBasicMaterial color="#1c6fd0" transparent opacity={0.16} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      <group ref={grp}>
        {rings.map((rg, i) => (
          <mesh key={i} position={[0, 0, rg.z]}>
            <ringGeometry args={[rg.r, rg.r + 0.055, 128]} />
            <meshBasicMaterial color="#8fe0ff" transparent opacity={rg.op} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} />
          </mesh>
        ))}
      </group>
      {/* counter-rotating bright inner ring near the emitter */}
      <group ref={grp2}>
        <mesh position={[0, 0, -0.85]}>
          <ringGeometry args={[0.62, 0.7, 96]} />
          <meshBasicMaterial color="#e6fbff" transparent opacity={0.7} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} />
        </mesh>
      </group>
      {/* bright emitter core at the funnel mouth */}
      <mesh position={[0, 0, -0.95]}>
        <circleGeometry args={[0.4, 48]} />
        <meshBasicMaterial color="#eaffff" transparent opacity={0.8} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
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
    <group position={GLOBE_POS} rotation={[0.18, GLOBE_START_ROT, 0]}>
      {connections.map((c) => (
        <lineSegments key={c.key} geometry={c.geometry}>
          <lineBasicMaterial color="#3fe0ff" transparent opacity={0.18 + ai * 0.18} blending={THREE.AdditiveBlending} />
        </lineSegments>
      ))}
    </group>
  );
}

function FallbackGlobe() {
  return (
    <mesh position={GLOBE_POS}>
      <sphereGeometry args={[EARTH_R, 48, 48]} />
      <meshStandardMaterial color="#0a2233" emissive="#0a4a66" emissiveIntensity={0.4} />
    </mesh>
  );
}

function EarthScene({ audioIntensity = 0, capture = false, showPillars = true }: EarthProps) {
  return (
    <>
      {/* even, bright key illumination so the visible hemisphere reads as real Earth */}
      <hemisphereLight args={["#eaf7ff", "#0a2740", 1.35]} />
      <ambientLight intensity={0.55} />
      <pointLight position={[3, 2.5, 7]} intensity={3.2} color="#f2faff" />
      {/* softened top light so it reads as projector beams, not a bright white blob */}
      <pointLight position={[0, 6, 1.5]} intensity={0.8} color="#ffffff" />
      {/* cool rim light from behind to carve the globe silhouette out of the dark */}
      <pointLight position={[-4, 1.5, -6]} intensity={2.4} color="#2f9bff" />

      <Suspense fallback={<FallbackGlobe />}>
        <TexturedEarth ai={audioIntensity} />
      </Suspense>
      <Atmosphere ai={audioIntensity} />
      <TopProjector />
      <LightBeam />
      <HexFloor ai={audioIntensity} />
      {showPillars && <FloorBeams ai={audioIntensity} />}
      <Platform ai={audioIntensity} />
      <ArcLines ai={audioIntensity} />

      {/* Capture mode: a single lightweight Bloom so screenshots still show the glow
          (fast on the demand frameloop). Normal mode: full cinematic chain. */}
      {capture ? (
        <EffectComposer multisampling={0} frameBufferType={THREE.HalfFloatType}>
          <Bloom intensity={1.0} luminanceThreshold={0.42} luminanceSmoothing={0.9} radius={0.6} mipmapBlur />
        </EffectComposer>
      ) : (
        <EffectComposer multisampling={0} frameBufferType={THREE.HalfFloatType}>
          <SMAA />
          {/* bright emissive cores cross this threshold → they bloom into light, not stripes */}
          <Bloom
            intensity={1.15 + audioIntensity * 0.8}
            luminanceThreshold={0.42}
            luminanceSmoothing={0.9}
            radius={0.72}
            mipmapBlur
          />
          {/* color grade: punchier neon "trailer" look */}
          <HueSaturation saturation={0.18} />
          <BrightnessContrast brightness={0.02} contrast={0.12} />
          <Vignette offset={0.3} darkness={0.72} />
        </EffectComposer>
      )}
    </>
  );
}

export default function HolographicEarth3D({ audioIntensity = 0, capture = false, showPillars = true }: EarthProps) {
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
      camera={{ position: [0, 0.6, 6.9], fov: 44 }}
      dpr={capture ? 2.5 : [1, 1.5]}
      frameloop={capture ? "demand" : "always"}
      gl={{ antialias: false, alpha: true, powerPreference: "high-performance" }}
      onCreated={({ gl }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping;
        gl.toneMappingExposure = 1.55;
      }}
      style={{ background: "transparent" }}
    >
      <EarthScene audioIntensity={audioIntensity} capture={capture} showPillars={showPillars} />
    </Canvas>
  );
}
