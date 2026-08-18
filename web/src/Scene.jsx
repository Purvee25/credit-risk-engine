import React, { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Html } from "@react-three/drei";
import * as THREE from "three";
import { useStore, CATEGORY_COLORS, ACCENT } from "./store.js";

const SPREAD_X = 34;
const SPREAD_Z = 26;
const HEIGHT = 16; // risk 0..100 maps to y 0..HEIGHT

// Small deterministic pseudo-random so the same applicant always lands the same.
function hash(i) {
  const s = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return s - Math.floor(s); // 0..1
}

// Deterministic layout: income drives X, risk drives Y (height), credit score
// drives Z depth. Phyllotaxis jitter de-clumps points at similar incomes.
function computeLayout(applicants, meta) {
  const iMin = meta.income_min;
  const iMax = meta.income_max;
  return applicants.map((a, i) => {
    const nx = (a.income - iMin) / (iMax - iMin); // 0..1
    const nz = (a.credit_score - 300) / 550; // 0..1
    const jx = (hash(i) - 0.5) * 4.0;
    const jz = (hash(i + 99) - 0.5) * 4.0;
    return {
      x: (nx - 0.5) * SPREAD_X + jx,
      z: (nz - 0.5) * SPREAD_Z + jz,
      y: (a.risk / 100) * HEIGHT,
    };
  });
}

