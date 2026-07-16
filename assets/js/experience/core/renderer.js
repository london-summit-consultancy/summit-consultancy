// Renderer + post pipeline. CSP constraint: production serves default-src
// 'none' with script-src 'self' — so no workers, no external assets, no data:
// texture loads. Everything below is pure GPU work from bundled code (FXAA is
// used instead of SMAA precisely because SMAA loads data-URI lookup images).
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { FXAAShader } from "three/addons/shaders/FXAAShader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

export class Pipeline {
  constructor(host, scene, camera, tier, { alpha = false } = {}) {
    this.host = host;
    this.scene = scene;
    this.camera = camera;
    this.dpr = Math.min(window.devicePixelRatio || 1, tier.dprCap);

    this.renderer = new THREE.WebGLRenderer({
      antialias: !tier.composer,
      alpha,
      powerPreference: "high-performance",
    });
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1;
    if (alpha) this.renderer.setClearColor(0x000000, 0);
    host.appendChild(this.renderer.domElement);

    // Procedural environment map — reflections without a single texture fetch.
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();

    this.composer = null;
    this.bloomPass = null;
    this.fxaaPass = null;
    if (tier.composer) {
      this.composer = new EffectComposer(this.renderer);
      this.composer.addPass(new RenderPass(scene, camera));
      this.bloomPass = new UnrealBloomPass(new THREE.Vector2(1, 1), 1.0, 0.55, 0.85);
      this.composer.addPass(this.bloomPass);
      if (tier.fxaa) {
        this.fxaaPass = new ShaderPass(FXAAShader);
        this.composer.addPass(this.fxaaPass);
      }
      this.composer.addPass(new OutputPass());
    }

    this.setSize();
  }

  setSize() {
    const w = this.host.clientWidth || window.innerWidth;
    const h = this.host.clientHeight || window.innerHeight;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setPixelRatio(this.dpr);
    this.renderer.setSize(w, h);
    if (this.composer) {
      this.composer.setPixelRatio(this.dpr);
      this.composer.setSize(w, h);
    }
    if (this.fxaaPass) {
      this.fxaaPass.material.uniforms.resolution.value.set(1 / (w * this.dpr), 1 / (h * this.dpr));
    }
  }

  setBloom(strength) {
    if (this.bloomPass) this.bloomPass.strength = strength;
  }

  setExposure(exposure) {
    this.renderer.toneMappingExposure = exposure;
  }

  render() {
    if (this.composer) this.composer.render();
    else this.renderer.render(this.scene, this.camera);
  }
}
