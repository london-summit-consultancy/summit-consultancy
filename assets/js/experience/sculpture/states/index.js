// Assembles the seven chapter states into the buffers the sculpture consumes:
// particle targets, line networks, instance targets and resolved environments.
import * as THREE from "three";

import { mulberry32 } from "../../utils/maths.js";
import { buildInstanceStates } from "./composition.js";
import * as spark from "./spark.js";
import * as discovery from "./discovery.js";
import * as thinking from "./thinking.js";
import * as refinement from "./refinement.js";
import * as visualization from "./visualization.js";
import * as human from "./human.js";
import * as impact from "./impact.js";

const MODULES = [spark, discovery, thinking, refinement, visualization, human, impact];

function resolveEnv(e) {
  return {
    background: new THREE.Color(e.background),
    fogColor: new THREE.Color(e.fogColor),
    fogDensity: e.fogDensity,
    bloom: e.bloom,
    exposure: e.exposure,
    particle: {
      colorA: new THREE.Color(e.particle.colorA),
      colorB: new THREE.Color(e.particle.colorB),
      glowMix: e.particle.glowMix,
      size: e.particle.size,
      opacity: e.particle.opacity,
    },
    line: { color: new THREE.Color(e.line.color), opacity: e.line.opacity },
    mass: {
      color: new THREE.Color(e.mass.color),
      roughness: e.mass.roughness,
      metalness: e.mass.metalness,
      rim: e.mass.rim,
      noiseAmp: e.mass.noiseAmp,
      envInt: e.mass.envInt,
    },
    glassOpacity: e.glassOpacity,
    glassEnvInt: e.glassEnvInt,
    windowGlobal: e.windowGlobal,
    water: e.water,
    ground: {
      color: new THREE.Color(e.ground.color),
      edge: new THREE.Color(e.ground.edge),
      grid: new THREE.Color(e.ground.grid),
      gridInt: e.ground.gridInt,
      reveal: e.ground.reveal,
      opacity: e.ground.opacity,
    },
    hemi: {
      sky: new THREE.Color(e.hemi.sky),
      ground: new THREE.Color(e.hemi.ground),
      intensity: e.hemi.intensity,
    },
    key: {
      color: new THREE.Color(e.key.color),
      intensity: e.key.intensity,
      pos: new THREE.Vector3(e.key.pos[0], e.key.pos[1], e.key.pos[2]),
    },
  };
}

export const STATE_COUNT = MODULES.length;

export function buildStates(particleCount) {
  const particleTargets = [];
  const lineStates = [];
  const envs = [];
  MODULES.forEach((mod, idx) => {
    const target = new Float32Array(particleCount * 3);
    mod.fillParticles(target, particleCount, mulberry32(1000 + idx * 17));
    particleTargets.push(target);
    lineStates.push(mod.lines(mulberry32(2000 + idx * 17)));
    envs.push(resolveEnv(mod.env));
  });
  return { particleTargets, lineStates, envs, instances: buildInstanceStates() };
}
