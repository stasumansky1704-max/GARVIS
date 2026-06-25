import { Suspense, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Environment } from "@react-three/drei";
import {
  EffectComposer,
  Bloom,
  Vignette,
  Noise,
  SMAA,
  HueSaturation,
  BrightnessContrast,
  N8AO,
} from "@react-three/postprocessing";
import { BlendFunction } from "postprocessing";
import * as THREE from "three";

import NetworkGlobe from "./NetworkGlobe";
import CoreParticles from "./CoreParticles";
import Atmosphere from "./Atmosphere";

/** Subtle living camera: slow drift + eased mouse parallax, always looking at the core. */
function CameraRig() {
  const { camera } = useThree();
  const target = useRef(new THREE.Vector3(0, 0.35, 0));
  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const mx = state.pointer.x;
    const my = state.pointer.y;
    // near-centered symmetric framing (match reference); very subtle life only
    const dx = Math.sin(t * 0.1) * 0.12 + mx * 0.35;
    const dy = 0.45 + Math.sin(t * 0.15) * 0.08 + my * 0.25;
    const dz = 8.0 + Math.cos(t * 0.09) * 0.2;
    camera.position.x += (dx - camera.position.x) * 0.03;
    camera.position.y += (dy - camera.position.y) * 0.03;
    camera.position.z += (dz - camera.position.z) * 0.03;
    camera.lookAt(target.current);
  });
  return null;
}

export default function Scene() {
  return (
    <Canvas
      gl={{
        antialias: true,
        alpha: true,
        powerPreference: "high-performance",
        toneMapping: THREE.ACESFilmicToneMapping,
        preserveDrawingBuffer: true,
      }}
      dpr={[2, 3]}
      camera={{ position: [0, 0.7, 8.6], fov: 58, near: 0.1, far: 120 }}
      onCreated={({ gl }) => {
        gl.setClearColor(0x01030a, 0);
      }}
    >
      {/* midnight-navy fog (deep, dark, subtle blue) */}
      <fogExp2 attach="fog" args={[0x07142b, 0.032]} />

      {/* lighting: dim midnight ambient — only the core + stars glow */}
      <ambientLight intensity={0.4} color="#13476e" />
      <hemisphereLight args={["#235f96", "#03070f", 0.5]} />
      {/* core key (kept moderate so the room isn't blown out) */}
      <pointLight position={[0, 2, 4]} intensity={40} color="#38bdf8" distance={32} decay={2} />
      {/* wall-wash rims down both sides of the corridor */}
      <pointLight position={[5.0, 3.5, -4]} intensity={70} color="#46b4e0" distance={32} decay={2} />
      <pointLight position={[-5.0, 3.5, -4]} intensity={70} color="#46b4e0" distance={32} decay={2} />
      <pointLight position={[5.4, 3, -16]} intensity={60} color="#2f9fd0" distance={38} decay={2} />
      <pointLight position={[-5.4, 3, -16]} intensity={60} color="#2f9fd0" distance={38} decay={2} />
      <pointLight position={[5.6, 3, -28]} intensity={46} color="#2680ad" distance={40} decay={2} />
      <pointLight position={[-5.6, 3, -28]} intensity={46} color="#2680ad" distance={40} decay={2} />
      {/* ceiling-arch keylights from above so the beams show solid mass + shadow lines */}
      <pointLight position={[0, 10, -6]} intensity={55} color="#bfeaff" distance={28} decay={2} />
      <pointLight position={[0, 10, -18]} intensity={50} color="#7fd0ee" distance={34} decay={2} />
      <pointLight position={[0, 9, -30]} intensity={36} color="#2aa8d8" distance={44} decay={2} />
      {/* near foreground fill so the pylons beside the camera read */}
      <pointLight position={[6.0, 2, 6]} intensity={40} color="#2f9fd0" distance={20} decay={2} />
      <pointLight position={[-6.0, 2, 6]} intensity={40} color="#2f9fd0" distance={20} decay={2} />
      {/* hard cyan rim under the core to pick out the pedestal steps */}
      <spotLight position={[0, 6, 5]} target-position={[0, -4, 0]} angle={0.6} penumbra={0.7} intensity={70} color="#7fe0ff" distance={26} decay={2} />

      <Suspense fallback={null}>
        {/* HDRI environment — real reflections on the metal architecture.
            Hidden as a visible background; only used for material lighting. */}
        <Environment preset="night" environmentIntensity={0.85} />

        {/* pure void: no walls, no floor, no platform — only atmosphere dust,
            the core orb, and the stars */}
        <Atmosphere />

        <group position={[0, 0.35, 0]}>
          <NetworkGlobe />
          <CoreParticles />
        </group>
      </Suspense>

      <CameraRig />

      {/* Cinematic post chain — order matters: AA -> SSAO -> Bloom -> DoF -> grade.
          (r3f-cinematic-rendering skill) */}
      <EffectComposer multisampling={0} frameBufferType={THREE.HalfFloatType}>
        <SMAA />
        {/* N8AO — self-contained ambient occlusion (no manual NormalPass needed);
            adds contact shadow / depth to the metal architecture */}
        <N8AO
          aoRadius={1.8}
          intensity={1.8}
          distanceFalloff={1.0}
          color="#02060e"
          quality="high"
        />
        <Bloom
          intensity={1.0}
          luminanceThreshold={0.45}
          luminanceSmoothing={0.6}
          mipmapBlur
          radius={0.55}
        />
        {/* NO depth-of-field — keep the whole scene crisp and in focus */}
        {/* deep neon-blue grade: shift hue bluer, punchy saturation, crushed blacks */}
        <HueSaturation hue={-0.06} saturation={0.36} />
        <BrightnessContrast brightness={-0.05} contrast={0.24} />
        <Vignette eskil={false} offset={0.18} darkness={1.05} />
        <Noise opacity={0.016} blendFunction={BlendFunction.OVERLAY} />
      </EffectComposer>
    </Canvas>
  );
}
