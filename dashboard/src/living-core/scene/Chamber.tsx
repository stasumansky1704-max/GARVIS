import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { brushedMetal, nightCity } from "./textures";

/**
 * The command chamber that WRAPS the viewer. Two ribbed metallic side walls
 * pulled in close to the camera and continuing forward past it as big near
 * foreground pylons, so the room fills the frame edge-to-edge. Solid vaulted
 * ceiling arches enclose the top. Bright emissive panels (not just lights) make
 * the architecture read. The core itself is never touched.
 */

const RIBS_PER_WALL = 24;
const WALL_LEN = 64;
const WALL_HEIGHT = 18;
const NEAR_Z = 5; // near edge stays behind the core, not in front of camera
const WALL_X = 6.6; // framing distance; gentle tilt keeps walls off the center
const STEP = WALL_LEN / (RIBS_PER_WALL - 1);
const SHOW_CITY = true;
const SHOW_WALLS = true;

/* ---------------- side walls ---------------- */

function RibWall({ side }: { side: -1 | 1 }) {
  const seamGroup = useRef<THREE.Group>(null!);

  // brushed-metal map shared across the wall surfaces; tiled along the corridor
  const metal = useMemo(() => {
    const t = brushedMetal().clone();
    t.needsUpdate = true;
    t.repeat.set(8, 2);
    t.offset.set(side === 1 ? 0.37 : 0, 0); // break L/R mirror symmetry
    return t;
  }, [side]);

  // night-city skyline seen through the window band; offset per side for variety
  const city = useMemo(() => {
    const t = nightCity().clone();
    t.needsUpdate = true;
    t.wrapS = THREE.RepeatWrapping;
    t.repeat.set(1.9, 1); // larger skyline so towers fill the window
    t.offset.set(side === 1 ? 0.5 : 0.1, 0);
    return t;
  }, [side]);

  const ribs = useMemo(() => {
    const arr: number[] = [];
    for (let i = 0; i < RIBS_PER_WALL; i++) arr.push(NEAR_Z - i * STEP);
    return arr;
  }, []);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    seamGroup.current?.children.forEach((c, i) => {
      const m = (c as THREE.Mesh).material as THREE.MeshStandardMaterial;
      const wave = Math.sin(t * 1.1 - i * 0.4 + (side === 1 ? 1.5 : 0));
      m.emissiveIntensity = 1.8 + wave * 1.0;
    });
  });

  const xBase = side * WALL_X;
  const tilt = side * -0.16; // angle walls to face the camera (windows read as panels)

  // window band geometry (eye-level), framed by metal sill below + header above
  const WIN_Y = 3.4;
  const WIN_H = 6.2;
  const winZ = -WALL_LEN / 2 + NEAR_Z;
  // window planes must face INWARD and run along the corridor (Z): rotate 90°.
  const winRotY = side * -Math.PI / 2 + tilt;

  return (
    <group>
      {/* ---- CITY WINDOW BAND: the night skyline glows through the wall ---- */}
      {SHOW_CITY && (
        <>
          {/* base city image */}
          <mesh position={[xBase + side * 0.95, WIN_Y, winZ]} rotation={[0, winRotY, 0]}>
            <planeGeometry args={[WALL_LEN, WIN_H]} />
            <meshBasicMaterial map={city} toneMapped={false} side={THREE.DoubleSide} fog={false} />
          </mesh>
          {/* additive pass of the same skyline so the lit windows actually glow
              and survive fog/AO (self-illuminated city) */}
          <mesh position={[xBase + side * 0.93, WIN_Y, winZ]} rotation={[0, winRotY, 0]}>
            <planeGeometry args={[WALL_LEN, WIN_H]} />
            <meshBasicMaterial map={city} transparent opacity={0.9} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} toneMapped={false} fog={false} />
          </mesh>
          {/* faint cool horizon haze */}
          <mesh position={[xBase + side * 0.9, WIN_Y - 1.6, winZ]} rotation={[0, winRotY, 0]}>
            <planeGeometry args={[WALL_LEN, 2.4]} />
            <meshBasicMaterial color="#2f9fd0" transparent opacity={0.16} blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} toneMapped={false} fog={false} />
          </mesh>
        </>
      )}

      {/* solid metal wall ABOVE the windows (header + angled ceiling fascia) */}
      <mesh position={[xBase + side * 1.2, WIN_Y + WIN_H / 2 + 2.6, winZ]} rotation={[0, tilt, 0]}>
        <boxGeometry args={[0.9, 5.2, WALL_LEN]} />
        <meshStandardMaterial map={metal} color="#3a5e7e" roughness={0.4} metalness={0.82} emissive="#10405c" emissiveIntensity={0.5} envMapIntensity={1.0} />
      </mesh>
      <mesh position={[xBase + side * 0.7, WIN_Y + WIN_H / 2 + 4.5, winZ]} rotation={[0, tilt, side * 0.55]}>
        <boxGeometry args={[0.55, 3.6, WALL_LEN]} />
        <meshStandardMaterial map={metal} color="#3f648a" roughness={0.34} metalness={0.85} emissive="#155a78" emissiveIntensity={0.7} envMapIntensity={1.15} />
      </mesh>

      {/* solid metal wall BELOW the windows (sill + base) */}
      <mesh position={[xBase + side * 1.2, WIN_Y - WIN_H / 2 - 2.2, winZ]} rotation={[0, tilt, 0]}>
        <boxGeometry args={[0.9, 4.6, WALL_LEN]} />
        <meshStandardMaterial map={metal} color="#335575" roughness={0.42} metalness={0.8} emissive="#0d3a54" emissiveIntensity={0.45} envMapIntensity={0.95} />
      </mesh>

      {/* window MULLIONS — the rib fins become vertical frames between panes */}
      {ribs.map((z, i) => (
        <mesh key={i} position={[xBase + side * 0.62, WIN_Y, z]} rotation={[0, tilt, 0]}>
          <boxGeometry args={[0.5, WIN_H + 0.4, 0.42]} />
          <meshStandardMaterial map={metal} color="#456a90" roughness={0.36} metalness={0.86} emissive="#15506e" emissiveIntensity={0.7} envMapIntensity={1.15} />
        </mesh>
      ))}
      {/* horizontal window sill + header rails (frame top & bottom of the glass) */}
      {[WIN_Y + WIN_H / 2, WIN_Y - WIN_H / 2].map((yy, k) => (
        <mesh key={k} position={[xBase + side * 0.6, yy, winZ]} rotation={[0, tilt, 0]}>
          <boxGeometry args={[0.55, 0.5, WALL_LEN]} />
          <meshStandardMaterial map={metal} color="#3f648a" roughness={0.36} metalness={0.86} emissive="#1a6a8e" emissiveIntensity={0.9} envMapIntensity={1.1} />
        </mesh>
      ))}

      {/* bright accent seams on the LOWER sill only (don't cross the glass) */}
      <group ref={seamGroup}>
        {ribs.map((z, i) => (
          <mesh key={i} position={[xBase + side * 0.32, WIN_Y - WIN_H / 2 - 2.0, z + STEP / 2]} rotation={[0, tilt, 0]}>
            <boxGeometry args={[0.08, 3.4, 0.08]} />
            <meshStandardMaterial color="#0a2a3a" emissive="#5ad6ff" emissiveIntensity={2.6} toneMapped={false} />
          </mesh>
        ))}
      </group>

      {/* horizontal accent rail along the lower wall */}
      <mesh position={[xBase + side * 0.32, WIN_Y - WIN_H / 2 - 3.4, winZ]} rotation={[0, tilt, 0]}>
        <boxGeometry args={[0.07, 0.09, WALL_LEN]} />
        <meshStandardMaterial color="#0a2a3a" emissive="#37c4f0" emissiveIntensity={1.9} toneMapped={false} />
      </mesh>

      {/* floor-base strip light */}
      <mesh position={[xBase - side * 0.6, -3.6, -WALL_LEN / 2 + NEAR_Z]} rotation={[0, tilt, 0]}>
        <boxGeometry args={[0.12, 0.16, WALL_LEN]} />
        <meshStandardMaterial color="#0a2a3a" emissive="#2fb4e6" emissiveIntensity={2.0} toneMapped={false} />
      </mesh>
    </group>
  );
}

