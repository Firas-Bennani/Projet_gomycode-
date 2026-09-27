import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Text } from '@react-three/drei';
import * as THREE from 'three';

/* ─────────────────────── ANIMATED SMOKE ─────────────────────────── */
const SmokeParticles: React.FC<{ position: [number, number, number] }> = ({ position }) => {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.children.forEach((child, i) => {
        child.position.y += 0.02 + i * 0.003;
        child.position.x += Math.sin(state.clock.elapsedTime + i) * 0.005;
        (child as THREE.Mesh).scale.setScalar(1 + child.position.y * 0.04);
        const mat = (child as THREE.Mesh).material as THREE.MeshStandardMaterial;
        mat.opacity = Math.max(0, 0.45 - child.position.y * 0.03);

        if (child.position.y > 12) {
          child.position.y = 0;
          child.position.x = (Math.random() - 0.5) * 0.6;
          child.position.z = (Math.random() - 0.5) * 0.6;
          (child as THREE.Mesh).scale.setScalar(1);
        }
      });
    }
  });

  return (
    <group position={position} ref={groupRef}>
      {Array.from({ length: 8 }).map((_, i) => (
        <mesh
          key={`smoke-${i}`}
          position={[
            (Math.random() - 0.5) * 0.4,
            Math.random() * 6,
            (Math.random() - 0.5) * 0.4
          ]}
        >
          <sphereGeometry args={[0.35 + Math.random() * 0.25, 8, 8]} />
          <meshStandardMaterial
            color="#cbd5e1"
            transparent
            opacity={0.3}
            depthWrite={false}
          />
        </mesh>
      ))}
    </group>
  );
};

/* ───────────────────── SMOKESTACK ────────────────────────────────── */
const Smokestack: React.FC<{
  position: [number, number, number];
  height?: number;
}> = ({ position, height = 9 }) => (
  <group position={position}>
    <mesh position={[0, height / 2, 0]} castShadow>
      <cylinderGeometry args={[0.5, 0.7, height, 16]} />
      <meshStandardMaterial color="#f8fafc" roughness={0.4} />
    </mesh>
    {[0.4, 0.75, 0.95].map((f, i) => (
      <mesh key={`band-${i}`} position={[0, height * f, 0]}>
        <cylinderGeometry args={[0.52 + (1 - f) * 0.15, 0.52 + (1 - f) * 0.15, 0.35, 16]} />
        <meshStandardMaterial color="#dc2626" />
      </mesh>
    ))}
    <mesh position={[0, height, 0]}>
      <torusGeometry args={[0.5, 0.06, 8, 16]} />
      <meshStandardMaterial color="#1e293b" metalness={0.9} />
    </mesh>
    <SmokeParticles position={[0, height + 0.3, 0]} />
  </group>
);

/* ═══════════════════════════════════════════════════════════════════
   ADMINISTRATION / OFFICE BUILDING (Front Center in Reference Image)
   ═══════════════════════════════════════════════════════════════════ */
