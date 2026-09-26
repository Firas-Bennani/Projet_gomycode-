import React, { useRef, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Html } from '@react-three/drei';
import * as THREE from 'three';
import { Machine, Worker, Sensor, Zone3D, Incident } from '../../types';
import { AlertTriangle, Flame, ShieldAlert, Cpu, User, Thermometer } from 'lucide-react';

interface Factory3DProps {
  machines: Machine[];
  workers: Worker[];
  sensors: Sensor[];
  zones: Zone3D[];
  incidents: Incident[];
  onSelectObject: (obj: { type: 'machine' | 'worker' | 'sensor' | 'zone'; data: any }) => void;
  selectedId?: string | null;
}

// 3D Machine Component
function Machine3D({
  machine,
  isSelected,
  hasAlert,
  onClick
}: {
  machine: Machine;
  isSelected: boolean;
  hasAlert: boolean;
  onClick: () => void;
}) {
  const meshRef = useRef<THREE.Group>(null);
  const pos = machine.position || { x: 0, y: 0, z: 0 };

  useFrame((state) => {
    if (meshRef.current && hasAlert) {
      // Pulse animation if in critical alert
      const scale = 1 + 0.05 * Math.sin(state.clock.elapsedTime * 6);
      meshRef.current.scale.set(scale, scale, scale);
    } else if (meshRef.current) {
      meshRef.current.scale.set(1, 1, 1);
    }
  });

  const baseColor = hasAlert ? '#ef4444' : isSelected ? '#00f0ff' : '#334155';
  const accentColor = hasAlert ? '#f87171' : '#38bdf8';

  return (
    <group
      ref={meshRef}
      position={[pos.x, pos.y, pos.z]}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      {/* Machine Main Body Enclosure */}
      <mesh position={[0, 1.2, 0]} castShadow receiveShadow>
        <boxGeometry args={[3.2, 2.4, 2.4]} />
        <meshStandardMaterial
          color={baseColor}
          metalness={0.8}
          roughness={0.25}
          emissive={hasAlert ? '#7f1d1d' : '#082f49'}
          emissiveIntensity={hasAlert ? 0.8 : 0.2}
        />
      </mesh>

      {/* Machine Top Hood / Chimney */}
      <mesh position={[0, 2.6, 0]}>
        <boxGeometry args={[1.8, 0.4, 1.6]} />
        <meshStandardMaterial color="#1e293b" metalness={0.9} roughness={0.1} />
      </mesh>

      {/* Spindle / CNC Window */}
      <mesh position={[0, 1.4, 1.25]}>
        <planeGeometry args={[2.0, 1.2]} />
        <meshStandardMaterial
          color={hasAlert ? '#ffedd5' : '#00f0ff'}
          emissive={hasAlert ? '#f97316' : '#0284c7'}
          emissiveIntensity={0.6}
          transparent
          opacity={0.85}
        />
      </mesh>

      {/* Control Panel Console */}
      <mesh position={[1.8, 1.2, 0.8]} rotation={[0, -0.4, 0]}>
        <boxGeometry args={[0.3, 1.2, 0.6]} />
        <meshStandardMaterial color="#0f172a" />
      </mesh>

      {/* Machine Label in 3D */}
      <Text
        position={[0, 3.2, 0]}
        fontSize={0.5}
        color={hasAlert ? '#fca5a5' : '#e2e8f0'}
        anchorX="center"
        anchorY="middle"
      >
        {machine.id}
      </Text>

      {/* Alert Marker Floating Overlay */}
      {hasAlert && (
        <Html position={[0, 4.0, 0]} center distanceFactor={15}>
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-red-600/90 text-white rounded-full text-xs font-bold shadow-glow-red animate-bounce border border-red-400">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>CRITICAL</span>
          </div>
        </Html>
      )}
    </group>
  );
}

// 3D Worker Avatar
function Worker3D({ worker, onClick }: { worker: Worker; onClick: () => void }) {
  const pos = worker.position || { x: 0, y: 0, z: 0 };
  const isAtRisk = worker.status === 'AT_RISK';

  return (
    <group
      position={[pos.x, 0, pos.z]}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      {/* Body / High-vis Vest */}
      <mesh position={[0, 0.85, 0]}>
        <cylinderGeometry args={[0.25, 0.28, 0.9, 16]} />
        <meshStandardMaterial color={isAtRisk ? '#ef4444' : '#f59e0b'} metalness={0.1} roughness={0.8} />
      </mesh>

      {/* Head */}
      <mesh position={[0, 1.5, 0]}>
        <sphereGeometry args={[0.18, 16, 16]} />
        <meshStandardMaterial color="#fed7aa" />
      </mesh>

      {/* Safety Helmet */}
      <mesh position={[0, 1.62, 0]}>
        <cylinderGeometry args={[0.22, 0.24, 0.15, 16]} />
        <meshStandardMaterial color="#ffffff" roughness={0.3} />
      </mesh>

      {/* Worker Label */}
      <Text position={[0, 2.0, 0]} fontSize={0.3} color="#94a3b8" anchorX="center">
        {worker.id}
      </Text>
    </group>
  );
}