/* ---------------- near foreground pylons (frame the camera edges) ---------------- */

function ForegroundPylon({ side }: { side: -1 | 1 }) {
  const strip = useRef<THREE.Mesh>(null!);
  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (strip.current) {
      (strip.current.material as THREE.MeshStandardMaterial).emissiveIntensity =
        1.6 + Math.sin(t * 1.3 + side) * 0.7;
    }
  });
  // big dark structural pillar very close to the camera at the frame edge
  const x = side * 7.6;
  return (
    <group position={[x, 1, 7.2]}>
      <mesh rotation={[0, side * 0.35, 0]}>
        <boxGeometry args={[2.4, 22, 3.2]} />
        <meshStandardMaterial color="#16293d" roughness={0.4} metalness={0.85} emissive="#0a2f47" emissiveIntensity={0.5} envMapIntensity={0.9} />
      </mesh>
      {/* inner-facing bevel */}
      <mesh position={[side * -1.2, 0, 0.4]} rotation={[0, side * 0.35, 0]}>
        <boxGeometry args={[0.4, 22, 2.6]} />
        <meshStandardMaterial color="#22405b" roughness={0.36} metalness={0.86} emissive="#11506e" emissiveIntensity={0.8} />
      </mesh>
      {/* glowing vertical light strip on the inner edge */}
      <mesh ref={strip} position={[side * -1.35, 0, 1.0]} rotation={[0, side * 0.35, 0]}>
        <boxGeometry args={[0.12, 16, 0.12]} />
        <meshStandardMaterial color="#0a2a3a" emissive="#5ad6ff" emissiveIntensity={1.8} toneMapped={false} />
      </mesh>
    </group>
  );
}

