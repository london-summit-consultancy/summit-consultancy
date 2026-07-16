// Chapter 5 — Materials. An intimate macro study in gallery daylight: raking
// light reveals the micro-texture of exposed aggregate concrete, the clarity
// of structural glass, the machined grain of titanium. First context
// buildings rise at the edges; particles thin into daylight dust.
import { towerEdgePoint } from "./refinement.js";
import { circle, line, rect } from "./curves.js";

export function fillParticles(out, n, rng) {
  for (let i = 0; i < n; i++) {
    const o = i * 3;
    if (i / n < 0.55) {
      // Atmospheric dome — dust catching the raking daylight.
      const a = rng() * Math.PI * 2;
      const r = 18 + rng() * 30;
      out[o] = Math.cos(a) * r;
      out[o + 1] = 0.5 + Math.pow(rng(), 1.6) * 30;
      out[o + 2] = Math.sin(a) * r;
    } else {
      towerEdgePoint(rng, out, o);
    }
  }
}

export function lines() {
  return [
    circle(0, 0, 58, 0.05, 96),
    rect(16.4, 12.4, 0.06),
    line([-58, 0.05, 0], [58, 0.05, 0], 24),
    line([0, 0.05, -58], [0, 0.05, 58], 24),
  ];
}

export const env = {
  background: "#f7f7f6",
  fogColor: "#f7f7f6",
  fogDensity: 0.0018,
  bloom: 0.85,
  exposure: 1.0,
  particle: { colorA: "#9aa3ae", colorB: "#f7c477", glowMix: 0.2, size: 1.05, opacity: 0.35 },
  line: { color: "#b8b8c0", opacity: 0.25 },
  mass: { color: "#d9d9d8", roughness: 0.5, metalness: 0.1, rim: 0.18, noiseAmp: 0.34, envInt: 1.05 },
  glassOpacity: 0.28,
  glassEnvInt: 2.2,
  windowGlobal: 0,
  water: 0,
  ground: { color: "#f5f6f5", edge: "#e7e8e8", grid: "#c4c8cd", gridInt: 0.2, reveal: 80, opacity: 1 },
  hemi: { sky: "#ffffff", ground: "#dedfe0", intensity: 0.95 },
  key: { color: "#fff1dc", intensity: 1.6, pos: [34, 18, -12] },
};
