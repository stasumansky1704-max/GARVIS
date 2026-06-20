import { useRef, useMemo, useState, useEffect, Suspense } from "react";
import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import { MeshReflectorMaterial, Text } from "@react-three/drei";
import { Bloom, Vignette, EffectComposer, SMAA, HueSaturation, BrightnessContrast, Noise } from "@react-three/postprocessing";
import * as THREE from "three";

// Intelligence Hub holographic Earth.
// Recreated as a LIVING WebGL scene from the GARVIS CORE reference (textured Earth +
// overhead light beam + holographic hex platform). The reference is used only as a baked
// detail map on the live globe material (earth_map.jpg) - never as a background image.
// Same export + props as before; this component is used ONLY by the Intelligence Hub
// (Home / Living Core are untouched).

export interface Card3DData {
  id: string;
  title: string;
  state: string;
  maturity: string;
  accent: string;
  pos: [number, number, number];
}

interface EarthProps {
  audioIntensity?: number;
  capture?: boolean; // screenshot-friendly: no post-processing, render-on-demand
  showPillars?: boolean; // toggle the floor light pillars on/off
  cards3d?: Card3DData[]; // when provided, render the cards as real 3D meshes in-scene
  onSelectCard?: (id: string) => void;
  activeCardId?: string | null;
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

function atmoMat(color: string, power: number, strength: number) {
  return new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: new THREE.Color(color) },
      uPower: { value: power },
      uStrength: { value: strength },
    },
    vertexShader: ATMO_VERT,
    fragmentShader: ATMO_FRAG,
    transparent: true,
    blending: THREE.AdditiveBlending,
    side: THREE.BackSide,
    depthWrite: false,
  });
}

// A REALLY thin neon-blue rim hugging the limb (high power = concentrated at the edge),
// plus a barely-there soft edge so it isn't a hard line. No fat halo.
function Atmosphere({ ai = 0 }: { ai?: number }) {
  const rim = useMemo(() => atmoMat("#4aa6ff", 8.0, 0.14), []);
  const soft = useMemo(() => atmoMat("#2f8fe6", 5.0, 0.02), []);
  useEffect(() => () => { rim.dispose(); soft.dispose(); }, [rim, soft]);
  useFrame(() => {
    rim.uniforms.uStrength.value = 0.13 + ai * 0.06; // almost invisible — Earth first
  });
  return (
    <group position={GLOBE_POS}>
      <mesh>
        <sphereGeometry args={[EARTH_R * 1.011, 64, 64]} />
        <primitive object={rim} attach="material" />
      </mesh>
      <mesh>
        <sphereGeometry args={[EARTH_R * 1.04, 48, 48]} />
        <primitive object={soft} attach="material" />
      </mesh>
    </group>
  );
}

