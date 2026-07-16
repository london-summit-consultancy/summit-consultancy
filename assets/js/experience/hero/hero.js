// Wireframe hero — "the broken structure, refactored". An always-dark
// cinematic band that opens the homepage above the journey film. ~300 line
// fragments begin scattered and assemble phase-by-phase (setting out → columns
// → floors → bracing → envelope) into a structurally sound tower. All member
// motion runs in one vertex shader; a single anime.js timeline conducts the
// global build progress, the copy locks, the build log and the laser sweep.
//
// Independent of the Journey: its own renderer, rAF, resize and pause logic, so
// the two WebGL scenes never both burn frames — an IntersectionObserver parks
// this loop the moment the hero scrolls out of view.
import { animate, createTimeline, stagger } from "animejs";
import * as THREE from "three";

const INK = 0x0a1322;
const LINE = 0xd9e4f1;
const ACCENT = 0xf0521a;

const ASSEMBLE_START = 300; // ms into the timeline
const ASSEMBLE_MS = 4600;
const PHASE_STEP = 0.185; // phase p opens at p * STEP of build progress
const PHASE_SPAN = 0.26; // ...and completes with this much overlap

function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const clamp01 = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);
const smooth = (a, b, v) => {
  const t = clamp01((v - a) / (b - a));
  return t * t * (3 - 2 * t);
};

// The structure — a podium + tower on a bay grid, expressed as segments.
const LVL = 2.3;
const GX = [-6, -3, 0, 3, 6];
const GZ = [-4.5, -1.5, 1.5, 4.5];
const TX = [-3, 0, 3];
const TZ = [-1.5, 1.5];
const PODIUM_LEVELS = 2;
const TOP_LEVEL = 11;
const MAST_TOP = 30.5;

function buildSegments() {
  const segs = [];
  const seg = (a, b, phase, accent = 0) => segs.push({ a, b, phase, accent });

  // Phase 0 — setting out: datum axes, footprint, structural grid.
  const gy = 0.02;
  seg([-16, gy, 0], [16, gy, 0], 0);
  seg([0, gy, -13], [0, gy, 13], 0);
  seg([-6, gy, -4.5], [6, gy, -4.5], 0);
  seg([-6, gy, 4.5], [6, gy, 4.5], 0);
  seg([-6, gy, -4.5], [-6, gy, 4.5], 0);
  seg([6, gy, -4.5], [6, gy, 4.5], 0);
  for (const x of GX.slice(1, -1)) seg([x, gy, -4.5], [x, gy, 4.5], 0);
  for (const z of GZ.slice(1, -1)) seg([-6, gy, z], [6, gy, z], 0);

  // Phase 1 — frame: columns, one fragment per storey.
  for (const x of GX)
    for (const z of GZ)
      for (let l = 0; l < PODIUM_LEVELS; l++)
        seg([x, l * LVL, z], [x, (l + 1) * LVL, z], 1);
  for (const x of TX)
    for (const z of TZ)
      for (let l = PODIUM_LEVELS; l < TOP_LEVEL; l++)
        seg([x, l * LVL, z], [x, (l + 1) * LVL, z], 1);

  // Phase 2 — floors: beam grids at every level.
  for (let l = 1; l <= PODIUM_LEVELS; l++) {
    const y = l * LVL;
    for (const z of GZ) seg([-6, y, z], [6, y, z], 2);
    for (const x of GX) seg([x, y, -4.5], [x, y, 4.5], 2);
  }
  for (let l = PODIUM_LEVELS + 1; l <= TOP_LEVEL; l++) {
    const y = l * LVL;
    for (const z of TZ) seg([-3, y, z], [3, y, z], 2);
    for (const x of TX) seg([x, y, -1.5], [x, y, 1.5], 2);
  }

  // Phase 3 — core: alternating diagonal bracing on the tower faces, plus
  // corner braces steadying the podium.
  for (const z of TZ)
    for (let l = PODIUM_LEVELS; l < TOP_LEVEL; l++)
      for (let bay = 0; bay < 2; bay++) {
        const x0 = -3 + bay * 3;
        const up = (l + bay) % 2 === 0;
        seg(
          [up ? x0 : x0 + 3, l * LVL, z],
          [up ? x0 + 3 : x0, (l + 1) * LVL, z],
          3
        );
      }
  seg([-6, 0, -4.5], [-3, PODIUM_LEVELS * LVL, -4.5], 3);
  seg([6, 0, -4.5], [3, PODIUM_LEVELS * LVL, -4.5], 3);
  seg([-6, 0, 4.5], [-3, PODIUM_LEVELS * LVL, 4.5], 3);
  seg([6, 0, 4.5], [3, PODIUM_LEVELS * LVL, 4.5], 3);

  // Phase 4 — envelope + crown: mullions, parapet, and the orange summit mast.
  for (const z of TZ)
    for (const x of [-1.5, 1.5])
      for (let l = PODIUM_LEVELS; l < TOP_LEVEL; l++)
        seg([x, l * LVL, z], [x, (l + 1) * LVL, z], 4);
  for (const x of [-3, 3])
    for (let l = PODIUM_LEVELS; l < TOP_LEVEL; l++)
      seg([x, l * LVL, 0], [x, (l + 1) * LVL, 0], 4);
  const ty = TOP_LEVEL * LVL;
  const py = ty + 0.9;
  for (const x of [-3, 3]) for (const z of TZ) seg([x, ty, z], [x, py, z], 4);
  seg([-3, py, -1.5], [3, py, -1.5], 4);
  seg([-3, py, 1.5], [3, py, 1.5], 4);
  seg([-3, py, -1.5], [-3, py, 1.5], 4);
  seg([3, py, -1.5], [3, py, 1.5], 4);
  seg([0, py, 0], [0, MAST_TOP, 0], 4, 1); // the summit
  seg([-0.6, MAST_TOP - 1.4, 0], [0.6, MAST_TOP - 1.4, 0], 4, 1);

  return segs;
}