// Zone Floor Perimeter
function ZonePerimeter({ zone, hasIncident }: { zone: Zone3D; hasIncident: boolean }) {
  let x = 0;
  if (zone.id === 'ZONE_A') x = -10;
  if (zone.id === 'ZONE_B') x = 8;
  if (zone.id === 'ZONE_C') x = 20;
  if (zone.id === 'ZONE_D') x = -20;

  const floorColor = hasIncident ? '#450a0a' : '#09101d';
  const borderColor = hasIncident ? '#ef4444' : '#1e293b';

  return (
    <group position={[x, 0.01, 0]}>
      {/* Zone Floor Pad */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[11, 16]} />
        <meshStandardMaterial
          color={floorColor}
          emissive={hasIncident ? '#ef4444' : '#0369a1'}
          emissiveIntensity={hasIncident ? 0.35 : 0.05}
          roughness={0.8}
        />
      </mesh>

      {/* Boundary Lines */}
      <lineSegments>
        <edgesGeometry args={[new THREE.BoxGeometry(11, 0.05, 16)]} />
        <lineBasicMaterial color={borderColor} linewidth={2} />
      </lineSegments>

      {/* Zone Title on Floor */}
      <Text
        position={[0, 0.05, 7.0]}
        rotation={[-Math.PI / 2, 0, 0]}
        fontSize={0.65}
        color={hasIncident ? '#fca5a5' : '#38bdf8'}
        anchorX="center"
      >
        {zone.name.split('—')[0].trim()}
      </Text>
    </group>
  );
}

export const Factory3D: React.FC<Factory3DProps> = ({
  machines,
  workers,
  sensors,
  zones,
  incidents,
  onSelectObject,
  selectedId
}) => {
  const activeIncidents = incidents.filter((i) => i.status === 'ACTIVE');

  return (
    <div className="w-full h-full relative bg-[#040811] rounded-xl overflow-hidden border border-slate-800 shadow-2xl">
      {/* 3D Scene Overlay Badge */}
      <div className="absolute top-3 left-3 z-10 flex items-center gap-2 px-3 py-1.5 bg-slate-900/80 backdrop-blur-md rounded-lg border border-cyan-500/30 text-xs font-mono text-cyan-400">
        <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
        <span>3D DIGITAL TWIN • REAL-TIME TELEMETRY</span>
      </div>

      {/* Camera Guidance Controls HUD */}
      <div className="absolute bottom-3 right-3 z-10 px-3 py-1 bg-slate-950/70 backdrop-blur text-[11px] text-slate-400 rounded border border-slate-800 font-mono">
        🖱️ Left Click: Rotate • Right Click: Pan • Scroll: Zoom
      </div>

      <Canvas
        camera={{ position: [0, 24, 28], fov: 45 }}
        shadows
        gl={{ antialias: true }}
      >
        <ambientLight intensity={0.6} />
        <directionalLight
          position={[15, 30, 20]}
          intensity={1.2}
          castShadow
          shadow-mapSize-width={2048}
          shadow-mapSize-height={2048}
        />
        <pointLight position={[8, 8, 0]} intensity={1.5} color="#38bdf8" distance={25} />
        {activeIncidents.length > 0 && (
          <pointLight position={[8, 6, 0]} intensity={3.0} color="#ef4444" distance={30} />
        )}

        <OrbitControls
          maxPolarAngle={Math.PI / 2.1}
          minDistance={8}
          maxDistance={65}
          enableDamping
          dampingFactor={0.05}
        />

        {/* Global Ground Floor */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.05, 0]} receiveShadow>
          <planeGeometry args={[120, 120]} />
          <meshStandardMaterial color="#050a14" roughness={0.9} />
        </mesh>

        <gridHelper args={[100, 50, '#1e293b', '#0b1329']} position={[0, 0, 0]} />

        {/* Factory Zones */}
        {zones.map((zone) => {
          const hasInc = activeIncidents.some((i) => i.zone === zone.id);
          return <ZonePerimeter key={zone.id} zone={zone} hasIncident={hasInc} />;
        })}

        {/* 3D Machines */}
        {machines.map((machine) => {
          const hasAlert = machine.status === 'CRITICAL' || activeIncidents.some((i) => i.affected_assets.includes(machine.id));
          return (
            <Machine3D
              key={machine.id}
              machine={machine}
              isSelected={selectedId === machine.id}
              hasAlert={hasAlert}
              onClick={() => onSelectObject({ type: 'machine', data: machine })}
            />
          );
        })}

        {/* 3D Workers */}
        {workers.map((worker) => (
          <Worker3D
            key={worker.id}
            worker={worker}
            onClick={() => onSelectObject({ type: 'worker', data: worker })}
          />
        ))}
      </Canvas>
    </div>
  );
};