// --- Realistic Earth: the map is the surface; lighting reveals real continents/oceans.
function TexturedEarth({ ai = 0 }: { ai?: number }) {
  const ref = useRef<THREE.Group>(null);
  // Blue-Marble DAY map + city-lights NIGHT map; blended by sun direction in a shader.
  const [dayTex, nightTex, cloudTex] = useLoader(THREE.TextureLoader, [
    "/textures/earth_day.jpg",
    "/textures/earth_night.jpg",
    "/textures/earth_clouds.png",
  ]);
  [dayTex, nightTex].forEach((t) => {
    t.colorSpace = THREE.SRGBColorSpace;
    t.anisotropy = 16;
  });
  cloudTex.anisotropy = 8;
  cloudTex.wrapS = THREE.RepeatWrapping;

  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          dayMap: { value: dayTex },
          nightMap: { value: nightTex },
          cloudMap: { value: cloudTex },
          sunDir: { value: new THREE.Vector3(0.6, 0.22, 0.9).normalize() },
          uTime: { value: 0 },
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
          uniform sampler2D cloudMap;
          uniform vec3 sunDir;
          uniform float uTime;
          varying vec2 vUv;
          varying vec3 vNormalW;
          void main() {
            vec3 rawDay = texture2D(dayMap, vUv).rgb;
            vec3 night = texture2D(nightMap, vUv).rgb;
            // ocean mask: land reads green/brown (high R/G), ocean is darker → bias clouds to sea
            float landish = max(rawDay.r, rawDay.g * 0.9);
            float oceanMask = 1.0 - smoothstep(0.16, 0.40, landish);
            // lift + cool-boost the oceans so they read clearly brighter/bluer
            vec3 day = rawDay * 1.9 + vec3(0.03, 0.07, 0.14);
            day += oceanMask * vec3(0.02, 0.07, 0.15);               // brighter blue oceans
            float d = dot(normalize(vNormalW), normalize(sunDir));
            float mixf = smoothstep(-0.28, 0.34, d);                 // wider lit hemisphere = brighter
            vec3 col = mix(night * 3.2, day, mixf);                  // brighter day, punchier city lights
            // clouds: locked to the surface UV → rotate WITH the Earth. Embedded by BLENDING
            // into the surface (not added on top), lit by the sun, sparse, mostly over oceans.
            float cloud = texture2D(cloudMap, vUv).r;
            float cAmt = smoothstep(0.74, 0.99, cloud) * mix(0.02, 1.0, oceanMask) * (0.11 + 0.3 * mixf);
            col = mix(col, vec3(0.99, 1.0, 1.0), cAmt * 0.22);        // very sparse, ocean-only, pure white, sheer
            gl_FragColor = vec4(col, 1.0);
          }
        `,
      }),
    [dayTex, nightTex, cloudTex]
  );
  useEffect(() => () => material.dispose(), [material]);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    material.uniforms.uTime.value = t;
    if (ref.current) ref.current.rotation.y = GLOBE_START_ROT + t * 0.045;
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
  const apex = useMemo(() => new THREE.Vector3(GLOBE_POS[0], GLOBE_POS[1] + 2.6, GLOBE_POS[2]), []);

  // oriented glowing beam shafts (soft halo + bright core) fanning onto the globe
  const beams = useMemo(() => {
    const up = new THREE.Vector3(0, 1, 0);
    const N = 24;
    const out: { pos: [number, number, number]; quat: [number, number, number, number]; h: number }[] = [];
    for (let i = 0; i < N; i++) {
      const a = (i / N) * Math.PI * 2;
      const r = 1.2 + (i % 3) * 0.1;                  // narrow → lands ON the globe top, not outside
      const end = new THREE.Vector3(
        GLOBE_POS[0] + Math.cos(a) * r,
        GLOBE_POS[1] + 0.95,                          // higher → on the globe's upper cap
        GLOBE_POS[2] + Math.sin(a) * r
      );
      const mid = apex.clone().add(end).multiplyScalar(0.5);
      const dir = apex.clone().sub(end).normalize(); // cone +Y points back to the emitter
      const q = new THREE.Quaternion().setFromUnitVectors(up, dir);
      out.push({ pos: [mid.x, mid.y, mid.z], quat: [q.x, q.y, q.z, q.w], h: apex.distanceTo(end) });
    }
    return out;
  }, [apex]);

  // ENERGY PARTICLE FLOW — dense subatomic particles streaming down the beam (data stream)
  const sparkGeo = useMemo(() => {
    const arr: number[] = [];
    for (let i = 0; i < 200; i++) {
      const t = Math.random();
      const a = Math.random() * Math.PI * 2;
      const r = t * 1.45;                                 // fans out toward the globe
      arr.push(GLOBE_POS[0] + Math.cos(a) * r, GLOBE_POS[1] + 2.6 - t * 1.9, GLOBE_POS[2] + Math.sin(a) * r);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(arr, 3));
    return g;
  }, []);
  useEffect(() => () => sparkGeo.dispose(), [sparkGeo]);

  // central wide volumetric projection shaft: the single soft cone of light that
  // visibly carries the Earth hologram up to the emitter mouth.
  const shaftH = GLOBE_POS[1] + 2.6 - (GLOBE_POS[1] - 0.4);
  const shaftY = (GLOBE_POS[1] + 2.6 + (GLOBE_POS[1] - 0.4)) / 2;

  // life: each beam core flickers; sparkles twinkle; a bright ring scans DOWN the shaft.
  const grp = useRef<THREE.Group>(null);
  const scan = useRef<THREE.Mesh>(null);
  const shaft = useRef<THREE.Mesh>(null);
  const stream = useRef<THREE.Group>(null);
  const STREAM_N = 7;
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (scan.current) {
      // sweep from emitter mouth down onto the globe, then loop
      const p = (t * 0.45) % 1;
      scan.current.position.y = GLOBE_POS[1] + 2.4 - p * 2.1;
      scan.current.scale.setScalar(0.5 + p * 1.7);
      (scan.current.material as THREE.MeshBasicMaterial).opacity = 0.7 * (1 - p);
    }
    // DATA STREAM — horizontal scan rings continuously descend + fan out through the beam
    if (stream.current) stream.current.children.forEach((c, i) => {
      const m = c as THREE.Mesh;
      const p = (t * 0.3 + i / STREAM_N) % 1;
      m.position.y = GLOBE_POS[1] + 2.45 - p * 1.75;
      const s = 0.22 + p * 1.12;
      m.scale.set(s, s, 1);
      (m.material as THREE.MeshBasicMaterial).opacity = 0.5 * Math.sin(p * Math.PI);
    });
    if (shaft.current) (shaft.current.material as THREE.MeshBasicMaterial).opacity = 0.1 + 0.035 * Math.sin(t * 1.6);
    if (!grp.current) return;
    grp.current.children.forEach((c, i) => {
      const pts = c as THREE.Points;
      if (pts.isPoints) {
        (pts.material as THREE.PointsMaterial).opacity = 0.7 + 0.25 * Math.sin(t * 3 + i);
        return;
      }
      const core = (c as THREE.Group).children?.[1] as THREE.Mesh | undefined;
      if (core) (core.material as THREE.MeshBasicMaterial).opacity = 0.82 + 0.16 * Math.sin(t * 6 + i * 0.9);
    });
  });

  return (
    <group ref={grp}>
      {/* wide soft volumetric shaft enveloping the projection */}
      <mesh ref={shaft} position={[GLOBE_POS[0], shaftY, GLOBE_POS[2]]}>
        <coneGeometry args={[1.85, shaftH, 40, 1, true]} />
        <meshBasicMaterial color={C_BEAM_VOL} transparent opacity={0.1} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} />
      </mesh>
      {/* scanning ring sweeping down the shaft (the "projection refresh" sweep) */}
      <mesh ref={scan} position={[GLOBE_POS[0], GLOBE_POS[1] + 2.2, GLOBE_POS[2]]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.9, 0.02, 10, 64]} />
        <meshBasicMaterial color={C_BEAM_CORE} transparent opacity={0.6} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      {/* DATA STREAM PROJECTION — descending horizontal scan rings (data cross-sections) */}
      <group ref={stream}>
        {Array.from({ length: STREAM_N }).map((_, i) => (
          <mesh key={`st${i}`} position={[GLOBE_POS[0], GLOBE_POS[1] + 2.45, GLOBE_POS[2]]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[1, 0.007, 8, 72]} />
            <meshBasicMaterial color={C_PARTICLE} transparent opacity={0.4} blending={THREE.AdditiveBlending} depthWrite={false} />
          </mesh>
        ))}
      </group>
      {beams.map((b, i) => (
        <group key={i} position={b.pos} quaternion={b.quat}>
          {/* HOLOGRAPHIC BEAM (VOLUME) — soft volumetric shaft */}
          <mesh>
            <coneGeometry args={[0.032, b.h, 8, 1, true]} />
            <meshBasicMaterial color={C_BEAM_VOL} transparent opacity={0.16} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} />
          </mesh>
          {/* HOLOGRAPHIC BEAM (CORE) — bright defined core */}
          <mesh>
            <coneGeometry args={[0.009, b.h, 6, 1, true]} />
            <meshBasicMaterial color={C_BEAM_CORE} transparent opacity={1} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} />
          </mesh>
        </group>
      ))}
      {/* ENERGY PARTICLE FLOW — subatomic particles streaming down the beam */}
      <points geometry={sparkGeo}>
        <pointsMaterial color={C_PARTICLE} size={0.06} sizeAttenuation transparent opacity={0.95} blending={THREE.AdditiveBlending} depthWrite={false} />
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
    const xs = [
      -11, -10, -9, -8.2, -7.4, -6.6, -6, -5.2, -4.4, -3.6,
      3.6, 4.4, 5.2, 6, 6.6, 7.4, 8.2, 9, 10, 11,
    ];
    for (let i = 0; i < xs.length; i++) {
      out.push({ x: xs[i], z: -1.2 - Math.random() * 7.5, h: 3.0 + Math.random() * 2.6, w: 0.08 + Math.random() * 0.04 });
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
    float edge = smoothstep(0.478, 0.502, d);           // crisper, sharper thin border
    float fill = smoothstep(0.502, 0.30, d) * 0.022;     // even fainter fill (cleaner contrast)
    float dist = distance(vUv, vec2(0.5)) * 2.0;
    float fade = 1.0 - smoothstep(0.22, 0.86, dist);     // stronger perspective fade to black
    float pulse = 0.86 + 0.14 * sin(uTime * 1.2 - dist * 6.0);
    float scanR = fract(uTime * 0.16);                   // expanding scan ring
    float scan = smoothstep(0.045, 0.0, abs(dist - scanR * 1.45)) * 0.8;
    float a = (edge * 1.0 + fill) * fade * pulse * uIntensity + edge * scan * fade;
    vec3 col = uColor * (edge * 2.4 + fill * 0.5) + uColor * scan * edge * 1.5;
    gl_FragColor = vec4(col, a);
  }
`;

// --- Reflective base floor (glossy dark mirror) beneath the hex grid: the globe, beams
// and pillars reflect in it for a real "holographic platform on a wet floor" look. ---
function ReflectiveFloor() {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[GLOBE_POS[0], FLOOR_Y - 0.02, GLOBE_POS[2]]}>
      <planeGeometry args={[60, 60]} />
      <MeshReflectorMaterial
        resolution={512}
        mirror={0.55}
        mixBlur={1.4}
        mixStrength={1.3}
        blur={[420, 140]}
        roughness={0.85}
        metalness={0.5}
        color="#06121f"
        depthScale={1.1}
        minDepthThreshold={0.4}
        maxDepthThreshold={1.2}
      />
    </mesh>
  );
}

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

