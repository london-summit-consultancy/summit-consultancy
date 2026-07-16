// Scroll → journey progress. Raw progress comes from the track's bounding
// rect; the value the rest of the engine consumes is critically damped
// (τ ≈ 0.12s) so scrubbing is perfectly reversible and never snaps.
import { clamp01, damp } from "../utils/maths.js";

const CHAPTERS = 7;
const DAMP_LAMBDA = 8.3; // 1 / 0.12s

export class ScrollTracker {
  constructor(track) {
    this.track = track;
    this.raw = 0;
    this.p = 0;
    this.chapter = 0;
    this.local = 0;
    this.blend = { a: 0, b: Math.min(1, CHAPTERS - 1), t: 0 };
    this._measure();
    this.p = this.raw; // start settled, no boot lurch
    this._derive();
  }

  _measure() {
    const rect = this.track.getBoundingClientRect();
    const denom = rect.height - window.innerHeight;
    this.raw = denom > 0 ? clamp01(-rect.top / denom) : 0;
  }

  _derive() {
    const scaled = this.p * CHAPTERS;
    this.chapter = Math.min(CHAPTERS - 1, Math.floor(scaled));
    this.local = clamp01(scaled - this.chapter);
    this.blend.a = this.chapter;
    this.blend.b = Math.min(this.chapter + 1, CHAPTERS - 1);
    // Out-expo-flavoured blend window — cubic-bezier(0.16, 1, 0.3, 1) feel:
    // the morph launches decisively then settles softly into alignment.
    const w = clamp01((this.local - 0.32) / 0.6);
    this.blend.t = 1 - Math.pow(1 - w, 3.2);
  }

  update(dt) {
    this._measure();
    this.p = damp(this.p, this.raw, DAMP_LAMBDA, dt);
    if (Math.abs(this.p - this.raw) < 0.0004) this.p = this.raw;
    this._derive();
  }
}
