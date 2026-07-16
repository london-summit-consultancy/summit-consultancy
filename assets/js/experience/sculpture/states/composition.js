// The canonical architectural composition — one tower, one district, one
// plaza — shared by every chapter state. Slot ordering is fixed across all
// states so the same instance carries its element through the whole journey:
// the exploded massing study in chapter 3 IS the tower of chapters 4-7, the
// context slabs of chapter 5 grow into the full district of chapter 7.
// Everything is deterministic (seeded PRNG): a designed object, not noise.
import { mulberry32 } from "../../utils/maths.js";

export const FLOORS = 14;
export const FLOOR_H = 1.9;
export const PODIUM_H = 2.6;
export const TOWER_TOP = PODIUM_H + FLOORS * FLOOR_H;

// Mass slot layout (capacity 240).
export const MASS_CAPACITY = 240;
const SLOT_TOWER = 0; // 17 slots: podium, core, 14 slabs, crown
const SLOT_STUDY = 17; // 6 study planes (chapter 3)
const SLOT_BOARD = 23; // 3 drawing boards (chapter 2)
const SLOT_DISTRICT = 26;

export const GLASS_CAPACITY = 220;
export const WINDOW_CAPACITY = 640;
export const TREE_CAPACITY = 120;

export function rotY(x, z, ry) {
  const c = Math.cos(ry);
  const s = Math.sin(ry);
  return [c * x + s * z, -s * x + c * z];
}

export function floorSpec(k) {
  const w = 9 - (k >= 6 ? 1.2 : 0) - (k >= 10 ? 1.4 : 0);
  return { w, d: w * 0.82, ry: k * 0.035, y0: PODIUM_H + k * FLOOR_H };
}

function parked(def) {
  return { p: def.p, s: [0, 0, 0], ry: def.ry, i: 0 };
}

function parkedAll(defs) {
  return defs.map(parked);
}

// --- Tower (resolved form, chapters 4-7) ------------------------------------
function buildTowerMasses() {
  const list = [];
  list.push({ p: [0, PODIUM_H / 2, 0], s: [16, PODIUM_H, 12], ry: 0 });
  list.push({ p: [0, PODIUM_H + (FLOORS * FLOOR_H) / 2, 0], s: [2.6, FLOORS * FLOOR_H, 2.6], ry: 0 });
  for (let k = 0; k < FLOORS; k++) {
    const f = floorSpec(k);
    list.push({ p: [0, f.y0 + FLOOR_H - 0.18, 0], s: [f.w + 0.5, 0.36, f.d + 0.5], ry: f.ry });
  }
  list.push({ p: [0, TOWER_TOP + 0.8, 0], s: [3.6, 1.6, 3.2], ry: FLOORS * 0.035 });
  return list;
}

// --- Tower as exploded massing study (chapter 3) -----------------------------
function buildExplodedMasses() {
  const rng = mulberry32(30303);
  const list = [];
  list.push({ p: [0, 0.5, 0], s: [20, 1, 16], ry: 0 }); // podium -> base plate
  list.push({ p: [0, 6, 0], s: [2.6, 12, 2.6], ry: 0 }); // core -> study core
  for (let k = 0; k < FLOORS; k++) {
    const f = floorSpec(k);
    list.push({
      p: [Math.sin(k * 2.1) * 5.5, 2.2 + k * 2.2, Math.cos(k * 1.6) * 4.5],
      s: [f.w * 0.72, 1.5, f.d * 0.72],
      ry: f.ry + (rng() - 0.5) * 0.9,
    });
  }
  list.push({ p: [0, 2.2 + FLOORS * 2.2 + 1.6, 0], s: [3, 3, 3], ry: 0.6 }); // crown
  return list;
}

// --- Study planes (chapter 3) -------------------------------------------------
function buildStudyPlanes() {
  return [
    { p: [0, 11, 0], s: [0.08, 22, 16], ry: 0 },
    { p: [0, 11, 0], s: [0.08, 22, 16], ry: Math.PI / 3 },
    { p: [0, 11, 0], s: [0.08, 22, 16], ry: -Math.PI / 3 },
    { p: [0, 6, 0], s: [19, 0.08, 15], ry: 0.12 },
    { p: [0, 13, 0], s: [17, 0.08, 13], ry: -0.1 },
    { p: [0, 20, 0], s: [15, 0.08, 11], ry: 0.08 },
  ];
}