// --- Overhead projection MACHINE: dark gunmetal/titanium housing — tiered rings, engineered
// segmented hull panels, and a central EMITTER EYE (lens + iris + bright pupil) that is the
// hologram source. Dark metal revealed by internal lights, NOT a self-glowing blob. ---
// --- Projector blueprint palette (exact spec from the reference cutaway) ---
const TITANIUM = "#0a0d12";       // OUTER HOUSING — black titanium alloy armor
const C_COOLING = "#00e5ff";      // COOLING SYSTEM (vents)
const C_POWER = "#2979ff";        // POWER CORE LIGHTS (energy conduits)
const C_STABIL = "#9b5dff";       // STABILIZATION SYSTEM (gyroscopic ring)
const C_MAGLOCK = "#ffb800";      // MAGNETIC LOCKS (structural anchors)
const C_ACCENT = "#6a6dff";       // ACCENT / DIAGNOSTIC LEDs
const C_LENS = "#00f6ff";         // HOLOGRAPHIC LENS ARRAY (core cyan)
const C_BEAM_CORE = "#00f6ff";    // HOLOGRAPHIC BEAM — core
const C_BEAM_VOL = "#0099ff";     // HOLOGRAPHIC BEAM — volumetric
const C_PARTICLE = "#4dd9ff";     // ENERGY PARTICLE FLOW
const C_EMITTER = "#ffffff";      // PRIMARY EMITTER EYE (intense)
function TopProjector() {
  const grp = useRef<THREE.Group>(null);
  const lens = useRef<THREE.Group>(null);
  const pupil = useRef<THREE.Mesh>(null);
  const coolRef = useRef<THREE.Group>(null);

  // DEEP 7-tier titanium dome (outer → inner, strongly receding toward the emitter)
  const tiers = useMemo(() => ([
    { r: 2.40, z: 0.00, w: 0.12 },   // OUTER HOUSING RING (armor)
    { r: 2.14, z: -0.16, w: 0.07 },  // cooling-vent tier
    { r: 1.88, z: -0.34, w: 0.08 },  // upper structural tier
    { r: 1.60, z: -0.54, w: 0.07 },  // power-core / stabilization / mag-lock tier
    { r: 1.32, z: -0.76, w: 0.06 },  // diagnostic tier
    { r: 1.04, z: -0.98, w: 0.05 },  // lens-array shoulder
    { r: 0.78, z: -1.18, w: 0.05 },  // emitter throat
  ]), []);
  // SOLID machined dome walls connecting the tiers (so it reads as a closed engineered
  // bowl, not see-through floating rings)
  const frusta = useMemo(() => {
    const out: { rTop: number; rBot: number; h: number; z: number }[] = [];
    for (let i = 0; i < tiers.length - 1; i++) {
      const o = tiers[i], inr = tiers[i + 1];
      out.push({ rTop: o.r, rBot: inr.r, h: o.z - inr.z, z: (o.z + inr.z) / 2 });
    }
    return out;
  }, [tiers]);
  // ring helper: N segments around radius r
  const ring = (n: number, r: number) => Array.from({ length: n }, (_, i) => {
    const a = (i / n) * Math.PI * 2;
    return { a, x: Math.cos(a) * r, y: Math.sin(a) * r };
  });
  // OUTER HOUSING — large backlit rectangular panels (cyan housing + a purple STABILIZATION arc)
  const bigPanels = useMemo(() => Array.from({ length: 16 }, (_, i) => {
    const a = (i / 16) * Math.PI * 2;
    const stab = i >= 3 && i <= 6;                       // contiguous gyroscopic-stabilization arc
    return { a, x: Math.cos(a) * 2.18, y: Math.sin(a) * 2.18, stab };
  }), []);
  // COOLING VENTS — a 2-row cyan LED grid band
  const cooling = useMemo(() => {
    const out: { a: number; x: number; y: number; z: number }[] = [];
    const N = 34;
    for (let row = 0; row < 2; row++) {
      const r = 2.06 - row * 0.11;
      for (let i = 0; i < N; i++) { const a = (i / N) * Math.PI * 2 + row * 0.05; out.push({ a, x: Math.cos(a) * r, y: Math.sin(a) * r, z: -0.15 }); }
    }
    return out;
  }, []);
  // density: small indicator LEDs packed on the mid tiers (cyan + white status dots)
  const indic = useMemo(() => {
    const out: { a: number; x: number; y: number; z: number; white: boolean }[] = [];
    const bands = [{ r: 1.88, z: -0.31 }, { r: 1.60, z: -0.51 }, { r: 1.32, z: -0.73 }];
    bands.forEach((b, bi) => {
      const N = 40;
      for (let i = 0; i < N; i++) { const a = (i / N) * Math.PI * 2 + bi * 0.08; out.push({ a, x: Math.cos(a) * b.r, y: Math.sin(a) * b.r, z: b.z, white: i % 5 === 0 }); }
    });
    return out;
  }, []);
  // POWER CORE CHANNELS (blue) with a contiguous STABILIZATION arc (purple)
  const power = useMemo(() => Array.from({ length: 44 }, (_, i) => {
    const a = (i / 44) * Math.PI * 2;
    const stab = i >= 9 && i <= 16;                      // STABILIZATION purple arc
    return { a, x: Math.cos(a) * 1.60, y: Math.sin(a) * 1.60, stab };
  }), []);
  // MAGNETIC LOCKS — large amber 2x2 anchor grids at 6 cardinal positions
  const maglocks = useMemo(() => Array.from({ length: 6 }, (_, i) => {
    const a = (i / 6) * Math.PI * 2 + 0.26; return { a, x: Math.cos(a) * 1.60, y: Math.sin(a) * 1.60 };
  }), []);
  const mlCells = useMemo(() => [[-0.06, 0.08], [0.06, 0.08], [-0.06, -0.08], [0.06, -0.08]] as [number, number][], []);
  // INNER ACCENT / DIAGNOSTIC LEDs — indigo, bigger, sitting close to the lens
  const accents = useMemo(() => ring(36, 1.10), []);
  // HOLOGRAPHIC LENS ARRAY — deep multi-layer focusing spiral (tight inner → wide shoulder)
  const lensRings = useMemo(() => [0.20, 0.30, 0.40, 0.52, 0.64, 0.76, 0.88, 1.00, 1.12], []);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (grp.current) grp.current.rotation.z = t * 0.04;
    if (lens.current) lens.current.rotation.z = -t * 0.22;            // multi-layer focusing optics spin
    if (pupil.current) (pupil.current.material as THREE.MeshBasicMaterial).opacity = 0.8 + 0.2 * Math.sin(t * 2.6);
    if (coolRef.current) coolRef.current.children.forEach((c, i) => {
      const m = (c as THREE.Mesh).material as THREE.MeshStandardMaterial;
      m.emissiveIntensity = 2.0 + 1.2 * Math.sin(t * 2.2 + i * 0.5);  // active heat-dissipation pulse
    });
  });

  return (
    <group position={[GLOBE_POS[0], GLOBE_POS[1] + 3.92, GLOBE_POS[2]]} rotation={[-Math.PI / 2, 0, 0]} scale={1.05}>
      {/* internal lights that REVEAL the dark titanium (it is lit, not self-glowing) */}
      <pointLight position={[0, 0, -1.2]} intensity={8} distance={7} decay={2} color={C_BEAM_CORE} />
      <pointLight position={[0, 0, -0.5]} intensity={3.5} distance={5} decay={2} color={C_POWER} />
      {/* cool rim lights from the front/sides so the machined titanium catches real specular highlights */}
      <pointLight position={[2.6, 1.8, -1.6]} intensity={2.4} distance={9} decay={2} color="#bcd8ff" />
      <pointLight position={[-2.6, -1.8, -1.6]} intensity={2.0} distance={9} decay={2} color="#7fb6ff" />
      <group ref={grp}>
        {/* === SOLID machined dome walls between tiers (closed titanium bowl) === */}
        {frusta.map((f, i) => (
          <mesh key={`fr${i}`} position={[0, 0, f.z]} rotation={[-Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[f.rTop, f.rBot, f.h, 72, 1, true]} />
            <meshStandardMaterial color={TITANIUM} metalness={0.9} roughness={0.5} emissive="#05080e" emissiveIntensity={0.14} side={THREE.DoubleSide} />
          </mesh>
        ))}
        {/* === DEEP tiered BLACK TITANIUM ALLOY housing rings (raised lips on the walls) === */}
        {tiers.map((rg, i) => (
          <mesh key={i} position={[0, 0, rg.z]}>
            <torusGeometry args={[rg.r, rg.w, 16, 72]} />
            <meshStandardMaterial color={TITANIUM} metalness={0.96} roughness={0.38} emissive="#060a12" emissiveIntensity={0.2} />
          </mesh>
        ))}

        {/* OUTER HOUSING — large backlit rectangular panels (cyan + purple stabilization arc) */}
        {bigPanels.map((p, i) => (
          <group key={`bp${i}`} position={[p.x, p.y, 0.0]} rotation={[0, 0, p.a]}>
            <mesh><boxGeometry args={[0.5, 0.34, 0.06]} /><meshStandardMaterial color={TITANIUM} metalness={0.95} roughness={0.4} /></mesh>
            <mesh position={[0, 0, 0.04]}><boxGeometry args={[0.42, 0.26, 0.02]} /><meshStandardMaterial color="#000000" emissive={p.stab ? C_STABIL : C_COOLING} emissiveIntensity={1.7} toneMapped={false} /></mesh>
            {/* dark grid dividers so the panel reads as a backlit LED grid */}
            <mesh position={[0, 0, 0.06]}><boxGeometry args={[0.42, 0.02, 0.01]} /><meshStandardMaterial color={TITANIUM} metalness={0.9} roughness={0.5} /></mesh>
            <mesh position={[-0.1, 0, 0.06]}><boxGeometry args={[0.02, 0.26, 0.01]} /><meshStandardMaterial color={TITANIUM} metalness={0.9} roughness={0.5} /></mesh>
            <mesh position={[0.1, 0, 0.06]}><boxGeometry args={[0.02, 0.26, 0.01]} /><meshStandardMaterial color={TITANIUM} metalness={0.9} roughness={0.5} /></mesh>
          </group>
        ))}

        {/* COOLING VENTS — 2-row cyan LED grid (active heat dissipation, pulsing) */}
        <group ref={coolRef}>
          {cooling.map((p, i) => (
            <mesh key={`cv${i}`} position={[p.x, p.y, p.z]} rotation={[0, 0, p.a]}>
              <boxGeometry args={[0.05, 0.08, 0.03]} />
              <meshStandardMaterial color="#000000" emissive={C_COOLING} emissiveIntensity={2.4} toneMapped={false} />
            </mesh>
          ))}
        </group>

        {/* density: small cyan/white indicator LEDs packed across the mid tiers */}
        {indic.map((p, i) => (
          <mesh key={`in${i}`} position={[p.x, p.y, p.z]} rotation={[0, 0, p.a]}>
            <boxGeometry args={[0.035, 0.035, 0.025]} />
            <meshStandardMaterial color="#000000" emissive={p.white ? C_EMITTER : C_COOLING} emissiveIntensity={p.white ? 2.6 : 1.8} toneMapped={false} />
          </mesh>
        ))}

        {/* POWER CORE CHANNELS (blue conduits) + STABILIZATION arc (purple) */}
        {power.map((p, i) => (
          <mesh key={`pc${i}`} position={[p.x, p.y, -0.54]} rotation={[0, 0, p.a]}>
            <boxGeometry args={[0.06, 0.22, 0.03]} />
            <meshStandardMaterial color="#000000" emissive={p.stab ? C_STABIL : C_POWER} emissiveIntensity={2.7} toneMapped={false} />
          </mesh>
        ))}

        {/* MAGNETIC LOCKS — large amber 2x2 anchor grids (structural anchors) */}
        {maglocks.map((p, i) => (
          <group key={`ml${i}`} position={[p.x, p.y, -0.54]} rotation={[0, 0, p.a]}>
            <mesh><boxGeometry args={[0.3, 0.42, 0.08]} /><meshStandardMaterial color="#1a1206" metalness={0.9} roughness={0.4} /></mesh>
            {mlCells.map(([cx, cy], j) => (
              <mesh key={j} position={[cx, cy, 0.05]}><boxGeometry args={[0.1, 0.13, 0.03]} /><meshStandardMaterial color="#000000" emissive={C_MAGLOCK} emissiveIntensity={2.9} toneMapped={false} /></mesh>
            ))}
          </group>
        ))}

        {/* INNER ACCENT / DIAGNOSTIC LEDs — indigo status dots (bigger, near the lens) */}
        {accents.map((p, i) => (
          <mesh key={`ac${i}`} position={[p.x, p.y, -0.92]} rotation={[0, 0, p.a]}>
            <boxGeometry args={[0.06, 0.06, 0.03]} />
            <meshStandardMaterial color="#000000" emissive={C_ACCENT} emissiveIntensity={2.4} toneMapped={false} />
          </mesh>
        ))}

        {/* thin lit seams between tiers (read the dome depth) */}
        <mesh position={[0, 0, -0.25]}><torusGeometry args={[2.0, 0.01, 8, 90]} /><meshBasicMaterial color={C_COOLING} transparent opacity={0.45} blending={THREE.AdditiveBlending} /></mesh>
        <mesh position={[0, 0, -0.44]}><torusGeometry args={[1.74, 0.01, 8, 90]} /><meshBasicMaterial color={C_POWER} transparent opacity={0.5} blending={THREE.AdditiveBlending} /></mesh>
        <mesh position={[0, 0, -0.66]}><torusGeometry args={[1.46, 0.01, 8, 90]} /><meshBasicMaterial color={C_BEAM_VOL} transparent opacity={0.5} blending={THREE.AdditiveBlending} /></mesh>
        <mesh position={[0, 0, -0.88]}><torusGeometry args={[1.18, 0.01, 8, 90]} /><meshBasicMaterial color={C_BEAM_CORE} transparent opacity={0.55} blending={THREE.AdditiveBlending} /></mesh>
      </group>

      {/* ===== HOLOGRAPHIC LENS ARRAY — deep multi-layer focusing spiral (spinning) ===== */}
      <group ref={lens} position={[0, 0, -1.12]}>
        {lensRings.map((r, i) => (
          <mesh key={`ln${i}`} position={[0, 0, i * 0.045]}>
            <torusGeometry args={[r, 0.01 + i * 0.003, 8, 80]} />
            <meshBasicMaterial color={C_LENS} transparent opacity={0.9 - i * 0.1} blending={THREE.AdditiveBlending} depthWrite={false} />
          </mesh>
        ))}
      </group>

      {/* ===== PRIMARY EMITTER EYE — holographic projection source (intense white) ===== */}
      <group position={[0, 0, -1.26]}>
        {/* lens housing ring (dark titanium) */}
        <mesh><torusGeometry args={[0.5, 0.12, 16, 48]} /><meshStandardMaterial color={TITANIUM} metalness={0.96} roughness={0.3} /></mesh>
        {/* soft cyan flare = the glowing mouth */}
        <mesh position={[0, 0, -0.16]}><circleGeometry args={[0.62, 48]} /><meshBasicMaterial color={C_BEAM_CORE} transparent opacity={0.45} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        {/* bright core ring */}
        <mesh position={[0, 0, -0.13]}><ringGeometry args={[0.26, 0.36, 64]} /><meshBasicMaterial color={C_LENS} transparent opacity={0.95} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} /></mesh>
        {/* intense white pupil = projection source */}
        <mesh ref={pupil} position={[0, 0, -0.14]}><circleGeometry args={[0.28, 48]} /><meshBasicMaterial color={C_EMITTER} transparent opacity={0.95} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        {/* emitter light thrown onto the beam particles below */}
        <pointLight position={[0, 0, -0.2]} intensity={5} distance={5} decay={2} color={C_BEAM_CORE} />
      </group>
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

// --- Subtle cinematic camera drift/sway (eased) so the whole scene breathes ---
function CameraRig() {
  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    const cam = state.camera;
    cam.position.x += (Math.sin(t * 0.16) * 0.4 - cam.position.x) * 0.02;
    cam.position.y += (1.2 + Math.sin(t * 0.22) * 0.18 - cam.position.y) * 0.02;
    cam.lookAt(0, 0.95, -2.0);
  });
  return null;
}

