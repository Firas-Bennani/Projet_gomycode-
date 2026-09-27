import React, { useMemo } from 'react';
import * as THREE from 'three';

export const HyperbolicCoolingTower: React.FC<{ position: [number, number, number]; scale?: number }> = ({
  position,
  scale = 1.0
}) => {
  return (
    <group position={position} scale={[scale, scale, scale]}>
      <mesh position={[0, 6.0, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[2.2, 3.8, 12.0, 32, 1, true]} />
        <meshStandardMaterial color="#f1f5f9" roughness={0.5} side={THREE.DoubleSide} />
      </mesh>

      <mesh position={[0, 12.0, 0]}>
        <torusGeometry args={[2.2, 0.2, 16, 32]} />
        <meshStandardMaterial color="#334155" metalness={0.8} />
      </mesh>

      <mesh position={[0, 11.9, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[2.1, 32]} />
        <meshStandardMaterial color="#0f172a" />
      </mesh>

      {Array.from({ length: 12 }).map((_, i) => {
        const angle = (i * Math.PI * 2) / 12;
        const x = Math.cos(angle) * 3.6;
        const z = Math.sin(angle) * 3.6;
        return (
          <mesh key={`pillar-${i}`} position={[x, 0.6, z]} rotation={[0, -angle, 0]} castShadow>
            <boxGeometry args={[0.3, 1.2, 0.3]} />
            <meshStandardMaterial color="#cbd5e1" roughness={0.7} />
          </mesh>
        );
      })}
    </group>
  );
};

export const RefineryTankWithPiping: React.FC<{
  position: [number, number, number];
  radius?: number;
  height?: number;
}> = ({ position, radius = 3.6, height = 5.0 }) => {
  return (
    <group position={position}>
      <mesh position={[0, 0.15, 0]} receiveShadow>
        <cylinderGeometry args={[radius + 0.25, radius + 0.35, 0.3, 32]} />
        <meshStandardMaterial color="#eab308" metalness={0.7} roughness={0.3} />
      </mesh>

      <mesh position={[0, height / 2 + 0.3, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[radius, radius, height, 32]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.85} roughness={0.2} />
      </mesh>

      {[0.25, 0.55, 0.85].map((factor, idx) => (
        <mesh key={`band-${idx}`} position={[0, height * factor + 0.3, 0]}>
          <torusGeometry args={[radius + 0.04, 0.06, 8, 32]} />
          <meshStandardMaterial color="#334155" metalness={0.9} />
        </mesh>
      ))}

      <group position={[0, height + 0.3, 0]}>
        <mesh castShadow>
          <cylinderGeometry args={[radius * 0.98, radius, 0.3, 32]} />
          <meshStandardMaterial color="#cbd5e1" metalness={0.9} roughness={0.15} />
        </mesh>
        <mesh position={[0, 0.4, 0]}>
          <torusGeometry args={[radius * 0.94, 0.05, 8, 32]} />
          <meshStandardMaterial color="#0f172a" metalness={0.9} />
        </mesh>

        <mesh position={[-0.8, 0.7, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
          <cylinderGeometry args={[0.5, 0.5, 2.2, 16]} />
          <meshStandardMaterial color="#e2e8f0" metalness={0.9} roughness={0.1} />
        </mesh>
      </group>

      <group position={[-radius - 0.5, height / 2 + 0.3, 0]}>
        <mesh position={[0, -0.6, 0]} castShadow>
          <cylinderGeometry args={[0.45, 0.45, height + 1.2, 16]} />
          <meshStandardMaterial color="#cbd5e1" metalness={0.95} roughness={0.08} />
        </mesh>
        <mesh position={[0, -height / 2 - 1.0, 0]}>
          <cylinderGeometry args={[0.65, 0.65, 0.3, 16]} />
          <meshStandardMaterial color="#eab308" metalness={0.8} />
        </mesh>
        <mesh position={[0.65, height / 2 + 0.1, 0]} rotation={[0, 0, -Math.PI / 2]}>
          <torusGeometry args={[0.65, 0.45, 16, 16, Math.PI / 2]} />
          <meshStandardMaterial color="#cbd5e1" metalness={0.95} roughness={0.08} />
        </mesh>
      </group>
    </group>
  );
};

export const IronRoofFactoryComplex: React.FC<{
  position: [number, number, number];
  rotation?: [number, number, number];
}> = ({ position, rotation = [0, 0, 0] }) => {
  return (
    <group position={position} rotation={rotation}>
      <mesh position={[0, 2.4, 0]} castShadow receiveShadow>
        <boxGeometry args={[18, 4.8, 14]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.6} roughness={0.35} />
      </mesh>

      <group position={[0, 4.8, 0]}>
        <mesh position={[-4.6, 1.2, 0]} rotation={[0, 0, 0.28]} castShadow receiveShadow>
          <boxGeometry args={[9.6, 0.2, 14.4]} />
          <meshStandardMaterial color="#475569" metalness={0.8} roughness={0.25} />
        </mesh>

        <mesh position={[4.6, 1.2, 0]} rotation={[0, 0, -0.28]} castShadow receiveShadow>
          <boxGeometry args={[9.6, 0.2, 14.4]} />
          <meshStandardMaterial color="#475569" metalness={0.8} roughness={0.25} />
        </mesh>

        <mesh position={[0, 2.5, 0]}>
          <boxGeometry args={[0.5, 0.3, 14.5]} />
          <meshStandardMaterial color="#0f172a" metalness={0.9} />
        </mesh>
      </group>

      <mesh position={[0, 7.8, 0]} castShadow receiveShadow>
        <boxGeometry args={[11, 2.6, 9]} />
        <meshStandardMaterial color="#64748b" metalness={0.7} roughness={0.3} />
      </mesh>
      <mesh position={[0, 9.3, 0]} rotation={[0, 0, 0.22]} castShadow>
        <boxGeometry args={[11.5, 0.2, 9.4]} />
        <meshStandardMaterial color="#334155" metalness={0.85} roughness={0.2} />
      </mesh>

      <group position={[4.5, 8.5, -2]}>
        <mesh castShadow>
          <cylinderGeometry args={[0.8, 1.1, 10.0, 24]} />
          <meshStandardMaterial color="#334155" metalness={0.85} roughness={0.2} />
        </mesh>
        <mesh position={[0, 4.8, 0]}>
          <cylinderGeometry args={[0.82, 0.82, 0.8, 24]} />
          <meshStandardMaterial color="#ef4444" emissive="#dc2626" emissiveIntensity={0.6} />
        </mesh>
      </group>

      <mesh position={[-9.1, 3.2, 0]}>
        <boxGeometry args={[0.3, 0.3, 14.0]} />
        <meshStandardMaterial color="#eab308" metalness={0.8} />
      </mesh>

      {[-5, 0, 5].map((x, idx) => (
        <group key={`bay-${idx}`} position={[x, 1.8, 7.05]}>
          <mesh>
            <planeGeometry args={[3.6, 3.2]} />
            <meshStandardMaterial color="#334155" metalness={0.8} roughness={0.3} />
          </mesh>
          <mesh position={[0, 0, 0.02]}>
            <planeGeometry args={[3.8, 3.4]} />
            <meshStandardMaterial color="#0f172a" />
          </mesh>
        </group>
      ))}
    </group>
  );
};

export const LatticeFrameDistillationTower: React.FC<{ position: [number, number, number]; height?: number }> = ({
  position,
  height = 16.0
}) => {
  return (
    <group position={position}>
      <mesh position={[0, height / 2, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[1.2, 1.3, height, 24]} />
        <meshStandardMaterial color="#e2e8f0" metalness={0.85} roughness={0.15} />
      </mesh>

      <mesh position={[0, height, 0]} castShadow>
        <sphereGeometry args={[1.2, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial color="#cbd5e1" metalness={0.9} roughness={0.1} />
      </mesh>

      <group position={[0, height / 2, 0]}>
        {[-1.8, 1.8].map((x, i) =>
          [-1.8, 1.8].map((z, j) => (
            <mesh key={`lat-leg-${i}-${j}`} position={[x, 0, z]} castShadow>
              <boxGeometry args={[0.2, height, 0.2]} />
              <meshStandardMaterial color="#eab308" metalness={0.7} roughness={0.3} />
            </mesh>
          ))
        )}
        {[0.25, 0.5, 0.75, 0.95].map((factor, idx) => (
          <mesh key={`ring-${idx}`} position={[0, height * (factor - 0.5), 0]}>
            <boxGeometry args={[3.8, 0.15, 3.8]} />
            <meshStandardMaterial color="#ca8a04" metalness={0.8} />
          </mesh>
        ))}
      </group>
    </group>
  );
};

export const OverheadPipeTrussBridge: React.FC<{ position: [number, number, number]; length?: number }> = ({
  position,
  length = 24.0
}) => {
  return (
    <group position={position}>
      <mesh position={[0, 4.0, 0]} castShadow>
        <boxGeometry args={[length, 0.8, 1.4]} />
        <meshStandardMaterial color="#eab308" metalness={0.7} roughness={0.3} />
      </mesh>

      {[-0.3, 0.3].map((z, idx) => (
        <mesh key={`truss-pipe-${idx}`} position={[0, 4.0, z]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.25, 0.25, length, 16]} />
          <meshStandardMaterial color="#f8fafc" metalness={0.95} roughness={0.05} />
        </mesh>
      ))}

      {[-length / 2 + 0.5, length / 2 - 0.5].map((x, idx) => (
        <mesh key={`tower-${idx}`} position={[x, 2.0, 0]} castShadow>
          <boxGeometry args={[0.6, 4.0, 1.4]} />
          <meshStandardMaterial color="#0f172a" metalness={0.8} />
        </mesh>
      ))}
    </group>
  );
};

export const IndustrialBuildings: React.FC = () => {
  return (
    <group>
      {/* ─── REAR COOLING TOWER ROW (4 in a row as in reference image) ─── */}
      <group position={[0, 0, 0]}>
        <HyperbolicCoolingTower position={[-8, 0, -24]} scale={0.88} />
        <HyperbolicCoolingTower position={[-16, 0, -24]} scale={0.88} />
        <HyperbolicCoolingTower position={[-24, 0, -24]} scale={0.88} />
        <HyperbolicCoolingTower position={[-32, 0, -24]} scale={0.88} />
      </group>

      {/* ─── LEFT FLANK COOLING TOWERS (3 in a row framing the hangars) ─── */}
      <group position={[0, 0, 0]}>
        <HyperbolicCoolingTower position={[-38, 0, -10]} scale={0.85} />
        <HyperbolicCoolingTower position={[-38, 0, 2]} scale={0.85} />
        <HyperbolicCoolingTower position={[-38, 0, 14]} scale={0.85} />
      </group>

      {/* ─── REAR-RIGHT TALL DISTILLATION TOWERS (Lattice framework) ───── */}
      <LatticeFrameDistillationTower position={[22, 0, -24]} height={17} />
      <LatticeFrameDistillationTower position={[27, 0, -24]} height={15} />

      {/* ─── INDUSTRIAL IRON ROOF MANUFACTURING COMPLEX ───────────────── */}
      <IronRoofFactoryComplex position={[28, 0, -14]} />

      {/* ─── REFINERY STORAGE TANKS WITH PIPING & CATWALKS ────────────── */}
      <RefineryTankWithPiping position={[-20, 0, -15]} radius={3.2} height={4.8} />
      <RefineryTankWithPiping position={[-28, 0, -15]} radius={3.6} height={5.4} />

      {/* ─── OVERHEAD UTILITY PIPE TRUSS BRIDGES ───────────────────────── */}
      <OverheadPipeTrussBridge position={[-24, 0, -9]} length={18} />
      <OverheadPipeTrussBridge position={[25, 0, -18]} length={16} />
    </group>
  );
};
