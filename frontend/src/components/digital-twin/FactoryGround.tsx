import React from 'react';
import * as THREE from 'three';

/* ─────────────────────────────────────────────────────────────────
   ARQUITECTURAL ELEMENTS MATCHING THE REFERENCE DIORAMA
   ───────────────────────────────────────────────────────────────── */

/**
 * Stylized low-poly conical pine tree as seen on the grass islands
 */
const DioramaPineTree: React.FC<{ position: [number, number, number]; scale?: number }> = ({
  position,
  scale = 1.0
}) => (
  <group position={position} scale={[scale, scale, scale]}>
    {/* Trunk */}
    <mesh position={[0, 0.4, 0]} castShadow>
      <cylinderGeometry args={[0.08, 0.12, 0.8, 6]} />
      <meshStandardMaterial color="#5c3818" roughness={0.9} />
    </mesh>
    {/* Foliage Cones */}
    <mesh position={[0, 1.1, 0]} castShadow>
      <coneGeometry args={[0.7, 1.2, 7]} />
      <meshStandardMaterial color="#2d7a3e" roughness={0.8} />
    </mesh>
    <mesh position={[0, 1.7, 0]} castShadow>
      <coneGeometry args={[0.55, 1.0, 7]} />
      <meshStandardMaterial color="#388e3c" roughness={0.8} />
    </mesh>
    <mesh position={[0, 2.2, 0]} castShadow>
      <coneGeometry args={[0.38, 0.8, 7]} />
      <meshStandardMaterial color="#4caf50" roughness={0.8} />
    </mesh>
  </group>
);

/**
 * Arched Barrel-Vault Warehouse with Blue and White Stripes
 * (Matches the 3 arched hangars on the mid-left of the reference image)
 */
export const ArchedBarrelHangar: React.FC<{
  position: [number, number, number];
  rotation?: [number, number, number];
  width?: number;
  length?: number;
  height?: number;
}> = ({
  position,
  rotation = [0, 0, 0],
  width = 6.0,
  length = 9.0,
  height = 3.6
}) => {
  const stripeCount = 6;
  const stripeLength = length / stripeCount;

  return (
    <group position={position} rotation={rotation}>
      {/* Concrete foundation slab */}
      <mesh position={[0, 0.1, 0]} receiveShadow>
        <boxGeometry args={[width + 0.4, 0.2, length + 0.4]} />
        <meshStandardMaterial color="#d1d5db" roughness={0.7} />
      </mesh>

      {/* Arched striped roof segments */}
      {Array.from({ length: stripeCount }).map((_, i) => {
        const isBlue = i % 2 === 0;
        const zPos = -length / 2 + stripeLength / 2 + i * stripeLength;
        return (
          <group key={`stripe-${i}`} position={[0, 0.2, zPos]}>
            <mesh rotation={[0, 0, Math.PI / 2]} castShadow receiveShadow>
              <cylinderGeometry
                args={[height, height, stripeLength * 0.98, 24, 1, false, 0, Math.PI]}
              />
              <meshStandardMaterial
                color={isBlue ? '#1e3a5f' : '#f8fafc'}
                roughness={0.4}
                metalness={0.2}
                side={THREE.DoubleSide}
              />
            </mesh>
          </group>
        );
      })}

      {/* Front Entrance Portal */}
      <mesh position={[0, height * 0.45, length / 2 + 0.02]}>
        <boxGeometry args={[width * 0.5, height * 0.75, 0.1]} />
        <meshStandardMaterial color="#0f172a" metalness={0.8} />
      </mesh>
    </group>
  );
};

/**
 * Storage Tank with yellow/orange top & white cylinder
 * (Matches the tank farms in the reference image)
 */
