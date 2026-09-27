import React, { useLayoutEffect, useRef, useState, Suspense, Component, ErrorInfo, ReactNode } from 'react';
import { useGLTF } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface MachineGLBProps {
  position?: [number, number, number];
  scale?: number;
  rotation?: [number, number, number];
  targetSize?: number;
  label?: string;
}

class MachineErrorBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { hasError: boolean }> {
  constructor(props: { fallback: ReactNode; children: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.warn('Machine GLB loading error, using fallback:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

/**
 * High-tech automated industrial machine fallback inspired by:
 * "futuristic-orange-blue-automated-factory-production-line-hightech-manufacturing-process"
 */
export const FuturisticProductionLineMachine: React.FC<{
  position?: [number, number, number];
  rotation?: [number, number, number];
  scale?: number;
}> = ({ position = [0, 0, 0], rotation = [0, 0, 0], scale = 1.0 }) => {
  const armRef = useRef<THREE.Group>(null);
  const gearRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (armRef.current) {
      armRef.current.rotation.y = Math.sin(t * 1.2) * 0.4;
      armRef.current.rotation.z = Math.cos(t * 1.5) * 0.15;
    }
    if (gearRef.current) {
      gearRef.current.rotation.y += 0.03;
    }
  });

  return (
    <group position={position} rotation={rotation} scale={[scale, scale, scale]}>
      {/* Heavy base unit */}
      <mesh position={[0, 0.4, 0]} castShadow receiveShadow>
        <boxGeometry args={[4.2, 0.8, 3.2]} />
        <meshStandardMaterial color="#0f172a" metalness={0.8} roughness={0.2} />
      </mesh>

      {/* Cyber blue base ring */}
      <mesh position={[0, 0.82, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[1.2, 1.4, 32]} />
        <meshStandardMaterial color="#0284c7" emissive="#38bdf8" emissiveIntensity={0.8} />
      </mesh>

      {/* Industrial orange machine body */}
      <mesh position={[0, 1.8, 0]} castShadow receiveShadow>
        <boxGeometry args={[3.2, 1.4, 2.4]} />
        <meshStandardMaterial color="#ea580c" metalness={0.65} roughness={0.3} />
      </mesh>

      {/* Blue neon accent stripe */}
      <mesh position={[0, 1.8, 1.22]}>
        <planeGeometry args={[2.8, 0.12]} />
        <meshStandardMaterial color="#38bdf8" emissive="#38bdf8" emissiveIntensity={1.5} />
      </mesh>

      {/* Rotating robotic turret arm */}
      <group position={[0, 2.5, 0]} ref={armRef}>
        <mesh castShadow>
          <cylinderGeometry args={[0.7, 0.8, 0.8, 24]} />
          <meshStandardMaterial color="#1e293b" metalness={0.9} roughness={0.15} />
        </mesh>

        {/* Articulated joint 1 (Orange) */}
        <mesh position={[0.6, 0.8, 0]} rotation={[0, 0, -0.4]} castShadow>
          <boxGeometry args={[0.5, 1.8, 0.5]} />
          <meshStandardMaterial color="#f97316" metalness={0.7} roughness={0.25} />
        </mesh>

        {/* Joint elbow sphere (Metallic blue) */}
        <mesh position={[1.0, 1.8, 0]} castShadow>
          <sphereGeometry args={[0.4, 16, 16]} />
          <meshStandardMaterial color="#0284c7" metalness={0.9} roughness={0.1} />
        </mesh>

        {/* Articulated joint 2 */}
        <mesh position={[0.7, 2.6, 0]} rotation={[0, 0, 0.5]} castShadow>
          <boxGeometry args={[0.4, 1.6, 0.4]} />
          <meshStandardMaterial color="#334155" metalness={0.8} roughness={0.2} />
        </mesh>

        {/* End effector / laser tool head with blue glow */}
        <mesh position={[0.3, 3.4, 0]} castShadow>
          <cylinderGeometry args={[0.15, 0.25, 0.6, 16]} />
          <meshStandardMaterial color="#0284c7" emissive="#0ea5e9" emissiveIntensity={1.2} />
        </mesh>
      </group>

      {/* Conveyor feed station on side */}
      <mesh position={[-2.4, 0.9, 0]} castShadow receiveShadow>
        <boxGeometry args={[1.6, 1.0, 3.8]} />
        <meshStandardMaterial color="#1e293b" metalness={0.7} roughness={0.3} />
      </mesh>
      <mesh position={[-2.4, 1.42, 0]} ref={gearRef}>
        <cylinderGeometry args={[0.6, 0.6, 0.1, 16]} />
        <meshStandardMaterial color="#f59e0b" metalness={0.8} />
      </mesh>

      {/* Status beacon pole */}
      <group position={[1.4, 2.5, -1.0]}>
        <mesh>
          <cylinderGeometry args={[0.04, 0.04, 1.4, 8]} />
          <meshStandardMaterial color="#64748b" />
        </mesh>
        <mesh position={[0, 0.8, 0]}>
          <sphereGeometry args={[0.12, 12, 12]} />
          <meshStandardMaterial color="#10b981" emissive="#10b981" emissiveIntensity={2.0} />
        </mesh>
      </group>

      {/* Ground operational circle */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <circleGeometry args={[2.5, 32]} />
        <meshStandardMaterial
          color="#0284c7"
          emissive="#0284c7"
          emissiveIntensity={0.2}
          transparent
          opacity={0.25}
        />
      </mesh>
    </group>
  );
};

const GLBModelInner: React.FC<{
  targetSize: number;
  position: [number, number, number];
  rotation: [number, number, number];
  scale: number;
}> = ({ targetSize, position, rotation, scale }) => {
  const { scene } = useGLTF('/models/machine.glb');
  const groupRef = useRef<THREE.Group>(null);
  const [clonedScene, setClonedScene] = useState<THREE.Group | null>(null);

  useLayoutEffect(() => {
    if (scene) {
      const cloned = scene.clone(true);

      cloned.traverse((child) => {
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

      const box = new THREE.Box3().setFromObject(cloned);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());

      cloned.position.x = -center.x;
      cloned.position.y = -box.min.y;
      cloned.position.z = -center.z;

      const maxDim = Math.max(size.x, size.y, size.z);
      if (maxDim > 0) {
        const factor = targetSize / maxDim;
        cloned.scale.set(factor, factor, factor);
      }

      setClonedScene(cloned);
    }
  }, [scene, targetSize]);

  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.position.y = position[1] + Math.sin(state.clock.elapsedTime * 0.8) * 0.02;
    }
  });

  return (
    <group position={position} scale={[scale, scale, scale]} rotation={rotation} ref={groupRef}>
      {clonedScene && <primitive object={clonedScene} />}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
        <circleGeometry args={[targetSize * 0.4, 32]} />
        <meshStandardMaterial
          color="#0ea5e9"
          emissive="#0284c7"
          emissiveIntensity={0.15}
          transparent
          opacity={0.2}
        />
      </mesh>
    </group>
  );
};

export const MachineGLB: React.FC<MachineGLBProps> = ({
  position = [0, 0, 0],
  scale = 1.0,
  rotation = [0, 0, 0],
  targetSize = 6.0,
}) => {
  return (
    <MachineErrorBoundary
      fallback={
        <FuturisticProductionLineMachine
          position={position}
          rotation={rotation}
          scale={scale}
        />
      }
    >
      <Suspense
        fallback={
          <FuturisticProductionLineMachine
            position={position}
            rotation={rotation}
            scale={scale}
          />
        }
      >
        <GLBModelInner
          targetSize={targetSize}
          position={position}
          rotation={rotation}
          scale={scale}
        />
      </Suspense>
    </MachineErrorBoundary>
  );
};
