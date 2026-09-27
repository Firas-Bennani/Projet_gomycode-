import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface IndustrialInfrastructureProps {
  activeIncidents: any[];
}

export const IndustrialInfrastructure: React.FC<IndustrialInfrastructureProps> = ({ activeIncidents }) => {
  const smokeRef = useRef<THREE.Group>(null);
  const hasFire = activeIncidents.some((i) => i.type === 'FACTORY_FIRE' || i.type === 'MACHINE_OVERHEATING');

  useFrame(() => {
    if (smokeRef.current && hasFire) {
      smokeRef.current.children.forEach((child) => {
        child.position.y += 0.05;
        child.rotation.z += 0.02;
        if (child.position.y > 9.5) {
          child.position.y = 3.5;
          child.position.x = (Math.random() - 0.5) * 1.5;
          child.position.z = (Math.random() - 0.5) * 1.5;
        }
      });
    }
  });

  return (
    <group>
      {/* ─── OVERHEAD CABLE TRAYS ──────────────────────────────── */}
      <group position={[0, 0, 0]}>
        <mesh position={[0, 7.5, -14]}>
          <boxGeometry args={[48.0, 0.4, 0.4]} />
          <meshStandardMaterial color="#0284c7" metalness={0.9} roughness={0.1} />
        </mesh>

        <mesh position={[0, 7.0, -14]}>
          <boxGeometry args={[48.0, 0.4, 0.4]} />
          <meshStandardMaterial color="#f8fafc" metalness={0.95} roughness={0.05} />
        </mesh>

        <mesh position={[-16, 7.5, 0]}>
          <boxGeometry args={[0.4, 0.4, 34.0]} />
          <meshStandardMaterial color="#eab308" metalness={0.8} roughness={0.2} />
        </mesh>

        {[-20, 0, 20].map((x) => (
          <group key={`pylon-${x}`} position={[x, 3.7, -14]}>
            <mesh>
              <cylinderGeometry args={[0.25, 0.3, 7.4, 8]} />
              <meshStandardMaterial color="#0f172a" metalness={0.9} />
            </mesh>
            <mesh position={[0, 3.7, 0]}>
              <boxGeometry args={[0.6, 0.4, 2.4]} />
              <meshStandardMaterial color="#0284c7" />
            </mesh>
          </group>
        ))}
      </group>

      {/* ─── M-04 HAZARD PERIMETER ──────────────────────────────── */}
      <lineSegments position={[8.0, 0.04, -6.0]}>
        <edgesGeometry args={[new THREE.BoxGeometry(6.8, 0.01, 5.8)]} />
        <lineBasicMaterial color="#f59e0b" linewidth={4} />
      </lineSegments>

      {[-3.6, 3.6].map((x) =>
        [-3.0, 3.0].map((z) => (
          <group key={`bollard-${x}-${z}`} position={[8.0 + x, 0.6, -6.0 + z]}>
            <mesh>
              <cylinderGeometry args={[0.15, 0.15, 1.2, 12]} />
              <meshStandardMaterial color="#f59e0b" metalness={0.4} />
            </mesh>
            <mesh position={[0, 0.4, 0]}>
              <cylinderGeometry args={[0.16, 0.16, 0.2, 12]} />
              <meshStandardMaterial color="#0f172a" />
            </mesh>
          </group>
        ))
      )}

      {/* ─── CONVEYOR BELT SYSTEM ──────────────────────────────── */}
      <group position={[-10, 0, 2]}>
        {/* Belt supports */}
        {Array.from({ length: 6 }).map((_, i) => (
          <mesh key={`conv-leg-${i}`} position={[i * 3, 0.8, 0]} castShadow>
            <boxGeometry args={[0.2, 1.6, 0.8]} />
            <meshStandardMaterial color="#475569" metalness={0.7} />
          </mesh>
        ))}
        {/* Belt surface */}
        <mesh position={[7.5, 1.65, 0]}>
          <boxGeometry args={[18, 0.1, 0.7]} />
          <meshStandardMaterial color="#1e293b" roughness={0.9} />
        </mesh>
        {/* Belt side rails */}
        {[-0.4, 0.4].map((z) => (
          <mesh key={`rail-${z}`} position={[7.5, 1.75, z]}>
            <boxGeometry args={[18, 0.12, 0.06]} />
            <meshStandardMaterial color="#eab308" metalness={0.7} />
          </mesh>
        ))}
      </group>

      {/* ─── FIRE / SMOKE EFFECT (active incident) ─────────────── */}
      {hasFire && (
        <group position={[8.0, 3.8, -6.0]} ref={smokeRef}>
          {Array.from({ length: 16 }).map((_, i) => (
            <mesh
              key={`smoke-${i}`}
              position={[
                (Math.random() - 0.5) * 1.8,
                Math.random() * 4.5,
                (Math.random() - 0.5) * 1.8
              ]}
            >
              <sphereGeometry args={[0.7 + Math.random() * 0.5, 8, 8]} />
              <meshStandardMaterial
                color="#ef4444"
                emissive="#dc2626"
                emissiveIntensity={1.2}
                transparent
                opacity={0.65}
              />
            </mesh>
          ))}
        </group>
      )}
    </group>
  );
};
