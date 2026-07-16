// Ambient mode — every non-home page. The same sculpture, resting in one of
// its resolved states inside the page hero: transparent canvas, slow orbital
// drift, breathing particles, cursor attraction. No scroll scrubbing, no
// composer — it decorates the page, it never competes with it.
import * as THREE from "three";

import { Sculpture } from "../sculpture/sculpture.js";
import { Pointer } from "../core/pointer.js";
import { Pipeline } from "../core/renderer.js";

// data-variant → resting chapter state. All states now live in the same
// white-gallery daylight; the legacy variant names are kept because templates
// reference them via data-variant.
const VARIANTS = {
  studio: 2, // massing study with reinforcement cage (about)
  craft: 3, // resolved envelope in pale concrete (services)
  dusk: 4, // daylight material macro — concrete/glass/titanium (portfolio)
  night: 5, // detail junction study in soft daylight (detail pages)
  calm: 6, // converged district under gallery light (contact)
};

export class Ambient {
  constructor(root, tier) {
    this.canvasHost = root.querySelector("[data-experience-canvas]") || root;
    const state = VARIANTS[root.dataset.variant] ?? 3;

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(40, 1, 0.1, 400);

    const ambientTier = { ...tier, composer: false, particles: Math.min(tier.particles, 3800) };
    this.pipeline = new Pipeline(this.canvasHost, this.scene, this.camera, ambientTier, {
      alpha: true,
    });
    this.sculpture = new Sculpture(
      this.scene,
      { particles: ambientTier.particles },
      { ground: false }
    );
    this.sculpture.setPixelRatio(this.pipeline.dpr);
    // Transparent over the page — no background, no fog.
    this.scene.background = null;

    this.blend = { a: state, b: state, t: 1 };
    this.pointer = new Pointer();
    this._baseAngle = state * 1.3;
  }

  update(dt, time) {
    this.pointer.update(dt, time, this.camera);
    this.sculpture.setPointer(this.pointer.world, this.pointer.strength * 0.6);
    this.sculpture.update(dt, time, this.blend);
    this.pipeline.setExposure(this.sculpture.env.exposure);

    const angle = this._baseAngle + time * 0.05 + this.pointer.ndc.x * 0.12;
    const radius = 34;
    this.camera.position.set(
      Math.cos(angle) * radius,
      12 - this.pointer.ndc.y * 2,
      Math.sin(angle) * radius
    );
    this.camera.lookAt(0, 10, 0);

    this.pipeline.render();
  }

  resize() {
    this.pipeline.setSize();
  }
}