// --- Real 3D hex cards: extruded glass-metal meshes with emissive neon rim + 3D text,
// rotating in true perspective. Click opens the (HTML) detail drawer. ---
const HEX_SHAPE = (() => {
  const w = 0.74, h = 0.8;
  const s = new THREE.Shape();
  s.moveTo(-w, 0); s.lineTo(-w * 0.5, h); s.lineTo(w * 0.5, h); s.lineTo(w, 0);
  s.lineTo(w * 0.5, -h); s.lineTo(-w * 0.5, -h); s.closePath();
  return s;
})();
const HEX_GEO = new THREE.ExtrudeGeometry(HEX_SHAPE, {
  depth: 0.16, bevelEnabled: true, bevelThickness: 0.05, bevelSize: 0.05, bevelSegments: 2,
});

function Card3DItem({ card, onSelect, active }: { card: Card3DData; onSelect?: (id: string) => void; active: boolean }) {
  const ref = useRef<THREE.Group>(null);
  const [hover, setHover] = useState(false);
  const phase = useMemo(() => Math.random() * 6, []);
  useFrame(({ clock }) => {
    if (!ref.current) return;
    ref.current.rotation.y = Math.sin(clock.getElapsedTime() * 0.5 + phase) * 0.35; // real 3D turn
    const target = active || hover ? 1.14 : 1.0;
    const s = ref.current.scale.x + (target - ref.current.scale.x) * 0.15;
    ref.current.scale.set(s, s, s);
  });
  const lit = hover || active;
  return (
    <group ref={ref} position={card.pos}>
      {/* OUTER border layer: a slightly larger black plate set behind → reads as a frame/bezel */}
      <mesh geometry={HEX_GEO} position={[0, 0, -0.07]} scale={1.07}>
        <meshStandardMaterial color="#04070d" metalness={0.6} roughness={0.5} transparent opacity={0.9} depthWrite={false} />
      </mesh>
      <mesh
        geometry={HEX_GEO}
        onClick={(e) => { e.stopPropagation(); onSelect?.(card.id); }}
        onPointerOver={(e) => { e.stopPropagation(); setHover(true); document.body.style.cursor = "pointer"; }}
        onPointerOut={() => { setHover(false); document.body.style.cursor = "auto"; }}
      >
        {/* PURE-BLACK transparent glass — NO color of its own. ONLY the LED edges give it color. */}
        <meshStandardMaterial
          color="#000000"
          emissive="#000000"
          emissiveIntensity={0}
          metalness={0.25}
          roughness={0.5}
          transparent
          opacity={lit ? 0.5 : 0.42}
          depthWrite={false}
        />
      </mesh>
      {/* OUTER neon edge on the bezel plate → the double-frame reads as inner + outer border */}
      <lineSegments position={[0, 0, -0.07]} scale={1.07}>
        <edgesGeometry args={[HEX_GEO]} />
        <lineBasicMaterial color={card.accent} transparent opacity={lit ? 0.6 : 0.4} blending={THREE.AdditiveBlending} />
      </lineSegments>
      {/* bright neon-LED edges (blooms hard → spills light onto the black glass) */}
      <lineSegments>
        <edgesGeometry args={[HEX_GEO]} />
        <lineBasicMaterial color={card.accent} transparent opacity={1} blending={THREE.AdditiveBlending} />
      </lineSegments>
      <lineSegments scale={1.012}>
        <edgesGeometry args={[HEX_GEO]} />
        <lineBasicMaterial color={card.accent} transparent opacity={0.7} blending={THREE.AdditiveBlending} />
      </lineSegments>
      {/* holographic edge scattering: a faint over-scaled edge that bleeds outward */}
      <lineSegments scale={lit ? 1.05 : 1.03}>
        <edgesGeometry args={[HEX_GEO]} />
        <lineBasicMaterial color={card.accent} transparent opacity={lit ? 0.32 : 0.16} blending={THREE.AdditiveBlending} />
      </lineSegments>
      <Text position={[0, 0.12, 0.26]} fontSize={0.12} maxWidth={1.15} textAlign="center" anchorX="center" anchorY="middle" color="#ffffff" outlineWidth={0.004} outlineColor={card.accent}>
        {card.title}
      </Text>
      <Text position={[0, -0.2, 0.26]} fontSize={0.08} anchorX="center" anchorY="middle" color={card.accent}>
        {card.state}
      </Text>
      <Text position={[0, -0.36, 0.26]} fontSize={0.058} letterSpacing={0.08} anchorX="center" anchorY="middle" color="#7c8b9c">
        {card.maturity.toUpperCase()}
      </Text>
    </group>
  );
}

