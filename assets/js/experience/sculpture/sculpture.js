// THE sculpture — the single persistent system that carries the whole journey.
// Owns the particle body, line network, instanced architecture, ground and
// lights; each frame it blends the environment between the two active chapter
// states and dispatches the morph blend to every subsystem. Nothing here is
// ever destroyed or recreated: everything transforms.
import * as THREE from "three";

import {
  makeGlassMaterial,
  makeMassMaterial,
  makeTreeMaterial,
  makeWindowMaterial,
} from "../materials/materials.js";
import { lerp } from "../utils/maths.js";
import { Ground } from "./ground.js";
import { InstancedSet } from "./instances.js";
import { Lines } from "./lines.js";
import { Particles } from "./particles.js";
import { buildStates } from "./states/index.js";
import {
  GLASS_CAPACITY,
  MASS_CAPACITY,
  TREE_CAPACITY,
  WINDOW_CAPACITY,
} from "./states/composition.js";

const LINE_CAPACITY = 6000;

function cloneEnv(e) {
  return {
    background: e.background.clone(),
    fogColor: e.fogColor.clone(),
    fogDensity: e.fogDensity,
    bloom: e.bloom,
    exposure: e.exposure,
    particle: {
      colorA: e.particle.colorA.clone(),
      colorB: e.particle.colorB.clone(),
      glowMix: e.particle.glowMix,
      size: e.particle.size,
      opacity: e.particle.opacity,
    },
    line: { color: e.line.color.clone(), opacity: e.line.opacity },
    mass: { ...e.mass, color: e.mass.color.clone() },
    glassOpacity: e.glassOpacity,
    glassEnvInt: e.glassEnvInt,
    windowGlobal: e.windowGlobal,
    water: e.water,
    ground: {
      color: e.ground.color.clone(),
      edge: e.ground.edge.clone(),
      grid: e.ground.grid.clone(),
      gridInt: e.ground.gridInt,
      reveal: e.ground.reveal,
      opacity: e.ground.opacity,
    },
    hemi: { sky: e.hemi.sky.clone(), ground: e.hemi.ground.clone(), intensity: e.hemi.intensity },
    key: { color: e.key.color.clone(), intensity: e.key.intensity, pos: e.key.pos.clone() },
  };
}

function envLerp(a, b, t, out) {
  out.background.lerpColors(a.background, b.background, t);
  out.fogColor.lerpColors(a.fogColor, b.fogColor, t);
  out.fogDensity = lerp(a.fogDensity, b.fogDensity, t);
  out.bloom = lerp(a.bloom, b.bloom, t);
  out.exposure = lerp(a.exposure, b.exposure, t);
  out.particle.colorA.lerpColors(a.particle.colorA, b.particle.colorA, t);
  out.particle.colorB.lerpColors(a.particle.colorB, b.particle.colorB, t);
  out.particle.glowMix = lerp(a.particle.glowMix, b.particle.glowMix, t);
  out.particle.size = lerp(a.particle.size, b.particle.size, t);
  out.particle.opacity = lerp(a.particle.opacity, b.particle.opacity, t);
  out.line.color.lerpColors(a.line.color, b.line.color, t);
  out.line.opacity = lerp(a.line.opacity, b.line.opacity, t);
  out.mass.color.lerpColors(a.mass.color, b.mass.color, t);
  out.mass.roughness = lerp(a.mass.roughness, b.mass.roughness, t);
  out.mass.metalness = lerp(a.mass.metalness, b.mass.metalness, t);
  out.mass.rim = lerp(a.mass.rim, b.mass.rim, t);
  out.mass.noiseAmp = lerp(a.mass.noiseAmp, b.mass.noiseAmp, t);
  out.mass.envInt = lerp(a.mass.envInt, b.mass.envInt, t);
  out.glassOpacity = lerp(a.glassOpacity, b.glassOpacity, t);
  out.glassEnvInt = lerp(a.glassEnvInt, b.glassEnvInt, t);
  out.windowGlobal = lerp(a.windowGlobal, b.windowGlobal, t);
  out.water = lerp(a.water, b.water, t);
  out.ground.color.lerpColors(a.ground.color, b.ground.color, t);
  out.ground.edge.lerpColors(a.ground.edge, b.ground.edge, t);
  out.ground.grid.lerpColors(a.ground.grid, b.ground.grid, t);
  out.ground.gridInt = lerp(a.ground.gridInt, b.ground.gridInt, t);
  out.ground.reveal = lerp(a.ground.reveal, b.ground.reveal, t);
  out.ground.opacity = lerp(a.ground.opacity, b.ground.opacity, t);
  out.hemi.sky.lerpColors(a.hemi.sky, b.hemi.sky, t);
  out.hemi.ground.lerpColors(a.hemi.ground, b.hemi.ground, t);
  out.hemi.intensity = lerp(a.hemi.intensity, b.hemi.intensity, t);
  out.key.color.lerpColors(a.key.color, b.key.color, t);
  out.key.intensity = lerp(a.key.intensity, b.key.intensity, t);
  out.key.pos.lerpVectors(a.key.pos, b.key.pos, t);
}

