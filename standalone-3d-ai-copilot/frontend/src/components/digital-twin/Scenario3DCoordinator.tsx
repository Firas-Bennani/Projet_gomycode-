import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { Text, Html } from '@react-three/drei';
import * as THREE from 'three';
import { Incident, Action, Machine, Worker, Sensor } from '../../types';
import { AlertTriangle, ShieldAlert, Flame, CheckCircle, Zap } from 'lucide-react';

interface Scenario3DCoordinatorProps {
  currentScenario: string;
  incidents: Incident[];
  actions: Action[];
  machines: Machine[];
  workers: Worker[];
  sensors: Sensor[];
  onSelectMachine?: (machine: Machine) => void;
}

export const Scenario3DCoordinator: React.FC<Scenario3DCoordinatorProps> = ({
  currentScenario,
  incidents,
  actions,
  machines,
  workers,
  sensors,
  onSelectMachine
}) => {
  const activeIncident = incidents.find((i) => i.status === 'ACTIVE');
  const fireGroupRef = useRef<THREE.Group>(null);
  const waterSprinklerRef = useRef<THREE.Group>(null);
  const alarmLightRef = useRef<THREE.PointLight>(null);
  const cyberGridRef = useRef<THREE.Group>(null);
  const heatHazeRef = useRef<THREE.Group>(null);

  const isFire = currentScenario === 'scenario_3' || activeIncident?.type === 'FACTORY_FIRE';
  const isOverheat = currentScenario === 'scenario_1' || activeIncident?.type === 'MACHINE_OVERHEATING';
  const isCyber = currentScenario === 'scenario_2' || activeIncident?.type === 'CYBER_ATTACK' || activeIncident?.type === 'UNAUTHORIZED_ACCESS';

  // Check if mitigation action was authorized/completed
  const isActionAuthorized = actions.some(
    (a) => (a.status === 'AUTHORIZED' || a.status === 'IN_PROGRESS' || a.status === 'COMPLETED') &&
           (isFire ? (a.action_type.includes('ALARM') || a.action_type.includes('FIRE') || a.action_type.includes('SPRINKLER')) :
            isOverheat ? (a.action_type.includes('COOLANT') || a.action_type.includes('SHUTDOWN')) :
            (a.action_type.includes('QUARANTINE') || a.action_type.includes('ISOLATE')))
  );

  // Animate dynamic scenario elements
  useFrame((state) => {
    const t = state.clock.elapsedTime;

    // 1. Factory Fire animation
    if (isFire && fireGroupRef.current) {
      fireGroupRef.current.children.forEach((child, i) => {
        child.position.y += 0.08 + (i % 3) * 0.02;
        child.rotation.y += 0.05;
        child.rotation.z += 0.03;
        const scale = 1.0 - (child.position.y / 8.0);
        child.scale.setScalar(Math.max(0.1, scale));

        if (child.position.y > 7.0) {
          child.position.y = 0.5;
          child.position.x = (Math.random() - 0.5) * 3.5;
          child.position.z = (Math.random() - 0.5) * 3.5;
        }
      });
    }

    // 2. Sprinkler deluge animation
    if (isFire && isActionAuthorized && waterSprinklerRef.current) {
      waterSprinklerRef.current.children.forEach((drop) => {
        drop.position.y -= 0.15;
        if (drop.position.y < 0.2) {
          drop.position.y = 6.0;
          drop.position.x = (Math.random() - 0.5) * 5.0;
          drop.position.z = (Math.random() - 0.5) * 5.0;
        }
      });
    }

    // 3. Alarm Strobe
    if ((isFire || isOverheat || isCyber) && alarmLightRef.current) {
      alarmLightRef.current.intensity = Math.sin(t * 8) > 0 ? 8.0 : 0.5;
    }

    // 4. Cyber Intrusion Matrix animation
    if (isCyber && cyberGridRef.current) {
      cyberGridRef.current.rotation.y += 0.01;
    }

    // 5. Overheating thermal haze animation
    if (isOverheat && heatHazeRef.current) {
      heatHazeRef.current.children.forEach((child, i) => {
        child.position.y += 0.04;
        child.rotation.z += 0.02;
        if (child.position.y > 6.0) {
          child.position.y = 1.5;
          child.position.x = (Math.random() - 0.5) * 2.0;
          child.position.z = (Math.random() - 0.5) * 2.0;
        }
      });
    }
  });

  return (
    <group>
      {/* ═════════════════════════════════════════════════════════════
          SCENARIO 1: M-04 OVERHEATING (Zone B: [8, 0, -6])
         ═════════════════════════════════════════════════════════════ */}
      {isOverheat && (
        <group position={[8, 0, -6]}>
          {/* Thermal heat dome */}
          <mesh position={[0, 2.5, 0]}>
            <sphereGeometry args={[3.2, 16, 16]} />
            <meshStandardMaterial
              color="#dc2626"
              emissive="#ea580c"
              emissiveIntensity={1.2}
              transparent
              opacity={0.3}
              wireframe
            />
          </mesh>

          {/* Pulsing ground heat hazard perimeter */}
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.05, 0]}>
            <ringGeometry args={[3.0, 3.4, 32]} />
            <meshStandardMaterial
              color="#ef4444"
              emissive="#dc2626"
              emissiveIntensity={2.0}
            />
          </mesh>

          {/* Thermal smoke particles */}
          <group ref={heatHazeRef}>
            {Array.from({ length: 12 }).map((_, i) => (
              <mesh
                key={`haze-${i}`}
                position={[(Math.random() - 0.5) * 1.5, 1.5 + Math.random() * 3, (Math.random() - 0.5) * 1.5]}
              >
                <sphereGeometry args={[0.35 + Math.random() * 0.25, 8, 8]} />
                <meshStandardMaterial
                  color="#f97316"
                  emissive="#ea580c"
                  emissiveIntensity={0.8}
                  transparent
                  opacity={0.5}
                />
              </mesh>
            ))}
          </group>

          {/* AI Perception scanner beam from above */}
          <mesh position={[0, 5.5, 0]}>
            <cylinderGeometry args={[0.05, 2.8, 5.0, 16, 1, true]} />
            <meshStandardMaterial
              color="#0284c7"
              emissive="#38bdf8"
              emissiveIntensity={1.2}
              transparent
              opacity={0.25}
              side={THREE.DoubleSide}
            />
          </mesh>

          {/* 3D Floating Tactical Banner */}
          <Html position={[0, 6.5, 0]} center distanceFactor={22}>
            <div className="flex flex-col items-center gap-1 pointer-events-none select-none">
              <div className="flex items-center gap-2 px-3 py-1.5 bg-red-600/90 backdrop-blur-md text-white font-mono text-xs font-bold rounded-lg border border-red-400 shadow-glow-red animate-pulse">
                <AlertTriangle className="w-4 h-4 text-yellow-300" />
                <span>THERMAL RUNAWAY: M-04 [89.4°C]</span>
              </div>
              <div className="px-2 py-0.5 bg-slate-950/90 text-cyan-300 font-mono text-[10px] rounded border border-cyan-500/40">
                {isActionAuthorized ? 'COOLANT INJECTION: ACTIVE' : 'AI COPILOT: EMERGENCY COOLANT PROPOSED'}
              </div>
            </div>
          </Html>

          {isActionAuthorized && (
            <group position={[0, 3.8, 0]}>
              <mesh>
                <ringGeometry args={[1.5, 2.2, 24]} />
                <meshStandardMaterial
                  color="#38bdf8"
                  emissive="#0284c7"
                  emissiveIntensity={2.0}
                  transparent
                  opacity={0.7}
                />
              </mesh>
            </group>
          )}
        </group>
      )}

      {/* ═════════════════════════════════════════════════════════════
          SCENARIO 2: CYBER INTRUSION (Robotic Cell: [22, 0, 14])
         ═════════════════════════════════════════════════════════════ */}
      {isCyber && (
        <group position={[22, 0, 14]}>
          {/* Cyber quarantine isolation dome */}
          <group ref={cyberGridRef}>
            <mesh position={[0, 2.5, 0]}>
              <cylinderGeometry args={[4.2, 4.2, 5.0, 16, 4, true]} />
              <meshStandardMaterial
                color="#a855f7"
                emissive="#9333ea"
                emissiveIntensity={1.5}
                transparent
                opacity={0.35}
                wireframe
              />
            </mesh>
          </group>

          {/* Floor isolation barrier */}
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.05, 0]}>
            <ringGeometry args={[4.0, 4.4, 32]} />
            <meshStandardMaterial
              color="#a855f7"
              emissive="#c084fc"
              emissiveIntensity={2.5}
            />
          </mesh>

          {/* 3D Floating Tactical Banner */}
          <Html position={[0, 6.2, 0]} center distanceFactor={22}>
            <div className="flex flex-col items-center gap-1 pointer-events-none select-none">
              <div className="flex items-center gap-2 px-3 py-1.5 bg-purple-600/90 backdrop-blur-md text-white font-mono text-xs font-bold rounded-lg border border-purple-400 shadow-lg animate-pulse">
                <ShieldAlert className="w-4 h-4 text-purple-200" />
                <span>UNAUTHORIZED PLC PACKET INTRUSION</span>
              </div>
              <div className="px-2 py-0.5 bg-slate-950/90 text-purple-300 font-mono text-[10px] rounded border border-purple-500/40">
                {isActionAuthorized ? 'AIR-GAP QUARANTINE: ENFORCED' : 'AI THREAT MESH: VLAN ISOLATION PROPOSED'}
              </div>
            </div>
          </Html>
        </group>
      )}

      {/* ═════════════════════════════════════════════════════════════
          SCENARIO 3: FACTORY FIRE & EVACUATION (Zone B / M-04 Area: [8, 0, -6])
         ═════════════════════════════════════════════════════════════ */}
      {isFire && (
        <group position={[8, 0, -6]}>
          {/* Central Fire Vortex */}
          <group ref={fireGroupRef} position={[0, 0.5, 0]}>
            {Array.from({ length: 18 }).map((_, i) => (
              <mesh
                key={`flame-${i}`}
                position={[
                  (Math.random() - 0.5) * 2.8,
                  Math.random() * 4.0,
                  (Math.random() - 0.5) * 2.8
                ]}
              >
                <sphereGeometry args={[0.6 + (i % 3) * 0.25, 8, 8]} />
                <meshStandardMaterial
                  color={i % 2 === 0 ? '#ef4444' : '#f97316'}
                  emissive={i % 2 === 0 ? '#dc2626' : '#ea580c'}
                  emissiveIntensity={2.5}
                  transparent
                  opacity={0.8}
                />
              </mesh>
            ))}
          </group>

          {/* Fire point light */}
          <pointLight position={[0, 3.5, 0]} intensity={8.0} color="#f97316" distance={25} />

          {/* Plant-wide rotating emergency strobe */}
          <pointLight ref={alarmLightRef} position={[0, 10, 0]} color="#ef4444" distance={60} />

          {/* Fire perimeter ring */}
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.05, 0]}>
            <ringGeometry args={[4.5, 5.0, 32]} />
            <meshStandardMaterial color="#dc2626" emissive="#ef4444" emissiveIntensity={3.0} />
          </mesh>

          {/* Emergency Evacuation Path (Green laser arrows on floor) */}
          {[-6, -9, -12, -15, -18].map((z, i) => (
            <mesh key={`evac-${i}`} rotation={[-Math.PI / 2, 0, 0]} position={[-8, 0.06, z]}>
              <planeGeometry args={[1.5, 1.0]} />
              <meshStandardMaterial
                color="#10b981"
                emissive="#22c55e"
                emissiveIntensity={2.0}
              />
            </mesh>
          ))}

          {/* Deluge Sprinkler System (if action authorized) */}
          {isActionAuthorized && (
            <group ref={waterSprinklerRef} position={[0, 0, 0]}>
              {Array.from({ length: 30 }).map((_, i) => (
                <mesh
                  key={`drop-${i}`}
                  position={[
                    (Math.random() - 0.5) * 5.0,
                    1.0 + Math.random() * 5.0,
                    (Math.random() - 0.5) * 5.0
                  ]}
                >
                  <sphereGeometry args={[0.08, 6, 6]} />
                  <meshStandardMaterial
                    color="#38bdf8"
                    emissive="#0284c7"
                    emissiveIntensity={1.0}
                    transparent
                    opacity={0.8}
                  />
                </mesh>
              ))}
            </group>
          )}

          {/* 3D Floating Tactical Banner */}
          <Html position={[0, 7.5, 0]} center distanceFactor={24}>
            <div className="flex flex-col items-center gap-1.5 pointer-events-none select-none">
              <div className="flex items-center gap-2 px-3.5 py-2 bg-red-700 text-white font-mono text-xs font-black rounded-lg border-2 border-white shadow-glow-red animate-bounce">
                <Flame className="w-5 h-5 text-yellow-300 animate-pulse" />
                <span>ACTIVE FACTORY FIRE • ZONE B</span>
              </div>
              <div className="px-3 py-1 bg-slate-950/95 text-emerald-400 font-mono text-[11px] font-bold rounded-full border border-emerald-500/50 flex items-center gap-1.5">
                <CheckCircle className="w-3.5 h-3.5" />
                <span>EVACUATION ROUTE CLEAR • SPRINKLERS {isActionAuthorized ? 'ACTIVE' : 'READY'}</span>
              </div>
            </div>
          </Html>
        </group>
      )}

      {/* ═════════════════════════════════════════════════════════════
          NORMAL BASELINE: GREEN PULSING TELEMETRY NODES
         ═════════════════════════════════════════════════════════════ */}
      {!isFire && !isOverheat && !isCyber && (
        <group>
          {/* Subtle green laser grid floor pulse */}
          {[-14, 0, 14, 28].map((x, i) => (
            <mesh key={`grid-pulse-${i}`} rotation={[-Math.PI / 2, 0, 0]} position={[x, 0.03, 0]}>
              <ringGeometry args={[2.8, 2.9, 32]} />
              <meshStandardMaterial
                color="#10b981"
                emissive="#10b981"
                emissiveIntensity={0.6}
                transparent
                opacity={0.4}
              />
            </mesh>
          ))}
        </group>
      )}
    </group>
  );
};
