// Damped pointer. Exposes normalized device coordinates (for camera parallax)
// and a world-space point on the sculpture's mid-plane (for the particle
// attractor). Strength eases in while the cursor moves and decays after ~2.5s
// of stillness, so touch/scroll-only visitors are never penalised.
import * as THREE from "three";

import { damp } from "../utils/maths.js";

const PLANE_Y = 4;

export class Pointer {
  constructor() {
    this.ndc = { x: 0, y: 0 };
    this._raw = { x: 0, y: 0 };
    this.world = new THREE.Vector3(0, PLANE_Y, 0);
    this.strength = 0;
    this._lastMove = -10;
    this._dir = new THREE.Vector3();

    window.addEventListener(
      "pointermove",
      (event) => {
        this._raw.x = (event.clientX / window.innerWidth) * 2 - 1;
        this._raw.y = (event.clientY / window.innerHeight) * 2 - 1;
        this._lastMove = performance.now() / 1000;
      },
      { passive: true }
    );
  }

  update(dt, time, camera) {
    this.ndc.x = damp(this.ndc.x, this._raw.x, 6, dt);
    this.ndc.y = damp(this.ndc.y, this._raw.y, 6, dt);

    const active = time - this._lastMove < 2.5 ? 1 : 0;
    this.strength = damp(this.strength, active, 3, dt);

    // Unproject through the mid-plane the sculpture lives on.
    this._dir.set(this.ndc.x, -this.ndc.y, 0.5).unproject(camera).sub(camera.position).normalize();
    const t = (PLANE_Y - camera.position.y) / (this._dir.y || 1e-6);
    if (t > 0 && t < 200) {
      this.world.copy(camera.position).addScaledVector(this._dir, t);
      const r = Math.hypot(this.world.x, this.world.z);
      if (r > 40) {
        this.world.x *= 40 / r;
        this.world.z *= 40 / r;
      }
    }
  }
}