function makeTreeGeometry() {
  const geometry = new THREE.ConeGeometry(0.55, 1, 6);
  geometry.translate(0, 0.5, 0); // origin at the base so trees grow from ground
  return geometry;
}

export class Sculpture {
  constructor(scene, counts, { ground = true } = {}) {
    const data = buildStates(counts.particles);
    this.envs = data.envs;
    this.env = cloneEnv(this.envs[0]);

    this.particles = new Particles(counts.particles, data.particleTargets);
    scene.add(this.particles.points);

    this.lines = new Lines(data.lineStates, LINE_CAPACITY);
    scene.add(this.lines.group);

    this.massMaterial = makeMassMaterial();
    this.masses = new InstancedSet(
      new THREE.BoxGeometry(1, 1, 1),
      this.massMaterial,
      MASS_CAPACITY,
      data.instances.masses
    );
    scene.add(this.masses.mesh);

    this.glassMaterial = makeGlassMaterial();
    this.glass = new InstancedSet(
      new THREE.PlaneGeometry(1, 1),
      this.glassMaterial,
      GLASS_CAPACITY,
      data.instances.glass
    );
    scene.add(this.glass.mesh);

    this.windows = new InstancedSet(
      new THREE.PlaneGeometry(1, 1),
      makeWindowMaterial(),
      WINDOW_CAPACITY,
      data.instances.windows,
      { color: 0xffc07a, staggerByIndex: true }
    );
    scene.add(this.windows.mesh);

    this.trees = new InstancedSet(
      makeTreeGeometry(),
      makeTreeMaterial(),
      TREE_CAPACITY,
      data.instances.trees
    );
    scene.add(this.trees.mesh);

    this.ground = null;
    if (ground) {
      this.ground = new Ground();
      scene.add(this.ground.group);
    }

    this.hemi = new THREE.HemisphereLight(0xffffff, 0xe8e6e0, 0.9);
    scene.add(this.hemi);
    this.key = new THREE.DirectionalLight(0xffffff, 0.7);
    this.key.position.set(18, 30, 14);
    scene.add(this.key);
  }

  setPointer(worldPoint, strength) {
    this.particles.setPointer(worldPoint, strength);
  }

  setPixelRatio(pr) {
    this.particles.setPixelRatio(pr);
  }

  // blend: { a, b, t } from the scroll state (t already eased).
  update(dt, time, blend) {
    const env = this.env;
    envLerp(this.envs[blend.a], this.envs[blend.b], blend.t, env);

    this.particles.update(dt, time, blend);
    this.particles.applyEnv(
      env.particle.colorA,
      env.particle.colorB,
      env.particle.glowMix,
      env.particle.size,
      env.particle.opacity
    );

    this.lines.update(blend);
    this.lines.applyEnv(env.line.color, env.line.opacity);

    this.masses.update(dt, blend);
    this.glass.update(dt, blend);
    this.windows.update(dt, blend, env.windowGlobal);
    this.trees.update(dt, blend);

    const mass = this.massMaterial;
    mass.color.copy(env.mass.color);
    mass.roughness = env.mass.roughness;
    mass.metalness = env.mass.metalness;
    mass.envMapIntensity = env.mass.envInt;
    const shader = mass.userData.shader;
    if (shader) {
      shader.uniforms.uNoiseAmp.value = env.mass.noiseAmp;
      shader.uniforms.uRim.value = env.mass.rim;
    }

    this.glassMaterial.opacity = env.glassOpacity;
    this.glassMaterial.envMapIntensity = env.glassEnvInt;
    this.glass.mesh.visible = env.glassOpacity > 0.01;

    if (this.ground) this.ground.applyEnv(env);

    this.hemi.color.copy(env.hemi.sky);
    this.hemi.groundColor.copy(env.hemi.ground);
    this.key.color.copy(env.key.color);

    // Living light — a seamless ~10s daylight loop: the key light drifts a few
    // degrees around the composition and breathes in intensity, so highlights
    // travel across concrete, glass and titanium while the geometry itself
    // stays monumentally still.
    const sway = Math.sin(time * 0.6283) * 0.12; // 2π/10s, ±~7°
    const c = Math.cos(sway);
    const s = Math.sin(sway);
    const kp = env.key.pos;
    this.key.position.set(kp.x * c + kp.z * s, kp.y, -kp.x * s + kp.z * c);
    this.key.intensity = env.key.intensity * (1 + 0.06 * Math.sin(time * 0.6283 + 1.7));
    this.hemi.intensity = env.hemi.intensity * (1 + 0.03 * Math.sin(time * 0.5236 + 0.6)); // 12s
  }
}
