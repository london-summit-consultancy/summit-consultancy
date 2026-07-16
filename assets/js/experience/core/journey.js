// Journey mode — the homepage. Wires scroll, camera, pointer, overlay and THE
// sculpture into one continuous scroll-scrubbed film. At the very end the
// canvas fades out and hands the page back to conventional content.
import * as THREE from "three";

import { Sculpture } from "../sculpture/sculpture.js";
import { CameraRig } from "./camera.js";
import { Overlay } from "./overlay.js";
import { Pointer } from "./pointer.js";
import { Pipeline } from "./renderer.js";
import { ScrollTracker } from "./scroll.js";
import { remap } from "../utils/maths.js";

export class Journey {
  constructor(root, tier) {
    this.canvasHost = root.querySelector("#experience-canvas");
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(42, 1, 0.1, 400);

    this.pipeline = new Pipeline(this.canvasHost, this.scene, this.camera, tier, {
      alpha: false,
    });
    this.sculpture = new Sculpture(this.scene, { particles: tier.particles });
    this.sculpture.setPixelRatio(this.pipeline.dpr);

    this.scene.background = this.sculpture.env.background;
    this.scene.fog = new THREE.FogExp2(this.sculpture.env.fogColor, 0);

    this.scroll = new ScrollTracker(root.querySelector(".experience-track"));
    this.rig = new CameraRig(this.camera);
    this.pointer = new Pointer();
    this.overlay = new Overlay(root);
    this._fade = 1;
  }

  update(dt, time) {
    this.scroll.update(dt);
    const { p, chapter, local, blend } = this.scroll;

    this.pointer.update(dt, time, this.camera);
    this.sculpture.setPointer(this.pointer.world, this.pointer.strength);
    this.sculpture.update(dt, time, blend);

    const env = this.sculpture.env;
    // background/fogColor are the working env's own Color instances — the
    // sculpture mutates them in place, the scene reads them every render.
    this.scene.fog.color = env.fogColor;
    this.scene.fog.density = env.fogDensity;
    this.pipeline.setBloom(env.bloom);
    this.pipeline.setExposure(env.exposure);

    this.rig.update(p, time, this.pointer.ndc);
    this.overlay.update(chapter, local, p);

    // Hand-off: the film dissolves into the page at the end of the track.
    const fade = 1 - remap(p, 0.965, 0.998, 0, 1);
    if (fade !== this._fade) {
      this._fade = fade;
      this.canvasHost.style.opacity = fade.toFixed(3);
    }
    if (fade <= 0.001 && this.scroll.raw >= 0.999) return; // parked past the end
    this.pipeline.render();
  }

  resize() {
    this.pipeline.setSize();
  }
}