// Geometry: two vertices per segment; the scattered "broken" pose is encoded
// per segment (offset + axis-angle about its midpoint) and resolved on the GPU.
function makeStructure() {
  const segs = buildSegments();
  const rng = mulberry32(20260711);
  const n = segs.length;

  const position = new Float32Array(n * 6);
  const mid = new Float32Array(n * 6);
  const scatter = new Float32Array(n * 8); // offset xyz + rotation angle
  const axis = new Float32Array(n * 6);
  const meta = new Float32Array(n * 6); // delay, phase, accent

  for (let i = 0; i < n; i++) {
    const s = segs[i];
    const mx = (s.a[0] + s.b[0]) / 2;
    const my = (s.a[1] + s.b[1]) / 2;
    const mz = (s.a[2] + s.b[2]) / 2;

    const theta = rng() * Math.PI * 2;
    const lift = (rng() - 0.35) * 10;
    const r = 8 + rng() * 9;
    const ox = Math.cos(theta) * r;
    const oy = lift + my * 0.15;
    const oz = Math.sin(theta) * r;
    const ang = 0.6 + rng() * 1.9;
    let ax = rng() * 2 - 1;
    let ay = rng() * 2 - 1;
    let az = rng() * 2 - 1;
    const al = Math.hypot(ax, ay, az) || 1;
    ax /= al;
    ay /= al;
    az /= al;

    const delay =
      s.phase === 0
        ? clamp01(Math.hypot(mx, mz) / 17) * 0.7 + rng() * 0.3
        : clamp01(my / (MAST_TOP * 0.92)) * 0.62 + rng() * 0.38;

    for (let v = 0; v < 2; v++) {
      const p = v === 0 ? s.a : s.b;
      const o3 = (i * 2 + v) * 3;
      position[o3] = p[0];
      position[o3 + 1] = p[1];
      position[o3 + 2] = p[2];
      mid[o3] = mx;
      mid[o3 + 1] = my;
      mid[o3 + 2] = mz;
      axis[o3] = ax;
      axis[o3 + 1] = ay;
      axis[o3 + 2] = az;
      const o4 = (i * 2 + v) * 4;
      scatter[o4] = ox;
      scatter[o4 + 1] = oy;
      scatter[o4 + 2] = oz;
      scatter[o4 + 3] = ang;
      meta[o3] = clamp01(delay);
      meta[o3 + 1] = s.phase;
      meta[o3 + 2] = s.accent;
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(position, 3));
  geometry.setAttribute("aMid", new THREE.BufferAttribute(mid, 3));
  geometry.setAttribute("aScatter", new THREE.BufferAttribute(scatter, 4));
  geometry.setAttribute("aAxis", new THREE.BufferAttribute(axis, 3));
  geometry.setAttribute("aMeta", new THREE.BufferAttribute(meta, 3));

  const material = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    uniforms: {
      uProgress: { value: 0 },
      uScanY: { value: -10 },
      uScanAmp: { value: 0 },
      uLine: { value: new THREE.Color(LINE) },
      uAccent: { value: new THREE.Color(ACCENT) },
    },
    vertexShader: /* glsl */ `
      attribute vec3 aMid;
      attribute vec4 aScatter;
      attribute vec3 aAxis;
      attribute vec3 aMeta; // delay, phase, accent
      uniform float uProgress;
      varying float vGlow;
      varying float vAccent;
      varying float vY;

      vec3 rotateAxis(vec3 p, vec3 ax, float a) {
        float c = cos(a);
        float s = sin(a);
        return p * c + cross(ax, p) * s + ax * dot(ax, p) * (1.0 - c);
      }

      void main() {
        float open = aMeta.y * ${PHASE_STEP};
        float local = clamp((uProgress - open) / ${PHASE_SPAN}, 0.0, 1.0);
        float t = clamp((local - aMeta.x * 0.55) / 0.45, 0.0, 1.0);
        float e = 1.0 - pow(1.0 - t, 4.0); // members snap home, then settle
        float settle = e + 0.05 * sin(t * 3.14159) * (1.0 - t);

        vec3 rel = position - aMid;
        vec3 p = rotateAxis(rel, aAxis, aScatter.w * (1.0 - e)) + aMid
               + aScatter.xyz * (1.0 - settle);

        vGlow = e;
        vAccent = aMeta.z;
        vY = p.y;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
      }
    `,
    fragmentShader: /* glsl */ `
      uniform vec3 uLine;
      uniform vec3 uAccent;
      uniform float uScanY;
      uniform float uScanAmp;
      varying float vGlow;
      varying float vAccent;
      varying float vY;

      void main() {
        float scan = exp(-abs(vY - uScanY) * 1.35) * uScanAmp;
        vec3 col = mix(uLine, uAccent, vAccent);
        col = col * (0.5 + 0.5 * vGlow) + uAccent * scan;
        float alpha = 0.16 + 0.74 * vGlow + scan * 0.4;
        gl_FragColor = vec4(col, alpha);
      }
    `,
  });

  const lines = new THREE.LineSegments(geometry, material);
  lines.frustumCulled = false;
  return { lines, material };
}

