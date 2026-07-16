// One continuous camera shot. Two CatmullRom splines (position + look target)
// keyed two-per-chapter, so p maps directly onto key indices; a whisper of
// noise drift and damped cursor parallax keep the shot alive without ever
// cutting.
import * as THREE from "three";

import { snoise } from "../utils/maths.js";

const POSITION_KEYS = [
  [0, 6, 46],
  [2, 5, 34],
  [6, 8, 26], // ch1 → ch2
  [4, 22, 14],
  [-10, 18, 16], // ch2 → ch3
  [-16, 8, 20],
  [-20, 16, 14], // ch3 → ch4
  [-8, 14, 10],
  [2, 16, 8], // ch4 → ch5 (diagonal glide into the facade)
  [8, 9, 11], // ch5: vertical reveal — descending macro material study
  [20, 9, 27], // ch5 → ch6
  [15, 5, 21],
  [10, 2.5, 18], // ch6 → ch7 (orbital drift at the junction)
  [4, 20, 46],
  [-2, 26, 72], // controlled withdrawal — the monument revealed, then stillness
].map(([x, y, z]) => new THREE.Vector3(x, y, z));

const TARGET_KEYS = [
  [0, 4, 0],
  [0, 4, 0],
  [0, 4.5, 0],
  [0, 3, 0],
  [0, 4, 0],
  [0, 7, 0],
  [0, 9, 0],
  [0, 11, 0],
  [0, 12, 0],
  [0, 12, 0],
  [0, 13, 0],
  [0, 10, 2],
  [2, 16, 0],
  [0, 12, 0],
  [0, 11, 0],
].map(([x, y, z]) => new THREE.Vector3(x, y, z));

export class CameraRig {
  constructor(camera) {
    this.camera = camera;
    this.posCurve = new THREE.CatmullRomCurve3(POSITION_KEYS, false, "catmullrom", 0.5);
    this.targetCurve = new THREE.CatmullRomCurve3(TARGET_KEYS, false, "catmullrom", 0.5);
    this._pos = new THREE.Vector3();
    this._tgt = new THREE.Vector3();
  }

  // p: damped journey progress; parallax: damped pointer NDC {x, y}.
  update(p, time, parallax) {
    this.posCurve.getPoint(p, this._pos);
    this.targetCurve.getPoint(p, this._tgt);

    this._pos.x += snoise(time * 0.12, 1.7, 7.1) * 0.35;
    this._pos.y += snoise(time * 0.09, 4.2, 2.3) * 0.22;

    this._tgt.x += parallax.x * 1.6;
    this._tgt.y -= parallax.y * 1.0;

    this.camera.position.copy(this._pos);
    this.camera.lookAt(this._tgt);
  }
}
