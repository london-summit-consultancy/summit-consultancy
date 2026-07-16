// Device tier detection. Ambient mode always runs one tier below the detected
// level — it decorates a page rather than being the page.

const TIERS = [
  { name: "low", dprCap: 1, composer: false, fxaa: false, particles: 4000 },
  { name: "medium", dprCap: 1.25, composer: true, fxaa: false, particles: 7000 },
  { name: "high", dprCap: 1.75, composer: true, fxaa: true, particles: 12000 },
];

export function detectTier(mode) {
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  const small = window.innerWidth < 820;
  const cores = navigator.hardwareConcurrency || 4;
  const memory = navigator.deviceMemory || 8;

  let level = 2;
  if (coarse || small) level = 0;
  else if (cores <= 4 || memory <= 4) level = 1;
  if (mode === "ambient") level = Math.max(0, level - 1);

  return TIERS[level];
}

export function webgl2Available() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(window.WebGL2RenderingContext && canvas.getContext("webgl2"));
  } catch {
    return false;
  }
}
