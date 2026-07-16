// The drawn scaffold of the sculpture: construction guides, floor-plan
// splines, section lines, road grids. Two line layers cross-fade — the
// outgoing state retracts while the incoming one draws itself, so the
// network always appears to be re-sketching, never swapping.
import * as THREE from "three";

import { makeLineMaterial } from "../materials/materials.js";
import { clamp01, remap } from "../utils/maths.js";

const SEGMENTS_PER_CURVE = 48;

// Build a LineSegments geometry from an array of polylines
// [{ points: THREE.Vector3[] }] with an aProgress attribute (0-1 per curve).
function buildGeometry(curves, capacity) {
  const positions = new Float32Array(capacity * 6);
  const progress = new Float32Array(capacity * 2);
  let seg = 0;
  outer: for (const curve of curves) {
    const pts = curve.points;
    for (let i = 0; i < pts.length - 1; i++) {
      if (seg >= capacity) break outer;
      const p = seg * 6;
      positions[p] = pts[i].x;
      positions[p + 1] = pts[i].y;
      positions[p + 2] = pts[i].z;
      positions[p + 3] = pts[i + 1].x;
      positions[p + 4] = pts[i + 1].y;
      positions[p + 5] = pts[i + 1].z;
      const g = seg * 2;
      progress[g] = i / (pts.length - 1);
      progress[g + 1] = (i + 1) / (pts.length - 1);
      seg++;
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("aProgress", new THREE.BufferAttribute(progress, 1));
  geometry.setDrawRange(0, seg * 2);
  return geometry;
}

// Sample a THREE.Curve into a polyline.
export function sampleCurve(curve, divisions = SEGMENTS_PER_CURVE) {
  return { points: curve.getPoints(divisions) };
}

export class Lines {
  // stateCurves: array (per state) of polyline arrays. capacity: max segments.
  constructor(stateCurves, capacity) {
    this.stateCurves = stateCurves;
    this.capacity = capacity;
    this.group = new THREE.Group();

    this.layers = [0, 1].map(() => {
      const material = makeLineMaterial();
      const mesh = new THREE.LineSegments(buildGeometry([], capacity), material);
      mesh.frustumCulled = false;
      this.group.add(mesh);
      return { mesh, material, state: -1 };
    });
    this._setLayerState(0, 0);
    this._setLayerState(1, 1);
  }

  _setLayerState(layerIndex, stateIndex) {
    const layer = this.layers[layerIndex];
    if (layer.state === stateIndex) return;
    layer.state = stateIndex;
    layer.mesh.geometry.dispose();
    layer.mesh.geometry = buildGeometry(this.stateCurves[stateIndex] || [], this.capacity);
  }

  // blend: { a, b, t }. Layer A carries state a (retracting as t rises past
  // 0.45), layer B carries state b (drawing in from t 0.3 → 0.95).
  update(blend) {
    this._setLayerState(0, blend.a);
    this._setLayerState(1, blend.b);
    const retract = 1 - remap(blend.t, 0.45, 0.95, 0, 1);
    const draw = blend.a === blend.b ? retract : remap(blend.t, 0.3, 0.95, 0, 1);
    this.layers[0].material.uniforms.uDraw.value = clamp01(retract);
    this.layers[1].material.uniforms.uDraw.value = blend.a === blend.b ? 0 : clamp01(draw);
  }

  applyEnv(color, opacity) {
    for (const layer of this.layers) {
      layer.material.uniforms.uColor.value.copy(color);
      layer.material.uniforms.uOpacity.value = opacity;
    }
  }
}
