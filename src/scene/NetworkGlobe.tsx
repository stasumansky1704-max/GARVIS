import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { readVoiceLevel } from "./voiceLevel";

/**
 * The JARVIS core: a glowing neon-blue energy sphere surrounded by sharp
 * star-like node points only (no wireframe, no rings, no chords). Slowly
 * rotates and breathes.
 */

const R = 2.0;

function nodePoints() {
  const pts: number[] = [];
  const N = 320;
  for (let i = 0; i < N; i++) {
    // fibonacci sphere for even node distribution
    const y = 1 - (i / (N - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const theta = i * 2.399963;
    pts.push(Math.cos(theta) * r * R, y * R, Math.sin(theta) * r * R);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
  return g;
}

function nodePointsOuter() {
  // a second, slightly larger + jittered shell for depth/density
  const pts: number[] = [];
  const N = 220;
  let s = 71;
  const rnd = () => { s = (s * 1103515245 + 12345) & 0x7fffffff; return s / 0x7fffffff; };
  for (let i = 0; i < N; i++) {
    const y = 1 - (i / (N - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const theta = i * 2.399963 + 0.4;
    const rad = R * (1.04 + rnd() * 0.14);
    pts.push(Math.cos(theta) * r * rad, y * rad, Math.sin(theta) * r * rad);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
  return g;
}

function nodeSprite() {
  // very sharp hot core + tight tiny halo — crisp pinpoint stars, not blobs
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const ctx = c.getContext("2d")!;
  const cx = 64;
  const g = ctx.createRadialGradient(cx, cx, 0, cx, cx, 64);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.06, "rgba(235,250,255,1)");
  g.addColorStop(0.14, "rgba(120,205,255,0.85)");
  g.addColorStop(0.3, "rgba(50,150,255,0.18)");
  g.addColorStop(1, "rgba(30,120,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  // hard bright pinpoint center
  ctx.fillStyle = "rgba(255,255,255,1)";
  ctx.beginPath();
  ctx.arc(cx, cx, 4, 0, Math.PI * 2);
  ctx.fill();
  const tex = new THREE.CanvasTexture(c);
  tex.anisotropy = 4;
  return tex;
}

/** Radiant sun glow — bright hot center fading smoothly to transparent (no hard edge). */
function sunSprite() {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const ctx = c.getContext("2d")!;
  const cx = 128;
  const g = ctx.createRadialGradient(cx, cx, 0, cx, cx, 128);
  g.addColorStop(0.0, "rgba(255,255,255,1)");
  g.addColorStop(0.08, "rgba(255,255,255,1)");
  g.addColorStop(0.18, "rgba(225,245,255,0.9)");
  g.addColorStop(0.36, "rgba(130,205,255,0.45)");
  g.addColorStop(0.6, "rgba(60,150,255,0.14)");
  g.addColorStop(1, "rgba(40,120,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 256, 256);
  const tex = new THREE.CanvasTexture(c);
  tex.anisotropy = 4;
  return tex;
}

export default function NetworkGlobe() {
  const group = useRef<THREE.Group>(null!);
  const core = useRef<THREE.Mesh>(null!);
  const sun = useRef<THREE.Sprite>(null!);

  // stars only: two node shells (surface + a slightly larger one) for density
  const nodeGeo = useMemo(nodePoints, []);
  const nodeGeo2 = useMemo(nodePointsOuter, []);
  const sprite = useMemo(nodeSprite, []);
  const sunTex = useMemo(sunSprite, []);

  useFrame((state, dt) => {
    const t = state.clock.elapsedTime;
    group.current.rotation.y = t * 0.1;

    // voice-reactive: 0 when idle, surges 0..1 while GARVIS speaks
    const voice = readVoiceLevel(dt, t);

    // idle = gentle breathing; speaking = stronger pulse driven by the voice envelope
    const idleBreathe = Math.sin(t * 0.8) * 0.02;
    const speakPulse = voice * 0.18; // up to +18% scale on loud syllables
    group.current.scale.setScalar(1 + idleBreathe + speakPulse * 0.4);

    // sun core: scale + brightness ride the voice so it looks like sound emits from it
    const baseS = 1.45 + Math.sin(t * 1.4) * 0.06;
    const s = (baseS + voice * 0.9) * R;
    sun.current.scale.set(s, s, 1);
    (sun.current.material as THREE.SpriteMaterial).opacity =
      Math.min(1.6, 0.85 + Math.sin(t * 1.4) * 0.08 + voice * 0.7);

    // hot center flares with the voice too
    (core.current.material as THREE.MeshBasicMaterial).opacity = 1;
    core.current.scale.setScalar(1 + voice * 0.5);
  });

  return (
    <group ref={group}>
      {/* blazing sun core — a small solid white-hot sphere ... */}
      <mesh ref={core}>
        <sphereGeometry args={[R * 0.16, 64, 64]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </mesh>
      {/* ... plus a radiant sun glow sprite that fades to nothing (no hard circle) */}
      <sprite ref={sun} scale={[R * 1.5, R * 1.5, 1]}>
        <spriteMaterial map={sunTex} color="#ffffff" transparent opacity={1} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
      </sprite>

      {/* ===== STARS ONLY — brighter glowing node points ===== */}
      <points geometry={nodeGeo}>
        <pointsMaterial size={0.3} map={sprite} color="#ffffff" transparent opacity={1} sizeAttenuation blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
      </points>
      <points geometry={nodeGeo2}>
        <pointsMaterial size={0.2} map={sprite} color="#bfe2ff" transparent opacity={1} sizeAttenuation blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
      </points>
    </group>
  );
}