// Site grid — quiet context, faded by fog.
function makeSiteGrid() {
  const pts = [];
  for (let i = -48; i <= 48; i += 3) {
    pts.push(i, 0, -48, i, 0, 48, -48, 0, i, 48, 0, i);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(pts), 3));
  const material = new THREE.LineBasicMaterial({
    color: 0x22334e,
    transparent: true,
    opacity: 0.5,
    fog: true,
  });
  return new THREE.LineSegments(geometry, material);
}

// Mount the hero if its section is present. Self-gating and self-contained:
// safe to call on every page; it no-ops where there is no [data-hero-wireframe].
export function mountHero() {
  const root = document.querySelector("[data-hero-wireframe]");
  if (!root) return;
  const host = root.querySelector(".lsx-canvas");
  const logText = root.querySelector(".lsx-logtext");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  root.classList.add("lsx--js");

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
  } catch {
    root.classList.add("lsx--flat", "lsx--settled");
    return;
  }
  renderer.setClearColor(0x000000, 0);
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(INK, 42, 110);
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 220);

  const { lines, material } = makeStructure();
  scene.add(lines);
  scene.add(makeSiteGrid());

  const build = { t: reduceMotion ? 1 : 0 };
  const scan = { y: -10, amp: 0, auto: false, autoFrom: 0 };
  const pointer = { x: 0, y: 0, tx: 0, ty: 0 };
  const target = new THREE.Vector3(0, 13, 0);
  let targetX = 0;

  function resize() {
    const w = host.clientWidth;
    const h = host.clientHeight;
    if (!w || !h) return;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    targetX = camera.aspect > 1.05 ? -7 : 0; // tower sits right of the copy
  }
  resize();
  window.addEventListener("resize", resize);

  root.addEventListener("pointermove", (e) => {
    const r = root.getBoundingClientRect();
    pointer.tx = ((e.clientX - r.left) / r.width) * 2 - 1;
    pointer.ty = ((e.clientY - r.top) / r.height) * 2 - 1;
  });

  const clock = new THREE.Clock();
  let raf = 0;

  function frame() {
    raf = requestAnimationFrame(frame);
    const dt = Math.min(clock.getDelta(), 0.05);
    const time = clock.elapsedTime;
    const k = 1 - Math.exp(-4 * dt);
    pointer.x += (pointer.tx - pointer.x) * k;
    pointer.y += (pointer.ty - pointer.y) * k;

    material.uniforms.uProgress.value = build.t;

    if (scan.auto) {
      const sp = ((time - scan.autoFrom) % 9) / 9;
      scan.y = -2 + sp * 33;
      scan.amp = smooth(0, 0.12, sp) * (1 - smooth(0.86, 1, sp)) * 0.34;
    }
    material.uniforms.uScanY.value = scan.y;
    material.uniforms.uScanAmp.value = scan.amp;

    const drift = reduceMotion ? 0 : Math.sin(time * 0.1) * 0.05;
    const az = -0.62 + drift + pointer.x * 0.05;
    const polar = 1.32 + pointer.y * 0.03;
    const radius = 68 - 14 * build.t;
    target.x += (targetX - target.x) * k;
    camera.position.set(
      target.x + radius * Math.sin(polar) * Math.sin(az),
      target.y + radius * Math.cos(polar),
      radius * Math.sin(polar) * Math.cos(az)
    );
    camera.lookAt(target);
    renderer.render(scene, camera);
  }

  // Frames run only while the hero is both on-screen and the tab is visible, so
  // scrolling down to the journey hands the whole GPU to that scene.
  let onScreen = true;
  let docVisible = !document.hidden;
  function sync() {
    const shouldRun = onScreen && docVisible;
    if (shouldRun && !raf) {
      clock.getDelta(); // drop the idle gap so motion never lurches on resume
      frame();
    } else if (!shouldRun && raf) {
      cancelAnimationFrame(raf);
      raf = 0;
    }
  }
  frame();

  if ("IntersectionObserver" in window) {
    new IntersectionObserver(
      (entries) => {
        onScreen = entries[0].isIntersecting;
        sync();
      },
      { threshold: 0 }
    ).observe(root);
  }
  document.addEventListener("visibilitychange", () => {
    docVisible = !document.hidden;
    sync();
  });

  // Reduced motion: everything arrives settled, no assembly, no autoplay sweep.
  if (reduceMotion) {
    root.classList.add("lsx--settled", "lsx--sound");
    if (logText) logText.textContent = "STATUS — STRUCTURALLY SOUND";
    return;
  }

  const phaseAt = (p) => ASSEMBLE_START + p * PHASE_STEP * ASSEMBLE_MS;
  const tl = createTimeline({ defaults: { ease: "outExpo" } });

  const logBeat = (at, text) =>
    tl.add(
      logText,
      {
        opacity: [0.3, 1],
        duration: 340,
        ease: "outQuad",
        onBegin: () => {
          logText.textContent = text;
        },
      },
      at
    );

  tl.add(".lsx-ax-v", { scaleY: [0, 1], duration: 1100 }, 60);
  tl.add(".lsx-ax-h", { scaleX: [0, 1], duration: 1100 }, 60);
  tl.add(".lsx-coord", { opacity: [0, 1], duration: 700, ease: "outQuad" }, 700);
  tl.add(".lsx-top .e", { opacity: [0, 1], y: [10, 0], duration: 800, delay: stagger(140) }, 150);
  tl.add(".lsx-eyebrow", { opacity: [0, 1], y: [12, 0], duration: 800 }, 350);

  tl.add(build, { t: 1, duration: ASSEMBLE_MS, ease: "inOutSine" }, ASSEMBLE_START);

  logBeat(phaseAt(0), "00 · SETTING OUT — ESTABLISHING GRID");
  logBeat(phaseAt(1), "01 · FRAME — COLUMNS TO PLUMB");
  logBeat(phaseAt(2), "02 · FLOORS — LEVELLING PLATES");
  logBeat(phaseAt(3), "03 · CORE — TYING BRACING");
  logBeat(phaseAt(4), "04 · ENVELOPE — CLOSING LINES");

  const word = (sel, at) => tl.add(sel, { y: ["112%", "0%"], duration: 1000 }, at);
  word(".lsx-w--1", 1450);
  word(".lsx-w--2", 2250);
  word(".lsx-w--3", 3350);

  tl.add(".lsx-lede", { opacity: [0, 1], y: [16, 0], duration: 900 }, 4100);
  tl.add(".lsx-actions .lsx-btn", { opacity: [0, 1], y: [14, 0], duration: 800, delay: stagger(150) }, 4300);
  tl.add(".lsx-tb span", { opacity: [0, 1], y: [8, 0], duration: 600, delay: stagger(110) }, 4750);

  tl.add(
    scan,
    {
      y: [-2, 31],
      amp: [0.9, 0.9],
      duration: 1300,
      ease: "inOutQuad",
      onComplete: () => {
        scan.auto = true;
        scan.autoFrom = clock.elapsedTime;
      },
    },
    4700
  );
  tl.add(
    logText,
    {
      opacity: [0.3, 1],
      duration: 400,
      ease: "outQuad",
      onBegin: () => {
        if (logText) logText.textContent = "STATUS — STRUCTURALLY SOUND";
        root.classList.add("lsx--sound");
      },
    },
    5250
  );
}
