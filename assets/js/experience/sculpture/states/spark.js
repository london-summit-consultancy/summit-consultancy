// Chapter 1 — The Spark. A luminous idea breathing in pure white negative
// space while precision drafting materialises beneath it: floor plan,
// structural grid, dimension ticks and pinned elevation studies draw
// themselves with magnetic accuracy — every project begins as a drawing.
import { line, rect, v } from "./curves.js";

export function fillParticles(out, n, rng) {
  for (let i = 0; i < n; i++) {
    const o = i * 3;
    const u = i / n;
    if (u < 0.22) {
      // Dense breathing core.
      out[o] = (rng() + rng() + rng() - 1.5) * 1.0;
      out[o + 1] = 4 + (rng() + rng() + rng() - 1.5) * 1.0;
      out[o + 2] = (rng() + rng() + rng() - 1.5) * 1.0;
    } else if (u < 0.85) {
      // Orbital shells, squashed toward a horizontal band.
      const r = 3 + 7 * Math.pow(rng(), 1.4);
      const a = rng() * Math.PI * 2;
      const e = (rng() - 0.5) * Math.PI;
      out[o] = Math.cos(a) * Math.cos(e) * r;
      out[o + 1] = 4 + Math.sin(e) * r * 0.55;
      out[o + 2] = Math.sin(a) * Math.cos(e) * r;
    } else {
      // Faint far field.
      const r = 12 + rng() * 10;
      const a = rng() * Math.PI * 2;
      out[o] = Math.cos(a) * r;
      out[o + 1] = 1 + rng() * 12;
      out[o + 2] = Math.sin(a) * r;
    }
  }
}

export function lines() {
  const y = 0.05;
  const list = [];
  // Floor plan — the podium footprint the whole journey resolves onto.
  list.push(rect(16.4, 12.4, y));
  // Structural grid inside the plan.
  for (let x = -6; x <= 6; x += 3) list.push(line([x, y, -6.2], [x, y, 6.2], 12));
  for (let z = -4.5; z <= 4.5; z += 3) list.push(line([-8.2, y, z], [8.2, y, z], 12));
  // Setting-out axes running past the plan.
  list.push(line([-13, y, 0], [13, y, 0], 16));
  list.push(line([0, y, -11], [0, y, 11], 16));
  // Dimension ticks and dimension lines outside the plan edge.
  for (let x = -8.2; x <= 8.2; x += 4.1) list.push(line([x, y, 7.2], [x, y, 8], 2));
  list.push(line([-8.2, y, 7.6], [8.2, y, 7.6], 8));
  for (let z = -6.2; z <= 6.2; z += 3.1) list.push(line([-9.2, y, z], [-10, y, z], 2));
  list.push(line([-9.6, y, -6.2], [-9.6, y, 6.2], 8));
  // Elevation studies pinned upright behind the plan.
  const ez = -9.4;
  list.push({
    points: [v(-6, 1.2, ez), v(-6, 8.2, ez), v(0, 8.2, ez), v(0, 1.2, ez), v(-6, 1.2, ez)],
  });
  for (let k = 1; k <= 3; k++) list.push(line([-6, 1.2 + k * 1.75, ez], [0, 1.2 + k * 1.75, ez], 6));
  list.push({
    points: [v(1.6, 1.2, ez), v(1.6, 6.4, ez), v(6.4, 7.8, ez), v(6.4, 1.2, ez), v(1.6, 1.2, ez)],
  });
  // Vertical datum — the idea's centreline.
  list.push(line([0, y, 0], [0, 9, 0], 16));
  return list;
}

export const env = {
  background: "#ffffff",
  fogColor: "#ffffff",
  fogDensity: 0,
  bloom: 1.0,
  exposure: 1.0,
  particle: { colorA: "#334155", colorB: "#f59e0b", glowMix: 0.18, size: 1.7, opacity: 0.9 },
  line: { color: "#45536b", opacity: 0.78 },
  mass: { color: "#f2f2f1", roughness: 0.95, metalness: 0, rim: 0, noiseAmp: 0, envInt: 0.4 },
  glassOpacity: 0,
  glassEnvInt: 1.0,
  windowGlobal: 0,
  water: 0,
  ground: { color: "#ffffff", edge: "#f2f3f4", grid: "#c3c7cd", gridInt: 0.3, reveal: 26, opacity: 1 },
  hemi: { sky: "#ffffff", ground: "#eceded", intensity: 0.95 },
  key: { color: "#ffffff", intensity: 0.7, pos: [18, 30, 14] },
};
