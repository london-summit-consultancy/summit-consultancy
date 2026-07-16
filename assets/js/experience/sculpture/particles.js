// The particle body of the sculpture. One persistent THREE.Points whose
// positions spring toward per-state target buffers — nothing is ever
// recreated, the same particles carry the idea from spark to legacy.
import * as THREE from "three";

import { makeParticleMaterial } from "../materials/materials.js";
import { clamp01, lerp } from "../utils/maths.js";

const STAGGER = 0.38; // per-particle offset so morphs sweep, not snap
const LAMBDA_MIN = 1.6;
const LAMBDA_SPAN = 2.6;

export class Particles {
  // targets: Float32Array[stateCount], each count*3, built by the states.
  constructor(count, targets) {
    this.count = count;
    this.targets = targets;

    this.positions = new Float32Array(targets[0]); // start at state 0
    this.rand = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      // Deterministic per-particle randoms derived from index.
      this.rand[i] = ((i * 2654435761) >>> 8) / 16777216;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(this.positions, 3));
    geometry.setAttribute("aRand", new THREE.BufferAttribute(this.rand, 1));

    this.material = makeParticleMaterial();
    this.points = new THREE.Points(geometry, this.material);
    this.points.frustumCulled = false;
  }

  // blend: { a, b, t } — state indices and morph progress between them.
  update(dt, time, blend) {
    const pos = this.positions;
    const ta = this.targets[blend.a];
    const tb = this.targets[blend.b];
    const rand = this.rand;
    const k = 1 - Math.exp(-(LAMBDA_MIN + LAMBDA_SPAN * 0.5) * dt);
    for (let i = 0; i < this.count; i++) {
      const r = rand[i];
      // Staggered morph progress: early particles lead, late ones follow.
      const t = clamp01((blend.t * (1 + STAGGER) - r * STAGGER) / 1.0);
      const s = t * t * (3 - 2 * t);
      const j = i * 3;
      const ki = k * (0.6 + 0.8 * r);
      pos[j] += (lerp(ta[j], tb[j], s) - pos[j]) * ki;
      pos[j + 1] += (lerp(ta[j + 1], tb[j + 1], s) - pos[j + 1]) * ki;
      pos[j + 2] += (lerp(ta[j + 2], tb[j + 2], s) - pos[j + 2]) * ki;
    }
    this.points.geometry.attributes.position.needsUpdate = true;
    this.material.uniforms.uTime.value = time;
  }

  setPointer(worldPoint, strength) {
    if (worldPoint) this.material.uniforms.uPointer.value.copy(worldPoint);
    this.material.uniforms.uPointerStrength.value = strength;
  }

  // env: { colorA, colorB, glowMix, size, opacity } — lerped by the sculpture.
  applyEnv(colorA, colorB, glowMix, size, opacity) {
    this.material.uniforms.uColorA.value.copy(colorA);
    this.material.uniforms.uColorB.value.copy(colorB);
    this.material.uniforms.uGlowMix.value = glowMix;
    this.material.uniforms.uSize.value = size;
    this.material.uniforms.uOpacity.value = opacity;
  }

  setPixelRatio(pr) {
    this.material.uniforms.uPixelRatio.value = pr;
  }
}
