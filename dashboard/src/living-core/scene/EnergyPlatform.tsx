import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

/**
 * The energy platform directly beneath the core: a metallic hex pedestal with
 * concentric glowing rings and a rotating accent ring laid on the floor. Gives
 * the floating core a "source" and anchors it in the chamber (command-center-
 * layout). Sits below the frozen core group; does not alter the core.
 */
export default function EnergyPlatform() {
  const innerGlow = useRef<THREE.Mesh>(null!);
  const spinRing = useRef<THREE.Mesh>(null!);
  const pulseRing = useRef<THREE.Mesh>(null!);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    // breathing inner disc
    (innerGlow.current.material as THREE.MeshBasicMaterial).opacity =
      0.5 + Math.sin(t * 1.6) * 0.18;
    // slow rotating tech ring
    spinRing.current.rotation.z = t * 0.18;
    // expanding pulse ring
    const p = (t % 4) / 4; // 0..1
    const s = 1 + p * 1.6;
    pulseRing.current.scale.set(s, s, s);
    (pulseRing.current.material as THREE.MeshBasicMaterial).opacity =
      0.5 * (1 - p);
  });

  const y = -4.2; // platform top, well below the core

  return (
    <group position={[0, y, 0]}>
      {/* --- clean round pedestal: a low wide platform + a shallow inner step
            (concentric, like the reference) --- */}
      <mesh position={[0, -0.85, 0]}>
        <cylinderGeometry args={[5.0, 5.3, 0.5, 96]} />
        <meshStandardMaterial color="#1b3349" roughness={0.42} metalness={0.84} emissive="#0a2a3e" emissiveIntensity={0.4} envMapIntensity={0.95} />
      </mesh>
      <mesh position={[0, -0.42, 0]}>
        <cylinderGeometry args={[4.2, 4.5, 0.42, 96]} />
        <meshStandardMaterial color="#22405b" roughness={0.4} metalness={0.86} emissive="#0c3147" emissiveIntensity={0.5} envMapIntensity={1.0} />
      </mesh>
      <mesh position={[0, -0.08, 0]}>
        <cylinderGeometry args={[3.4, 3.7, 0.36, 96]} />
        <meshStandardMaterial color="#274966" roughness={0.38} metalness={0.88} emissive="#0e3b54" emissiveIntensity={0.6} envMapIntensity={1.1} />
      </mesh>

      {/* concentric glowing rings on the pedestal top face */}
      {[5.0, 4.2, 3.4, 2.6].map((r, i) => (
        <mesh key={i} position={[0, -0.6 + i * 0.18, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[r - 0.07, r + 0.07, 128]} />
          <meshBasicMaterial color={i % 2 === 0 ? "#7fe0ff" : "#38bdf8"} transparent opacity={0.85 - i * 0.12} side={THREE.DoubleSide} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
        </mesh>
      ))}

      {/* hex top cap of the dais */}
      <mesh position={[0, 0.08, 0]}>
        <cylinderGeometry args={[2.5, 2.7, 0.3, 6]} />
        <meshStandardMaterial color="#16293c" roughness={0.35} metalness={0.95} emissive="#0e3b54" emissiveIntensity={0.7} envMapIntensity={1.0} />
      </mesh>

      {/* the flat energy face on top of the dais */}
      <group position={[0, 0.24, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      {/* raised rim ring of the pedestal */}
      <mesh position={[0, 0, 0.02]}>
        <ringGeometry args={[2.45, 2.62, 6]} />
        <meshStandardMaterial
          color="#0c2535"
          emissive="#2fb4e6"
          emissiveIntensity={1.1}
          toneMapped={false}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* glowing inner energy disc */}
      <mesh ref={innerGlow} position={[0, 0, 0.05]}>
        <circleGeometry args={[2.2, 64]} />
        <meshBasicMaterial
          color="#1aa6e0"
          transparent
          opacity={0.55}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>

      {/* concentric tech ring (static) */}
      <mesh position={[0, 0, 0.06]}>
        <ringGeometry args={[1.5, 1.58, 64]} />
        <meshBasicMaterial
          color="#7dd3fc"
          transparent
          opacity={0.7}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>

      {/* rotating dashed accent ring */}
      <mesh ref={spinRing} position={[0, 0, 0.07]}>
        <ringGeometry args={[1.95, 2.05, 48, 1]} />
        <meshBasicMaterial
          color="#38bdf8"
          transparent
          opacity={0.45}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>

      {/* outward energy pulse */}
      <mesh ref={pulseRing} position={[0, 0, 0.08]}>
        <ringGeometry args={[1.0, 1.12, 64]} />
        <meshBasicMaterial
          color="#bfeaff"
          transparent
          opacity={0.4}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>
      </group>
    </group>
  );
}