// --- Drawing boards (chapter 2) ------------------------------------------------
function buildBoards() {
  return [
    { p: [0, 3.55, 0], s: [22, 0.1, 16], ry: 0 },
    { p: [-12.5, 6.5, -5], s: [0.08, 7.5, 9], ry: 0.45 },
    { p: [11.5, 6, -8], s: [0.08, 6.5, 9], ry: -0.5 },
  ];
}

// --- District (chapter 7, subsets earlier as context) ---------------------------
function buildDistrict() {
  const rng = mulberry32(70701);
  const raw = [];
  for (let gx = -5; gx <= 5; gx++) {
    for (let gz = -5; gz <= 5; gz++) {
      const x = gx * 11.5 + (rng() - 0.5) * 2;
      const z = gz * 11.5 + (rng() - 0.5) * 2;
      if (Math.abs(x) < 15 && Math.abs(z) < 13) continue; // tower zone
      if (Math.hypot(x, z - 48) < 27) continue; // lake
      const h = 2.2 + rng() * 8.5;
      raw.push({
        p: [x, h / 2, z],
        s: [5.5 + rng() * 2.5, h, 5.5 + rng() * 2.5],
        ry: (rng() - 0.5) * 0.14,
        dist: Math.hypot(x, z),
      });
    }
  }
  raw.sort((a, b) => a.dist - b.dist);
  const max = MASS_CAPACITY - SLOT_DISTRICT;
  return raw.slice(0, max).map(({ p, s, ry }) => ({ p, s, ry }));
}

export const DISTRICT = buildDistrict();
export const EXPLODED = buildExplodedMasses();
export const TOWER = buildTowerMasses();
const STUDY = buildStudyPlanes();
const BOARDS = buildBoards();

// First n district blocks at reduced height (background context), rest parked.
function districtContext(n, hScale) {
  return DISTRICT.map((d, i) => {
    if (i >= n) return parked(d);
    const h = d.s[1] * hScale;
    return { p: [d.p[0], h / 2, d.p[2]], s: [d.s[0], h, d.s[2]], ry: d.ry };
  });
}

// --- Glass (tower facade panels, slots 0..55) -----------------------------------
function buildTowerGlass() {
  const list = [];
  const h = FLOOR_H - 0.42;
  for (let k = 0; k < FLOORS; k++) {
    const f = floorSpec(k);
    const yc = f.y0 + FLOOR_H / 2 - 0.1;
    const faces = [
      { lx: 0, lz: f.d / 2 - 0.05, w: f.w - 0.4, a: 0 },
      { lx: 0, lz: -(f.d / 2 - 0.05), w: f.w - 0.4, a: Math.PI },
      { lx: f.w / 2 - 0.05, lz: 0, w: f.d - 0.4, a: Math.PI / 2 },
      { lx: -(f.w / 2 - 0.05), lz: 0, w: f.d - 0.4, a: -Math.PI / 2 },
    ];
    for (const face of faces) {
      const [x, z] = rotY(face.lx, face.lz, f.ry);
      list.push({ p: [x, yc, z], s: [face.w, h, 1], ry: f.ry + face.a });
    }
  }
  return list;
}

export const TOWER_GLASS = buildTowerGlass();

// --- Windows ----------------------------------------------------------------------
// Tower windows ordered floor-by-floor bottom-up so index-staggered blends read
// as a warm cascade climbing the building.
function buildTowerWindows() {
  const list = [];
  for (let k = 0; k < FLOORS; k++) {
    const f = floorSpec(k);
    const yc = f.y0 + FLOOR_H / 2 - 0.1;
    const faces = [
      { axis: "x", lz: f.d / 2 + 0.06, span: f.w, a: 0 },
      { axis: "x", lz: -(f.d / 2 + 0.06), span: f.w, a: Math.PI },
      { axis: "z", lx: f.w / 2 + 0.06, span: f.d, a: Math.PI / 2 },
      { axis: "z", lx: -(f.w / 2 + 0.06), span: f.d, a: -Math.PI / 2 },
    ];
    for (const face of faces) {
      for (let j = -1; j <= 1; j++) {
        const off = j * (face.span / 3.2);
        const lx = face.axis === "x" ? off : face.lx;
        const lz = face.axis === "x" ? face.lz : off;
        const [x, z] = rotY(lx, lz, f.ry);
        list.push({ p: [x, yc, z], s: [face.span / 5.5, 1.0, 1], ry: f.ry + face.a });
      }
    }
  }
  return list;
}