export const DioramaStorageTank: React.FC<{
  position: [number, number, number];
  radius?: number;
  height?: number;
}> = ({ position, radius = 1.6, height = 3.2 }) => (
  <group position={position}>
    {/* Concrete base pad */}
    <mesh position={[0, 0.1, 0]} receiveShadow>
      <cylinderGeometry args={[radius + 0.2, radius + 0.25, 0.2, 24]} />
      <meshStandardMaterial color="#94a3b8" roughness={0.7} />
    </mesh>

    {/* Tank Body (White/Cream) */}
    <mesh position={[0, height / 2 + 0.2, 0]} castShadow receiveShadow>
      <cylinderGeometry args={[radius, radius, height, 28]} />
      <meshStandardMaterial color="#f8fafc" roughness={0.3} metalness={0.15} />
    </mesh>

    {/* Tank Roof / Rim (Bright Yellow/Orange) */}
    <mesh position={[0, height + 0.25, 0]} castShadow>
      <cylinderGeometry args={[radius * 0.98, radius, 0.18, 28]} />
      <meshStandardMaterial color="#f59e0b" roughness={0.3} metalness={0.4} />
    </mesh>
    <mesh position={[0, height + 0.35, 0]}>
      <torusGeometry args={[radius * 0.92, 0.05, 8, 28]} />
      <meshStandardMaterial color="#ea580c" metalness={0.6} />
    </mesh>
  </group>
);

/**
 * Thin Industrial Smokestack with Red & White Hazard Bands
 */
export const ThinBandedSmokestack: React.FC<{
  position: [number, number, number];
  height?: number;
  radius?: number;
}> = ({ position, height = 8.0, radius = 0.25 }) => {
  const bands = 7;
  const bandHeight = height / bands;

  return (
    <group position={position}>
      {Array.from({ length: bands }).map((_, i) => {
        const isRed = i % 2 === 1;
        return (
          <mesh
            key={`band-${i}`}
            position={[0, bandHeight / 2 + i * bandHeight, 0]}
            castShadow
          >
            <cylinderGeometry args={[radius * 0.9, radius, bandHeight, 16]} />
            <meshStandardMaterial
              color={isRed ? '#dc2626' : '#f8fafc'}
              roughness={0.4}
            />
          </mesh>
        );
      })}
    </group>
  );
};

/**
 * White External HVAC Chiller Unit (lined up on factory exterior walls)
 */
export const ExternalChillerUnit: React.FC<{ position: [number, number, number] }> = ({ position }) => (
  <group position={position}>
    <mesh position={[0, 0.7, 0]} castShadow receiveShadow>
      <boxGeometry args={[1.2, 1.4, 0.9]} />
      <meshStandardMaterial color="#f1f5f9" roughness={0.4} metalness={0.2} />
    </mesh>
    {/* Fan Grate */}
    <mesh position={[0, 0.8, 0.46]}>
      <circleGeometry args={[0.35, 16]} />
      <meshStandardMaterial color="#334155" metalness={0.8} />
    </mesh>
  </group>
);

/* ─────────────────────────────────────────────────────────────────
   MAIN EXACT DIORAMA GROUND PLATFORM
   ───────────────────────────────────────────────────────────────── */