const AdminOfficeBuilding: React.FC<{ position: [number, number, number] }> = ({ position }) => (
  <group position={position}>
    {/* Main 2-story white modernist block */}
    <mesh position={[0, 2.6, 0]} castShadow receiveShadow>
      <boxGeometry args={[16, 5.2, 8]} />
      <meshStandardMaterial color="#f1f5f9" roughness={0.4} />
    </mesh>

    {/* Upper floor window strip (front) */}
    <mesh position={[0, 3.8, 4.02]}>
      <planeGeometry args={[14.5, 1.2]} />
      <meshStandardMaterial color="#1e3a5f" roughness={0.2} metalness={0.6} />
    </mesh>

    {/* Lower floor window strip (front) */}
    <mesh position={[0, 1.6, 4.02]}>
      <planeGeometry args={[14.5, 1.2]} />
      <meshStandardMaterial color="#1e3a5f" roughness={0.2} metalness={0.6} />
    </mesh>

    {/* Side window strips */}
    <mesh position={[-8.02, 3.8, 0]} rotation={[0, -Math.PI / 2, 0]}>
      <planeGeometry args={[6.5, 1.2]} />
      <meshStandardMaterial color="#1e3a5f" roughness={0.2} metalness={0.6} />
    </mesh>
    <mesh position={[8.02, 3.8, 0]} rotation={[0, Math.PI / 2, 0]}>
      <planeGeometry args={[6.5, 1.2]} />
      <meshStandardMaterial color="#1e3a5f" roughness={0.2} metalness={0.6} />
    </mesh>

    {/* Glass Entrance Canopy */}
    <mesh position={[0, 1.2, 4.8]} castShadow>
      <boxGeometry args={[3.2, 0.15, 1.6]} />
      <meshStandardMaterial color="#38bdf8" metalness={0.9} transparent opacity={0.7} />
    </mesh>
    {[-1.4, 1.4].map((x, i) => (
      <mesh key={`post-${i}`} position={[x, 0.6, 5.4]} castShadow>
        <cylinderGeometry args={[0.05, 0.05, 1.2, 8]} />
        <meshStandardMaterial color="#475569" metalness={0.8} />
      </mesh>
    ))}

    {/* Rooftop HVAC Units (matching image) */}
    {[-5, -2, 2, 5].map((x, i) => (
      <mesh key={`hvac-${i}`} position={[x, 5.6, (i % 2 === 0 ? 1.5 : -1.5)]} castShadow>
        <boxGeometry args={[1.6, 0.8, 1.2]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.7} />
      </mesh>
    ))}
    {/* Elevator Penthouse */}
    <mesh position={[0, 6.0, -1.0]} castShadow>
      <boxGeometry args={[3.0, 1.6, 2.5]} />
      <meshStandardMaterial color="#cbd5e1" roughness={0.5} />
    </mesh>
  </group>
);

/* ═══════════════════════════════════════════════════════════════════
   LARGE INDUSTRIAL GABLED FACTORY HALL (Right Side in Reference Image)
   ═══════════════════════════════════════════════════════════════════ */
const LargeGabledFactoryHall: React.FC<{ position: [number, number, number] }> = ({ position }) => (
  <group position={position}>
    {/* Main Hall Body (Dark Steel Blue) */}
    <mesh position={[0, 4.5, 0]} castShadow receiveShadow>
      <boxGeometry args={[22, 9.0, 24]} />
      <meshStandardMaterial color="#233546" roughness={0.5} metalness={0.3} />
    </mesh>

    {/* Gabled Pitched Roof (Steel Blue / Navy) */}
    <group position={[0, 9.0, 0]}>
      {/* Left Roof Slope */}
      <mesh position={[-5.8, 1.8, 0]} rotation={[0, 0, 0.32]} castShadow receiveShadow>
        <boxGeometry args={[12.4, 0.3, 24.4]} />
        <meshStandardMaterial color="#2b435a" roughness={0.4} metalness={0.4} />
      </mesh>
      {/* Right Roof Slope */}
      <mesh position={[5.8, 1.8, 0]} rotation={[0, 0, -0.32]} castShadow receiveShadow>
        <boxGeometry args={[12.4, 0.3, 24.4]} />
        <meshStandardMaterial color="#2b435a" roughness={0.4} metalness={0.4} />
      </mesh>
      {/* Roof Ridge Peak */}
      <mesh position={[0, 3.8, 0]}>
        <boxGeometry args={[0.6, 0.4, 24.5]} />
        <meshStandardMaterial color="#0f172a" metalness={0.8} />
      </mesh>
    </group>

    {/* Industrial Bay Doors (Front & Side) */}
    {[-5, 5].map((x, i) => (
      <group key={`bay-${i}`} position={[x, 2.2, 12.02]}>
        <mesh>
          <planeGeometry args={[3.8, 4.2]} />
          <meshStandardMaterial color="#f8fafc" metalness={0.6} roughness={0.3} />
        </mesh>
        {/* Door Frame */}
        <lineSegments>
          <edgesGeometry args={[new THREE.PlaneGeometry(3.8, 4.2)]} />
          <lineBasicMaterial color="#0f172a" linewidth={2} />
        </lineSegments>
      </group>
    ))}

    {/* Side Bay Doors */}
    {[-6, 0, 6].map((z, i) => (
      <group key={`side-bay-${i}`} position={[-11.02, 2.2, z]}>
        <mesh rotation={[0, -Math.PI / 2, 0]}>
          <planeGeometry args={[3.4, 4.0]} />
          <meshStandardMaterial color="#334155" metalness={0.7} />
        </mesh>
      </group>
    ))}

    {/* Roof Ventilation Chimneys */}
    {[-7, 0, 7].map((z, i) => (
      <mesh key={`vent-${i}`} position={[0, 13.2, z]} castShadow>
        <cylinderGeometry args={[0.18, 0.18, 1.2, 8]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.8} />
      </mesh>
    ))}
  </group>
);