// Four window quads per district block, on the +/-z facades.
function buildDistrictWindows(blockCount) {
  const rng = mulberry32(60606);
  const list = [];
  for (let b = 0; b < Math.min(blockCount, DISTRICT.length); b++) {
    const d = DISTRICT[b];
    for (let j = 0; j < 4; j++) {
      const side = j % 2 === 0 ? 1 : -1;
      const lx = (rng() - 0.5) * d.s[0] * 0.6;
      const y = 0.8 + rng() * Math.max(0.4, d.s[1] - 1.6);
      const [x, z] = rotY(lx, side * (d.s[2] / 2 + 0.05), d.ry);
      list.push({
        p: [d.p[0] + x, y, d.p[2] + z],
        s: [0.9, 0.7, 1],
        ry: d.ry + (side > 0 ? 0 : Math.PI),
      });
    }
  }
  return list;
}

const TOWER_WINDOWS = buildTowerWindows(); // 168
const DISTRICT_WINDOWS = buildDistrictWindows(60); // 240

// Apply per-window intensity; zero-intensity windows park at zero scale so
// unlit quads never render as dark rectangles.
function withIntensity(defs, fn) {
  return defs.map((d, idx) => {
    const i = fn(idx);
    if (i <= 0.01) return { p: d.p, s: [0, 0, 0], ry: d.ry, i: 0 };
    return { p: d.p, s: d.s, ry: d.ry, i };
  });
}

// --- Trees -----------------------------------------------------------------------
function buildTrees() {
  const rng = mulberry32(50505);
  const list = [];
  for (let i = 0; i < 16; i++) {
    // Plaza ring around the podium.
    const a = (i / 16) * Math.PI * 2;
    list.push({
      p: [Math.cos(a) * 12.5, 0, Math.sin(a) * 12.5],
      s: [1.5 + rng() * 0.5, 2.1 + rng() * 0.7, 1.5 + rng() * 0.5],
      ry: rng() * Math.PI * 2,
    });
  }
  // Avenues along the district roads.
  for (const z of [16.5, -16.5]) {
    for (let x = -52; x <= 52; x += 5.5) {
      if (list.length >= TREE_CAPACITY) break;
      list.push({
        p: [x + (rng() - 0.5), 0, z + (rng() - 0.5)],
        s: [1.3 + rng() * 0.5, 1.9 + rng() * 0.7, 1.3 + rng() * 0.5],
        ry: rng() * Math.PI * 2,
      });
    }
  }
  for (const x of [18.5, -18.5]) {
    for (let z = -52; z <= 52; z += 5.5) {
      if (list.length >= TREE_CAPACITY) break;
      if (Math.hypot(x, z - 48) < 26) continue; // lake
      list.push({
        p: [x + (rng() - 0.5), 0, z + (rng() - 0.5)],
        s: [1.3 + rng() * 0.5, 1.9 + rng() * 0.7, 1.3 + rng() * 0.5],
        ry: rng() * Math.PI * 2,
      });
    }
  }
  return list.slice(0, TREE_CAPACITY);
}

const TREES = buildTrees();

function treesVisible(count, scale) {
  return TREES.map((t, i) => {
    if (i >= count) return parked(t);
    return { p: t.p, s: [t.s[0] * scale, t.s[1] * scale, t.s[2] * scale], ry: t.ry };
  });
}

// --- Per-state assembly -------------------------------------------------------------
function massState({ tower, study, board, district }) {
  return [
    ...(tower || parkedAll(TOWER)),
    ...(study || parkedAll(STUDY)),
    ...(board || parkedAll(BOARDS)),
    ...(district || parkedAll(DISTRICT)),
  ];
}

