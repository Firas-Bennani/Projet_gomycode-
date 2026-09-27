import React, { useLayoutEffect, useRef } from 'react';
import { useGLTF } from '@react-three/drei';
import * as THREE from 'three';

interface FactoryGLBProps {
  position?: [number, number, number];
  scale?: number;
  rotation?: [number, number, number];
  targetSize?: number;
}

export const FactoryGLB: React.FC<FactoryGLBProps> = ({
  position = [0, 0, 0],
  scale = 1.0,
  rotation = [0, 0, 0],
  targetSize = 55.0
}) => {
  const { scene } = useGLTF('/models/factory.glb');
  const groupRef = useRef<THREE.Group>(null);

  useLayoutEffect(() => {
    if (scene) {
      // Traverse all meshes to enable double-sided materials & shadows
      scene.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          child.castShadow = true;
          child.receiveShadow = true;

          const mesh = child as THREE.Mesh;
          if (mesh.material) {
            if (Array.isArray(mesh.material)) {
              mesh.material.forEach((mat) => {
                mat.side = THREE.DoubleSide;
                mat.needsUpdate = true;
              });
            } else {
              mesh.material.side = THREE.DoubleSide;
              mesh.material.needsUpdate = true;
            }
          }
        }
      });

      // Compute bounding box to auto-center and auto-scale the model
      const box = new THREE.Box3().setFromObject(scene);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());

      // Center model X and Z, align bottom to Y = 0
      scene.position.x = -center.x;
      scene.position.y = -box.min.y;
      scene.position.z = -center.z;

      // Auto scale model if it is small (< 10 units)
      const maxDim = Math.max(size.x, size.z);
      if (maxDim > 0 && maxDim < 15) {
        const autoScaleFactor = targetSize / maxDim;
        scene.scale.set(autoScaleFactor, autoScaleFactor, autoScaleFactor);
      }
    }
  }, [scene, targetSize]);

  return (
    <group ref={groupRef} position={position} scale={[scale, scale, scale]} rotation={rotation}>
      <primitive object={scene} />
    </group>
  );
};

useGLTF.preload('/models/factory.glb');
