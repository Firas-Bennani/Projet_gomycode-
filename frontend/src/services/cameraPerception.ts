import * as THREE from 'three';
import { Camera, Worker, Machine, Incident } from '../types';

export interface CameraConfig {
  id: string;
  name: string;
  zone: string;
  position: THREE.Vector3;
  target: THREE.Vector3;
  fov: number;
}

export const INDUSTRIAL_CAMERAS: CameraConfig[] = [
  {
    id: 'CAM-A-01',
    name: 'CCTV North Machining Cell',
    zone: 'ZONE_A',
    position: new THREE.Vector3(-16, 7, -14),
    target: new THREE.Vector3(-10, 1.5, -6),
    fov: 50
  },
  {
    id: 'CAM-B-01',
    name: 'CCTV Heavy Milling Cell M-04',
    zone: 'ZONE_B',
    position: new THREE.Vector3(14, 7.5, -13),
    target: new THREE.Vector3(8, 1.8, -6),
    fov: 55
  },
  {
    id: 'CAM-B-02',
    name: 'CCTV East Furnace Area M-05',
    zone: 'ZONE_B',
    position: new THREE.Vector3(14, 7.5, 12),
    target: new THREE.Vector3(8, 1.8, 6),
    fov: 55
  },
  {
    id: 'CAM-C-01',
    name: 'CCTV Robotic Cell C-01',
    zone: 'ZONE_C',
    position: new THREE.Vector3(26, 6.5, -6),
    target: new THREE.Vector3(20, 1.5, 0),
    fov: 50
  }
];

export interface DetectedBoundingBox {
  id: string;
  label: string;
  confidence: number;
  x: number; // 0 to 100%
  y: number; // 0 to 100%
  width: number;
  height: number;
}

export interface CameraPerceptionResult {
  cameraId: string;
  timestamp: string;
  detectedObjects: string[];
  boundingBoxes: DetectedBoundingBox[];
  hasSmokeFire: boolean;
}

/**
 * Calculates geometric frustum visibility for 3D objects from camera perspective.
 */
export function processCameraPerception(
  camConfig: CameraConfig,
  workers: Worker[],
  machines: Machine[],
  incidents: Incident[]
): CameraPerceptionResult {
  const threeCam = new THREE.PerspectiveCamera(camConfig.fov, 16 / 9, 0.5, 50);
  threeCam.position.copy(camConfig.position);
  threeCam.lookAt(camConfig.target);
  threeCam.updateMatrixWorld();
  threeCam.updateProjectionMatrix();

  const frustum = new THREE.Frustum();
  const projScreenMatrix = new THREE.Matrix4();
  projScreenMatrix.multiplyMatrices(threeCam.projectionMatrix, threeCam.matrixWorldInverse);
  frustum.setFromProjectionMatrix(projScreenMatrix);

  const detectedObjects: string[] = [];
  const boundingBoxes: DetectedBoundingBox[] = [];

  // 1. Check Workers in FOV
  workers.forEach((w) => {
    const pos = w.position ? new THREE.Vector3(w.position.x, 1.0, w.position.z) : new THREE.Vector3(0, 0, 0);
    if (frustum.containsPoint(pos)) {
      detectedObjects.push(`Worker ${w.id} (${w.name.split(' ')[0]})`);

      // Project 3D point to 2D screen coordinates
      const proj = pos.clone().project(threeCam);
      const x = (proj.x * 0.5 + 0.5) * 100;
      const y = (-proj.y * 0.5 + 0.5) * 100;

      boundingBoxes.push({
        id: w.id,
        label: `PERSON: ${w.id}`,
        confidence: 0.94 + (Math.random() * 0.04 - 0.02),
        x: Math.max(10, Math.min(80, x - 8)),
        y: Math.max(15, Math.min(75, y - 15)),
        width: 16,
        height: 30
      });
    }
  });

  // 2. Check Machines in FOV
  machines.forEach((m) => {
    const pos = m.position ? new THREE.Vector3(m.position.x, 1.5, m.position.z) : new THREE.Vector3(0, 0, 0);
    if (frustum.containsPoint(pos)) {
      detectedObjects.push(`Machine ${m.id}`);

      const proj = pos.clone().project(threeCam);
      const x = (proj.x * 0.5 + 0.5) * 100;
      const y = (-proj.y * 0.5 + 0.5) * 100;

      boundingBoxes.push({
        id: m.id,
        label: `EQUIPMENT: ${m.id}`,
        confidence: 0.97,
        x: Math.max(15, Math.min(70, x - 15)),
        y: Math.max(20, Math.min(65, y - 20)),
        width: 30,
        height: 40
      });
    }
  });

  // 3. Check Smoke/Fire Incidents in FOV
  const activeIncident = incidents.find((i) => i.status === 'ACTIVE' && i.zone === camConfig.zone);
  let hasSmokeFire = false;
  if (activeIncident && (activeIncident.type === 'FACTORY_FIRE' || activeIncident.type === 'MACHINE_OVERHEATING')) {
    hasSmokeFire = true;
    detectedObjects.push(`HAZARD: ${activeIncident.type}`);
    boundingBoxes.push({
      id: 'HAZARD-01',
      label: activeIncident.type === 'FACTORY_FIRE' ? 'FIRE / SMOKE DETECTED' : 'THERMAL OVERHEAT DETECTED',
      confidence: 0.98,
      x: 35,
      y: 25,
      width: 30,
      height: 35
    });
  }

  return {
    cameraId: camConfig.id,
    timestamp: new Date().toLocaleTimeString(),
    detectedObjects,
    boundingBoxes,
    hasSmokeFire
  };
}