/* ---------------- solid enclosing ceiling arches ---------------- */

function CeilingArches() {
  const group = useRef<THREE.Group>(null!);
  useFrame((state) => {
    const t = state.clock.elapsedTime;
    group.current?.children.forEach((arch, i) => {
      const strip = (arch as THREE.Group).children[1] as THREE.Mesh | undefined;
      if (strip) {
        const m = strip.material as THREE.MeshStandardMaterial;
        m.emissiveIntensity = 1.4 + Math.sin(t * 0.9 - i * 0.6) * 0.7;
      }
    });
  });

  const arches = useMemo(() => {
    const arr: number[] = [];
    for (let i = 0; i < 11; i++) arr.push(6 - i * 6.0);
    return arr;
  }, []);

  return (
    <group ref={group}>
      {arches.map((z, i) => (
        <group key={i} position={[0, 0, z]}>
          {/* thick structural arch vaulting over the room */}
          <mesh position={[0, 3.0, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[7.4, 0.6, 16, 56, Math.PI]} />
            <meshStandardMaterial color="#243f59" roughness={0.4} metalness={0.86} emissive="#0f3b54" emissiveIntensity={0.7} envMapIntensity={1.1} />
          </mesh>
          {/* glowing inner light rib on the arch */}
          <mesh position={[0, 3.0, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[6.85, 0.08, 8, 56, Math.PI]} />
            <meshStandardMaterial color="#0a2a3a" emissive="#4cd2ff" emissiveIntensity={1.5} toneMapped={false} />
          </mesh>
        </group>
      ))}
    </group>
  );
}

/* ---------------- far back wall + horizon ---------------- */

function BackWall() {
  return (
    <group position={[0, 1, -44]}>
      <mesh>
        <planeGeometry args={[64, 32]} />
        <meshStandardMaterial color="#0b1828" roughness={0.5} metalness={0.75} emissive="#08243a" emissiveIntensity={0.45} />
      </mesh>
      <mesh position={[0, -12, 0.3]}>
        <planeGeometry args={[64, 10]} />
        <meshBasicMaterial color="#124d6c" transparent opacity={0.55} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
      </mesh>
    </group>
  );
}

export default function Chamber() {
  return (
    <group>
      {SHOW_WALLS && <RibWall side={-1} />}
      {SHOW_WALLS && <RibWall side={1} />}
      <ForegroundPylon side={-1} />
      <ForegroundPylon side={1} />
      <CeilingArches />
      <BackWall />
    </group>
  );
}
