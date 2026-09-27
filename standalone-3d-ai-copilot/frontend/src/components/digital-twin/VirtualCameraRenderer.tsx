import React, { useEffect, useRef } from 'react';
import { useThree, useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { INDUSTRIAL_CAMERAS, CameraConfig, processCameraPerception, CameraPerceptionResult } from '../../services/cameraPerception';
import { Worker, Machine, Incident } from '../../types';

interface VirtualCameraRendererProps {
  workers: Worker[];
  machines: Machine[];
  incidents: Incident[];
  onPerceptionUpdate: (results: Record<string, CameraPerceptionResult>) => void;
  activeCameraId?: string | null;
}

export const VirtualCameraRenderer: React.FC<VirtualCameraRendererProps> = ({
  workers,
  machines,
  incidents,
  onPerceptionUpdate,
  activeCameraId
}) => {
  const { gl, scene } = useThree();
  const renderTargetRef = useRef<THREE.WebGLRenderTarget | null>(null);
  const camerasRef = useRef<Record<string, THREE.PerspectiveCamera>>({});
  const frameCountRef = useRef(0);

  useEffect(() => {
    // Create shared offscreen WebGLRenderTarget (320x180 resolution for high performance)
    renderTargetRef.current = new THREE.WebGLRenderTarget(320, 180, {
      minFilter: THREE.LinearFilter,
      magFilter: THREE.LinearFilter,
      format: THREE.RGBAFormat
    });

    // Create 3D cameras for each configured camera station
    INDUSTRIAL_CAMERAS.forEach((cam) => {
      const threeCam = new THREE.PerspectiveCamera(cam.fov, 16 / 9, 0.5, 60);
      threeCam.position.copy(cam.position);
      threeCam.lookAt(cam.target);
      threeCam.updateProjectionMatrix();
      threeCam.updateMatrixWorld();
      camerasRef.current[cam.id] = threeCam;
    });

    return () => {
      renderTargetRef.current?.dispose();
    };
  }, []);

  useFrame(() => {
    frameCountRef.current += 1;

    // Throttle offscreen rendering & perception calculation to every 8 frames (~7-8 FPS)
    if (frameCountRef.current % 8 !== 0) return;
    if (!renderTargetRef.current) return;

    const currentRenderTarget = gl.getRenderTarget();

    const results: Record<string, CameraPerceptionResult> = {};

    INDUSTRIAL_CAMERAS.forEach((camConfig) => {
      const camera = camerasRef.current[camConfig.id];
      if (!camera) return;

      // Render 3D Scene offscreen from this virtual camera's perspective
      gl.setRenderTarget(renderTargetRef.current);
      gl.clear();
      gl.render(scene, camera);

      // Perform camera perception calculations (frustum visibility + bounding box mapping)
      const res = processCameraPerception(camConfig, workers, machines, incidents);
      results[camConfig.id] = res;
    });

    // Restore main viewport rendering target
    gl.setRenderTarget(currentRenderTarget);

    // Notify application state of perception results
    onPerceptionUpdate(results);
  });

  return null;
};
