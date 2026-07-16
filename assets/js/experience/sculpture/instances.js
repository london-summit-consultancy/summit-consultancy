// Instanced architectural elements (masses, glass, windows, trees). Every set
// owns per-state target buffers; instances spring toward the blended target
// each frame with a per-instance stagger, so massing studies visibly resolve
// into the final form instead of swapping. Absent elements park at their own
// position with zero scale — they grow in place, never teleport.
import * as THREE from "three";

import { clamp01 } from "../utils/maths.js";

const STRIDE = 8; // px py pz sx sy sz ry intensity
const STAGGER = 0.34; // ≈200-400ms entry delays at architectural durations
const LAMBDA = 4.2; // exponential settle ≈ the 300-600ms position lock

export class InstancedSet {
  // stateDefs: array (per state) of def arrays [{ p:[3], s:[3], ry, i }].
  // opts.color: base instance colour (enables instanceColor intensity, e.g.
  // windows). opts.staggerByIndex: stagger sweeps in build order (window
  // cascades) instead of hashed randomness.
  constructor(geometry, material, capacity, stateDefs, opts = {}) {
    this.capacity = capacity;
    this.useColor = Boolean(opts.color);
    this.staggerByIndex = Boolean(opts.staggerByIndex);

    this.targets = stateDefs.map((defs) => this._pack(defs));
    this.current = new Float32Array(this.targets[0]);

    this.mesh = new THREE.InstancedMesh(geometry, material, capacity);
    this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.mesh.frustumCulled = false;
    if (this.useColor) {
      this.colorBase = new THREE.Color(opts.color);
      const white = new THREE.Color(0, 0, 0);
      for (let i = 0; i < capacity; i++) this.mesh.setColorAt(i, white);
      this.mesh.instanceColor.setUsage(THREE.DynamicDrawUsage);
    }
    this._dummy = new THREE.Object3D();
    this._color = new THREE.Color();
    this._write(1);
  }

  _pack(defs) {
    const arr = new Float32Array(this.capacity * STRIDE);
    const n = Math.min(defs ? defs.length : 0, this.capacity);
    for (let i = 0; i < n; i++) {
      const d = defs[i];
      const o = i * STRIDE;
      arr[o] = d.p[0];
      arr[o + 1] = d.p[1];
      arr[o + 2] = d.p[2];
      arr[o + 3] = d.s[0];
      arr[o + 4] = d.s[1];
      arr[o + 5] = d.s[2];
      arr[o + 6] = d.ry || 0;
      arr[o + 7] = d.i == null ? 1 : d.i;
    }
    return arr;
  }

  // blend: { a, b, t }. windowGlobal scales instance intensity (env-driven).
  update(dt, blend, windowGlobal = 1) {
    const ta = this.targets[blend.a];
    const tb = this.targets[blend.b];
    const cur = this.current;
    const n = this.capacity;
    const k = 1 - Math.exp(-LAMBDA * dt);
    for (let i = 0; i < n; i++) {
      const r = this.staggerByIndex ? i / n : ((i * 2654435761) >>> 8) / 16777216;
      let t = clamp01(blend.t * (1 + STAGGER) - r * STAGGER);
      // Out-cubic per instance: rigid bodies snap toward position then ease
      // into magnetic alignment (the damp below supplies the inertia).
      const inv = 1 - t;
      t = 1 - inv * inv * inv;
      const o = i * STRIDE;
      for (let j = 0; j < STRIDE; j++) {
        const target = ta[o + j] + (tb[o + j] - ta[o + j]) * t;
        cur[o + j] += (target - cur[o + j]) * k;
      }
    }
    this._write(windowGlobal);
  }

  _write(windowGlobal) {
    const cur = this.current;
    const mesh = this.mesh;
    const dummy = this._dummy;
    for (let i = 0; i < this.capacity; i++) {
      const o = i * STRIDE;
      dummy.position.set(cur[o], cur[o + 1], cur[o + 2]);
      // Floor at a hair above zero so instance matrices stay invertible.
      dummy.scale.set(
        Math.max(cur[o + 3], 1e-4),
        Math.max(cur[o + 4], 1e-4),
        Math.max(cur[o + 5], 1e-4)
      );
      dummy.rotation.y = cur[o + 6];
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      if (this.useColor) {
        // >1 values push the emissive quads over the bloom threshold.
        const glow = cur[o + 7] * windowGlobal * 2.4;
        this._color.copy(this.colorBase).multiplyScalar(glow);
        mesh.setColorAt(i, this._color);
      }
    }
    mesh.instanceMatrix.needsUpdate = true;
    if (this.useColor) mesh.instanceColor.needsUpdate = true;
  }
}
