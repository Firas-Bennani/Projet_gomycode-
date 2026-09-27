import React, { useState, Suspense, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Text, Grid } from '@react-three/drei';
import * as THREE from 'three';
import { Machine, Worker, Sensor, Zone3D, Incident, Action } from '../../types';
import { IndustrialBuildings } from './IndustrialBuildings';
import { IndustrialEquipment } from './IndustrialEquipment';
import { IndustrialInfrastructure } from './IndustrialInfrastructure';
import { FactoryGround } from './FactoryGround';
import { MainFactoryBuilding } from './MainFactoryBuilding';
import { MachineGLB } from './MachineGLB';
import { Scenario3DCoordinator } from './Scenario3DCoordinator';
import { Camera3DOverlay } from './Camera3DOverlay';
import { VirtualCameraRenderer } from './VirtualCameraRenderer';
import { PerformancePanel } from './PerformancePanel';
import { CameraConfig, CameraPerceptionResult } from '../../services/cameraPerception';
import {
  Activity, Eye, Flame, ShieldAlert, AlertTriangle, Layers,
  Compass, Crosshair, ChevronRight, CheckCircle2, RotateCcw
} from 'lucide-react';

interface Factory3DProps {
  machines: Machine[];
  workers: Worker[];
  sensors: Sensor[];
  zones: Zone3D[];
  incidents: Incident[];
  actions?: Action[];
  currentScenario?: string;
  onSelectObject: (obj: { type: 'machine' | 'worker' | 'sensor' | 'zone' | 'camera'; data: any }) => void;
  selectedId?: string | null;
  onPerceptionUpdate?: (results: Record<string, CameraPerceptionResult>) => void;
}

type CameraPreset = 'overview' | 'diorama' | 'zone_a' | 'zone_b' | 'zone_c' | 'incident' | 'top_down';

const CAMERA_PRESETS: Record<CameraPreset, { pos: [number, number, number]; target: [number, number, number] }> = {
  overview: { pos: [0, 26, 32], target: [0, 2, 0] },
  diorama: { pos: [48, 38, 48], target: [0, 2, 0] }, // Exact isometric angle as the user's reference image!
  zone_a: { pos: [-10, 16, 18], target: [-10, 2, 0] },
  zone_b: { pos: [8, 16, 18], target: [8, 2, -4] },
  zone_c: { pos: [20, 18, 24], target: [20, 2, 8] },
  incident: { pos: [8, 16, 16], target: [8, 2, -4] },
  top_down: { pos: [0, 65, 0.1], target: [0, 0, 0] }
};

/**
 * Animated Camera Controller: animates smoothly to target preset when clicked,
 * then RELEASES control so user can freely zoom in, zoom out to petite échelle, rotate, and pan!
 */
function CameraController({
  preset,
  controlsRef,
  animTrigger
}: {
  preset: CameraPreset;
  controlsRef: React.RefObject<any>;
  animTrigger: number;
}) {
  const { camera } = useThree();
  const targetConfig = CAMERA_PRESETS[preset] || CAMERA_PRESETS.diorama;
  const desiredPos = useRef(new THREE.Vector3(...targetConfig.pos));
  const desiredTarget = useRef(new THREE.Vector3(...targetConfig.target));
  const isAnimating = useRef(true);
  const frameCount = useRef(0);

  React.useEffect(() => {
    desiredPos.current.set(...targetConfig.pos);
    desiredTarget.current.set(...targetConfig.target);
    isAnimating.current = true;
    frameCount.current = 0;
  }, [preset, animTrigger, targetConfig]);

  useFrame(() => {
    if (!isAnimating.current) return;
    frameCount.current += 1;

    camera.position.lerp(desiredPos.current, 0.08);
    if (controlsRef.current) {
      controlsRef.current.target.lerp(desiredTarget.current, 0.08);
      controlsRef.current.update();
    }

    // Stop animating once close enough or after ~35 frames (~0.5s) so user has 100% free mouse zoom/pan/rotate!
    if (camera.position.distanceTo(desiredPos.current) < 0.25 || frameCount.current > 40) {
      isAnimating.current = false;
    }
  });

  return null;
}

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
      onPointerOver={() => { document.body.style.cursor = 'pointer'; }}
      onPointerOut={() => { document.body.style.cursor = 'auto'; }}
    >
      <mesh position={[0, 0.85, 0]} castShadow>
        <cylinderGeometry args={[0.26, 0.3, 0.9, 16]} />
        <meshStandardMaterial color={isAtRisk ? '#ef4444' : '#f97316'} metalness={0.1} roughness={0.8} />
      </mesh>

      <mesh position={[0, 1.5, 0]}>
        <sphereGeometry args={[0.18, 16, 16]} />
        <meshStandardMaterial color="#fed7aa" />
      </mesh>

      <mesh position={[0, 1.62, 0]}>
        <cylinderGeometry args={[0.23, 0.25, 0.16, 16]} />
        <meshStandardMaterial color="#ffffff" roughness={0.2} />
      </mesh>

      <Text
        position={[0, 2.1, 0]}
        fontSize={0.35}
        color={isAtRisk ? '#ef4444' : '#f8fafc'}
        anchorX="center"
        outlineWidth={0.03}
        outlineColor="#020617"
      >
        {worker.name.split(' ')[0]}
      </Text>
    </group>
  );
}