export const FactoryGround: React.FC = () => {
  return (
    <group>
      {/* ─── 1. ELEVATED DIORAMA RECTANGULAR PLATFORM ──────────── */}
      {/* Concrete side bevel/skirt (creates the isometric plinth) */}
      <mesh position={[0, -0.6, 0]} receiveShadow>
        <boxGeometry args={[94, 1.2, 70]} />
        <meshStandardMaterial color="#2d2a27" roughness={0.85} />
      </mesh>

      {/* Main Top Asphalt Slab */}
      <mesh position={[0, 0.01, 0]} receiveShadow>
        <boxGeometry args={[93, 0.05, 69]} />
        <meshStandardMaterial color="#4a4642" roughness={0.78} />
      </mesh>

      {/* White Perimeter Curb Wrapping the Diorama */}
      <lineSegments position={[0, 0.05, 0]}>
        <edgesGeometry args={[new THREE.BoxGeometry(93.2, 0.08, 69.2)]} />
        <lineBasicMaterial color="#e2e8f0" linewidth={3} />
      </lineSegments>

      {/* ─── 2. ROADS & INNER CONCRETE PATHS ───────────────────── */}
      {/* Main horizontal dividing road */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 3]} receiveShadow>
        <planeGeometry args={[92, 5.0]} />
        <meshStandardMaterial color="#383533" roughness={0.8} />
      </mesh>
      {/* Road border curb lines */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.025, 0.5]}>
        <planeGeometry args={[92, 0.15]} />
        <meshStandardMaterial color="#cbd5e1" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.025, 5.5]}>
        <planeGeometry args={[92, 0.15]} />
        <meshStandardMaterial color="#cbd5e1" />
      </mesh>

      {/* Vertical cross road */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-4, 0.02, 0]} receiveShadow>
        <planeGeometry args={[5.0, 68]} />
        <meshStandardMaterial color="#383533" roughness={0.8} />
      </mesh>

      {/* ─── 3. ANGLED PARKING LOT 1 (Front-Center) ────────────── */}
      <group position={[-5, 0, 16]}>
        {/* White angled 45-degree parking stripes as in the image */}
        {Array.from({ length: 9 }).map((_, i) => (
          <mesh
            key={`p1-stripe-${i}`}
            rotation={[-Math.PI / 2, 0, Math.PI / 4]}
            position={[-7 + i * 1.8, 0.03, 0]}
          >
            <planeGeometry args={[0.12, 3.8]} />
            <meshStandardMaterial color="#f8fafc" />
          </mesh>
        ))}
        {/* Lane dividers */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, -2.6]}>
          <planeGeometry args={[16, 0.12]} />
          <meshStandardMaterial color="#f8fafc" />
        </mesh>
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 2.6]}>
          <planeGeometry args={[16, 0.12]} />
          <meshStandardMaterial color="#f8fafc" />
        </mesh>
      </group>

      {/* ─── 4. ANGLED PARKING LOT 2 (Mid-Left between Hangars & Towers) ── */}
      <group position={[-16, 0, -10]}>
        {Array.from({ length: 7 }).map((_, i) => (
          <mesh
            key={`p2-stripe-${i}`}
            rotation={[-Math.PI / 2, 0, Math.PI / 4]}
            position={[-5 + i * 1.6, 0.03, 0]}
          >
            <planeGeometry args={[0.12, 3.4]} />
            <meshStandardMaterial color="#f8fafc" />
          </mesh>
        ))}
      </group>

      {/* ─── 5. ANGLED PARKING LOT 3 (Rear-Right behind Main Hall) ── */}
      <group position={[20, 0, -23]}>
        {Array.from({ length: 8 }).map((_, i) => (
          <mesh
            key={`p3-stripe-${i}`}
            rotation={[-Math.PI / 2, 0, Math.PI / 4]}
            position={[-6 + i * 1.6, 0.03, 0]}
          >
            <planeGeometry args={[0.12, 3.4]} />
            <meshStandardMaterial color="#f8fafc" />
          </mesh>
        ))}
      </group>

      {/* ─── 6. GREEN LAWN ISLAND WITH PINE TREES (Front-Center) ── */}
      <group position={[3, 0.03, 22]}>
        {/* Triangular/wedge grass patch */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <planeGeometry args={[10, 6]} />
          <meshStandardMaterial color="#2d7a3e" roughness={0.9} />
        </mesh>
        {/* Concrete border */}
        <lineSegments>
          <edgesGeometry args={[new THREE.BoxGeometry(10.1, 0.05, 6.1)]} />
          <lineBasicMaterial color="#e2e8f0" linewidth={2} />
        </lineSegments>
        {/* Trees on the island */}
        <DioramaPineTree position={[-3, 0, 0]} scale={0.9} />
        <DioramaPineTree position={[-0.5, 0, 1.2]} scale={1.1} />
        <DioramaPineTree position={[1.8, 0, -0.8]} scale={0.85} />
        <DioramaPineTree position={[3.5, 0, 0.8]} scale={1.0} />
      </group>

      {/* Rear Green Tree Line */}
      <group position={[14, 0, -28]}>
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
          <planeGeometry args={[14, 2.5]} />
          <meshStandardMaterial color="#2d7a3e" roughness={0.9} />
        </mesh>
        {[-5, -2, 1, 4].map((x, i) => (
          <DioramaPineTree key={`rear-tree-${i}`} position={[x, 0, 0]} scale={0.95} />
        ))}
      </group>

      {/* ─── 7. THREE ARCHED BARREL-VAULT HANGARS (Mid-Left) ──── */}
      {/* Matching the exact blue-and-white striped arched warehouses */}
      <group position={[-25, 0, 2]}>
        <ArchedBarrelHangar position={[-6.5, 0, 0]} width={5.5} length={10.0} height={3.4} />
        <ArchedBarrelHangar position={[0, 0, 0]} width={5.5} length={10.0} height={3.4} />
        <ArchedBarrelHangar position={[6.5, 0, 0]} width={5.5} length={10.0} height={3.4} />
      </group>

      {/* ─── 8. STORAGE TANK FARMS (Rear-Right & Far-Right) ────── */}
      {/* Cluster of 4 tanks behind Main Hall */}
      <group position={[10, 0, -22]}>
        <DioramaStorageTank position={[-2.2, 0, -2.2]} radius={1.7} height={3.6} />
        <DioramaStorageTank position={[2.2, 0, -2.2]} radius={1.7} height={3.6} />
        <DioramaStorageTank position={[-2.2, 0, 2.2]} radius={1.7} height={3.6} />
        <DioramaStorageTank position={[2.2, 0, 2.2]} radius={1.7} height={3.6} />
      </group>

      {/* Cluster of 6 tanks on Far Right */}
      <group position={[38, 0, -4]}>
        <DioramaStorageTank position={[-2.2, 0, -4.5]} radius={1.6} height={3.2} />
        <DioramaStorageTank position={[2.2, 0, -4.5]} radius={1.6} height={3.2} />
        <DioramaStorageTank position={[-2.2, 0, 0]} radius={1.6} height={3.2} />
        <DioramaStorageTank position={[2.2, 0, 0]} radius={1.6} height={3.2} />
        <DioramaStorageTank position={[-2.2, 0, 4.5]} radius={1.6} height={3.2} />
        <DioramaStorageTank position={[2.2, 0, 4.5]} radius={1.6} height={3.2} />
      </group>

      {/* Small tank cluster near the office */}
      <group position={[-14, 0, 16]}>
        <DioramaStorageTank position={[-2.0, 0, 0]} radius={1.4} height={2.8} />
        <DioramaStorageTank position={[1.8, 0, 0]} radius={1.3} height={2.6} />
      </group>

      {/* ─── 9. THIN BANDED RED & WHITE SMOKESTACKS ────────────── */}
      <ThinBandedSmokestack position={[-17, 0, 14]} height={7.5} radius={0.22} />
      <ThinBandedSmokestack position={[-18.5, 0, 15]} height={8.5} radius={0.25} />
      <ThinBandedSmokestack position={[32, 0, -10]} height={9.0} radius={0.26} />
      <ThinBandedSmokestack position={[34, 0, -10]} height={8.0} radius={0.22} />
      <ThinBandedSmokestack position={[16, 0, -16]} height={8.5} radius={0.24} />

      {/* ─── 10. EXTERNAL CHILLER UNITS ON MAIN HALL WALL ──────── */}
      {[-10, -5, 0, 5, 10].map((z, i) => (
        <ExternalChillerUnit key={`chiller-${i}`} position={[12, 0, 12 + z * 0.8]} />
      ))}
    </group>
  );
};
