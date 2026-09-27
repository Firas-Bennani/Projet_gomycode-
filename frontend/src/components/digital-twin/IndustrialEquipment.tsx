import React, { useState } from 'react';
import * as THREE from 'three';
import { Text, Html } from '@react-three/drei';
import { Machine, Sensor } from '../../types';
import { AlertTriangle } from 'lucide-react';

interface IndustrialEquipmentProps {
  machines: Machine[];
  sensors: Sensor[];
  selectedId?: string | null;
  onSelectObject: (obj: { type: 'machine'; data: Machine }) => void;
  activeIncidents: any[];
}

export const IndustrialEquipment: React.FC<IndustrialEquipmentProps> = ({
  machines,
  sensors,
  selectedId,
  onSelectObject,
  activeIncidents
}) => {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const m01 = machines.find((m) => m.id === 'M-01');
  const m02 = machines.find((m) => m.id === 'M-02');
  const m04 = machines.find((m) => m.id === 'M-04');
  const m05 = machines.find((m) => m.id === 'M-05');
  const m06 = machines.find((m) => m.id === 'M-06');

  const m04Alert = m04?.status === 'CRITICAL' || activeIncidents.some((i) => i.affected_assets?.includes('M-04'));
  const isSelected = (id: string) => selectedId === id;
  const isHovered = (id: string) => hoveredId === id;

  return (
    <group>
      {/* ─── HEAVY MILLING M-04 (Zone B / Incident Target) ───────── */}
      <group
        position={[8.0, 0, -6.0]}
        onClick={(e) => {
          e.stopPropagation();
          if (m04) onSelectObject({ type: 'machine', data: m04 });
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHoveredId('M-04');
          document.body.style.cursor = 'pointer';
        }}
        onPointerOut={() => {
          setHoveredId(null);
          document.body.style.cursor = 'auto';
        }}
      >
        <mesh position={[0, 0.6, 0]} castShadow receiveShadow>
          <boxGeometry args={[4.4, 1.2, 3.4]} />
          <meshStandardMaterial color="#334155" metalness={0.7} roughness={0.3} />
        </mesh>

        <mesh position={[0, 2.3, 0]} castShadow receiveShadow>
          <boxGeometry args={[4.0, 2.2, 3.0]} />
          <meshStandardMaterial
            color={m04Alert ? '#dc2626' : isSelected('M-04') ? '#38bdf8' : '#ea580c'}
            metalness={0.6}
            roughness={0.3}
            emissive={m04Alert ? '#991b1b' : isSelected('M-04') ? '#0284c7' : '#9a3412'}
            emissiveIntensity={m04Alert ? 0.9 : 0.25}
          />
        </mesh>

        <mesh position={[0, 3.9, -0.4]} castShadow>
          <boxGeometry args={[1.8, 1.0, 1.8]} />
          <meshStandardMaterial color="#f8fafc" metalness={0.9} roughness={0.1} />
        </mesh>

        <mesh position={[0, 2.3, 1.51]}>
          <planeGeometry args={[2.8, 1.4]} />
          <meshStandardMaterial
            color={m04Alert ? '#fb923c' : '#38bdf8'}
            emissive={m04Alert ? '#ea580c' : '#0284c7'}
            emissiveIntensity={m04Alert ? 0.9 : 0.6}
            transparent
            opacity={0.85}
          />
        </mesh>

        <group position={[-1.9, 3.5, -1.2]}>
          <mesh position={[0, 0.5, 0]}>
            <cylinderGeometry args={[0.06, 0.06, 1.0, 8]} />
            <meshStandardMaterial color="#64748b" />
          </mesh>
          <mesh position={[0, 1.3, 0]}>
            <cylinderGeometry args={[0.12, 0.12, 0.2, 12]} />
            <meshStandardMaterial color="#ef4444" emissive="#ef4444" emissiveIntensity={m04Alert ? 1.8 : 0.1} />
          </mesh>
          <mesh position={[0, 1.1, 0]}>
            <cylinderGeometry args={[0.12, 0.12, 0.2, 12]} />
            <meshStandardMaterial color="#f59e0b" emissive="#f59e0b" emissiveIntensity={m04Alert ? 0.3 : 0.1} />
          </mesh>
          <mesh position={[0, 0.9, 0]}>
            <cylinderGeometry args={[0.12, 0.12, 0.2, 12]} />
            <meshStandardMaterial color="#10b981" emissive="#10b981" emissiveIntensity={m04Alert ? 0.0 : 1.2} />
          </mesh>
        </group>

        {(isSelected('M-04') || isHovered('M-04')) && (
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
            <ringGeometry args={[2.6, 2.8, 32]} />
            <meshStandardMaterial color="#38bdf8" emissive="#38bdf8" emissiveIntensity={2.0} />
          </mesh>
        )}

        <Text position={[0, 4.9, 0]} fontSize={0.6} color={m04Alert ? '#fca5a5' : '#f8fafc'} anchorX="center" outlineWidth={0.04} outlineColor="#020617">
          HEAVY MILLING M-04
        </Text>

        {m04Alert && (
          <Html position={[0, 6.0, 0]} center distanceFactor={16}>
            <div className="flex items-center gap-1.5 px-3.5 py-1.5 bg-red-600 text-white rounded-full text-xs font-extrabold shadow-glow-red animate-bounce border-2 border-white font-mono">
              <AlertTriangle className="w-4 h-4 text-yellow-300" />
              <span>CRITICAL OVERHEATING</span>
            </div>
          </Html>
        )}
      </group>

      {/* ─── INDUCTION FURNACE M-05 (Zone C) ─────────────────────── */}
      <group
        position={[22.0, 0, -4.0]}
        onClick={(e) => {
          e.stopPropagation();
          if (m05) onSelectObject({ type: 'machine', data: m05 });
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHoveredId('M-05');
          document.body.style.cursor = 'pointer';
        }}
        onPointerOut={() => {
          setHoveredId(null);
          document.body.style.cursor = 'auto';
        }}
      >
        <mesh position={[0, 2.2, 0]} castShadow receiveShadow>
          <cylinderGeometry args={[1.9, 2.0, 4.0, 24]} />
          <meshStandardMaterial color="#64748b" metalness={0.9} roughness={0.2} />
        </mesh>

        <mesh position={[0, 4.1, 0]}>
          <cylinderGeometry args={[1.6, 1.6, 0.3, 24]} />
          <meshStandardMaterial color="#f97316" emissive="#ea580c" emissiveIntensity={1.8} />
        </mesh>

        <mesh position={[0, 2.2, 0]}>
          <torusGeometry args={[2.0, 0.08, 12, 24]} />
          <meshStandardMaterial color="#f59e0b" />
        </mesh>

        {(isSelected('M-05') || isHovered('M-05')) && (
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
            <ringGeometry args={[2.3, 2.5, 32]} />
            <meshStandardMaterial color="#38bdf8" emissive="#38bdf8" emissiveIntensity={2.0} />
          </mesh>
        )}

        <Text position={[0, 4.8, 0]} fontSize={0.55} color="#f8fafc" anchorX="center" outlineWidth={0.03} outlineColor="#020617">
          INDUCTION FURNACE M-05
        </Text>
      </group>

      {/* ─── CNC 01 (M-01) (Zone A) ─────────────────────────────── */}
      <group
        position={[-2.0, 0, -6.0]}
        onClick={(e) => {
          e.stopPropagation();
          if (m01) onSelectObject({ type: 'machine', data: m01 });
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHoveredId('M-01');
          document.body.style.cursor = 'pointer';
        }}
        onPointerOut={() => {
          setHoveredId(null);
          document.body.style.cursor = 'auto';
        }}
      >
        <mesh position={[0, 1.5, 0]} castShadow receiveShadow>
          <boxGeometry args={[3.6, 2.8, 2.8]} />
          <meshStandardMaterial color="#0284c7" metalness={0.6} roughness={0.3} />
        </mesh>
        <mesh position={[0, 1.7, 1.41]}>
          <planeGeometry args={[2.2, 1.4]} />
          <meshStandardMaterial color="#38bdf8" emissive="#0284c7" emissiveIntensity={0.5} transparent opacity={0.8} />
        </mesh>

        {(isSelected('M-01') || isHovered('M-01')) && (
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
            <ringGeometry args={[2.1, 2.3, 32]} />
            <meshStandardMaterial color="#38bdf8" emissive="#38bdf8" emissiveIntensity={2.0} />
          </mesh>
        )}

        <Text position={[0, 3.4, 0]} fontSize={0.5} color="#f8fafc" anchorX="center" outlineWidth={0.03} outlineColor="#020617">
          CNC 01 (M-01)
        </Text>
      </group>

      {/* ─── PRESS 02 (M-02) (Zone A/B) ─────────────────────────── */}
      <group
        position={[-2.0, 0, 4.0]}
        onClick={(e) => {
          e.stopPropagation();
          if (m02) onSelectObject({ type: 'machine', data: m02 });
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHoveredId('M-02');
          document.body.style.cursor = 'pointer';
        }}
        onPointerOut={() => {
          setHoveredId(null);
          document.body.style.cursor = 'auto';
        }}
      >
        <mesh position={[0, 1.9, 0]} castShadow receiveShadow>
          <boxGeometry args={[3.0, 3.6, 3.0]} />
          <meshStandardMaterial color="#475569" metalness={0.8} roughness={0.2} />
        </mesh>

        {(isSelected('M-02') || isHovered('M-02')) && (
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
            <ringGeometry args={[2.0, 2.2, 32]} />
            <meshStandardMaterial color="#38bdf8" emissive="#38bdf8" emissiveIntensity={2.0} />
          </mesh>
        )}

        <Text position={[0, 4.2, 0]} fontSize={0.5} color="#f8fafc" anchorX="center" outlineWidth={0.03} outlineColor="#020617">
          PRESS 02 (M-02)
        </Text>
      </group>

      {/* ─── ROBOTIC CELL C-01 (M-06) (Zone C) ──────────────────── */}
      <group
        position={[22.0, 0, 14.0]}
        onClick={(e) => {
          e.stopPropagation();
          if (m06) onSelectObject({ type: 'machine', data: m06 });
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHoveredId('M-06');
          document.body.style.cursor = 'pointer';
        }}
        onPointerOut={() => {
          setHoveredId(null);
          document.body.style.cursor = 'auto';
        }}
      >
        <mesh position={[0, 0.4, 0]} castShadow>
          <cylinderGeometry args={[1.2, 1.4, 0.8, 16]} />
          <meshStandardMaterial color="#1e293b" metalness={0.8} />
        </mesh>

        <mesh position={[0, 1.6, 0]} rotation={[0.2, 0, 0]} castShadow>
          <boxGeometry args={[0.6, 1.8, 0.6]} />
          <meshStandardMaterial color="#eab308" metalness={0.5} roughness={0.3} />
        </mesh>

        <mesh position={[0, 2.5, 0.3]}>
          <sphereGeometry args={[0.45, 16, 16]} />
          <meshStandardMaterial color="#0284c7" metalness={0.9} />
        </mesh>

        <mesh position={[0, 3.2, -0.2]} rotation={[-0.4, 0, 0]} castShadow>
          <boxGeometry args={[0.5, 1.6, 0.5]} />
          <meshStandardMaterial color="#eab308" metalness={0.5} roughness={0.3} />
        </mesh>

        <mesh position={[0, 3.9, -0.6]}>
          <boxGeometry args={[0.7, 0.3, 0.7]} />
          <meshStandardMaterial color="#0284c7" emissive="#0284c7" emissiveIntensity={0.6} />
        </mesh>

        <lineSegments position={[0, 2.0, 0]}>
          <edgesGeometry args={[new THREE.BoxGeometry(5.8, 4.0, 5.8)]} />
          <lineBasicMaterial color="#0d9488" linewidth={2} />
        </lineSegments>

        {(isSelected('M-06') || isHovered('M-06')) && (
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
            <ringGeometry args={[3.0, 3.2, 32]} />
            <meshStandardMaterial color="#2dd4bf" emissive="#2dd4bf" emissiveIntensity={2.0} />
          </mesh>
        )}

        <Text position={[0, 4.7, 0]} fontSize={0.55} color="#2dd4bf" anchorX="center" outlineWidth={0.03} outlineColor="#020617">
          ROBOTIC CELL C-01 (M-06)
        </Text>
      </group>
    </group>
  );
};
