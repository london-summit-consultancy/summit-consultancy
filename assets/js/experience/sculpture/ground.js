// Ground plane (radial void + engineering grid) and the reflective water
// disc that appears in the Impact chapter.
import * as THREE from "three";

import { makeGroundMaterial, makeWaterMaterial } from "../materials/materials.js";

export class Ground {
  constructor() {
    this.group = new THREE.Group();

    this.material = makeGroundMaterial();
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(320, 320), this.material);
    plane.rotation.x = -Math.PI / 2;
    plane.renderOrder = -2;
    this.group.add(plane);

    this.waterMaterial = makeWaterMaterial();
    this.water = new THREE.Mesh(new THREE.CircleGeometry(22, 48), this.waterMaterial);
    this.water.rotation.x = -Math.PI / 2;
    this.water.position.set(0, 0.06, 48);
    this.water.renderOrder = -1;
    this.group.add(this.water);
  }

  applyEnv(env) {
    const u = this.material.uniforms;
    u.uColor.value.copy(env.ground.color);
    u.uEdgeColor.value.copy(env.ground.edge);
    u.uGridColor.value.copy(env.ground.grid);
    u.uGrid.value = env.ground.gridInt;
    u.uReveal.value = env.ground.reveal;
    u.uOpacity.value = env.ground.opacity;

    this.waterMaterial.opacity = env.water * 0.94;
    this.water.visible = env.water > 0.02;
  }
}
