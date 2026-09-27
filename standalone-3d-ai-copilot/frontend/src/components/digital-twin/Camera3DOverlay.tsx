import React from 'react';
import * as THREE from 'three';
import { Text, Html } from '@react-three/drei';
import { INDUSTRIAL_CAMERAS, CameraConfig } from '../../services/cameraPerception';
import { Video, Eye } from 'lucide-react';

interface Camera3DOverlayProps {
  selectedCameraId?: string | null;
  onSelectCamera: (cam: CameraConfig) => void;
  activeIncidents: any[];
}

export const Camera3DOverlay: React.FC<Camera3DOverlayProps> = ({
  selectedCameraId,
  onSelectCamera,
  activeIncidents
}) => {
  return (
    <group>
      {INDUSTRIAL_CAMERAS.map((cam) => {
        const isSelected = selectedCameraId === cam.id;
        const pos = cam.position;
        const target = cam.target;

        // Calculate direction rotation matrix
        const dummyCam = new THREE.Object3D();
        dummyCam.position.copy(pos);
        dummyCam.lookAt(target);

        return (
          <group key={cam.id}>
            {/* Camera Physical Mount Box & Lens Mesh */}
            <group
              position={[pos.x, pos.y, pos.z]}
              rotation={[dummyCam.rotation.x, dummyCam.rotation.y, dummyCam.rotation.z]}
              onClick={(e) => {
                e.stopPropagation();
                onSelectCamera(cam);
              }}
            >
              {/* Mounting Bracket Base */}
              <mesh position={[0, 0, -0.4]}>
                <boxGeometry args={[0.3, 0.3, 0.6]} />
                <meshStandardMaterial color="#0f172a" metalness={0.9} />
              </mesh>

              {/* Camera Body Enclosure */}
              <mesh position={[0, 0, 0]} castShadow>
                <boxGeometry args={[0.5, 0.4, 0.9]} />
                <meshStandardMaterial
                  color={isSelected ? '#0284c7' : '#1e293b'}
                  emissive={isSelected ? '#0284c7' : '#0f172a'}
                  emissiveIntensity={isSelected ? 0.6 : 0.2}
                  metalness={0.8}
                />
              </mesh>

              {/* Optical Glass Lens Rim */}
              <mesh position={[0, 0, 0.5]} rotation={[Math.PI / 2, 0, 0]}>
                <cylinderGeometry args={[0.18, 0.18, 0.2, 16]} />
                <meshStandardMaterial color="#38bdf8" emissive="#38bdf8" emissiveIntensity={0.8} />
              </mesh>

              {/* Indicator Status LED */}
              <mesh position={[0.2, 0.15, 0.3]}>
                <sphereGeometry args={[0.05, 8, 8]} />
                <meshStandardMaterial color="#10b981" emissive="#10b981" emissiveIntensity={1.2} />
              </mesh>

              {/* 3D Label */}
              <Text position={[0, 0.6, 0]} fontSize={0.35} color={isSelected ? '#38bdf8' : '#94a3b8'} anchorX="center">
                {cam.id}
              </Text>
            </group>

            {/* 3D FOV Frustum Cone Pyramid when Camera is Selected or Active */}
            {(isSelected || selectedCameraId === 'ALL') && (
              <group position={[pos.x, pos.y, pos.z]} rotation={[dummyCam.rotation.x, dummyCam.rotation.y, dummyCam.rotation.z]}>
                <mesh position={[0, 0, 8.0]} rotation={[Math.PI / 2, 0, 0]}>
                  <coneGeometry args={[6.0, 16.0, 4]} />
                  <meshStandardMaterial
                    color="#0284c7"
                    emissive="#0369a1"
                    emissiveIntensity={0.4}
                    transparent
                    opacity={0.15}
                    side={THREE.DoubleSide}
                    depthWrite={false}
                  />
                </mesh>

                {/* Frustum Boundary Edges */}
                <lineSegments position={[0, 0, 8.0]}>
                  <edgesGeometry args={[new THREE.ConeGeometry(6.0, 16.0, 4)]} />
                  <lineBasicMaterial color="#38bdf8" linewidth={2} transparent opacity={0.6} />
                </lineSegments>
              </group>
            )}
          </group>
        );
      })}
    </group>
  );
};
