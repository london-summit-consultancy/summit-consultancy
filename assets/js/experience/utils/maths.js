// Shared math helpers for the experience engine. Everything here is
// allocation-free so it can be called safely inside the rAF loop.

export function clamp01(v) {
  return v < 0 ? 0 : v > 1 ? 1 : v;
}

export function lerp(a, b, t) {
  return a + (b - a) * t;
}

// Map v from [a, b] into [c, d], clamped.
export function remap(v, a, b, c, d) {
  return c + (d - c) * clamp01((v - a) / (b - a));
}

export function smoothstep(edge0, edge1, v) {
  const t = clamp01((v - edge0) / (edge1 - edge0));
  return t * t * (3 - 2 * t);
}

// Frame-rate independent exponential approach (critically damped feel).
export function damp(current, target, lambda, dt) {
  return lerp(current, target, 1 - Math.exp(-lambda * dt));
}

// Deterministic PRNG — every procedural generator is seeded so the sculpture
// is identical on every visit (a designed object, not random noise).
export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Cheap smooth pseudo-noise (sum of sines) — enough for drift and sway.
export function snoise(x, y, z) {
  return (
    Math.sin(x * 1.7 + y * 0.8) * 0.5 +
    Math.sin(y * 1.3 + z * 1.1) * 0.3 +
    Math.sin(z * 2.1 + x * 0.6) * 0.2
  );
}

export const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