function Cards3D({ cards, onSelect, activeId }: { cards: Card3DData[]; onSelect?: (id: string) => void; activeId?: string | null }) {
  return <group>{cards.map((c) => <Card3DItem key={c.id} card={c} onSelect={onSelect} active={activeId === c.id} />)}</group>;
}

// --- floating atmospheric dust / fragments drifting through the chamber ---
function DustField() {
  const geo = useMemo(() => {
    const arr: number[] = [];
    for (let i = 0; i < 240; i++) {
      arr.push((Math.random() - 0.5) * 18, (Math.random() - 0.5) * 12, (Math.random() - 0.5) * 12 - 2);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(arr, 3));
    return g;
  }, []);
  useEffect(() => () => geo.dispose(), [geo]);
  const ref = useRef<THREE.Points>(null);
  useFrame(({ clock }) => {
    if (ref.current) {
      const t = clock.getElapsedTime();
      ref.current.rotation.y = t * 0.012;
      ref.current.position.y = Math.sin(t * 0.1) * 0.2;
    }
  });
  return (
    <points ref={ref} geometry={geo}>
      <pointsMaterial color="#86bfe6" size={0.028} sizeAttenuation transparent opacity={0.45} blending={THREE.AdditiveBlending} depthWrite={false} />
    </points>
  );
}