function ZonePerimeter({ zone, hasIncident, isSelected }: { zone: Zone3D; hasIncident: boolean; isSelected: boolean }) {
  let x = 0;

  if (zone.id === 'ZONE_A') {
    x = -10;
  } else if (zone.id === 'ZONE_B') {
    x = 8;
  } else if (zone.id === 'ZONE_C') {
    x = 20;
  } else if (zone.id === 'ZONE_D') {
    x = -20;
  }

  const activeFloorColor = hasIncident ? '#7f1d1d' : isSelected ? '#0369a1' : '#1e293b';
  const borderColor = hasIncident ? '#ef4444' : isSelected ? '#38bdf8' : '#0284c7';

  return (
    <group position={[x, 0.03, 0]}>
      {/* Zone Floor Plate */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[11.5, 16.5]} />
        <meshStandardMaterial
          color={activeFloorColor}
          emissive={hasIncident ? '#ef4444' : '#000000'}
          emissiveIntensity={hasIncident ? 0.35 : 0.0}
          roughness={0.6}
          metalness={0.2}
          transparent
          opacity={0.8}
        />
      </mesh>

      {/* Boundary Line */}
      <lineSegments>
        <edgesGeometry args={[new THREE.BoxGeometry(11.5, 0.04, 16.5)]} />
        <lineBasicMaterial color={borderColor} linewidth={3} />
      </lineSegments>

      {/* Zone Header Nameplate on floor */}
      <Text
        position={[0, 0.06, 7.2]}
        rotation={[-Math.PI / 2, 0, 0]}
        fontSize={0.65}
        color={hasIncident ? '#fca5a5' : '#f8fafc'}
        anchorX="center"
        outlineWidth={0.03}
        outlineColor="#020617"
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
  actions = [],
  currentScenario = 'normal',
  onSelectObject,
  selectedId,
  onPerceptionUpdate
}) => {
  const activeIncidents = incidents.filter((i) => i.status === 'ACTIVE');
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [showPerfPanel, setShowPerfPanel] = useState(false);
  const [activePreset, setActivePreset] = useState<CameraPreset>('overview');

  const controlsRef = useRef<any>(null);

  const [animTrigger, setAnimTrigger] = useState(0);

  const handleSelectPreset = (p: CameraPreset) => {
    setActivePreset(p);
    setAnimTrigger((prev) => prev + 1);
  };

  const handleZoom = (zoomIn: boolean) => {
    if (controlsRef.current) {
      const cameraObj = controlsRef.current.object;
      const factor = zoomIn ? 0.75 : 1.35;
      cameraObj.position.multiplyScalar(factor);
      controlsRef.current.update();
    }
  };

  // Auto-switch to incident preset when an incident starts
  React.useEffect(() => {
    if (activeIncidents.length > 0) {
      if (currentScenario === 'scenario_1') {
        CAMERA_PRESETS.incident = { pos: [8, 16, 16], target: [8, 2, -4] };
      } else if (currentScenario === 'scenario_3') {
        CAMERA_PRESETS.incident = { pos: [8, 16, 16], target: [8, 2, -4] };
      } else if (currentScenario === 'scenario_2') {
        CAMERA_PRESETS.incident = { pos: [20, 18, 24], target: [20, 2, 8] };
      }
      handleSelectPreset('incident');
    }
  }, [currentScenario, activeIncidents.length]);

  const handleSelectCamera = (cam: CameraConfig) => {
    setSelectedCameraId(cam.id);
    onSelectObject({ type: 'camera', data: cam });
  };

  return (
    <div className="w-full h-full relative bg-[#446682] rounded-xl overflow-hidden border border-slate-700/60 shadow-2xl select-none">
      {/* ─── TOP STATUS & CONTROL HUD ───────────────────────────── */}
      <div className="absolute top-3 left-3 z-10 flex items-center gap-2 font-mono">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-900/90 backdrop-blur-md rounded-lg border border-cyan-500/40 text-xs text-cyan-400 shadow-lg">
          <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
          <span className="font-bold text-white">DIGITAL TWIN COCKPIT</span>
          <span className="text-slate-500">•</span>
          <span className="text-cyan-300 font-semibold">SUPERVISORY VIEW</span>
        </div>

        {activeIncidents.length > 0 && (
          <button
            onClick={() => handleSelectPreset('incident')}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600/90 hover:bg-red-500 text-white rounded-lg text-xs font-bold shadow-glow-red animate-pulse border border-red-400 transition-all"
          >
            <Crosshair className="w-3.5 h-3.5" />
            <span>FOCUS INCIDENT ({activeIncidents[0].type.replace('_', ' ')})</span>
          </button>
        )}
      </div>

      {/* ─── INTERACTIVE CAMERA & ZOOM TOOLBAR ──────────────────── */}
      <div className="absolute top-3 right-3 z-10 flex items-center gap-1 p-1 bg-slate-900/90 backdrop-blur-md rounded-lg border border-slate-700 text-xs font-mono shadow-xl">
        <span className="px-2 text-slate-400 text-[10px] flex items-center gap-1 font-bold">
          <Eye className="w-3 h-3 text-cyan-400" /> VUE:
        </span>
        {[
          { id: 'diorama', label: '🔍 Petite Échelle' },
          { id: 'overview', label: '🌐 Vue Globale' },
          { id: 'zone_a', label: '⚙️ Zone A' },
          { id: 'zone_b', label: '🔥 Zone B' },
          { id: 'zone_c', label: '🤖 Zone C' },
          { id: 'top_down', label: '🗺️ Plan' },
        ].map((btn) => (
          <button
            key={btn.id}
            onClick={() => handleSelectPreset(btn.id as CameraPreset)}
            className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all ${
              activePreset === btn.id
                ? 'bg-cyan-500/25 text-cyan-300 border border-cyan-500/60 shadow-glow-cyan font-bold'
                : 'text-slate-300 hover:text-white hover:bg-slate-800/80'
            }`}
          >
            {btn.label}
          </button>
        ))}

        <div className="h-4 w-px bg-slate-700 mx-1" />

        {/* Quick Zoom Buttons */}
        <button
          onClick={() => handleZoom(true)}
          title="Zoom In (Rapprocher)"
          className="px-2 py-1 rounded text-xs font-bold text-slate-200 hover:text-white hover:bg-slate-800 transition-all"
        >
          ➕
        </button>
        <button
          onClick={() => handleZoom(false)}
          title="Zoom Out (Petite Échelle / Éloigner)"
          className="px-2 py-1 rounded text-xs font-bold text-slate-200 hover:text-white hover:bg-slate-800 transition-all"
        >
          ➖
        </button>
      </div>

      {/* ─── BOTTOM RIGHT CONTROLS & HINT ───────────────────────── */}
      <div className="absolute bottom-3 right-3 z-10 flex items-center gap-2 font-mono">
        <button
          onClick={() => setShowPerfPanel(!showPerfPanel)}
          className={`px-2.5 py-1 rounded text-[11px] font-bold border transition-all flex items-center gap-1.5 ${
            showPerfPanel
              ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 shadow-glow-cyan'
              : 'bg-slate-900/80 text-slate-400 hover:text-white border-slate-800'
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          <span>PERF DEBUG</span>
        </button>

        <div className="px-3 py-1 bg-slate-950/80 backdrop-blur text-[11px] text-slate-300 rounded border border-slate-700">
          🖱️ Molette: Zoom (Petite Échelle) • Clic gauche: Orbiter • Clic droit: Glisser
        </div>
      </div>

      {showPerfPanel && (
        <PerformancePanel
          fps={60.0}
          drawCalls={38}
          triangles={28400}
          visibleObjects={36}
          cameraInferenceFps={8.5}
          wsRate={5}
          onClose={() => setShowPerfPanel(false)}
        />
      )}

      {/* ─── 3D THREE.JS CANVAS (Light Studio Background like reference image) ─ */}
      <Canvas
        camera={{ position: CAMERA_PRESETS.diorama.pos, fov: 42 }}
        shadows
        gl={{ antialias: true, powerPreference: 'high-performance' }}
      >
        {/* Light Studio Background matching reference image */}
        <color attach="background" args={['#446682']} />
        <fog attach="fog" args={['#446682', 110, 360]} />

        {/* Studio Lighting */}
        <hemisphereLight args={['#f0f9ff', '#334155', 1.2]} />
        <ambientLight intensity={1.1} />

        <directionalLight
          position={[50, 75, 40]}
          intensity={2.3}
          castShadow
          shadow-mapSize-width={2048}
          shadow-mapSize-height={2048}
          shadow-camera-far={180}
          shadow-camera-left={-75}
          shadow-camera-right={75}
          shadow-camera-top={75}
          shadow-camera-bottom={-75}
          shadow-bias={-0.0001}
        />

        {/* Accent lights */}
        <pointLight position={[-10, 15, -6]} intensity={1.5} color="#38bdf8" distance={40} />
        <pointLight position={[8, 15, -6]} intensity={1.5} color="#f59e0b" distance={40} />

        {/* Camera Preset Transition Controller */}
        <CameraController preset={activePreset} controlsRef={controlsRef} animTrigger={animTrigger} />

        <OrbitControls
          ref={controlsRef}
          maxPolarAngle={Math.PI / 2.05}
          minDistance={3}
          maxDistance={350}
          enableZoom={true}
          enablePan={true}
          enableRotate={true}
          enableDamping
          dampingFactor={0.06}
        />

        <Suspense fallback={null}>
          {/* ─── ORGANIZED FACTORY GROUND (Roads, apron, perimeter) ─ */}
          <FactoryGround />

          {/* ─── FACTORY GRID ───────────────────────────────────── */}
          <Grid
            position={[0, 0.04, 0]}
            args={[90, 65]}
            cellSize={2}
            cellThickness={0.5}
            cellColor="#1e293b"
            sectionSize={10}
            sectionThickness={1.0}
            sectionColor="#0284c7"
            fadeDistance={70}
            fadeStrength={2.0}
          />

          {/* ─── 4 INDUSTRIAL ZONES ─────────────────────────────── */}
          {zones.map((zone) => {
            const hasInc = activeIncidents.some((i) => i.zone === zone.id);
            const isSel = selectedId === zone.id;
            return <ZonePerimeter key={zone.id} zone={zone} hasIncident={hasInc} isSelected={isSel} />;
          })}

          {/* ─── SCENARIO 3D COORDINATOR (Fire, Overheating, Cyber) ─ */}
          <Scenario3DCoordinator
            currentScenario={currentScenario}
            incidents={incidents}
            actions={actions}
            machines={machines}
            workers={workers}
            sensors={sensors}
            onSelectMachine={(m) => onSelectObject({ type: 'machine', data: m })}
          />

          {/* ─── MAIN FACTORY BUILDING (Mid-Rear Factory, Front Admin, Right Hall) ── */}
          <MainFactoryBuilding position={[0, 0, 0]} />

          {/* ─── INDUSTRIAL BUILDINGS (Gantry, Office, Towers) ────── */}
          <IndustrialBuildings />

          {/* ─── INDUSTRIAL INFRASTRUCTURE (Cables, gantries) ─────── */}
          <IndustrialInfrastructure activeIncidents={activeIncidents} />

          {/* ─── SUPERVISED MACHINE GLB MODELS ───────────────────── */}
          <MachineGLB
            position={[-10, 0, 4]}
            targetSize={6}
            scale={1.0}
            rotation={[0, Math.PI / 4, 0]}
          />
          <MachineGLB
            position={[15, 0, 6]}
            targetSize={5}
            scale={0.9}
            rotation={[0, -Math.PI / 6, 0]}
          />

          {/* ─── INTERACTIVE EQUIPMENT (M-01 to M-06) ─────────────── */}
          <IndustrialEquipment
            machines={machines}
            sensors={sensors}
            selectedId={selectedId}
            onSelectObject={(obj) => onSelectObject(obj)}
            activeIncidents={activeIncidents}
          />

          {/* ─── WORKERS ─────────────────────────────────────────── */}
          {workers.map((worker) => (
            <Worker3D
              key={worker.id}
              worker={worker}
              onClick={() => onSelectObject({ type: 'worker', data: worker })}
            />
          ))}

          {/* ─── CAMERA STATION CONES ────────────────────────────── */}
          <Camera3DOverlay
            selectedCameraId={selectedCameraId}
            onSelectCamera={handleSelectCamera}
            activeIncidents={activeIncidents}
          />

          {/* ─── OFFSCREEN VIRTUAL CAMERA PERCEPTION ──────────────── */}
          <VirtualCameraRenderer
            workers={workers}
            machines={machines}
            incidents={incidents}
            onPerceptionUpdate={(results) => {
              if (onPerceptionUpdate) onPerceptionUpdate(results);
            }}
            activeCameraId={selectedCameraId}
          />
        </Suspense>
      </Canvas>
    </div>
  );
};
