// Chapter 3 — Design Thinking. The sketch gains volume and reveals its
// structural logic: an exploded massing study hangs in space, wireframe edges
// sketching each volume while a precision reinforcement cage — columns, beam
// rings, diagonal bracing — materialises within the core in titanium line
// work. These boxes ARE the tower slabs — chapter 4 pulls them into place.
import { EXPLODED, boxCorners, boxSurfacePoint } from "./composition.js";
import { line, rect } from "./curves.js";

// Edge pairs for the corner ordering produced by boxCorners (index bits x,y,z).
const EDGES = [
  [0, 1],
  [1, 5],
  [5, 4],
  [4, 0],
  [2, 3],
  [3, 7],
  [7, 6],
  [6, 2],
  [0, 2],
  [1, 3],
  [5, 7],
  [4, 6],
];

export function fillParticles(out, n, rng) {
  for (let i = 0; i < n; i++) {
    const o = i * 3;
    if (i / n < 0.82) {
      const box = EXPLODED[Math.floor(rng() * EXPLODED.length)];
      boxSurfacePoint(box, rng, out, o);
    } else {
      // Connective dust drifting between the studies.
      const a = rng() * Math.PI * 2;
      const r = rng() * 9;
      out[o] = Math.cos(a) * r;
      out[o + 1] = 1 + rng() * 33;
      out[o + 2] = Math.sin(a) * r;
    }
  }
}

export function lines() {
  const list = [];
  for (const box of EXPLODED) {
    const c = boxCorners(box);
    for (const [a, b] of EDGES) {
      list.push(line([c[a][0], c[a][1], c[a][2]], [c[b][0], c[b][1], c[b][2]], 4));
    }
  }
  // Reference droplines from each slab down to the base plate.
  for (let k = 2; k < EXPLODED.length - 1; k += 3) {
    const box = EXPLODED[k];
    list.push(line([box.p[0], box.p[1] - box.s[1] / 2, box.p[2]], [box.p[0], 1, box.p[2]], 8));
  }
  // Reinforcement cage around the study core (EXPLODED[1]): corner columns,
  // horizontal beam rings, diagonal bracing — the invisible engineering that
  // makes the massing possible, traced as thin titanium load paths.
  const core = EXPLODED[1];
  const cx = core.s[0] / 2 - 0.2;
  const cz = core.s[2] / 2 - 0.2;
  const y0 = core.p[1] - core.s[1] / 2;
  const y1 = core.p[1] + core.s[1] / 2;
  for (const sx of [1, -1]) {
    for (const sz of [1, -1]) {
      list.push(line([sx * cx, y0, sz * cz], [sx * cx, y1, sz * cz], 10));
    }
  }
  for (let y = y0 + 2; y < y1; y += 2) list.push(rect(cx * 2, cz * 2, y));
  for (const sz of [1, -1]) {
    list.push(line([-cx, y0, sz * cz], [cx, y0 + 4, sz * cz], 6));
    list.push(line([cx, y0 + 4, sz * cz], [-cx, y0 + 8, sz * cz], 6));
    list.push(line([-cx, y0 + 8, sz * cz], [cx, y1, sz * cz], 6));
  }
  return list;
}

export const env = {
  background: "#fbfbfa",
  fogColor: "#fbfbfa",
  fogDensity: 0,
  bloom: 0.9,
  exposure: 1.0,
  particle: { colorA: "#3b4657", colorB: "#f59e0b", glowMix: 0.15, size: 1.35, opacity: 0.8 },
  line: { color: "#9aa0ad", opacity: 0.75 },
  mass: { color: "#e9e9e7", roughness: 0.85, metalness: 0, rim: 0.06, noiseAmp: 0.16, envInt: 0.55 },
  glassOpacity: 0,
  glassEnvInt: 1.0,
  windowGlobal: 0,
  water: 0,
  ground: { color: "#fbfbfa", edge: "#eeefef", grid: "#bfc3c9", gridInt: 0.4, reveal: 70, opacity: 1 },
  hemi: { sky: "#ffffff", ground: "#e4e5e5", intensity: 1.0 },
  key: { color: "#fff6e8", intensity: 1.0, pos: [24, 26, 10] },
};
