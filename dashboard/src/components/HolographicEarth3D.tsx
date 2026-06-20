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
  glyph: string;      // monogram/icon shown in the badge
  subtitle: string;   // what it connects (e.g. "Stripe / PayPal / custom")
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
// how much higher the projector + its beam origin sit, so the top half of the dome
// crops off the top of the frame (only the lower half + emitter show)
const PROJ_RAISE = 1.3;

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

function atmoMat(color: string, power: number, strength: number, side: THREE.Side = THREE.BackSide) {
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
    side,
    depthWrite: false,
  });
}

// A REALLY thin neon-blue rim hugging the limb (high power = concentrated at the edge),
// plus a barely-there soft edge so it isn't a hard line. No fat halo.
function Atmosphere({ ai = 0 }: { ai?: number }) {
  // 01 ATMOSPHERE GLOW — thin #00E6FF rim, strong edge scattering, fades into space
  const rim = useMemo(() => atmoMat("#00e6ff", 7.0, 0.32), []);
  const soft = useMemo(() => atmoMat("#00c6ff", 4.0, 0.05), []);
  // 02 HOLOGRAPHIC SHELL — ultra-thin #00C6FF refractive energy shell (~15%), seen from outside
  const shell = useMemo(() => atmoMat("#00c6ff", 3.2, 0.15, THREE.FrontSide), []);
  useEffect(() => () => { rim.dispose(); soft.dispose(); shell.dispose(); }, [rim, soft, shell]);
  useFrame(() => {
    rim.uniforms.uStrength.value = 0.3 + ai * 0.12;   // thin but clearly-read blue rim
    shell.uniforms.uStrength.value = 0.13 + ai * 0.05;
  });
  return (
    <group position={GLOBE_POS}>
      {/* 02 holographic energy shell (ultra-thin, just outside the surface) */}
      <mesh>
        <sphereGeometry args={[EARTH_R * 1.018, 64, 64]} />
        <primitive object={shell} attach="material" />
      </mesh>
      {/* 01 atmosphere glow rim */}
      <mesh>
        <sphereGeometry args={[EARTH_R * 1.012, 64, 64]} />
        <primitive object={rim} attach="material" />
      </mesh>
      <mesh>
        <sphereGeometry args={[EARTH_R * 1.045, 48, 48]} />
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
          // cheap per-pixel hash for the city-light twinkle
          float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
          void main() {
            vec3 rawDay = texture2D(dayMap, vUv).rgb;
            vec3 night = texture2D(nightMap, vUv).rgb;
            // ocean mask: land reads green/brown (high R/G), ocean is darker
            float landish = max(rawDay.r, rawDay.g * 0.9);
            float oceanMask = 1.0 - smoothstep(0.16, 0.40, landish);

            // 06 OCEAN DEPTH — dark navy (#001A33) deep → blue (#003366) shallow, by ocean luminance
            float oceanLum = clamp((rawDay.b * 0.6 + rawDay.g * 0.4) * 2.2, 0.0, 1.0);
            vec3 oceanCol = mix(vec3(0.0, 0.102, 0.2), vec3(0.0, 0.2, 0.4), smoothstep(0.05, 0.5, oceanLum));
            // 04 SURFACE (DAY) — sharper: crisp contrast + boosted saturation
            vec3 landCol = rawDay * 1.65 + vec3(0.015, 0.02, 0.025);
            landCol = (landCol - 0.5) * 1.16 + 0.5;                  // crisp local contrast
            float lum = dot(landCol, vec3(0.299, 0.587, 0.114));
            landCol = mix(vec3(lum), landCol, 1.2);                  // richer, more alive color
            vec3 day = mix(landCol, oceanCol, oceanMask);

            float d = dot(normalize(vNormalW), normalize(sunDir));
            float mixf = smoothstep(-0.25, 0.30, d);                 // day/night blend

            // 05 CITY LIGHTS (NIGHT) — warm amber, brighter + a living twinkle so the dark side feels alive
            float nb = max(night.r, max(night.g, night.b));
            float twinkle = 0.78 + 0.22 * sin(uTime * 2.2 + hash(vUv) * 42.0);
            vec3 cityCol = mix(vec3(1.0, 0.835, 0.416), vec3(1.0, 0.6, 0.0), smoothstep(0.2, 0.85, nb));
            vec3 cityLights = cityCol * nb * 4.6 * twinkle;          // bright glow → blooms hard

            // dark side: faint continents stay visible in the shadow + bright living city lights
            vec3 nightBase = day * 0.05;
            vec3 nightSide = nightBase + cityLights;
            vec3 col = mix(nightSide, day, mixf);

            // warm terminator (sunset band) along the day/night boundary → life on the limb
            float term = smoothstep(0.0, 0.32, mixf) * (1.0 - smoothstep(0.32, 0.72, mixf));
            col += term * vec3(0.26, 0.12, 0.04);

            // 03 CLOUD LAYER — soft white clouds, lit by the sun (locked to surface UV → rotate WITH Earth)
            float cloud = texture2D(cloudMap, vUv).r;
            float cAmt = smoothstep(0.55, 0.98, cloud) * (0.22 + 0.55 * mixf);
            col = mix(col, vec3(1.0), cAmt * 0.55);
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

        {/* 07 HOLOGRAPHIC GRID — lat/long lines, #00D9FF, faint (~15%), conforms to curvature */}
        <mesh scale={1.005}>
          <sphereGeometry args={[EARTH_R, 36, 18]} />
          <meshBasicMaterial color="#00d9ff" wireframe transparent opacity={0.13 + ai * 0.04} blending={THREE.AdditiveBlending} depthWrite={false} />
        </mesh>

        {/* 08 DATA POINTS — pulsing scanning nodes at strategic cities */}
        <DataPoints />
      </group>
    </group>
  );
}

// 09 HOLOGRAPHIC BASE RING — projection anchor ring under the globe with rotating segments
function BaseRing() {
  const seg = useRef<THREE.Group>(null);
  const segs = useMemo(() => Array.from({ length: 28 }, (_, i) => (i / 28) * Math.PI * 2), []);
  useFrame(({ clock }) => { if (seg.current) seg.current.rotation.y = clock.getElapsedTime() * 0.22; });
  const y = GLOBE_POS[1] - EARTH_R - 0.12;        // just below the globe
  const R = EARTH_R * 0.92;
  return (
    <group position={[GLOBE_POS[0], y, GLOBE_POS[2]]}>
      {/* static anchor rings */}
      <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[R, 0.02, 8, 120]} /><meshBasicMaterial color="#00e6ff" transparent opacity={0.55} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[R * 1.18, 0.01, 8, 120]} /><meshBasicMaterial color="#00e6ff" transparent opacity={0.3} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[R * 0.74, 0.008, 8, 96]} /><meshBasicMaterial color="#00e6ff" transparent opacity={0.25} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
      {/* rotating segment ticks */}
      <group ref={seg}>
        {segs.map((a, i) => (
          <mesh key={i} position={[Math.cos(a) * R * 1.06, 0, Math.sin(a) * R * 1.06]} rotation={[0, -a, 0]}>
            <boxGeometry args={[0.11, 0.014, 0.02]} />
            <meshBasicMaterial color="#66f9ff" transparent opacity={0.75} blending={THREE.AdditiveBlending} depthWrite={false} />
          </mesh>
        ))}
      </group>
    </group>
  );
}

