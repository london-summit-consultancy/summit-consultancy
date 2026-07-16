// Chapter 7 — Impact. The camera withdraws and the idea stands revealed as a
// district in soft gallery daylight: blocks grow across the road grid, a pale
// reflecting pool gathers, avenues fill with trees — and above it all the
// particles converge into a calm aerial ring, the signature of the journey
// coming to rest. The monument is still; only the light keeps moving.
import { DISTRICT, TOWER_TOP, rectPerimeterPoint } from "./composition.js";
import { circle, line } from "./curves.js";

const TALL = [...DISTRICT].sort((a, b) => b.s[1] - a.s[1]).slice(0, 8);

export function fillParticles(out, n, rng) {
  for (let i = 0; i < n; i++) {
    const o = i * 3;
    const u = i / n;
    if (u < 0.55) {
      // Roofline edges across the district.
      const d = DISTRICT[Math.floor(rng() * DISTRICT.length)];
      rectPerimeterPoint(d.s[0], d.s[2], d.s[1], d.ry, rng, out, o);
      out[o] += d.p[0];
      out[o + 2] += d.p[2];
    } else if (u < 0.7) {
      // Columns of light above the landmarks.
      const src = rng() < 0.3 ? { p: [0, 0, 0], s: [0, TOWER_TOP, 0] } : TALL[Math.floor(rng() * TALL.length)];
      out[o] = src.p[0] + (rng() - 0.5) * 1.6;
      out[o + 1] = src.s[1] + rng() * 9;
      out[o + 2] = src.p[2] + (rng() - 0.5) * 1.6;
    } else {
      // The calm signature ring, high above the city.
      const a = rng() * Math.PI * 2;
      const r = 30 + rng() * 4;
      out[o] = Math.cos(a) * r;
      out[o + 1] = 26 + rng() * 4;
      out[o + 2] = Math.sin(a) * r;
    }
  }
}

export function lines() {
  const list = [];
  // The road grid drawing itself outward.
  for (let g = -4; g <= 4; g++) {
    const c = g * 11.5 + 5.75;
    list.push(line([c, 0.05, -58], [c, 0.05, 58], 32));
    list.push(line([-58, 0.05, c], [58, 0.05, c], 32));
  }
  list.push(circle(0, 48, 22.5, 0.08, 64)); // lake edge
  list.push(circle(0, 0, 32, 27.5, 96)); // echo of the signature ring
  return list;
}

export const env = {
  background: "#f8f8f7",
  fogColor: "#f8f8f7",
  fogDensity: 0.0025,
  bloom: 0.85,
  exposure: 1.0,
  particle: { colorA: "#aab3bd", colorB: "#f59e0b", glowMix: 0.18, size: 1.25, opacity: 0.5 },
  line: { color: "#b4b9c2", opacity: 0.35 },
  mass: { color: "#dedddb", roughness: 0.55, metalness: 0.1, rim: 0.15, noiseAmp: 0.28, envInt: 0.95 },
  glassOpacity: 0.24,
  glassEnvInt: 1.8,
  windowGlobal: 0.12,
  water: 0.7,
  ground: { color: "#f6f7f6", edge: "#e8e9e9", grid: "#c6cad0", gridInt: 0.3, reveal: 95, opacity: 1 },
  hemi: { sky: "#ffffff", ground: "#dddfe0", intensity: 0.95 },
  key: { color: "#fff2e0", intensity: 1.25, pos: [-26, 20, 26] },
};