export function buildInstanceStates() {
  const parkTowerGlass = parkedAll(TOWER_GLASS);
  const parkTowerWin = withIntensity(TOWER_WINDOWS, () => 0);
  const parkDistrictWin = withIntensity(DISTRICT_WINDOWS, () => 0);
  const vizRng = mulberry32(40404);
  const vizIntensity = TOWER_WINDOWS.map(() => (vizRng() < 0.25 ? 0.5 + vizRng() * 0.5 : 0));
  const humanRng = mulberry32(40405);
  const humanIntensity = TOWER_WINDOWS.map(() => 0.75 + humanRng() * 0.25);
  const impactRng = mulberry32(40406);
  const impactDistrict = DISTRICT_WINDOWS.map(() => 0.35 + impactRng() * 0.4);

  return {
    masses: [
      massState({}), // 1 spark: everything parked
      massState({ board: BOARDS }), // 2 discovery
      massState({ tower: EXPLODED, study: STUDY }), // 3 thinking
      massState({ tower: TOWER }), // 4 refinement
      massState({ tower: TOWER, district: districtContext(8, 0.55) }), // 5 visualization
      massState({ tower: TOWER, district: districtContext(12, 0.7) }), // 6 human
      massState({ tower: TOWER, district: DISTRICT }), // 7 impact
    ],
    glass: [
      parkTowerGlass,
      parkTowerGlass,
      parkTowerGlass,
      TOWER_GLASS,
      TOWER_GLASS,
      TOWER_GLASS,
      TOWER_GLASS,
    ],
    windows: [
      [...parkTowerWin, ...parkDistrictWin],
      [...parkTowerWin, ...parkDistrictWin],
      [...parkTowerWin, ...parkDistrictWin],
      [...parkTowerWin, ...parkDistrictWin],
      [...withIntensity(TOWER_WINDOWS, (i) => vizIntensity[i]), ...parkDistrictWin],
      [...withIntensity(TOWER_WINDOWS, (i) => humanIntensity[i]), ...withIntensity(DISTRICT_WINDOWS, (i) => (i < 48 ? 0.4 : 0))],
      [...withIntensity(TOWER_WINDOWS, () => 0.5), ...withIntensity(DISTRICT_WINDOWS, (i) => impactDistrict[i])],
    ],
    trees: [
      treesVisible(0, 1),
      treesVisible(0, 1),
      treesVisible(0, 1),
      treesVisible(0, 1),
      treesVisible(8, 0.8),
      treesVisible(16, 1),
      treesVisible(TREE_CAPACITY, 1),
    ],
  };
}

// --- Particle samplers ------------------------------------------------------------
// Write a random point on a box surface (def transform applied) into out[o..o+2].
export function boxSurfacePoint(def, rng, out, o) {
  const face = Math.floor(rng() * 6);
  let lx = (rng() - 0.5) * def.s[0];
  let ly = (rng() - 0.5) * def.s[1];
  let lz = (rng() - 0.5) * def.s[2];
  if (face === 0) lx = def.s[0] / 2;
  else if (face === 1) lx = -def.s[0] / 2;
  else if (face === 2) lz = def.s[2] / 2;
  else if (face === 3) lz = -def.s[2] / 2;
  else if (face === 4) ly = def.s[1] / 2;
  else ly = -def.s[1] / 2;
  const [x, z] = rotY(lx, lz, def.ry);
  out[o] = def.p[0] + x;
  out[o + 1] = def.p[1] + ly;
  out[o + 2] = def.p[2] + z;
}

// Random point along the perimeter of a rotated rect (w×d at height y).
export function rectPerimeterPoint(w, d, y, ry, rng, out, o) {
  const t = rng() * (2 * w + 2 * d);
  let lx;
  let lz;
  if (t < w) {
    lx = t - w / 2;
    lz = d / 2;
  } else if (t < w + d) {
    lx = w / 2;
    lz = t - w - d / 2;
  } else if (t < 2 * w + d) {
    lx = t - w - d - w / 2;
    lz = -d / 2;
  } else {
    lx = -w / 2;
    lz = t - 2 * w - d - d / 2;
  }
  const [x, z] = rotY(lx, lz, ry);
  out[o] = x;
  out[o + 1] = y;
  out[o + 2] = z;
}

// The 8 corners of a box def, world space.
export function boxCorners(def) {
  const corners = [];
  for (const sx of [-0.5, 0.5]) {
    for (const sy of [-0.5, 0.5]) {
      for (const sz of [-0.5, 0.5]) {
        const [x, z] = rotY(sx * def.s[0], sz * def.s[2], def.ry);
        corners.push([def.p[0] + x, def.p[1] + sy * def.s[1], def.p[2] + z]);
      }
    }
  }
  return corners;
}
