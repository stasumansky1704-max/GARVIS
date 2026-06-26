import { Component, Suspense } from "react";
import type { ReactNode } from "react";
import { Canvas } from "@react-three/fiber";
import { useGLTF, Bounds, Center } from "@react-three/drei";

/**
 * Opt-in holographic preview of a single Meshy GLB. Loaded as a LAZY chunk (see MeshyIntelAssets)
 * so the GLTF loader code never ships to users who don't open a preview. Every 3D failure mode —
 * heavy/slow load, parse error, Draco without a decoder — degrades to a wireframe orb, so this
 * can never blank. Desktop-only, mounted only when the user explicitly requests a preview.
 */

function FallbackOrb() {
  return (
    <mesh>
      <icosahedronGeometry args={[1.05, 1]} />
      <meshBasicMaterial color="#7dd3fc" wireframe transparent opacity={0.7} />
    </mesh>
  );
}

/** Catches any error thrown by the GLTF loader inside the Canvas → shows the orb instead. */
class CanvasErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? <FallbackOrb /> : this.props.children;
  }
}

function Model({ url }: { url: string }) {
  const gltf = useGLTF(url);
  // Bounds + Center auto-fit a model of unknown scale into frame — no manual scale guessing.
  return (
    <Bounds fit clip observe margin={1.25}>
      <Center>
        <primitive object={gltf.scene} />
      </Center>
    </Bounds>
  );
}

export default function ProjectorHologram({ url }: { url: string }) {
  return (
    <Canvas dpr={[1, 2]} camera={{ position: [0, 0.4, 4], fov: 45 }} gl={{ alpha: true, antialias: true }}>
      <ambientLight intensity={0.7} color="#9ad8ff" />
      <pointLight position={[2, 3, 3]} intensity={30} color="#7dd3fc" distance={20} decay={2} />
      <pointLight position={[-3, -1, -2]} intensity={16} color="#22d3ee" distance={18} decay={2} />
      <Suspense fallback={<FallbackOrb />}>
        <CanvasErrorBoundary>
          <Model url={url} />
        </CanvasErrorBoundary>
      </Suspense>
    </Canvas>
  );
}
