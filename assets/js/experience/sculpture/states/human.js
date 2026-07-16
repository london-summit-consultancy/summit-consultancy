// Chapter 6 — Human Experience. The camera settles at a critical junction:
// cantilever meets glazing meets titanium fixing. Interior life is visible
// through the ultra-clear glass as soft warm motes, the street level softens
// with trees and plaza geometry — precision, inhabited.
import { FLOORS, FLOOR_H, floorSpec, rotY } from "./composition.js";
import { circle, line } from "./curves.js";

export function fillParticles(out, n, rng) {
  for (let i = 0; i < n; i++) {
    const o = i * 3;
    const u = i / n;
    if (u < 0.45) {
      // Interior life — warm motes just inside the facades.
      const k = Math.floor(rng() * FLOORS);
      const f = floorSpec(k);
      const lx = (rng() - 0.5) * f.w * 0.8;
      const lz = (rng() - 0.5) * f.d * 0.8;
      const [x, z] = rotY(lx, lz, f.ry);
      out[o] = x;
      out[o + 1] = f.y0 + 0.3 + rng() * (FLOOR_H - 0.7);
      out[o + 2] = z;
    } else if (u < 0.7) {
      // Street-level drift across the plaza.
      out[o] = (rng() - 0.5) * 26;
      out[o + 1] = 0.3 + rng() * 3;
      out[o + 2] = (rng() - 0.5) * 22;
    } else {
      // Soft ambient air around the junction.
      const a = rng() * Math.PI * 2;
      const r = 10 + rng() * 24;
      out[o] = Math.cos(a) * r;
      out[o + 1] = 1 + rng() * 24;
      out[o + 2] = Math.sin(a) * r;
    }
  }
}

export function lines() {
  const list = [];
  list.push(circle(0, 0, 13, 0.06, 72));
  // Kerb lines along the plaza roads.
  list.push(line([-30, 0.06, 15], [30, 0.06, 15], 24));
  list.push(line([-30, 0.06, -15], [30, 0.06, -15], 24));
  // Crosswalk stripes at the plaza entrance.
  for (let k = 0; k < 6; k++) {
    const x = -2.5 + k;
    list.push(line([x, 0.06, 13.4], [x, 0.06, 14.6], 2));
  }
  return list;
}

export const env = {
  background: "#f6f6f5",
  fogColor: "#f6f6f5",
  fogDensity: 0.002,
  bloom: 0.9,
  exposure: 1.0,
  particle: { colorA: "#c2ab89", colorB: "#ffd9a0", glowMix: 0.3, size: 1.15, opacity: 0.4 },
  line: { color: "#adb1ba", opacity: 0.35 },
  mass: { color: "#dbdbd9", roughness: 0.5, metalness: 0.12, rim: 0.22, noiseAmp: 0.32, envInt: 1.1 },
  glassOpacity: 0.26,
  glassEnvInt: 2.0,
  windowGlobal: 0.22,
  water: 0,
  ground: { color: "#f4f5f4", edge: "#e6e7e7", grid: "#c4c8cd", gridInt: 0.2, reveal: 80, opacity: 1 },
  hemi: { sky: "#ffffff", ground: "#dcdedf", intensity: 0.9 },
  key: { color: "#fff0da", intensity: 1.35, pos: [-20, 24, 16] },
};
