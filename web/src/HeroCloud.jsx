import React, { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useStore } from "./store.js";

const COLORS = { Low: "#37d67a", Medium: "#f2b134", High: "#e4572e" };
const SPREAD_X = 30, SPREAD_Z = 24, HEIGHT = 15;

function hash(i) {
  const s = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return s - Math.floor(s);
}

function Cloud({ applicants, meta }) {
  const meshRef = useRef();
  const groupRef = useRef();
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const tmp = useMemo(() => new THREE.Color(), []);
  const n = applicants.length;

  const layout = useMemo(() => {
    const iMin = meta.income_min, iMax = meta.income_max;
    return applicants.map((a, i) => {
      const nx = (a.income - iMin) / (iMax - iMin);
      const nz = (a.credit_score - 300) / 550;
      return {
        x: (nx - 0.5) * SPREAD_X + (hash(i) - 0.5) * 4,
        z: (nz - 0.5) * SPREAD_Z + (hash(i + 99) - 0.5) * 4,
        y: (a.risk / 100) * HEIGHT,
        cat: a.category,
      };
    });
  }, [applicants, meta]);

  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    layout.forEach((p, i) => {
      dummy.position.set(p.x, p.y - HEIGHT / 2, p.z);
      dummy.scale.setScalar(0.36);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      mesh.setColorAt(i, tmp.set(COLORS[p.cat]));
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [layout, dummy, tmp]);

  useFrame((_, dt) => {
    if (groupRef.current) groupRef.current.rotation.y += dt * 0.08;
  });

  return (
    <group ref={groupRef}>
      <instancedMesh ref={meshRef} args={[null, null, n]}>
        <sphereGeometry args={[1, 16, 16]} />
        <meshStandardMaterial toneMapped={false} roughness={0.4} metalness={0.1} />
      </instancedMesh>
    </group>
  );
}

export default function HeroCloud() {
  // Share the applicant fetch with the Dashboard via the store (loads once).
  const data = useStore((s) => s.data);
  const load = useStore((s) => s.load);

  useEffect(() => {
    load();
  }, [load]);

  if (!data) return <div className="hero-field" aria-hidden />;

  return (
    <div className="hero-canvas" aria-hidden>
      <Canvas
        camera={{ position: [2, 4, 34], fov: 50 }}
        dpr={[1, 1.6]}
        gl={{ antialias: true, alpha: true }}
        onCreated={({ scene }) => {
          // Match fog to the current site background so the cloud blends in
          // both dark and light themes.
          const bg = getComputedStyle(document.querySelector(".site") || document.body)
            .getPropertyValue("--bg").trim() || "#070d1a";
          scene.fog = new THREE.FogExp2(bg, 0.02);
        }}
      >
        <ambientLight intensity={0.7} />
        <directionalLight position={[15, 25, 15]} intensity={1.1} />
        <pointLight position={[-15, 5, -10]} intensity={0.5} color="#38bdf8" />
        <Cloud applicants={data.applicants} meta={data.meta} />
      </Canvas>
    </div>
  );
}