function ApplicantCloud({ layout, onSelect }) {
  const data = useStore((s) => s.data);
  const threshold = useStore((s) => s.threshold);
  const view = useStore((s) => s.view);
  const selectedId = useStore((s) => s.selectedId);
  const hoveredId = useStore((s) => s.hoveredId);
  const setHovered = useStore((s) => s.setHovered);
  const select = useStore((s) => s.select);
  const setView = useStore((s) => s.setView);

  const meshRef = useRef();
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const applicants = data.applicants;
  const n = applicants.length;

  const tmpColor = useMemo(() => new THREE.Color(), []);

  // Position + seed per-instance colors once (setColorAt creates instanceColor).
  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    layout.forEach((p, i) => {
      dummy.position.set(p.x, p.y, p.z);
      dummy.scale.setScalar(0.38);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      mesh.setColorAt(i, tmpColor.set(CATEGORY_COLORS[applicants[i].category]));
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [layout, dummy, tmpColor, applicants]);

  const white = useMemo(() => new THREE.Color("#ffffff"), []);
  const paintKey = useRef(null);

  // Recolor only when an input that affects colour actually changes, instead of
  // rewriting every instance colour on every frame.
  useFrame(() => {
    const mesh = meshRef.current;
    if (!mesh || !mesh.instanceColor) return;
    const key = `${threshold}|${selectedId}|${hoveredId}|${view}|${n}`;
    if (paintKey.current === key) return;
    paintKey.current = key;
    const arr = mesh.instanceColor.array;
    for (let i = 0; i < n; i++) {
      const a = applicants[i];
      const approved = a.risk < threshold;
      tmpColor.set(CATEGORY_COLORS[a.category]);
      if (view !== "hero" && !approved) tmpColor.multiplyScalar(0.35);
      if (a.id === selectedId && (view === "applicant" || view === "compare")) {
        tmpColor.set(ACCENT);
      } else if (a.id === hoveredId) {
        tmpColor.lerp(white, 0.5);
      }
      tmpColor.toArray(arr, i * 3);
    }
    mesh.instanceColor.needsUpdate = true;
  });

  return (
    <instancedMesh
      ref={meshRef}
      key={n}
      args={[null, null, n]}
      onPointerMove={(e) => {
        e.stopPropagation();
        if (e.instanceId != null) setHovered(applicants[e.instanceId].id);
      }}
      onPointerOut={() => setHovered(null)}
      onClick={(e) => {
        e.stopPropagation();
        if (e.instanceId != null) {
          const id = applicants[e.instanceId].id;
          select(id);
          if (onSelect) {
            // Embedded (e.g. Risk Map): let the caller show details — no camera fly-in.
            onSelect(id);
          } else if (view === "hero" || view === "portfolio") {
            setView("applicant");
          }
        }
      }}
    >
      <sphereGeometry args={[1, 20, 20]} />
      <meshStandardMaterial
        toneMapped={false}
        emissiveIntensity={0.0}
        roughness={0.4}
        metalness={0.1}
      />
    </instancedMesh>
  );
}

function ThresholdPlane() {
  const threshold = useStore((s) => s.threshold);
  const view = useStore((s) => s.view);
  const y = (threshold / 100) * HEIGHT;
  const visible = view === "portfolio";
  const ref = useRef();
  useFrame(() => {
    if (ref.current) {
      ref.current.position.y += (y - ref.current.position.y) * 0.15;
      ref.current.material.opacity +=
        ((visible ? 0.16 : 0) - ref.current.material.opacity) * 0.15;
    }
  });
  return (
    <group>
      <mesh ref={ref} rotation={[-Math.PI / 2, 0, 0]} position={[0, y, 0]}>
        <planeGeometry args={[SPREAD_X + 12, SPREAD_Z + 12]} />
        <meshBasicMaterial
          color={ACCENT}
          transparent
          opacity={0}
          side={THREE.DoubleSide}
        />
      </mesh>
    </group>
  );
}

function GridFloor() {
  return (
    <gridHelper
      args={[80, 40, "#1b2b45", "#12203a"]}
      position={[0, -0.5, 0]}
    />
  );
}

function HoverTip({ layout }) {
  const hoveredId = useStore((s) => s.hoveredId);
  const data = useStore((s) => s.data);
  if (!hoveredId) return null;
  const idx = data.applicants.findIndex((a) => a.id === hoveredId);
  if (idx < 0) return null;
  const a = data.applicants[idx];
  const p = layout[idx];
  return (
    <Html position={[p.x, p.y + 1.1, p.z]} center distanceFactor={26}>
      <div className="tip">
        <b>{a.id}</b>
        <span>{a.risk.toFixed(1)}% risk</span>
      </div>
    </Html>
  );
}

const CAM_TARGETS = {
  hero: { pos: [0, 10, 46], look: [0, 7, 0] },
  portfolio: { pos: [30, 20, 38], look: [0, 7, 0] },
  applicant: { pos: [0, 9, 30], look: [0, 7, 0] },
  compare: { pos: [0, 9, 32], look: [0, 7, 0] },
  fairness: { pos: [-10, 12, 40], look: [0, 7, 0] },
  performance: { pos: [0, 14, 44], look: [0, 8, 0] },
};

const _pos = new THREE.Vector3();
const _look = new THREE.Vector3();

function CameraRig({ layout, controls }) {
  const view = useStore((s) => s.view);
  const selectedId = useStore((s) => s.selectedId);
  const data = useStore((s) => s.data);
  const { camera } = useThree();
  const userActive = useRef(false);

  // While the user is dragging, don't fight OrbitControls.
  useEffect(() => {
    const c = controls.current;
    if (!c) return;
    const start = () => (userActive.current = true);
    const end = () => (userActive.current = false);
    c.addEventListener("start", start);
    c.addEventListener("end", end);
    return () => {
      c.removeEventListener("start", start);
      c.removeEventListener("end", end);
    };
  }, [controls]);

  useFrame(() => {
    const c = controls.current;
    if (!c || userActive.current) return;
    const t = CAM_TARGETS[view] || CAM_TARGETS.hero;
    _pos.set(t.pos[0], t.pos[1], t.pos[2]);
    _look.set(t.look[0], t.look[1], t.look[2]);

    if (view === "applicant" && selectedId) {
      const idx = data.applicants.findIndex((a) => a.id === selectedId);
      const p = layout[idx];
      if (p) {
        _pos.set(p.x + 8, p.y + 5, p.z + 16);
        _look.set(p.x, p.y, p.z);
      }
    }
    camera.position.lerp(_pos, 0.06);
    c.target.lerp(_look, 0.06);
    c.update();
  });
  return null;
}

export default function Scene({ onSelect, centered = false }) {
  const data = useStore((s) => s.data);
  const layout = useMemo(
    () => computeLayout(data.applicants, data.meta),
    [data]
  );
  const view = useStore((s) => s.view);
  const spinRef = useRef();
  const offsetRef = useRef();
  const controls = useRef();

  // Slow auto-rotation of the whole cloud only on the hero view.
  const InnerSpin = () => {
    useFrame((_, dt) => {
      if (spinRef.current && view === "hero") {
        spinRef.current.rotation.y += dt * 0.05;
      }
      // Slide the whole cloud into the clear zone: right on the hero (text is
      // on the left), left on data views (the panel is on the right). A
      // standalone embed (e.g. the Risk Map) stays centered instead.
      if (offsetRef.current) {
        const targetX = centered ? 0 : view === "hero" ? 11 : -6;
        offsetRef.current.position.x +=
          (targetX - offsetRef.current.position.x) * 0.08;
      }
    });
    return null;
  };

  return (
    <Canvas
      camera={{ position: [0, 10, 46], fov: 50 }}
      dpr={[1, 1.8]}
      gl={{ antialias: true }}
      onCreated={({ scene }) => {
        scene.fog = new THREE.FogExp2("#070d1a", 0.014);
      }}
    >
      <color attach="background" args={["#070d1a"]} />
      <ambientLight intensity={0.6} />
      <directionalLight position={[20, 30, 20]} intensity={1.1} />
      <pointLight position={[-20, 10, -10]} intensity={0.6} color={ACCENT} />

      <InnerSpin />
      <group ref={offsetRef}>
        <group ref={spinRef}>
          <ApplicantCloud layout={layout} onSelect={onSelect} />
          <HoverTip layout={layout} />
        </group>
        <ThresholdPlane />
      </group>
      <GridFloor />
      <CameraRig layout={layout} controls={controls} />
      <OrbitControls
        ref={controls}
        enablePan={false}
        enableZoom={view !== "hero"}
        minDistance={16}
        maxDistance={70}
        target={[0, 7, 0]}
        makeDefault
      />
    </Canvas>
  );
}