function EarthScene({ audioIntensity = 0, capture = false, showPillars = true, cards3d, onSelectCard, activeCardId }: EarthProps) {
  return (
    <>
      {/* depth fog: pushes the floor + far rim into the dark so the chamber reads deep */}
      <fogExp2 attach="fog" args={["#03060e", 0.034]} />
      {/* even, bright key illumination so the visible hemisphere reads as real Earth */}
      <hemisphereLight args={["#eaf7ff", "#0a2740", 1.35]} />
      <ambientLight intensity={0.55} />
      <pointLight position={[3, 2.5, 7]} intensity={3.2} color="#f2faff" />
      {/* softened top light so it reads as projector beams, not a bright white blob */}
      <pointLight position={[0, 6, 1.5]} intensity={0.8} color="#ffffff" />
      {/* cool rim light from behind to carve the globe silhouette out of the dark */}
      <pointLight position={[-4, 1.5, -6]} intensity={2.4} color="#2f9bff" />

      {!capture && <CameraRig />}
      <Suspense fallback={<FallbackGlobe />}>
        <TexturedEarth ai={audioIntensity} />
      </Suspense>
      <Atmosphere ai={audioIntensity} />
      <TopProjector />
      <LightBeam />
      <ReflectiveFloor />
      <HexFloor ai={audioIntensity} />
      {showPillars && <FloorBeams ai={audioIntensity} />}
      <ArcLines ai={audioIntensity} />
      <DustField />
      {cards3d && cards3d.length > 0 && <Cards3D cards={cards3d} onSelect={onSelectCard} activeId={activeCardId} />}

      {/* Capture mode: a single lightweight Bloom so screenshots still show the glow
          (fast on the demand frameloop). Normal mode: full cinematic chain. */}
      {capture ? (
        <EffectComposer multisampling={0} frameBufferType={THREE.HalfFloatType}>
          <Bloom intensity={1.25} luminanceThreshold={0.42} luminanceSmoothing={0.9} radius={0.7} mipmapBlur />
        </EffectComposer>
      ) : (
        <EffectComposer multisampling={0} frameBufferType={THREE.HalfFloatType}>
          <SMAA />
          {/* bright emissive cores cross this threshold → they bloom into light, not stripes */}
          <Bloom
            intensity={1.45 + audioIntensity * 0.8}
            luminanceThreshold={0.42}
            luminanceSmoothing={0.9}
            radius={0.78}
            mipmapBlur
          />
          {/* color grade: punchier neon-blue "trailer" look */}
          <HueSaturation saturation={0.3} />
          <BrightnessContrast brightness={0.03} contrast={0.15} />
          {/* faint holographic grain (uses the effect's default blend) */}
          <Noise premultiply opacity={0.045} />
          <Vignette offset={0.3} darkness={0.74} />
        </EffectComposer>
      )}
    </>
  );
}

export default function HolographicEarth3D({ audioIntensity = 0, capture = false, showPillars = true, cards3d, onSelectCard, activeCardId }: EarthProps) {
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
      camera={{ position: [0, 1.2, 6.05], fov: 47 }}
      dpr={capture ? 2.5 : [1, 1.5]}
      frameloop={capture ? "demand" : "always"}
      gl={{ antialias: false, alpha: true, powerPreference: "high-performance" }}
      onCreated={({ gl, camera }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping;
        gl.toneMappingExposure = 1.55;
        camera.lookAt(0, 0.95, -2.0); // closer on the globe, still framing the engine + beams above
      }}
      style={{ background: "transparent" }}
    >
      <EarthScene audioIntensity={audioIntensity} capture={capture} showPillars={showPillars} cards3d={cards3d} onSelectCard={onSelectCard} activeCardId={activeCardId} />
    </Canvas>
  );
}