/* ═══════════════════════════════════════════════════════════════════
   MAIN COMPOSITE FACTORY COMPLEX
   ─────────────────────────────────────────────────────────────────
   Combines the dark blue "FACTORY" building, the modernist
   administration office, and the large gabled production hall
   exactly as composed in the reference image.
   ═══════════════════════════════════════════════════════════════════ */
export { AdminOfficeBuilding, LargeGabledFactoryHall };

export const MainFactoryBuilding: React.FC<{
  position?: [number, number, number];
}> = ({ position = [0, 0, 0] }) => {
  return (
    <group position={position}>
      {/* ─── 1. MID-REAR "FACTORY" BUILDING (Dark Navy/Slate) ─── */}
      {/* Positioned at Z = -25, well behind M-04 (which is at Z = -6) */}
      <group position={[4, 0, -25]}>
        {/* Main Body */}
        <mesh position={[0, 4.5, 0]} castShadow receiveShadow>
          <boxGeometry args={[18, 9.0, 12]} />
          <meshStandardMaterial color="#1e2d3d" roughness={0.55} metalness={0.25} />
        </mesh>

        {/* Roof Cap */}
        <mesh position={[0, 9.2, 0]} castShadow>
          <boxGeometry args={[18.6, 0.4, 12.6]} />
          <meshStandardMaterial color="#2d3f52" metalness={0.6} roughness={0.3} />
        </mesh>

        {/* "FACTORY" Sign on Facade */}
        <Text
          position={[0, 5.2, 6.05]}
          fontSize={1.4}
          color="#ffffff"
          anchorX="center"
          anchorY="middle"
          outlineWidth={0.05}
          outlineColor="#0f172a"
        >
          FACTORY
        </Text>

        {/* Dual Smokestacks on Roof */}
        <Smokestack position={[5.5, 9.4, -2]} height={8.5} />
        <Smokestack position={[7.5, 9.4, -2]} height={9.5} />

        {/* Rooftop Ventilation Pipes */}
        <mesh position={[-4, 10.0, 1]} castShadow>
          <boxGeometry args={[3.5, 1.2, 2.0]} />
          <meshStandardMaterial color="#64748b" metalness={0.7} />
        </mesh>
      </group>

      {/* ─── 2. FRONT-COURTYARD ADMINISTRATION OFFICE BUILDING ── */}
      {/* Positioned at front-left perimeter (Z = 20, X = -8) matching the reference image */}
      {/* Leaves M-04 (at X=8, Z=-6) completely clear and 100% visible! */}
      <AdminOfficeBuilding position={[-8, 0, 20]} />

      {/* ─── 3. LARGE GABLED PRODUCTION HALL (Right Flank) ─────── */}
      {/* Positioned at X = 34, Z = 6 along the eastern edge of the diorama */}
      <LargeGabledFactoryHall position={[34, 0, 6]} />
    </group>
  );
};
