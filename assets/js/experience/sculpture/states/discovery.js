// Chapter 2 — Discovery. The idea becomes drawing: plan sketches, wall lines,
// door swings and dimension ticks self-draw across a floating drawing board.
// Particles condense along the same strokes, so the sketch and the cloud are
// one object.
import { circle, line, rect, v } from "./curves.js";

const BOARD_Y = 3.72;

function buildSketch() {
  const y = BOARD_Y;
  const list = [];
  // Plan outline and structural walls.
  list.push(rect(16, 12, y));
  list.push(line([-8, y, -2], [2, y, -2]));
  list.push(line([2, y, -2], [2, y, 6]));
  list.push(line([-3, y, -6], [-3, y, 2]));
  list.push(line([4.5, y, -6], [4.5, y, -2]));
  list.push(line([-8, y, 2.5], [-3, y, 2.5]));
  // Door swings.
  list.push(circle(2, -2, 1.6, y, 18, Math.PI, Math.PI * 1.5));
  list.push(circle(-3, 2, 1.6, y, 18, -Math.PI / 2, 0));
  // Circulation study.
  list.push(circle(3.5, 2, 2.2, y, 48));
  // Dimension ticks outside the plan.
  for (let x = -8; x <= 8; x += 4) list.push(line([x, y, 6.8], [x, y, 7.6], 2));
  list.push(line([-8, y, 7.2], [8, y, 7.2]));
  for (let z = -6; z <= 6; z += 4) list.push(line([-8.8, y, z], [-9.6, y, z], 2));
  list.push(line([-9.2, y, -6], [-9.2, y, 6]));
  // Elevation studies pinned up behind the plan.
  const ez = -8.6;
  list.push({
    points: [
      v(-7, 1.5, ez),
      v(-7, 8.5, ez),
      v(-1, 8.5, ez),
      v(-1, 1.5, ez),
      v(-7, 1.5, ez),
    ],
  });
  for (let k = 1; k <= 3; k++) list.push(line([-7, 1.5 + k * 1.75, ez], [-1, 1.5 + k * 1.75, ez], 6));
  list.push({
    points: [v(1.5, 1.5, ez), v(1.5, 7, ez), v(6.5, 8.5, ez), v(6.5, 1.5, ez), v(1.5, 1.5, ez)],
  });
  return list;
}

const SKETCH = buildSketch();

// Flatten the sketch into length-weighted segments for particle sampling.
function buildSegments() {
  const segs = [];
  let total = 0;
  for (const poly of SKETCH) {
    const pts = poly.points;
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i];
      const b = pts[i + 1];
      const len = Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z);
      total += len;
      segs.push({ a, b, acc: total });
    }
  }
  return { segs, total };
}

const { segs: SEGS, total: TOTAL } = buildSegments();

function segmentPoint(rng, out, o) {
  const pick = rng() * TOTAL;
  let lo = 0;
  let hi = SEGS.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (SEGS[mid].acc < pick) lo = mid + 1;
    else hi = mid;
  }
  const s = SEGS[lo];
  const t = rng();
  out[o] = s.a.x + (s.b.x - s.a.x) * t + (rng() - 0.5) * 0.14;
  out[o + 1] = s.a.y + (s.b.y - s.a.y) * t + (rng() - 0.5) * 0.1;
  out[o + 2] = s.a.z + (s.b.z - s.a.z) * t + (rng() - 0.5) * 0.14;
}

export function fillParticles(out, n, rng) {
  for (let i = 0; i < n; i++) {
    const o = i * 3;
    if (i / n < 0.78) {
      segmentPoint(rng, out, o);
    } else {
      // Loose ideas hovering above the board.
      out[o] = (rng() - 0.5) * 22;
      out[o + 1] = BOARD_Y + 0.5 + rng() * 5;
      out[o + 2] = (rng() - 0.5) * 16;
    }
  }
}

export function lines() {
  return SKETCH;
}

export const env = {
  background: "#fdfdfc",
  fogColor: "#fdfdfc",
  fogDensity: 0,
  bloom: 0.85,
  exposure: 1.0,
  particle: { colorA: "#334155", colorB: "#f59e0b", glowMix: 0.15, size: 1.5, opacity: 0.9 },
  line: { color: "#4a5568", opacity: 0.85 },
  mass: { color: "#f2f2f1", roughness: 0.95, metalness: 0, rim: 0, noiseAmp: 0.04, envInt: 0.4 },
  glassOpacity: 0,
  glassEnvInt: 1.0,
  windowGlobal: 0,
  water: 0,
  ground: { color: "#fdfdfc", edge: "#f0f1f1", grid: "#bfc3c9", gridInt: 0.45, reveal: 60, opacity: 1 },
  hemi: { sky: "#ffffff", ground: "#ebecec", intensity: 0.95 },
  key: { color: "#fffaf2", intensity: 0.85, pos: [20, 28, 12] },
};
