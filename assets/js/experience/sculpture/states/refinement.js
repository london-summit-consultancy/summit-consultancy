// Chapter 4 — Refinement. The massing study resolves into the tower and
// receives its envelope: floating slabs stack with a gentle twist, ultra-clear
// structural glazing slides into the concrete frame, particles trace the
// crisp edges of the form. Matte study white gives way to exposed aggregate
// concrete, glass and titanium.
import { FLOORS, FLOOR_H, PODIUM_H, TOWER_TOP, floorSpec, rectPerimeterPoint, rotY } from "./composition.js";
import { line, rect } from "./curves.js";

// Random point on the tower's edge network — shared with later chapters.
export function towerEdgePoint(rng, out, o) {
  const pick = rng();
  if (pick < 0.58) {
    // Slab perimeter, random floor.
    const k = Math.floor(rng() * FLOORS);
    const f = floorSpec(k);
    rectPerimeterPoint(f.w + 0.5, f.d + 0.5, f.y0 + FLOOR_H - 0.18, f.ry, rng, out, o);
  } else if (pick < 0.72) {
    // Twisting corner verticals.
    const t = rng() * FLOORS;
    const k = Math.min(FLOORS - 1, Math.floor(t));
    const f = floorSpec(k);
    const cx = (rng() < 0.5 ? 1 : -1) * (f.w / 2 + 0.25);
    const cz = (rng() < 0.5 ? 1 : -1) * (f.d / 2 + 0.25);
    const [x, z] = rotY(cx, cz, f.ry);
    out[o] = x;
    out[o + 1] = f.y0 + (t - k) * FLOOR_H;
    out[o + 2] = z;
  } else if (pick < 0.84) {
    // Core edges.
    rectPerimeterPoint(2.6, 2.6, PODIUM_H + rng() * FLOORS * FLOOR_H, 0, rng, out, o);
    out[o + 1] = PODIUM_H + rng() * FLOORS * FLOOR_H;
  } else if (pick < 0.94) {
    // Podium perimeter.
    rectPerimeterPoint(16, 12, rng() * PODIUM_H, 0, rng, out, o);
    out[o + 1] = 0.1 + rng() * PODIUM_H;
  } else {
    // Crown halo.
    const a = rng() * Math.PI * 2;
    const r = 2.5 + rng() * 2;
    out[o] = Math.cos(a) * r;
    out[o + 1] = TOWER_TOP + rng() * 2.4;
    out[o + 2] = Math.sin(a) * r;
  }
}

export function fillParticles(out, n, rng) {
  for (let i = 0; i < n; i++) {
    const o = i * 3;
    if (i / n < 0.9) {
      towerEdgePoint(rng, out, o);
    } else {
      // A quiet halo of remaining study dust.
      const a = rng() * Math.PI * 2;
      const r = 11 + rng() * 8;
      out[o] = Math.cos(a) * r;
      out[o + 1] = 1 + rng() * 26;
      out[o + 2] = Math.sin(a) * r;
    }
  }
}

export function lines() {
  const list = [];
  list.push(rect(16.4, 12.4, 0.06));
  for (let k = 0; k < FLOORS; k++) {
    const f = floorSpec(k);
    list.push(rect(f.w + 0.6, f.d + 0.6, f.y0 + FLOOR_H - 0.18, f.ry));
  }
  // Twisting corner splines, floor to floor.
  for (const sx of [1, -1]) {
    for (const sz of [1, -1]) {
      const points = [];
      for (let k = 0; k < FLOORS; k++) {
        const f = floorSpec(k);
        const [x, z] = rotY((sx * (f.w + 0.6)) / 2, (sz * (f.d + 0.6)) / 2, f.ry);
        points.push({ x, y: f.y0 + FLOOR_H - 0.18, z });
      }
      list.push({ points });
    }
  }
  list.push(line([0, TOWER_TOP, 0], [0, TOWER_TOP + 2.4, 0], 4));
  return list;
}

export const env = {
  background: "#f7f8f8",
  fogColor: "#f7f8f8",
  fogDensity: 0.0015,
  bloom: 0.85,
  exposure: 1.0,
  particle: { colorA: "#63707f", colorB: "#f59e0b", glowMix: 0.12, size: 1.2, opacity: 0.5 },
  line: { color: "#a8adb8", opacity: 0.4 },
  mass: { color: "#dfdfdd", roughness: 0.6, metalness: 0.06, rim: 0.12, noiseAmp: 0.3, envInt: 0.9 },
  glassOpacity: 0.24,
  glassEnvInt: 2.0,
  windowGlobal: 0,
  water: 0,
  ground: { color: "#f6f7f7", edge: "#e9eaeb", grid: "#c0c4ca", gridInt: 0.3, reveal: 80, opacity: 1 },
  hemi: { sky: "#ffffff", ground: "#dfe1e2", intensity: 1.0 },
  key: { color: "#fff3e4", intensity: 1.3, pos: [26, 22, 10] },
};