// 08 DATA POINTS — strategic nodes that PULSE (not blink); #00E6FF -> #66F9FF, glow + bloom
function DataPoints() {
  const grp = useRef<THREE.Group>(null);
  const pts = useMemo(() => CITIES.map((c, i) => ({ pos: latLonToVec3(c.lat, c.lon, EARTH_R * 1.012), phase: i * 0.7 })), []);
  useFrame(({ clock }) => {
    if (!grp.current) return;
    const t = clock.getElapsedTime();
    grp.current.children.forEach((c, i) => {
      const m = c as THREE.Mesh;
      const p = 0.5 + 0.5 * Math.sin(t * 1.8 + pts[i].phase);  // smooth pulse, never a hard blink
      m.scale.setScalar(0.7 + p * 0.7);
      (m.material as THREE.MeshBasicMaterial).opacity = 0.35 + p * 0.55;
    });
  });
  return (
    <group ref={grp}>
      {pts.map((pt, i) => (
        <mesh key={i} position={pt.pos}>
          <sphereGeometry args={[0.02, 12, 12]} />
          <meshBasicMaterial color="#4df2ff" transparent opacity={0.8} blending={THREE.AdditiveBlending} depthWrite={false} />
        </mesh>
      ))}
    </group>
  );
}

// --- Projector beams: THIN, crisp, well-defined light shafts converging on the globe top
// (sharp — NOT a wide washed-out wall of light). Each beam = a faint narrow halo + a
// bright defined core. ---
function LightBeam() {
  // Emitter at the projector's mouth; many THIN sharp neon rays fan down onto the globe.
  const apex = useMemo(() => new THREE.Vector3(GLOBE_POS[0], GLOBE_POS[1] + 2.6 + PROJ_RAISE, GLOBE_POS[2]), []);

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

  // ENERGY PARTICLE FLOW — fine, dense subatomic "data rain" streaming down the beam
  const sparkGeo = useMemo(() => {
    const arr: number[] = [];
    for (let i = 0; i < 340; i++) {
      const t = Math.random();
      const a = Math.random() * Math.PI * 2;
      const r = t * 1.45;                                 // fans out toward the globe
      arr.push(GLOBE_POS[0] + Math.cos(a) * r, GLOBE_POS[1] + 2.6 + PROJ_RAISE - t * (1.9 + PROJ_RAISE), GLOBE_POS[2] + Math.sin(a) * r);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(arr, 3));
    return g;
  }, []);
  useEffect(() => () => sparkGeo.dispose(), [sparkGeo]);

  // central wide volumetric projection shaft: the single soft cone of light that
  // visibly carries the Earth hologram up to the emitter mouth.
  const shaftH = GLOBE_POS[1] + 2.6 + PROJ_RAISE - (GLOBE_POS[1] - 0.4);
  const shaftY = (GLOBE_POS[1] + 2.6 + PROJ_RAISE + (GLOBE_POS[1] - 0.4)) / 2;

  // crisp vertical DATA LANES — straight bright lines structuring the beam (clean, not fuzzy)
  const lanes = useMemo(() => {
    const out: { pos: [number, number, number]; quat: [number, number, number, number]; h: number }[] = [];
    const up = new THREE.Vector3(0, 1, 0);
    const top = new THREE.Vector3(GLOBE_POS[0], GLOBE_POS[1] + 2.5 + PROJ_RAISE, GLOBE_POS[2]);
    const N = 16;
    for (let i = 0; i < N; i++) {
      const a = (i / N) * Math.PI * 2;
      const r = 0.55 + (i % 2) * 0.18;
      const end = new THREE.Vector3(GLOBE_POS[0] + Math.cos(a) * r, GLOBE_POS[1] + 0.9, GLOBE_POS[2] + Math.sin(a) * r);
      const mid = top.clone().add(end).multiplyScalar(0.5);
      const dir = top.clone().sub(end).normalize();
      const q = new THREE.Quaternion().setFromUnitVectors(up, dir);
      out.push({ pos: [mid.x, mid.y, mid.z], quat: [q.x, q.y, q.z, q.w], h: top.distanceTo(end) });
    }
    return out;
  }, []);

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
      scan.current.position.y = GLOBE_POS[1] + 2.4 + PROJ_RAISE - p * (2.1 + PROJ_RAISE);
      scan.current.scale.setScalar(0.5 + p * 1.7);
      (scan.current.material as THREE.MeshBasicMaterial).opacity = 0.7 * (1 - p);
    }
    // DATA STREAM — horizontal scan rings continuously descend + fan out through the beam
    if (stream.current) stream.current.children.forEach((c, i) => {
      const m = c as THREE.Mesh;
      const p = (t * 0.3 + i / STREAM_N) % 1;
      m.position.y = GLOBE_POS[1] + 2.45 + PROJ_RAISE - p * (1.75 + PROJ_RAISE);
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
      {/* crisp vertical DATA LANES — straight bright lines that structure the beam */}
      {lanes.map((b, i) => (
        <mesh key={`la${i}`} position={b.pos} quaternion={b.quat}>
          <cylinderGeometry args={[0.004, 0.004, b.h, 5, 1, true]} />
          <meshBasicMaterial color={C_BEAM_CORE} transparent opacity={0.55} blending={THREE.AdditiveBlending} depthWrite={false} />
        </mesh>
      ))}
      {/* ENERGY PARTICLE FLOW — fine, dense data-rain particles streaming down the beam */}
      <points geometry={sparkGeo}>
        <pointsMaterial color={C_PARTICLE} size={0.038} sizeAttenuation transparent opacity={0.95} blending={THREE.AdditiveBlending} depthWrite={false} />
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
const TITANIUM = "#3a434f";       // OUTER HOUSING — machined gunmetal titanium (lifted so detail reads)
const TITANIUM_RIB = "#93a2b6";   // raised machined panel ribs (bright → read clearly even small)
const RIB_GLOW = "#8fb4e6";       // faint cool edge-glow on the ribs so the paneling blooms slightly
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
  // ENGRAVED PANEL GRID — radial seam bars running along the slope of each dome wall,
  // so every tier reads as machined plates divided by recessed grooves.
  const panelSeams = useMemo(() => {
    const up = new THREE.Vector3(0, 1, 0);
    const out: { pos: [number, number, number]; quat: [number, number, number, number]; len: number }[] = [];
    frusta.slice(0, 4).forEach((f) => {                 // the 4 largest, most-visible walls
      const zTop = f.z + f.h / 2, zBot = f.z - f.h / 2;
      const N = 18;                                     // fewer → larger, clearly-read panels
      for (let i = 0; i < N; i++) {
        const a = (i / N) * Math.PI * 2;
        const k = 1.02;                                 // raised ridge proud of the wall (catches light)
        const Pt = new THREE.Vector3(Math.cos(a) * f.rTop * k, Math.sin(a) * f.rTop * k, zTop);
        const Pb = new THREE.Vector3(Math.cos(a) * f.rBot * k, Math.sin(a) * f.rBot * k, zBot);
        const mid = Pt.clone().add(Pb).multiplyScalar(0.5);
        const dir = Pt.clone().sub(Pb).normalize();
        const q = new THREE.Quaternion().setFromUnitVectors(up, dir);
        out.push({ pos: [mid.x, mid.y, mid.z], quat: [q.x, q.y, q.z, q.w], len: Pt.distanceTo(Pb) });
      }
    });
    return out;
  }, [frusta]);
  // concentric raised rib rings (horizontal panel divisions) at each wall mid-line
  const grooves = useMemo(() => frusta.map((f) => ({ r: (f.rTop + f.rBot) / 2 * 1.016, z: f.z })), [frusta]);
  // bolt / rivet heads ringing several tiers
  const rivets = useMemo(() => {
    const out: { x: number; y: number; z: number }[] = [];
    const bands = [{ r: 2.33, z: 0.02 }, { r: 2.0, z: -0.2 }, { r: 1.7, z: -0.42 }];
    bands.forEach((b) => { const N = 40; for (let i = 0; i < N; i++) { const a = (i / N) * Math.PI * 2 + 0.04; out.push({ x: Math.cos(a) * b.r, y: Math.sin(a) * b.r, z: b.z }); } });
    return out;
  }, [frusta]);
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
    <group position={[GLOBE_POS[0], GLOBE_POS[1] + 3.92 + PROJ_RAISE, GLOBE_POS[2]]} rotation={[-Math.PI / 2, 0, 0]} scale={1.05}>
      {/* internal lights that REVEAL the machined titanium (it is lit, not self-glowing) */}
      <pointLight position={[0, 0, -1.2]} intensity={9} distance={7} decay={2} color={C_BEAM_CORE} />
      <pointLight position={[0, 0, -0.5]} intensity={4} distance={5} decay={2} color={C_POWER} />
      {/* bright cool rim lights so the machined titanium + panel detail clearly READ as metal */}
      <pointLight position={[2.8, 2.0, -1.4]} intensity={5} distance={11} decay={2} color="#cfe2ff" />
      <pointLight position={[-2.8, -2.0, -1.4]} intensity={4.2} distance={11} decay={2} color="#9ec6ff" />
      <pointLight position={[0, 0, 1.4]} intensity={3} distance={9} decay={2} color="#acd0ff" />
      {/* soft fill so the dome surface never crushes to pure black */}
      <hemisphereLight args={["#9fc4ff", "#11161f", 0.7]} />
      <group ref={grp}>
        {/* === SOLID machined dome walls between tiers (closed titanium bowl) === */}
        {frusta.map((f, i) => (
          <mesh key={`fr${i}`} position={[0, 0, f.z]} rotation={[-Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[f.rTop, f.rBot, f.h, 72, 1, true]} />
            <meshStandardMaterial color={TITANIUM} metalness={0.62} roughness={0.42} side={THREE.DoubleSide} />
          </mesh>
        ))}
        {/* RAISED radial PANEL RIBS running along every dome wall (machined plate dividers
            with a faint cool edge-glow → the paneling reads even at small scale) */}
        {panelSeams.map((s, i) => (
          <mesh key={`ps${i}`} position={s.pos} quaternion={s.quat}>
            <boxGeometry args={[0.05, s.len * 0.98, 0.085]} />
            <meshStandardMaterial color={TITANIUM_RIB} metalness={0.85} roughness={0.28} emissive={RIB_GLOW} emissiveIntensity={0.8} />
          </mesh>
        ))}
        {/* concentric raised RIB rings (horizontal panel divisions) */}
        {grooves.map((g, i) => (
          <mesh key={`gv${i}`} position={[0, 0, g.z]}>
            <torusGeometry args={[g.r, 0.032, 8, 96]} />
            <meshStandardMaterial color={TITANIUM_RIB} metalness={0.85} roughness={0.3} emissive={RIB_GLOW} emissiveIntensity={0.85} />
          </mesh>
        ))}
        {/* RIVET / bolt heads ringing several tiers */}
        {rivets.map((p, i) => (
          <mesh key={`rv${i}`} position={[p.x, p.y, p.z + 0.05]}>
            <sphereGeometry args={[0.024, 8, 8]} />
            <meshStandardMaterial color="#7a8696" metalness={0.85} roughness={0.3} />
          </mesh>
        ))}
        {/* === DEEP tiered TITANIUM housing rings (raised machined lips on the walls) === */}
        {tiers.map((rg, i) => (
          <mesh key={i} position={[0, 0, rg.z]}>
            <torusGeometry args={[rg.r, rg.w, 16, 72]} />
            <meshStandardMaterial color={TITANIUM} metalness={0.7} roughness={0.34} />
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

      {/* ===== PRIMARY EMITTER EYE — holographic projection source (intense white, strong glow) ===== */}
      <group position={[0, 0, -1.26]}>
        {/* lens housing ring (machined titanium) */}
        <mesh><torusGeometry args={[0.5, 0.12, 16, 48]} /><meshStandardMaterial color={TITANIUM} metalness={0.7} roughness={0.3} /></mesh>
        {/* wide soft glow halo — feeds the bloom so the eye reads as a powerful light source */}
        <mesh position={[0, 0, -0.2]}><circleGeometry args={[0.95, 56]} /><meshBasicMaterial color={C_BEAM_VOL} transparent opacity={0.32} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        {/* mid cyan flare = the glowing mouth */}
        <mesh position={[0, 0, -0.17]}><circleGeometry args={[0.62, 48]} /><meshBasicMaterial color={C_BEAM_CORE} transparent opacity={0.6} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        {/* bright core ring */}
        <mesh position={[0, 0, -0.14]}><ringGeometry args={[0.26, 0.38, 64]} /><meshBasicMaterial color={C_LENS} transparent opacity={1} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} /></mesh>
        {/* intense white pupil = projection source (over-bright → blooms hard) */}
        <mesh position={[0, 0, -0.145]}><circleGeometry args={[0.34, 48]} /><meshBasicMaterial color={C_EMITTER} transparent opacity={0.85} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        <mesh ref={pupil} position={[0, 0, -0.15]}><circleGeometry args={[0.2, 48]} /><meshBasicMaterial color={C_EMITTER} transparent opacity={1} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        {/* emitter light thrown onto the beam particles below */}
        <pointLight position={[0, 0, -0.2]} intensity={6} distance={5} decay={2} color={C_BEAM_CORE} />
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
// the 6 hex vertices (for the bright connector nodes at each corner)
const HEX_VERTS: [number, number][] = [
  [-0.74, 0], [-0.37, 0.8], [0.37, 0.8], [0.74, 0], [0.37, -0.8], [-0.37, -0.8],
];

function Card3DItem({ card, onSelect, active }: { card: Card3DData; onSelect?: (id: string) => void; active: boolean }) {
  const ref = useRef<THREE.Group>(null);
  const dot = useRef<THREE.Mesh>(null);
  const sheen = useRef<THREE.Mesh>(null);
  const badge = useRef<THREE.Group>(null);
  const border = useRef<THREE.LineBasicMaterial>(null);
  const glow = useRef<THREE.MeshBasicMaterial>(null);
  const [hover, setHover] = useState(false);
  const phase = useMemo(() => Math.random() * 6, []);
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (ref.current) {
      ref.current.rotation.y = Math.sin(t * 0.5 + phase) * 0.32;          // real 3D turn
      const target = active || hover ? 1.16 : 1.0;
      const s = ref.current.scale.x + (target - ref.current.scale.x) * 0.15;
      ref.current.scale.set(s, s, s);
      const zT = active || hover ? 0.35 : 0.0;                            // lift toward camera on hover
      ref.current.position.z += (card.pos[2] + zT - ref.current.position.z) * 0.15;
    }
    if (dot.current) (dot.current.material as THREE.MeshBasicMaterial).opacity = 0.45 + 0.55 * (0.5 + 0.5 * Math.sin(t * 2.4 + phase)); // pulse, not blink
    if (badge.current) badge.current.rotation.z = t * 0.25;              // slow optic spin on the badge ring
    if (sheen.current) {                                                  // holographic sheen sweeping down the glass
      const p = (t * 0.35 + phase) % 1;
      sheen.current.position.y = 0.7 - p * 1.4;
      (sheen.current.material as THREE.MeshBasicMaterial).opacity = 0.12 * Math.sin(p * Math.PI);
    }
    if (border.current) border.current.opacity = 0.86 + 0.14 * Math.sin(t * 1.6 + phase); // border breathes
    if (glow.current) {                                                   // soft back-halo, stronger on hover
      const target = (active || hover) ? 0.16 : 0.05;
      glow.current.opacity += (target - glow.current.opacity) * 0.1;
    }
  });
  const lit = hover || active;
  return (
    <group ref={ref} position={card.pos}>
      {/* soft accent back-halo so the card pops from the dark (depth glow) */}
      <mesh geometry={HEX_GEO} position={[0, 0, -0.16]} scale={1.2}>
        <meshBasicMaterial ref={glow} color={card.accent} transparent opacity={0.05} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      {/* OUTER frame plate (bezel) set behind → reads as the outer hex border */}
      <mesh geometry={HEX_GEO} position={[0, 0, -0.08]} scale={1.08}>
        <meshStandardMaterial color="#05080f" metalness={0.6} roughness={0.5} transparent opacity={0.92} depthWrite={false} />
      </mesh>
      {/* main glass body — pure-black transparent; only the neon edges give it color */}
      <mesh
        geometry={HEX_GEO}
        onClick={(e) => { e.stopPropagation(); onSelect?.(card.id); }}
        onPointerOver={(e) => { e.stopPropagation(); setHover(true); document.body.style.cursor = "pointer"; }}
        onPointerOut={() => { setHover(false); document.body.style.cursor = "auto"; }}
      >
        <meshStandardMaterial color="#000000" emissive="#000000" emissiveIntensity={0} metalness={0.25} roughness={0.5} transparent opacity={lit ? 0.5 : 0.42} depthWrite={false} />
      </mesh>
      {/* INNER recessed "screen" panel — a slightly inset darker glass plate the content sits on */}
      <mesh geometry={HEX_GEO} scale={0.84} position={[0, 0, 0.04]}>
        <meshStandardMaterial color="#03060c" metalness={0.3} roughness={0.6} transparent opacity={0.64} depthWrite={false} />
      </mesh>
      {/* faint holographic scanlines across the screen */}
      {[0.34, 0.22, 0.0, -0.18, -0.32, -0.46].map((y, i) => (
        <mesh key={`sl${i}`} position={[0, y, 0.21]}>
          <boxGeometry args={[0.92, 0.004, 0.003]} />
          <meshBasicMaterial color={card.accent} transparent opacity={0.05} blending={THREE.AdditiveBlending} depthWrite={false} />
        </mesh>
      ))}
      {/* holographic sheen sweeping down the screen */}
      <mesh ref={sheen} position={[0, 0.4, 0.2]}>
        <planeGeometry args={[1.15, 0.16]} />
        <meshBasicMaterial color={card.accent} transparent opacity={0.08} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>

      {/* OUTER neon edge on the bezel (thin) */}
      <lineSegments position={[0, 0, -0.08]} scale={1.08}>
        <edgesGeometry args={[HEX_GEO]} />
        <lineBasicMaterial color={card.accent} transparent opacity={lit ? 0.65 : 0.42} blending={THREE.AdditiveBlending} />
      </lineSegments>
      {/* MAIN bright neon-LED border (blooms hard) — triple-stroked for a thick lit tube */}
      <lineSegments>
        <edgesGeometry args={[HEX_GEO]} />
        <lineBasicMaterial color="#ffffff" transparent opacity={lit ? 0.9 : 0.6} blending={THREE.AdditiveBlending} />
      </lineSegments>
      <lineSegments scale={1.012}>
        <edgesGeometry args={[HEX_GEO]} />
        <lineBasicMaterial ref={border} color={card.accent} transparent opacity={1} blending={THREE.AdditiveBlending} />
      </lineSegments>
      <lineSegments scale={1.026}>
        <edgesGeometry args={[HEX_GEO]} />
        <lineBasicMaterial color={card.accent} transparent opacity={0.55} blending={THREE.AdditiveBlending} />
      </lineSegments>
      {/* INNER hex outline → the recessed inner frame */}
      <lineSegments scale={0.84} position={[0, 0, 0.05]}>
        <edgesGeometry args={[HEX_GEO]} />
        <lineBasicMaterial color={card.accent} transparent opacity={lit ? 0.5 : 0.3} blending={THREE.AdditiveBlending} />
      </lineSegments>
      {/* holographic edge scattering that bleeds outward (stronger on hover) */}
      <lineSegments scale={lit ? 1.07 : 1.045}>
        <edgesGeometry args={[HEX_GEO]} />
        <lineBasicMaterial color={card.accent} transparent opacity={lit ? 0.32 : 0.15} blending={THREE.AdditiveBlending} />
      </lineSegments>
      {/* bright connector nodes at the hex vertices (dot + halo ring) */}
      {HEX_VERTS.map((v, i) => (
        <group key={i} position={[v[0], v[1], 0.06]}>
          <mesh><sphereGeometry args={[0.028, 10, 10]} /><meshBasicMaterial color="#ffffff" transparent opacity={0.95} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
          <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[0.05, 0.006, 8, 24]} /><meshBasicMaterial color={card.accent} transparent opacity={0.7} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        </group>
      ))}

      {/* HUD corner brackets framing the screen */}
      {([[-0.5, 0.56, 1, 1], [0.5, 0.56, -1, 1], [-0.5, -0.56, 1, -1], [0.5, -0.56, -1, -1]] as [number, number, number, number][]).map(([x, y, sx, sy], i) => (
        <group key={`br${i}`} position={[x, y, 0.26]}>
          <mesh position={[sx * 0.055, 0, 0]}><boxGeometry args={[0.11, 0.013, 0.004]} /><meshBasicMaterial color={card.accent} transparent opacity={0.65} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
          <mesh position={[0, sy * 0.045, 0]}><boxGeometry args={[0.013, 0.09, 0.004]} /><meshBasicMaterial color={card.accent} transparent opacity={0.65} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        </group>
      ))}
      {/* top accent bar under the upper hex edge */}
      <mesh position={[0, 0.7, 0.26]}>
        <boxGeometry args={[0.46, 0.016, 0.004]} />
        <meshBasicMaterial color={card.accent} transparent opacity={0.85} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>

      {/* ICON BADGE — dark disc + double accent ring + monogram glyph */}
      <mesh position={[0, 0.46, 0.24]}>
        <circleGeometry args={[0.18, 32]} />
        <meshBasicMaterial color="#02050b" transparent opacity={0.85} depthWrite={false} />
      </mesh>
      <group ref={badge} position={[0, 0.46, 0.25]}>
        <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[0.19, 0.013, 10, 44]} /><meshBasicMaterial color={card.accent} transparent opacity={0.95} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[0.155, 0.006, 10, 44]} /><meshBasicMaterial color={card.accent} transparent opacity={0.5} blending={THREE.AdditiveBlending} depthWrite={false} /></mesh>
      </group>
      <Text position={[0, 0.46, 0.27]} fontSize={0.19} anchorX="center" anchorY="middle" color="#ffffff" outlineWidth={0.006} outlineColor={card.accent}>
        {card.glyph}
      </Text>

      {/* TITLE */}
      <Text position={[0, 0.135, 0.27]} fontSize={0.108} maxWidth={1.2} lineHeight={1.02} letterSpacing={0.02} textAlign="center" anchorX="center" anchorY="middle" color="#ffffff" outlineWidth={0.005} outlineColor="#000000">
        {card.title}
      </Text>
      {/* SUBTITLE — what it connects */}
      <Text position={[0, -0.115, 0.27]} fontSize={0.055} maxWidth={1.1} lineHeight={1.18} letterSpacing={0.01} textAlign="center" anchorX="center" anchorY="middle" color="#a8bcd2" outlineWidth={0.002} outlineColor="#000000">
        {card.subtitle}
      </Text>
      {/* tech divider: line + center diamond node */}
      <mesh position={[0, -0.27, 0.26]}>
        <boxGeometry args={[0.72, 0.005, 0.004]} />
        <meshBasicMaterial color={card.accent} transparent opacity={0.45} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      <mesh position={[0, -0.27, 0.265]} rotation={[0, 0, Math.PI / 4]}>
        <boxGeometry args={[0.05, 0.05, 0.004]} />
        <meshBasicMaterial color={card.accent} transparent opacity={0.9} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      {/* bottom accent bar mirroring the top */}
      <mesh position={[0, -0.7, 0.26]}>
        <boxGeometry args={[0.46, 0.016, 0.004]} />
        <meshBasicMaterial color={card.accent} transparent opacity={0.85} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      {/* STATUS — pulsing dot + state */}
      <mesh ref={dot} position={[-0.34, -0.4, 0.27]}>
        <circleGeometry args={[0.03, 16]} />
        <meshBasicMaterial color={card.accent} transparent opacity={1} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      <Text position={[-0.28, -0.4, 0.27]} fontSize={0.062} anchorX="left" anchorY="middle" color={card.accent}>
        {card.state}
      </Text>
      {/* MATURITY */}
      <Text position={[0, -0.57, 0.27]} fontSize={0.048} letterSpacing={0.14} anchorX="center" anchorY="middle" color="#71808f">
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
      <BaseRing />
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
